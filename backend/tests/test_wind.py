"""Piloto eólico: energía hora por hora, BigTIFF/ZSTD del Atlas Eólico Global, serie horaria de NASA POWER y el sobre C2."""

import asyncio
import math
import struct
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
import pytest
import zstandard

from backend.app.connectors.cog import CogLevel, decode_tile, parse_header
from backend.app.connectors.gwa import wind_atlas
from backend.app.connectors.nasa.power_hourly import MIN_HOURS, parse_year
from backend.app.core.config import Settings
from backend.app.orchestration import extraction
from backend.app.reports.executive_pdf import render_executive_pdf
from backend.app.schemas.analysis import Observation, Point, Provenance, SourceMetadata
from backend.app.schemas.screening import DiscoveryKind, Sector
from backend.app.schemas.terrain import TerrainMetrics, TerrainResponse, TerrainSiteResult
from backend.app.schemas.wind import WindAssumptions, WindScreeningRequest
from backend.app.sectors import wind
from backend.app.sectors.wind_energy import (
    REFERENCE_DENSITY,
    air_density,
    calculate_wind_projection,
    capacity_factor,
    normalized_power,
    shear_exponent,
)

SIZE = 8
SCALE = 0.0025
ORIGIN = (-71.0, -17.0)        # esquina noroeste del archivo sintético


# --- Energía: funciones puras ---------------------------------------------------------------------------------

def test_power_curve_has_its_four_regions():
    speeds = np.array([2.9, 3.0, 7.5, 12.0, 20.0, 25.0])
    curve = normalized_power(speeds, 3.0, 12.0, 25.0)
    assert curve[0] == 0 and curve[1] == 0                       # bajo y en el arranque
    assert curve[2] == pytest.approx((7.5 ** 3 - 27) / (12 ** 3 - 27))
    assert curve[3] == 1 and curve[4] == 1                       # nominal hasta la parada
    assert curve[5] == 0                                         # parada por seguridad


def test_standard_atmosphere_density_and_altitude():
    assert air_density(0, 15) == pytest.approx(REFERENCE_DENSITY, abs=0.001)
    assert air_density(1400, 15) < air_density(0, 15) * 0.87      # ~15 % menos aire a 1,400 m


def test_shear_exponent_from_two_heights_and_its_limits():
    value, basis = shear_exponent(5.0, 4.0)
    assert value == pytest.approx(math.log(1.25) / math.log(5))
    assert "ln(v50 / v10)" in basis
    assert shear_exponent(10.0, 1.0)[0] == 0.5                   # acotado
    assert shear_exponent(5.0, 0.0)[0] == pytest.approx(1 / 7)   # sin dato a 10 m: supuesto declarado


def test_capacity_factor_saturates_above_rated_and_scales_with_level():
    assumptions = WindAssumptions(hub_height_m=50)
    strong = np.full(100, 15.0)
    assert capacity_factor(strong, assumptions, 0.0, REFERENCE_DENSITY) == 1.0
    weak = np.full(100, 6.0)
    base = capacity_factor(weak, assumptions, 0.0, REFERENCE_DENSITY)
    assert capacity_factor(weak, assumptions, 0.0, REFERENCE_DENSITY, level=1.5) > base
    assert capacity_factor(weak, assumptions, 0.0, REFERENCE_DENSITY * 0.85) < base     # aire menos denso, menos potencia


def test_projection_uses_explicit_formula():
    assumptions = WindAssumptions(capacity_mw=10, losses=0.1, energy_price_usd_mwh=50, horizon_years=2)
    result = calculate_wind_projection(0.4, assumptions)
    assert result.annual_energy_mwh == pytest.approx(10 * 8760 * 0.4 * 0.9)
    assert result.annual_revenue_usd == pytest.approx(result.annual_energy_mwh * 50)
    assert result.capacity_factor_net == pytest.approx(0.36)


def test_power_curve_must_be_ordered():
    with pytest.raises(ValueError, match="arranque"):
        WindAssumptions(cut_in_ms=9, rated_ms=8)


