"""Piloto hidroeléctrico: energía de pasada, regla del cauce de GloFAS, búsqueda de GEOGLOWS, salto por dos modelos de
elevación y el sobre C2. Todo sin red."""

import asyncio
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.connectors.copernicus import glofas
from backend.app.connectors.copernicus.dem import DemPoint
from backend.app.connectors.copernicus.glofas import GlofasConnector, GlofasError, NoRiverError, choose_cell
from backend.app.connectors.geoglows import streamflow
from backend.app.connectors.geoglows.streamflow import GeoglowsConnector, GeoglowsError, RiverChoice, parse_annual
from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.orchestration import extraction
from backend.app.orchestration.conformance import envelope_violations
from backend.app.orchestration.discoveries import flow_verdict
from backend.app.reports.executive_pdf import render_executive_pdf
from backend.app.schemas.analysis import Observation, Point, Provenance, SourceMetadata
from backend.app.schemas.hydro import HydroAssumptions, HydroScreeningRequest, HydroSite
from backend.app.schemas.screening import DiscoveryKind, Sector
from backend.app.schemas.terrain import TerrainMetrics, TerrainResponse, TerrainSiteResult
from backend.app.sectors import hydro
from backend.app.sectors.hydro_energy import (
    GRAVITY,
    calculate_hydro_projection,
    design_flow,
    exceedance_flow,
    flow_duration,
    plant_factor,
    power_mw,
    turbined_flow,
)

STAMP = datetime(2026, 11, 10, tzinfo=timezone.utc)


# --- Energía: funciones puras ---------------------------------------------------------------------------------

def test_exceedance_and_duration_curve_decrease_with_percent():
    flows = np.arange(1.0, 101.0)                       # 1 … 100 m³/s
    assert exceedance_flow(flows, 30) == pytest.approx(np.percentile(flows, 70))
    curve = flow_duration(flows)
    assert [percent for percent, _ in curve][0] == 5 and [percent for percent, _ in curve][-1] == 95
    assert all(a[1] >= b[1] for a, b in zip(curve, curve[1:]))


def test_design_flow_discounts_the_ecological_flow_and_never_goes_negative():
    flows = np.full(100, 10.0)
    assert design_flow(flows, 2.0, 30) == pytest.approx(8.0)
    assert design_flow(flows, 50.0, 30) == 0.0


def test_turbined_flow_caps_at_design_and_stops_below_the_technical_minimum():
    flows = np.array([1.0, 3.0, 6.0, 30.0])
    used = turbined_flow(flows, ecological=1.0, design=10.0, min_fraction=0.2)
    # 0 aprovechable; 2 = justo el mínimo técnico (opera); 5; tope en 10.
    assert used.tolist() == [0.0, 2.0, 5.0, 10.0]
    assert turbined_flow(np.array([2.9]), 1.0, 10.0, 0.2)[0] == 0.0


def test_power_formula_and_plant_factor():
    assert power_mw(10.0, 100.0, 0.9) == pytest.approx(1000 * GRAVITY * 10 * 100 * 0.9 / 1e6)
    always_full = np.full(365, 50.0)
    assert plant_factor(always_full, 5.0, 20.0, 0.2) == 1.0
    half = np.array([50.0] * 100 + [0.0] * 100)
    assert plant_factor(half, 0.0, 20.0, 0.2) == pytest.approx(0.5)
    # Si el río llevara la mitad del caudal, la central ya dimensionada produce menos.
    assert plant_factor(np.full(100, 20.0), 2.0, 18.0, 0.2, level=0.5) == pytest.approx(9.0 / 18.0)
    assert plant_factor(always_full, 5.0, 0.0, 0.2) == 0.0


