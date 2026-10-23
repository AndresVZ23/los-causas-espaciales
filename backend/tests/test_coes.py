from datetime import date, datetime, timezone
from io import BytesIO

import httpx
import pytest
from openpyxl import Workbook

from backend.app.connectors.energy.coes import COESConnector, COESConnectorError, parse_daily_workbook
from backend.app.core.config import Settings
from backend.app.schemas.analysis import Provenance
from backend.app.schemas.data_sources import COESMonthlyRequest


def _xlsx(*, sheet="PRODUCCIÓN DIARIA", month=1, include_clemesi=True):
    workbook = Workbook()
    active = workbook.active
    active.title = sheet
    active.append([None, None, None, None, None])
    active.append([None, None, None, None, None])
    active.append([None, None, None, None, None])
    active.append(["FECHA", "EMPRESA", "GRUPO/CENTRAL", "TIPO GENERACIÓN", "TOTAL"])
    active.append([datetime(2025, month, 1), "ORYGEN", "RUBI", "SOLAR", 100.25])
    active.append([datetime(2025, month, 2), "ORYGEN", "RUBI", "SOLAR", 90.75])
    if include_clemesi:
        active.append([f"01/{month:02d}/2025", "ENGIE", "CLEMESI", "SOLAR", 981.01])
    active.append([datetime(2025, month, 1), "OTRA", "NO SOLAR", "HIDROELÉCTRICA", 500])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _gisem():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"EMPRESA": "ORYGEN", "NOMBRE": "RUBI", "POT_INST": 144.48, "POT_EFEC": 144.48},
            "geometry": {"type": "Point", "coordinates": [-70.0, -17.0]},
        }],
    }


def test_daily_xlsx_aggregates_exact_solar_names_and_excludes_other_types():
    result = parse_daily_workbook(_xlsx(), date(2025, 1, 1), Provenance.REAL, datetime.now(timezone.utc))
    assert result["RUBI"]["generation_mwh"] == pytest.approx(191.0)
    assert result["RUBI"]["days_observed"] == 2
    assert result["CLEMESI"]["generation_mwh"] == pytest.approx(981.01)
    assert "NO SOLAR" not in result


def test_daily_xlsx_rejects_wrong_sheet():
    with pytest.raises(COESConnectorError, match="PRODUCCIÓN DIARIA"):
        parse_daily_workbook(_xlsx(sheet="OTRA"), date(2025, 1, 1), Provenance.REAL, datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_coes_uses_official_xlsx_params_cache_and_exact_gisem_match(tmp_path):
    coes_calls = 0
    gisem_calls = 0

    def handler(request: httpx.Request):
        nonlocal coes_calls, gisem_calls
        if request.url.host == "www.coes.org.pe":
            coes_calls += 1
            assert dict(request.url.params) == {
                "fechaInicial": "01/01/2025",
                "fechaFinal": "31/01/2025",
                "indicador": "1",
            }
            return httpx.Response(
                200,
                content=_xlsx(),
                headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            )
        gisem_calls += 1
        assert request.url.host == "gisem.osinergmin.gob.pe"
        assert request.url.params["outSR"] == "4326"
        return httpx.Response(200, json=_gisem())

    connector = COESConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
        request_interval_seconds=0,
    )
    request = COESMonthlyRequest(start_month="2025-01", end_month="2025-01")
    first = await connector.monthly_generation(request)
    second = await connector.monthly_generation(request)

    assert coes_calls == 1
    assert gisem_calls == 1
    assert first.provenance == Provenance.REAL
    assert second.provenance == Provenance.CACHED
    rubi = next(plant for plant in first.plants if plant.plant == "RUBI")
    assert rubi.capacity_reference.status == "READY"
    assert rubi.capacity_reference.longitude == -70.0
    expected = 191 / (144.48 * 31 * 24) * 100
    assert rubi.observations[0].capacity_factor_percent == pytest.approx(expected, abs=1e-4)
    clemesi = next(plant for plant in first.plants if plant.plant == "CLEMESI")
    assert clemesi.capacity_reference.status == "DATA_UNAVAILABLE"
    assert clemesi.observations[0].capacity_factor_percent is None
    assert first.source_id == "in-coes"


@pytest.mark.asyncio
async def test_gisem_failure_does_not_hide_real_coes_generation(tmp_path):
    def handler(request: httpx.Request):
        if request.url.host == "www.coes.org.pe":
            return httpx.Response(
                200,
                content=_xlsx(),
                headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            )
        return httpx.Response(200, json={"error": {"message": "Service unavailable"}})

    connector = COESConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
        request_interval_seconds=0,
    )
    result = await connector.monthly_generation(COESMonthlyRequest(start_month="2025-01", end_month="2025-01"))
    assert result.plants
    assert all(plant.status == "READY" for plant in result.plants)
    assert all(plant.capacity_reference.status == "DATA_UNAVAILABLE" for plant in result.plants)
    assert "Service unavailable" in result.plants[0].capacity_reference.limitations[0]


@pytest.mark.asyncio
async def test_missing_exact_plant_month_is_partial_and_never_substituted(tmp_path):
    def handler(request: httpx.Request):
        if request.url.host == "www.coes.org.pe":
            month = 2 if request.url.params["fechaInicial"] == "01/02/2025" else 1
            return httpx.Response(
                200,
                content=_xlsx(month=month, include_clemesi=month == 1),
                headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
            )
        return httpx.Response(200, json=_gisem())

    connector = COESConnector(
        settings=Settings(_env_file=None, cache_dir=tmp_path),
        transport=httpx.MockTransport(handler),
        request_interval_seconds=0,
    )
    result = await connector.monthly_generation(COESMonthlyRequest(start_month="2025-01", end_month="2025-02"))
    clemesi = next(plant for plant in result.plants if plant.plant == "CLEMESI")
    assert clemesi.status == "PARTIAL"
    assert [item.generation_mwh for item in clemesi.observations] == [981.01, None]
    assert clemesi.observations[1].provenance == Provenance.UNAVAILABLE
    assert "2025-02" in clemesi.limitations[-1]