def test_hourly_years_are_the_last_ten_complete_ones():
    assert list(wind.hourly_years(date(2001, 1, 1), date(2026, 10, 29))) == list(range(2016, 2026))
    assert list(wind.hourly_years(date(2001, 1, 1), date(2023, 12, 31))) == list(range(2014, 2024))
    assert list(wind.hourly_years(date(2019, 1, 1), date(2024, 6, 30))) == list(range(2019, 2024))


# --- NASA POWER horario ---------------------------------------------------------------------------------------

def test_hourly_parse_drops_fill_values_and_short_years():
    hours = [f"2024{index:06d}" for index in range(8760)]
    payload = {"properties": {"parameter": {"WS50M": {hour: 6.0 for hour in hours}, "WS10M": {hour: 5.0 for hour in hours}}}}
    payload["properties"]["parameter"]["WS50M"][hours[0]] = -999.0
    high, low = parse_year(payload)
    assert high.size == low.size == 8759 and high.mean() == 6.0
    for hour in hours[: int(8760 - MIN_HOURS) + 1]:
        payload["properties"]["parameter"]["WS10M"][hour] = -999.0
    assert parse_year(payload) is None                           # menos del 90 % de horas: el año no se usa


# --- BigTIFF con ZSTD (Atlas Eólico Global) -------------------------------------------------------------------

def _encode(values: np.ndarray) -> bytes:
    """Inverso del decodificador: float32 big-endian en planos de bytes, diferencia horizontal y ZSTD."""
    rows, cols = values.shape
    planes = values.astype(">f4").view(np.uint8).reshape(rows, cols, 4).transpose(0, 2, 1).reshape(rows, cols * 4)
    deltas = np.diff(planes.astype(np.int16), axis=1, prepend=0).astype(np.uint8)
    return zstandard.ZstdCompressor().compress(deltas.tobytes())


def _bigtiff(values: np.ndarray) -> bytes:
    block = _encode(values)
    entries = [(256, 3, 1, SIZE), (257, 3, 1, SIZE), (258, 3, 1, 32), (259, 3, 1, 50000), (317, 3, 1, 3), (322, 3, 1, SIZE), (323, 3, 1, SIZE),
               (324, 16, 1, None), (325, 16, 1, len(block)), (339, 3, 1, 3), (33550, 12, 3, None), (33922, 12, 6, None)]
    ifd_size = 8 + 20 * len(entries) + 8
    scale_at = 16 + ifd_size
    tie_at = scale_at + 24
    block_at = tie_at + 48
    values_for = {324: block_at, 33550: scale_at, 33922: tie_at}
    ifd = struct.pack("<Q", len(entries)) + b"".join(
        struct.pack("<HHQQ", tag, kind, n, values_for[tag] if value is None else value) for tag, kind, n, value in entries) + struct.pack("<Q", 0)
    extra = struct.pack("<3d", SCALE, SCALE, 0.0) + struct.pack("<6d", 0.0, 0.0, 0.0, ORIGIN[0], ORIGIN[1], 0.0)
    return b"II+\x00" + struct.pack("<HHQ", 8, 0, 16) + ifd + extra + block


def _field(base: float) -> np.ndarray:
    return np.tile(base + 0.1 * np.arange(SIZE, dtype=np.float32), (SIZE, 1)).astype(np.float32)


def _atlas_transport(blobs: dict[str, bytes]):
    def handler(request: httpx.Request) -> httpx.Response:
        blob = blobs[request.url.path.rsplit("/", 1)[-1]]
        start, end = (int(x) for x in request.headers["Range"].removeprefix("bytes=").split("-"))
        return httpx.Response(206, content=blob[start:end + 1])
    return httpx.MockTransport(handler)


def test_bigtiff_header_and_zstd_tile_round_trip():
    values = np.random.default_rng(3).uniform(0, 15, size=(SIZE, SIZE)).astype(np.float32)
    header = parse_header(_bigtiff(values))
    level = header.levels[0]
    assert (level.width, level.compression, level.predictor) == (SIZE, 50000, 3)
    assert header.scale == (SCALE, SCALE) and header.origin == ORIGIN
    raw = _bigtiff(values)[level.offsets[0]: level.offsets[0] + level.counts[0]]
    assert np.array_equal(decode_tile(raw, level), values.astype(np.float64))