def test_projection_uses_explicit_formula_and_handles_a_dry_river():
    assumptions = HydroAssumptions(capex_usd_per_mw=2_000_000, opex_fraction_of_capex=0.02, energy_price_usd_mwh=50, availability=0.9, horizon_years=2)
    result = calculate_hydro_projection(10.0, 0.5, assumptions)
    assert result.annual_energy_mwh == pytest.approx(10 * 8760 * 0.5 * 0.9)
    assert result.initial_capex_usd == 20_000_000 and result.annual_opex_usd == 400_000
    assert result.annual_revenue_usd == pytest.approx(result.annual_energy_mwh * 50)
    assert result.plant_factor_net == pytest.approx(0.45)
    dry = calculate_hydro_projection(0.0, 0.0, assumptions)
    assert dry.npv_usd == 0 and dry.annual_energy_mwh == 0 and dry.cash_flows_usd == [0.0, 0.0, 0.0]


def test_flow_verdict_thresholds():
    assert flow_verdict(1.10) == "coinciden" and flow_verdict(0.80) == "coinciden"
    assert flow_verdict(1.30) == "intermedio"
    assert flow_verdict(1.50) == "difieren" and flow_verdict(0.45) == "difieren"
    assert flow_verdict(0.05) == "no_comparable" and flow_verdict(12.0) == "no_comparable" and flow_verdict(None) == "no_comparable"


# --- GloFAS: regla del cauce y conector -----------------------------------------------------------------------

def _grid(center: float | None, neighbours: dict[tuple[int, int], float]) -> list[tuple[float, float, float | None]]:
    """Vecindario 3 × 3 alrededor de (-17, -71) con la celda del punto primero, como lo arma el conector."""
    return [(-17.0 + i * 0.05, -71.0 + j * 0.05, center if (i, j) == (0, 0) else neighbours.get((i, j), 0.0)) for i, j in glofas.OFFSETS]


def test_cell_of_the_point_is_kept_when_it_carries_the_channel():
    cell = choose_cell(-17.0, -71.0, _grid(6.3, {(0, -1): 15.3}), 2025)      # 41 % del máximo: está en un cauce
    assert not cell.moved and cell.used_cell_mean == 6.3 and cell.neighborhood_max == 15.3
    assert cell.distance_km == 0.0


def test_dry_cell_moves_to_the_nearest_channel_cell():
    # El cauce (54 m³/s) pasa al oeste (5.3 km) y al nordeste (7.7 km): se usa el más cercano.
    cell = choose_cell(-17.0, -71.0, _grid(0.0, {(0, -1): 54.0, (1, 1): 53.9, (-1, 0): 3.0}), 2025)
    assert cell.moved and cell.used_cell_mean == 54.0 and cell.point_cell_mean == 0.0
    assert cell.longitude == pytest.approx(-71.05) and 5.0 < cell.distance_km < 5.6


def test_no_river_in_the_neighbourhood_is_an_error_not_a_zero():
    with pytest.raises(NoRiverError, match="no modela un cauce"):
        choose_cell(-17.0, -71.0, _grid(0.0, {(0, 1): 0.01}), 2025)
    with pytest.raises(NoRiverError):
        choose_cell(-17.0, -71.0, _grid(None, {}), 2025)


def _flood_payload(lat: float, lon: float, start: date, end: date, flow: float | None) -> dict:
    days = [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]
    return {"latitude": lat, "longitude": lon, "daily": {"time": days, "river_discharge": [flow] * len(days)}}


def _flood_transport(calls: list[dict], flows: dict[tuple[float, float], float | None], status: int = 200):
    """Open-Meteo simulado: una o varias celdas por consulta, con el caudal constante que se declare por celda."""
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append(params)
        if status != 200:
            return httpx.Response(status, json={"error": True, "reason": "Minutely API request limit exceeded."})
        start, end = date.fromisoformat(params["start_date"]), date.fromisoformat(params["end_date"])
        lats, lons = [float(x) for x in params["latitude"].split(",")], [float(x) for x in params["longitude"].split(",")]
        cells = [_flood_payload(lat, lon, start, end, flows.get((round(lat, 3), round(lon, 3)), 0.0)) for lat, lon in zip(lats, lons, strict=True)]
        return httpx.Response(200, json=cells if len(cells) > 1 else cells[0])
    return httpx.MockTransport(handler)


