import asyncio
import json
from datetime import date

import pytest

from backend.app.connectors.nasa.power import PowerConnectorError
from backend.app.orchestration import extraction
from backend.app.orchestration.conformance import envelope_violations
from backend.app.reports.executive_pdf import render_executive_pdf
from backend.app.schemas.analysis import Point
from backend.app.orchestration.analysis import agreement, attach_countercheck
from backend.app.schemas.analysis import TrendResult
from backend.app.schemas.climate import Agreement, AtypicalYear, ClimateScreeningRequest, ExtremeIndexSummary
from backend.app.schemas.screening import AnnualObservation
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


def test_how_much_reports_every_significant_variable(response):
    # Una cláusula por variable significativa: no se elige un «mayor cambio» comparando mm con °C.
    how_much = next(question for question in response.nasa_questions if question.key == "how_much")
    for variable in {item.variable for item in response.trend_findings}:
        label = next(item.label for item in response.trend_findings if item.variable == variable)
        assert label.lower() in how_much.answer.lower()


def test_every_extreme_carries_imerg_countercheck(response):
    for site in response.sites:
        for item in site.extremes:
            assert item.countercheck is not None and item.countercheck.source.startswith("GPM IMERG")
            # Con la misma serie sintética en ambas fuentes, toda tendencia significativa se repite.
            if item.significant_after_bh:
                assert item.countercheck.agreement == Agreement.COINCIDE
    significant = next(question for question in response.nasa_questions if question.key == "significant")
    assert "Contraste con GPM IMERG" in significant.answer
    assert not any(gap.dataset == "GPM IMERG" for gap in response.data_gaps)


class NoImergConnector(FakePowerConnector):
    """IMERG sin años completos (solo pruebas): el contraste falla y debe declararse, sin tumbar el análisis."""

    async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
        output = await super().daily_point_multi(latitude, longitude, variables, start_date, end_date)
        if "IMERG_PRECTOT" in output:
            output["IMERG_PRECTOT"] = ([], output["IMERG_PRECTOT"][1])
        return output


def test_missing_imerg_becomes_a_declared_gap(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", NoImergConnector)
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)
    result = asyncio.run(climate.run_climate_screening(_request()))
    assert envelope_violations(result) == []
    assert any(gap.dataset == "GPM IMERG" for gap in result.data_gaps)
    assert all(item.countercheck is None for site in result.sites for item in site.extremes)


def _summary(direction: str, significant: bool, series=None, atypical=None):
    trend = TrendResult.model_construct(direction=direction, slope_per_year=1.0 if direction == "increasing" else -1.0)
    return ExtremeIndexSummary.model_construct(
        variable="RX1DAY", unit="mm", trend=trend, significant_after_bh=significant, adjusted_p_value=0.01 if significant else 0.4,
        valid_years=3, annual_series=series or [], atypical_years=atypical or [], countercheck=None,
    )


@pytest.mark.parametrize(("a", "b", "expected"), [
    (("increasing", True), ("increasing", True), Agreement.COINCIDE),
    (("increasing", True), ("decreasing", True), Agreement.CONTRADICE),
    (("increasing", True), ("no_trend", False), Agreement.SIN_RESPALDO),
    (("no_trend", False), ("increasing", True), Agreement.SOLO_CONTRASTE),
    (("no_trend", False), ("no_trend", False), Agreement.SIN_TENDENCIA),
])
def test_agreement_cases(a, b, expected):
    assert agreement(_summary(*a), _summary(*b)) == expected


def test_atypical_year_gets_countercheck_value():
    # El caso real que motivó el contraste: 300 mm en el reanálisis y 0 mm en IMERG el mismo año.
    primary = _summary("no_trend", False, atypical=[AtypicalYear(year=2022, value=300.2, robust_z=89.0)])
    other = _summary("no_trend", False, series=[AnnualObservation(year=2021, value=4.0), AnnualObservation(year=2022, value=0.0)])
    attach_countercheck([[primary]], [[other]], "GPM IMERG (prueba)")
    assert primary.atypical_years[0].countercheck_value == 0.0
    assert primary.countercheck.agreement == Agreement.SIN_TENDENCIA


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
