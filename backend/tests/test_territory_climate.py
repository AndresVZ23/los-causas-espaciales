"""Clima por territorio con celdas sintéticas (solo pruebas; sin red): promedio por área, tendencias por celda y contrato."""

import asyncio
from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from backend.app.connectors.nasa import power_regional
from backend.app.connectors.nasa.power import PowerConnectorError
from backend.app.orchestration import extraction, territory
from backend.app.orchestration.conformance import envelope_violations
from backend.app.schemas.analysis import Observation, Point
from backend.app.schemas.climate import ClimateScreeningRequest, TerritoryRef
from backend.app.schemas.spatial_sampling import PowerCellSeries, SamplingSubject, SpatialSamplingResponse
from backend.app.sectors import climate
from backend.tests.test_solar import FakePowerConnector, MetadataOnlyNasadem, _source

MOQUEGUA = TerritoryRef(level="department", ubigeo="18")
CELLS = [((-17.0, -71.25), 0.75), ((-17.0, -70.625), 0.25)]


class TwoCellRegional:
    """Descubrimiento sintético: dos celdas con pesos 0.75 y 0.25 (las series reales llegan luego por punto)."""

    def __init__(self, *args, **kwargs):
        pass

    async def sample(self, request):
        cells = [PowerCellSeries(cell_id=f"{lat:.6f},{lon:.6f}", center=Point(latitude=lat, longitude=lon), bounds=(lon - 0.3125, lat - 0.25, lon + 0.3125, lat + 0.25),
                                 overlap_area_km2=1000 * weight, weight=weight, observations=[Observation(timestamp=request.start_date, value=1.0)])
                 for (lat, lon), weight in CELLS]
        return SpatialSamplingResponse(mode="REGIONAL", subject=SamplingSubject(kind="polygon", name="Moquegua", origin="IGN", geometry_type="Polygon"),
                                       variable=request.variable, unit="C", grid_spacing_degrees=(0.5, 0.625), spatial_coverage_percent=98.0,
                                       cells=cells, aggregate=[], source=_source("T2M"), method="prueba", limitations=[])


class CellRamps(FakePowerConnector):
    """Cada celda tiene su propio nivel: la del oeste vale 10 y la del este 20 (más la rampa común de la prueba)."""

    async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
        output = await super().daily_point_multi(latitude, longitude, variables, start_date, end_date)
        offset = 0.0 if longitude < -71 else 10.0
        return {key: ([Observation(timestamp=o.timestamp, value=o.value + offset) for o in obs], source) for key, (obs, source) in output.items()}


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(territory, "RegionalPowerConnector", TwoCellRegional)
    monkeypatch.setattr(extraction, "PowerConnector", CellRamps)
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)


def _request(**overrides):
    data = dict(sites=[Point(label="Arequipa", latitude=-16.409, longitude=-71.537)], territories=[MOQUEGUA],
                start_date=date(2010, 1, 1), end_date=date(2023, 12, 31))
    data.update(overrides)
    return ClimateScreeningRequest(**data)


def test_territory_average_is_area_weighted(patched):
    result = asyncio.run(climate.run_climate_screening(_request()))
    assert envelope_violations(result) == []
    site = next(item for item in result.sites if item.territory)
    assert site.location.label == "Moquegua (depto.)" and site.territory.cells == 2 and site.territory.mode == "REGIONAL"
    point_mean = next(v.mean for v in result.sites[0].variables if v.variable == "T2M")   # sitio puntual, sin desplazamiento
    area_mean = next(v.mean for v in site.variables if v.variable == "T2M")
    # 0.75 · (base) + 0.25 · (base + 10) = base + 2.5 (el sitio puntual cae en la celda oeste: base).
    assert area_mean == pytest.approx(point_mean + 2.5, abs=1e-6)
    assert any("ponderado por área" in note for note in result.method_notes)


def test_cell_trends_cover_every_cell_and_variable(patched):
    site = next(item for item in asyncio.run(climate.run_climate_screening(_request())).sites if item.territory)
    assert {(c.cell_id, c.variable) for c in site.cell_trends} == {(f"{lat:.6f},{lon:.6f}", v) for (lat, lon), _ in CELLS for v in ("T2M", "PRECTOTCORR")}
    assert all(c.significant and c.direction == "increasing" for c in site.cell_trends)   # rampa sintética creciente
    assert all(c.adjusted_p_value is not None and c.adjusted_p_value >= c.p_value for c in site.cell_trends)


def test_too_many_cells_asks_for_a_smaller_territory(patched, monkeypatch):
    monkeypatch.setattr(territory, "MAX_CELLS", 1)
    with pytest.raises(territory.TerritoryAnalysisError, match="provincia o un distrito"):
        asyncio.run(climate.run_climate_screening(_request()))


class RegionalDown:
    """Descubrimiento que falla como lo hace el conector cuando NASA POWER no responde."""

    def __init__(self, *args, **kwargs):
        pass

    async def sample(self, request):
        try:
            raise httpx.ConnectError("All connection attempts failed")
        except httpx.HTTPError as exc:
            raise power_regional.RegionalPowerError(f"La consulta regional NASA POWER falló: {exc}") from exc


def test_provider_outage_is_a_provider_error_not_a_bad_request(patched, monkeypatch):
    monkeypatch.setattr(territory, "RegionalPowerConnector", RegionalDown)
    with pytest.raises(PowerConnectorError, match="Moquegua.*falló"):
        asyncio.run(climate.run_climate_screening(_request()))


def test_request_validation():
    with pytest.raises(ValidationError, match="entre 1 y 4"):
        _request(sites=[], territories=[])
    with pytest.raises(ValidationError, match="repetidos"):
        _request(territories=[MOQUEGUA, MOQUEGUA])
    assert len(_request(sites=[]).territories) == 1   # solo territorios es válido


def test_aggregate_cells_renormalizes_missing_days():
    stamp = date(2020, 1, 1)
    cells = [PowerCellSeries(cell_id=str(i), center=Point(latitude=0, longitude=i), bounds=(i, 0, i + 1, 1), overlap_area_km2=1, weight=w,
                             observations=[Observation(timestamp=stamp, value=v)] if v is not None else [])
             for i, (w, v) in enumerate([(0.5, 10.0), (0.3, 20.0), (0.2, None)])]
    day = power_regional.aggregate_cells(cells)[0]
    assert day.value == pytest.approx((0.5 * 10 + 0.3 * 20) / 0.8) and day.contributing_cells == 2