def test_glofas_scans_the_neighbourhood_and_reads_the_channel_cell(tmp_path):
    calls: list[dict] = []
    flows = {(-17.0, -71.05): 40.0}                     # el cauce pasa por la celda al oeste del punto
    settings = Settings(_env_file=None, cache_dir=tmp_path)
    connector = GlofasConnector(settings=settings, transport=_flood_transport(calls, flows))
    start, end = date(2020, 1, 1), date.today()
    series = asyncio.run(connector.discharge(-17.0, -71.0, start, end))

    assert series.cell.moved and series.cell.longitude == pytest.approx(-71.05) and series.cell.scan_year == date.today().year - 1
    assert series.provenance == Provenance.REAL
    assert series.observations[0].timestamp == start and series.observations[-1].timestamp == end
    assert {item.value for item in series.observations} == {40.0}
    # Una exploración de nueve celdas, la historia cerrada completa desde 1997 y el año en curso.
    assert len(calls) == 3 and calls[0]["latitude"].count(",") == 8
    assert calls[1]["start_date"] == "1997-01-01" and calls[1]["end_date"] == f"{date.today().year - 1}-12-31"
    again = asyncio.run(GlofasConnector(settings=settings, transport=_flood_transport(calls, flows)).discharge(-17.0, -71.0, start, end))
    assert again.provenance == Provenance.CACHED and len(calls) == 3


def test_glofas_drops_nulls_and_reports_quota_errors(tmp_path, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        start, end = date.fromisoformat(params["start_date"]), date.fromisoformat(params["end_date"])
        n = params["latitude"].count(",") + 1
        cell = _flood_payload(-17.0, -71.0, start, end, 12.0)
        if "2021-01-01" in cell["daily"]["time"]:        # un nulo no es un cero
            cell["daily"]["river_discharge"][cell["daily"]["time"].index("2021-01-01")] = None
        return httpx.Response(200, json=[cell] * n if n > 1 else cell)
    settings = Settings(_env_file=None, cache_dir=tmp_path / "a")
    series = asyncio.run(GlofasConnector(settings=settings, transport=httpx.MockTransport(handler)).discharge(-17.0, -71.0, date(2021, 1, 1), date(2021, 12, 31)))
    assert len(series.observations) == 364 and series.observations[0].timestamp == date(2021, 1, 2)

    monkeypatch.setattr(glofas, "RATE_WAIT_SECONDS", 0.0)
    limited = GlofasConnector(settings=Settings(_env_file=None, cache_dir=tmp_path / "b"), transport=_flood_transport([], {}, status=429))
    with pytest.raises(GlofasError, match="cuota por minuto"):
        asyncio.run(limited.discharge(-17.0, -71.0, date(2021, 1, 1), date(2021, 12, 31)))


# --- GEOGLOWS -------------------------------------------------------------------------------------------------

def test_annual_parse_skips_nulls_and_the_open_year():
    current = date.today().year
    payload = {"7": [10.0, None, 12.0, 99.0], "datetime": [f"{current - 3}-01-01T00:00:00+00:00", f"{current - 2}-01-01T00:00:00+00:00",
                                                         f"{current - 1}-01-01T00:00:00+00:00", f"{current}-01-01T00:00:00+00:00"]}
    series = parse_annual(payload, 7)
    assert [(item.timestamp.year, item.value) for item in series] == [(current - 3, 10.0), (current - 1, 12.0)]
    with pytest.raises(GeoglowsError, match="estructura inesperada"):
        parse_annual({"7": [1.0], "datetime": []}, 7)


def _geoglows_transport(calls: list[str], main_stem_at: tuple[int, int] | None):
    """GEOGLOWS simulado: todos los puntos devuelven una quebrada (río 1, 0.3 m³/s) salvo `main_stem_at` (río 2, 50 m³/s)."""
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/getriverid"):
            lat, lon = float(request.url.params["lat"]), float(request.url.params["lon"])
            offset = (round((lat + 17.0) / streamflow.SEARCH_DEGREES), round((lon + 71.0) / streamflow.SEARCH_DEGREES))
            return httpx.Response(200, json={"river_id": 2 if offset == main_stem_at else 1})
        river_id = int(request.url.path.rsplit("/", 1)[-1])
        years = list(range(2000, 2025))
        return httpx.Response(200, json={str(river_id): [50.0 if river_id == 2 else 0.3] * len(years),
                                         "datetime": [f"{year}-01-01T00:00:00+00:00" for year in years]})
    return httpx.MockTransport(handler)


def test_geoglows_takes_the_largest_river_of_the_search_grid(tmp_path):
    calls: list[str] = []
    settings = Settings(_env_file=None, cache_dir=tmp_path)
    choice = asyncio.run(GeoglowsConnector(settings=settings, transport=_geoglows_transport(calls, (2, -1))).river_near(-17.0, -71.0))
    assert isinstance(choice, RiverChoice)
    assert (choice.river_id, choice.nearest_river_id, choice.candidates) == (2, 1, 2)
    assert choice.nearest_mean == pytest.approx(0.3) and len(choice.annual) == 25 and choice.annual[0].value == 50.0
    assert sum(1 for path in calls if path.endswith("/getriverid")) == 25 and sum(1 for path in calls if "annualaverages" in path) == 2
    again = asyncio.run(GeoglowsConnector(settings=settings, transport=_geoglows_transport(calls, (2, -1))).river_near(-17.0, -71.0))
    assert again.provenance == Provenance.CACHED and len(calls) == 27


def test_geoglows_keeps_the_nearest_river_when_nothing_larger_is_around(tmp_path):
    choice = asyncio.run(GeoglowsConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=_geoglows_transport([], None)).river_near(-17.0, -71.0))
    assert (choice.river_id, choice.nearest_river_id, choice.candidates) == (1, 1, 1)


