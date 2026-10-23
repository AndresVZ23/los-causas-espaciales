from datetime import date, datetime, timezone

import httpx
import pytest

from backend.app.connectors.energy.coes import COESConnector, aggregate_month
from backend.app.core.config import Settings
from backend.app.schemas.analysis import Provenance
from backend.app.schemas.data_sources import COESMonthlyRequest


HEADERS = [
    "fechahora",
    "ENGIE -INTIPAMPA_SOLAR",
    "MAJES ARCUS S.A.C. -GTSMAJES",
    "MOQUEGUA FV S.A.C. -MOQUEGUA_SOLAR",
    "ORYGEN PERU S.A.A. -RUBI_CIRCUITO_1-5",
    "ORYGEN PERU S.A.A. -RUBI_CIRCUITO_6-10",
    "PANAMERICANA  SOLAR SAC. -PANAM_SOLAR",
    "REPARTICIÓN ARCUS S.A.C. -GTSREPAR",
]


def _csv(include_panamericana=True):
    headers = HEADERS if include_panamericana else [item for item in HEADERS if "PANAM_SOLAR" not in item]
    values = {header: index for index, header in enumerate(headers)}
    row = ["01/01/2025 00:15"] + [str(values[header]) for header in headers[1:]]
    return (", ".join(headers) + "\r\n" + ", ".join(row) + "\r\n").encode("cp1252")


def test_monthly_aggregation_uses_quarter_hour_energy_and_sums_both_rubi_circuits():
    result = aggregate_month(_csv(), date(2025, 1, 1), Provenance.REAL, datetime.now(timezone.utc))
    rubi_columns, rubi = result["Rubí"]
    assert len(rubi_columns) == 2
    assert rubi.generation_mwh == pytest.approx((4 + 5) * 0.25)
    assert result["Intipampa"][1].generation_mwh == pytest.approx(1 * 0.25)
    assert result["Panamericana"][1].generation_mwh == pytest.approx(6 * 0.25)


def test_missing_exact_plant_name_is_unavailable_not_substituted():
    result = aggregate_month(_csv(include_panamericana=False), date(2025, 1, 1), Provenance.REAL, datetime.now(timezone.utc))
    assert result["Panamericana"] == ([], None)


@pytest.mark.asyncio
async def test_coes_connector_uses_official_month_limit_and_cache(tmp_path):
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        assert request.url.params["tiposGeneracion"] == "3"
        assert request.url.params["parametros"] == "1"
        assert request.url.params["fechaInicial"] == "01/01/2025"
        assert request.url.params["fechaFinal"] == "31/01/2025"
        return httpx.Response(200, content=_csv(), headers={"content-type": "text/csv"})

    settings = Settings(_env_file=None, cache_dir=tmp_path)
    connector = COESConnector(settings=settings, transport=httpx.MockTransport(handler))
    request = COESMonthlyRequest(start_month="2025-01", end_month="2025-01")
    first = await connector.monthly_generation(request)
    second = await connector.monthly_generation(request)
    assert calls == 1
    assert first.provenance == Provenance.REAL
    assert second.provenance == Provenance.CACHED
    assert all(plant.status == "READY" for plant in first.plants)
    assert first.source_id == "in-coes"