def test_classic_tiff_still_rejects_unknown_compression():
    level = CogLevel(width=SIZE, height=SIZE, tile_width=SIZE, tile_height=SIZE, bits=32, compression=7, predictor=1, sample_format=3, offsets=(0,), counts=(0,))
    with pytest.raises(Exception, match="Compresión no prevista"):
        decode_tile(b"", level)


def test_atlas_reads_both_heights_at_the_point(tmp_path):
    transport = _atlas_transport({"50": _bigtiff(_field(8.0)), "100": _bigtiff(_field(9.0))})
    connector = wind_atlas.WindAtlasConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=transport)
    point = asyncio.run(connector.point(ORIGIN[1] - SCALE * 2.5, ORIGIN[0] + SCALE * 3.5))     # fila 2, columna 3
    assert point.speeds == {50: pytest.approx(8.3), 100: pytest.approx(9.3)}
    assert point.provenance == Provenance.REAL
    again = asyncio.run(wind_atlas.WindAtlasConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=transport).point(ORIGIN[1] - 0.006, ORIGIN[0] + 0.009))
    assert again.provenance == Provenance.CACHED


def test_atlas_declares_nodata_and_points_outside_the_file(tmp_path):
    values = _field(8.0)
    values[2, 3] = np.nan
    transport = _atlas_transport({"50": _bigtiff(values), "100": _bigtiff(values)})
    connector = wind_atlas.WindAtlasConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=transport)
    point = asyncio.run(connector.point(ORIGIN[1] - SCALE * 2.5, ORIGIN[0] + SCALE * 3.5))
    assert point.speeds == {50: None, 100: None}
    assert any("no tiene dato" in item for item in point.limitations)
    with pytest.raises(wind_atlas.WindAtlasError, match="fuera"):
        asyncio.run(connector.point(-10.0, -60.0))


# --- Sobre C2 del piloto eólico -------------------------------------------------------------------------------

UNITS = {"WS50M": "m/s", "WS10M": "m/s", "T2M": "C", "PRECTOTCORR": "mm/day"}


class FlatDailyPower:
    """NASA POWER diario sintético sin tendencia (wobble determinista), sin red."""

    async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
        days = [start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)]
        base = {"WS50M": 7.0, "WS10M": 5.6, "T2M": 18.0, "PRECTOTCORR": 0.2}
        return {variable: ([Observation(timestamp=day, value=base[variable] + ((day.year * 7) % 5 - 2) * 0.01) for day in days],
                           SourceMetadata(source_id="nasa-power", dataset="NASA POWER Daily Point", version="prueba", variable=variable, unit=UNITS[variable],
                                          temporal_resolution="diaria", spatial_resolution="grilla", downloaded_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
                                          source_url="https://power.larc.nasa.gov", provenance=Provenance.CACHED))
                for variable in variables}


class MetadataOnlyNasadem:
    async def points(self, sites):
        return TerrainResponse(generated_at=datetime(2026, 10, 30, tzinfo=timezone.utc), note="prueba",
                               sites=[TerrainSiteResult(location=site, status="METADATA_ONLY", metrics=TerrainMetrics(), granules=[],
                                                        provenance=Provenance.UNAVAILABLE, limitations=[]) for site in sites])


class FailingAtlas:
    def __init__(self, *args, **kwargs):
        pass

    async def point(self, latitude, longitude):
        raise wind_atlas.WindAtlasError("atlas fuera de servicio (prueba)")


@pytest.fixture
def offline_daily(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FlatDailyPower)
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)


def _request() -> WindScreeningRequest:
    return WindScreeningRequest(sites=[Point(label="Marcona", latitude=-15.36, longitude=-75.16), Point(label="Moquegua", latitude=-17.193, longitude=-70.934)],
                                start_date=date(2014, 1, 1), end_date=date(2023, 12, 31))