def test_geoglows_failure_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(streamflow, "RETRY_SECONDS", 0.0)
    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="fuera de servicio"))
    with pytest.raises(GeoglowsError, match="no ubicó un río"):
        asyncio.run(GeoglowsConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=transport).river_near(-17.0, -71.0))


# --- Sobre C2 del piloto hidroeléctrico -----------------------------------------------------------------------

UNITS = {"T2M": "C", "PRECTOTCORR": "mm/day"}


class FlatDailyPower:
    """NASA POWER diario sintético sin tendencia, sin red."""

    async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
        days = [start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)]
        base = {"T2M": 12.0, "PRECTOTCORR": 1.5}
        return {variable: ([Observation(timestamp=day, value=base[variable] + ((day.year * 7) % 5 - 2) * 0.01) for day in days],
                           SourceMetadata(source_id="nasa-power", dataset="NASA POWER Daily Point", version="prueba", variable=variable, unit=UNITS[variable],
                                          temporal_resolution="diaria", spatial_resolution="grilla", downloaded_at=STAMP,
                                          source_url="https://power.larc.nasa.gov", provenance=Provenance.CACHED))
                for variable in variables}


def _elevation(latitude: float, per_degree: float = 4000.0) -> float:
    """Terreno sintético que baja hacia el sur: 2,000 m en -17.00° y 200 m menos cada 0.05°."""
    return 2000.0 + (latitude + 17.0) * per_degree


class SlopingNasadem:
    async def points(self, sites):
        return TerrainResponse(generated_at=STAMP, note="prueba", sites=[
            TerrainSiteResult(location=site, status="READY", granules=[], provenance=Provenance.CACHED, limitations=[],
                              metrics=TerrainMetrics(elevation_m=_elevation(site.latitude), slope_degrees=12.0, aspect_degrees=180.0, aspect_cardinal="S"))
            for site in sites])


