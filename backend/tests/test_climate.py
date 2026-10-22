import asyncio
import json
from datetime import date

import pytest

from backend.app.connectors.nasa.power import PowerConnectorError
from backend.app.orchestration import extraction
from backend.app.orchestration.conformance import envelope_violations
from backend.app.reports.executive_pdf import render_executive_pdf
from backend.app.schemas.analysis import Point
from backend.app.schemas.climate import ClimateScreeningRequest
from backend.app.schemas.screening import PipelineStatus, ScreeningEnvelope, Sector
from backend.app.sectors import climate
from backend.tests.test_solar import FakePowerConnector, FlatPowerConnector, MetadataOnlyNasadem


def _request(**overrides) -> ClimateScreeningRequest:
    data = dict(sites=[Point(label="Moquegua", latitude=-17.193, longitude=-70.934), Point(label="Arequipa", latitude=-16.409, longitude=-71.537)],
                start_date=date(2010, 1, 1), end_date=date(2023, 12, 31))
    data.update(overrides)
    return ClimateScreeningRequest(**data)


@pytest.fixture
def response(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FakePowerConnector)
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)
    return asyncio.run(climate.run_climate_screening(_request()))


def test_climate_response_conforms_and_carries_extremes(response):
    assert envelope_violations(response) == []
    assert response.sector == Sector.CLIMATE
    assert response.assumption_items == []
    codes = [item.variable for item in response.sites[0].extremes]
    assert codes == ["RX1DAY", "RX5DAY", "R95P", "PRCPTOT", "R10MM", "CDD"]
    rx1 = response.sites[0].extremes[0]
    # Rampa sintética: la precipitación diaria sube 0.1 mm por año, así que la lluvia máxima diaria también.
    assert rx1.trend.slope_per_year == pytest.approx(0.1)
    assert rx1.valid_years == 14 and rx1.discarded_years == 0


def test_extreme_trends_reach_nasa_questions(response):
    findings = {(item.site, item.variable) for item in response.trend_findings}
    assert ("Moquegua", "RX1DAY") in findings
    what = next(question for question in response.nasa_questions if question.key == "what")
    assert "lluvia máxima en 1 día" in what.answer.lower()
    so_what = next(question for question in response.nasa_questions if question.key == "so_what")
    assert "huaicos" in so_what.answer and "no usa supuestos financieros" in so_what.answer


def test_finance_stage_is_declared_not_applicable(response):
    finance = next(stage for stage in response.pipeline if stage.key == "finance")
    assert finance.status == PipelineStatus.UNAVAILABLE
    assert "No aplica" in finance.summary


def test_climate_pdf_renders_from_generic_envelope(response):
    generic = ScreeningEnvelope.model_validate(json.loads(response.model_dump_json()))
    assert render_executive_pdf(generic).startswith(b"%PDF")


def test_short_period_is_rejected():
    with pytest.raises(ValueError, match="diez años"):
        _request(start_date=date(2018, 1, 1))


def test_without_complete_years_the_provider_error_is_explicit(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FlatPowerConnector)
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)
    with pytest.raises(PowerConnectorError, match="años completos"):
        asyncio.run(climate.run_climate_screening(_request()))