def test_screening_uses_atlas_level_with_nasa_hourly_shape(offline_daily):
    result = asyncio.run(wind.run_wind_screening(_request()))
    assert result.sector == Sector.WIND and len(result.pipeline) == 9
    site = result.sites[0]
    resource, check = site.resource, site.atlas_check
    assert resource.years == "2014–2023" and resource.hours == 87_600
    assert resource.level_source.startswith("Global Wind Atlas")
    assert resource.mean_speed_hub_used == pytest.approx(check.speed_hub, abs=0.01)
    assert resource.capacity_factor_gross == pytest.approx(check.capacity_factor_gross_at_atlas)
    assert resource.capacity_factor_gross_nasa_level != resource.capacity_factor_gross
    assert "Copernicus" in resource.density_basis                  # NASADEM sin métricas: la elevación viene del segundo modelo
    assert site.finance.capacity_factor_net == pytest.approx(resource.capacity_factor_gross * 0.85, abs=1e-4)
    keys = [bar.key for bar in result.financial_sensitivity[0].tornado]
    assert "atlas_ratio" in keys and "capacity_factor" in keys
    assert result.scorecard is not None and {item.subject for item in result.scorecard.subjects} == {"Marcona", "Moquegua"}
    assert any(gap.dataset.startswith("Medición de viento") for gap in result.data_gaps)
    # Atlas sintético de costa (11 m/s a 100 m) frente a ~7.7 m/s de MERRA-2 al buje: más de 20 %, contradicción.
    assert check.gap_percent_hub >= 20
    kinds = [item.kind for item in result.discoveries if "Atlas Eólico" in item.title]
    assert kinds == [DiscoveryKind.CONTRADICTION, DiscoveryKind.CONTRADICTION]


def test_without_atlas_the_nasa_level_is_used_and_declared(offline_daily, monkeypatch):
    monkeypatch.setattr(wind, "WindAtlasConnector", FailingAtlas)
    result = asyncio.run(wind.run_wind_screening(_request()))
    resource = result.sites[0].resource
    assert resource.level_source == "NASA POWER (MERRA-2)" and resource.level_factor == 1.0
    assert result.sites[0].atlas_check is None
    assert any("atlas fuera de servicio" in gap.impact for gap in result.data_gaps)
    assert any("Sin Atlas Eólico Global" in caution for caution in result.sites[0].cautions)
    assert "atlas_ratio" not in [bar.key for bar in result.financial_sensitivity[0].tornado]


def test_wind_envelope_renders_the_executive_pdf(offline_daily):
    result = asyncio.run(wind.run_wind_screening(_request()))
    assert render_executive_pdf(result)[:4] == b"%PDF"


def test_atlas_gap_becomes_contradiction_or_agreement():
    from backend.app.orchestration.discoveries import wind_atlas_discoveries

    resource = wind.WindResource(years="2014–2023", hours=87_600, mean_speed_10m=5.0, mean_speed_50m=6.0, shear_exponent=0.14, shear_basis="prueba",
                                 hub_height_m=100, mean_speed_hub=6.6, mean_speed_hub_used=6.6, air_density_kg_m3=1.2, density_basis="prueba",
                                 capacity_factor_gross=0.3, annual_capacity_factors=[], capacity_factor_gross_nasa_level=0.3,
                                 provenance=Provenance.CACHED, downloaded_at=datetime(2026, 10, 30, tzinfo=timezone.utc), source_url="x", version="x")
    far = wind.WindAtlasCheck(source="GWA", speed_50m=9.0, speed_100m=9.9, speed_hub=9.9, power_speed_50m=6.0, gap_percent_50m=50.0, gap_percent_hub=50.0,
                              capacity_factor_gross_at_atlas=0.5, annual_energy_mwh_at_atlas=1.0, provenance=Provenance.CACHED,
                              downloaded_at=datetime(2026, 10, 30, tzinfo=timezone.utc), urls=[], license="CC BY 4.0", limitations=[])
    near = far.model_copy(update={"speed_hub": 6.8, "gap_percent_hub": 3.0})
    kinds = [item.kind for item in wind_atlas_discoveries([("A", resource, far), ("B", resource, near), ("C", resource, None)])]
    assert kinds == [DiscoveryKind.CONTRADICTION, DiscoveryKind.AGREEMENT]