class MetadataOnlyNasadem:
    async def points(self, sites):
        return TerrainResponse(generated_at=STAMP, note="prueba", sites=[
            TerrainSiteResult(location=site, status="METADATA_ONLY", metrics=TerrainMetrics(), granules=[], provenance=Provenance.UNAVAILABLE, limitations=[])
            for site in sites])


class SlopingCopernicus:
    """Segundo modelo de elevación: 2 % más de desnivel que el primero."""

    def __init__(self, *args, **kwargs):
        pass

    async def point(self, latitude, longitude):
        return DemPoint(elevation_m=_elevation(latitude, 4080.0), slope_degrees=12.0, tile_url="https://example.org/cop.tif", provenance=Provenance.CACHED,
                        downloaded_at=STAMP, limitations=[])


class FailingGeoglows:
    def __init__(self, *args, **kwargs):
        pass

    async def river_near(self, latitude, longitude):
        raise GeoglowsError("GEOGLOWS fuera de servicio (prueba)")


class TinyGeoglows:
    """Devuelve una quebrada: 0.2 m³/s frente a los 30 de GloFAS."""

    def __init__(self, *args, **kwargs):
        pass

    async def river_near(self, latitude, longitude):
        annual = [Observation(timestamp=date(year, 7, 1), value=0.2) for year in range(1990, 2025)]
        return RiverChoice(river_id=9, nearest_river_id=9, candidates=3, annual=annual, nearest_mean=0.2, provenance=Provenance.CACHED, downloaded_at=STAMP)


class SlowGeoglows:
    def __init__(self, *args, **kwargs):
        pass

    async def river_near(self, latitude, longitude):
        await asyncio.sleep(30)


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FlatDailyPower)
    monkeypatch.setattr(extraction, "NasademConnector", SlopingNasadem)
    monkeypatch.setattr(extraction, "CopernicusDemConnector", SlopingCopernicus)


def _sites() -> list[HydroSite]:
    return [
        HydroSite(label="Río Alto", intake=Point(latitude=-17.00, longitude=-71.00), powerhouse=Point(latitude=-17.05, longitude=-71.00)),
        HydroSite(label="Río Bajo", intake=Point(latitude=-17.10, longitude=-71.20), powerhouse=Point(latitude=-17.12, longitude=-71.20)),
    ]


def _request(sites: list[HydroSite] | None = None, **assumptions) -> HydroScreeningRequest:
    return HydroScreeningRequest(sites=sites or _sites(), start_date=date(2010, 1, 1), end_date=date(2024, 12, 31), assumptions=HydroAssumptions(**assumptions))


def test_screening_builds_a_run_of_river_plant_on_the_common_envelope(offline):
    result = asyncio.run(hydro.run_hydro_screening(_request()))

    assert envelope_violations(result) == []
    assert result.sector == Sector.HYDRO and len(result.pipeline) == 9
    assert [subject.kind for subject in result.subjects] == ["segment", "segment"]
    site = result.sites[0]
    head, resource, check = site.head, site.resource, site.flow_check
    # Salto: 200 m con NASADEM y 204 m con el segundo modelo (+2 %).
    assert head.source == "NASADEM" and head.gross_head_m == pytest.approx(200.0) and head.gap_percent == pytest.approx(2.0)
    assert head.conduction_km == pytest.approx(5.53, abs=0.05)
    # Recurso: quince años completos del caudal sintético (media 30 m³/s) y su central.
    assert resource.period == "2010–2024" and resource.mean_flow_m3s == pytest.approx(30.0, abs=0.3)
    assert resource.ecological_flow_m3s == pytest.approx(resource.mean_flow_m3s * 0.10, abs=0.01)
    assert resource.net_head_m == pytest.approx(190.0)
    assert resource.capacity_mw == pytest.approx(power_mw(resource.design_flow_m3s, 190.0, 0.87), abs=0.01)
    assert 0.3 < resource.plant_factor < 1.0 and len(resource.annual_plant_factors) == 15
    assert [point.exceedance_percent for point in resource.flow_duration][:2] == [5, 10]
    assert site.finance.plant_factor_net == pytest.approx(resource.plant_factor * 0.95, abs=1e-4)
    assert site.finance.initial_capex_usd == pytest.approx(resource.capacity_mw * 2_500_000, rel=1e-6)
    # Segunda opinión: GEOGLOWS sintético lleva 10 % más caudal: coinciden y la tendencia queda contrastada.
    assert check.verdict == "coinciden" and check.gap_percent == pytest.approx(10.0, abs=1.0) and check.period == "2010–2024"
    assert check.plant_factor_at_second > resource.plant_factor
    discharge = next(item for item in site.variables if item.variable == "RIVER_DISCHARGE")
    assert discharge.display_unit == "m³/s" and discharge.label == "Caudal del río"
    assert [item.source for item in discharge.counterchecks] == [hydro.GEOGLOWS_SOURCE]
    titles = [(item.kind, item.title) for item in result.discoveries]
    assert (DiscoveryKind.AGREEMENT, "Río Alto: GloFAS y GEOGLOWS coinciden en el caudal") in titles
    assert (DiscoveryKind.AGREEMENT, "Río Alto: NASADEM y Copernicus coinciden en el salto") in titles
    keys = [bar.key for bar in result.financial_sensitivity[0].tornado]
    assert {"plant_factor", "flow_ratio", "head_ratio", "capex_usd_per_mw"} <= set(keys)
    assert result.scorecard is not None and all(item.coverage == pytest.approx(1.0) for item in result.scorecard.subjects)
    assert any(gap.dataset.startswith("Aforo en la toma") for gap in result.data_gaps)
    # El relieve lleva los dos puntos de cada sitio y la toma conserva el nombre del sujeto.
    assert [item.location.label for item in result.terrain.sites] == ["Río Alto", "Río Alto · casa de máquinas", "Río Bajo", "Río Bajo · casa de máquinas"]
    extraction_stage = result.pipeline[2]
    assert "NASA POWER y GloFAS entregaron" in extraction_stage.summary
    assert any(item.label == "GloFAS · Río Alto" for item in extraction_stage.evidence)
    assert "GloFAS de 5 km" in result.nasa_questions[1].evidence[0]


def test_site_design_flow_overrides_the_exceedance_rule(offline):
    sites = _sites()
    sites[0].design_flow_m3s = 12.0
    result = asyncio.run(hydro.run_hydro_screening(_request(sites)))
    resource = result.sites[0].resource
    assert resource.design_flow_m3s == 12.0 and "Declarado por el usuario" in resource.design_basis
    assert "excedido el 30 %" in result.sites[1].resource.design_basis


def test_without_second_source_the_gap_is_declared(offline, monkeypatch):
    monkeypatch.setattr(hydro, "GeoglowsConnector", FailingGeoglows)
    result = asyncio.run(hydro.run_hydro_screening(_request()))
    assert envelope_violations(result) == []
    assert result.sites[0].flow_check is None
    assert any("GEOGLOWS fuera de servicio" in gap.impact for gap in result.data_gaps)
    assert any("Sin segunda opinión del caudal" in caution for caution in result.sites[0].cautions)
    assert "flow_ratio" not in [bar.key for bar in result.financial_sensitivity[0].tornado]
    assert result.scorecard.subjects[0].coverage < 1.0
    discharge = next(item for item in result.sites[0].variables if item.variable == "RIVER_DISCHARGE")
    assert discharge.counterchecks == []


def test_slow_second_source_is_reported_as_pending(offline, monkeypatch):
    monkeypatch.setattr(hydro, "GeoglowsConnector", SlowGeoglows)
    monkeypatch.setattr(hydro, "GEOGLOWS_WAIT_SECONDS", 0.05)
    result = asyncio.run(hydro.run_hydro_screening(_request()))
    assert result.sites[0].flow_check is None
    assert any(gap.dataset.endswith("(en consulta)") and "Río Alto, Río Bajo" in gap.impact for gap in result.data_gaps)
    assert any("sigue en curso" in caution for caution in result.sites[0].cautions)


def test_second_source_that_sees_another_river_is_not_compared(offline, monkeypatch):
    monkeypatch.setattr(hydro, "GeoglowsConnector", TinyGeoglows)
    result = asyncio.run(hydro.run_hydro_screening(_request()))
    check = result.sites[0].flow_check
    assert check.verdict == "no_comparable" and check.plant_factor_at_second is None and check.annual_energy_mwh_at_second is None
    discharge = next(item for item in result.sites[0].variables if item.variable == "RIVER_DISCHARGE")
    assert discharge.counterchecks == []                # la tendencia de una quebrada no se compara con la del río
    assert any(item.kind == DiscoveryKind.CONTRADICTION and "no ubican el mismo río" in item.title for item in result.discoveries)
    assert "flow_ratio" not in [bar.key for bar in result.financial_sensitivity[0].tornado]
    row = result.scorecard.subjects[0]
    assert next(item for item in row.criteria if item.key == "flow_confidence").value == 100.0


def test_without_nasadem_metrics_the_head_comes_from_copernicus(offline, monkeypatch):
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)
    result = asyncio.run(hydro.run_hydro_screening(_request()))
    head = result.sites[0].head
    assert head.source.startswith("Copernicus") and head.gross_head_m == pytest.approx(204.0) and head.second_source is None and head.gap_percent is None
    assert any("sin contraste" in item for item in head.limitations)
    assert any(gap.dataset.startswith("Contraste del salto") for gap in result.data_gaps)
    assert "head_ratio" not in [bar.key for bar in result.financial_sensitivity[0].tornado]


def test_powerhouse_above_the_intake_is_rejected(offline):
    sites = [HydroSite(label="Al revés", intake=Point(latitude=-17.05, longitude=-71.0), powerhouse=Point(latitude=-17.00, longitude=-71.0))]
    with pytest.raises(hydro.HydroSiteError, match="no está por debajo de la toma"):
        asyncio.run(hydro.run_hydro_screening(_request(sites)))
    response = TestClient(app).post("/api/v1/projects/hydro-screening", json=json.loads(_request(sites).model_dump_json()))
    assert response.status_code == 422 and "Al revés" in response.json()["detail"]


def test_single_site_and_early_start_date(offline):
    single = asyncio.run(hydro.run_hydro_screening(_request(_sites()[:1])))
    assert envelope_violations(single) == []
    assert single.sites[0].relative_position_text == "1 de 1 por energía anual"
    assert any("un solo aprovechamiento" in note for note in single.scorecard.notes)
    early = HydroScreeningRequest(sites=_sites(), start_date=date(1990, 1, 1), end_date=date(2024, 12, 31))
    with pytest.raises(hydro.HydroSiteError, match="1997-01-01"):
        asyncio.run(hydro.run_hydro_screening(early))


def test_request_needs_distinct_site_names():
    sites = _sites()
    sites[1].label = "Río Alto"
    with pytest.raises(ValueError, match="nombre distinto"):
        HydroScreeningRequest(sites=sites, start_date=date(2010, 1, 1), end_date=date(2024, 12, 31))


def test_hydro_envelope_renders_the_executive_pdf(offline):
    from io import BytesIO

    from pypdf import PdfReader
    result = asyncio.run(hydro.run_hydro_screening(_request()))
    pdf = render_executive_pdf(result)
    assert pdf[:4] == b"%PDF"
    # La validación con producción real acompaña al método en el sobre y en el PDF, con su fecha y su alcance.
    assert len(result.method_validation) == 1 and "Machupicchu" in result.method_validation[0] and "Es un solo caso" in result.method_validation[0]
    text = " ".join(" ".join(page.extract_text().split()) for page in PdfReader(BytesIO(pdf)).pages)
    assert "Validación del método con producción real" in text and "74.1 %" in text
