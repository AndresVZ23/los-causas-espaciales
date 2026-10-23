import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.connectors.nasa.nasadem import NasademConnectorError
from backend.app.connectors.nasa.power import PowerConnectorError
from backend.app.schemas.analysis import Observation, Point, Provenance, SourceMetadata
from backend.app.schemas.pipeline import PipelineStatus, QuestionStatus, SolarAssumptions, SolarScreeningRequest
from backend.app.schemas.terrain import TerrainMetrics, TerrainResponse, TerrainSiteResult
from backend.app.orchestration import extraction
from backend.app.sectors import solar
from backend.app.sectors.solar import SOLAR_VARIABLES, calculate_solar_projection


def test_solar_projection_uses_explicit_formula():
    assumptions = SolarAssumptions(
        capacity_mw=10,
        performance_ratio=0.8,
        initial_capex_usd=8_000_000,
        annual_opex_usd=150_000,
        energy_price_usd_mwh=50,
        discount_rate=0.1,
        horizon_years=2,
    )
    result = calculate_solar_projection(6, assumptions)
    assert result.specific_yield_kwh_kwp_year == 1752
    assert result.annual_energy_mwh == 17_520
    assert result.annual_revenue_usd == 876_000
    assert result.model_provenance == "MODEL_ESTIMATE"
    assert result.assumption_provenance == "USER_ASSUMPTION"


def test_higher_irradiance_increases_energy_and_npv():
    assumptions = SolarAssumptions()
    low = calculate_solar_projection(4.5, assumptions)
    high = calculate_solar_projection(6.5, assumptions)
    assert high.annual_energy_mwh > low.annual_energy_mwh
    assert high.npv_usd > low.npv_usd


def _source(variable: str) -> SourceMetadata:
    units = {
        "ALLSKY_SFC_SW_DWN": "kW-hr/m^2/day",
        "T2M": "C",
        "WS10M": "m/s",
        "PRECTOTCORR": "mm/day",
        "IMERG_PRECTOT": "mm/day",
    }
    return SourceMetadata(
        source_id=f"power-{variable}",
        dataset="NASA POWER Daily Point",
        version="10",
        variable=variable,
        unit=units[variable],
        temporal_resolution="daily",
        spatial_resolution="documented by parameter family",
        downloaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_url="https://power.larc.nasa.gov/api/temporal/daily/point",
        provenance=Provenance.CACHED,
    )


class FakePowerConnector:
    """Rampa sintética diaria (solo pruebas): +0.1 por año, constante dentro de cada año."""

    async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
        solar_base = 6.5 if latitude < -17 else 5.5
        days = [start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)]
        output = {}
        for variable in variables:
            base = solar_base if variable == "ALLSKY_SFC_SW_DWN" else 10.0
            observations = [Observation(timestamp=day, value=base + (day.year - 2018) * 0.1) for day in days]
            output[variable] = (observations, _source(variable))
        return output


class SparsePowerConnector:
    """Una observación por año: la cobertura diaria queda muy por debajo del umbral."""

    async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
        return {
            variable: ([Observation(timestamp=date(year, 1, 1), value=6.5 + (year - 2018) * 0.1) for year in range(2018, 2024)], _source(variable))
            for variable in variables
        }


class FlatPowerConnector:
    """Series sintéticas sin tendencia (solo pruebas): ninguna variable debe declararse significativa."""

    async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
        pattern = [0.0, 0.3, -0.2, 0.1, -0.3, 0.2]
        output = {}
        for variable in variables:
            base = 6.5 if variable == "ALLSKY_SFC_SW_DWN" else 10.0
            observations = [Observation(timestamp=date(2018 + index, 1, 1), value=base + noise) for index, noise in enumerate(pattern)]
            output[variable] = (observations, _source(variable))
        return output


class MetadataOnlyNasadem:
    async def points(self, sites):
        return TerrainResponse(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sites=[TerrainSiteResult(location=site, status="METADATA_ONLY", metrics=TerrainMetrics(), granules=[], provenance=Provenance.UNAVAILABLE, limitations=[]) for site in sites],
            note="prueba",
        )


class FailingNasadem:
    async def points(self, sites):
        raise NasademConnectorError("CMR fuera de servicio (prueba)")


@pytest.fixture(autouse=True)
def offline_nasadem(monkeypatch):
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)


def _request() -> SolarScreeningRequest:
    return SolarScreeningRequest(
        sites=[
            Point(label="Moquegua", latitude=-17.193, longitude=-70.934),
            Point(label="Arequipa", latitude=-16.409, longitude=-71.537),
        ],
        start_date=date(2018, 1, 1),
        end_date=date(2023, 12, 31),
    )


def test_screening_orchestrates_pipeline_and_preserves_provenance(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FakePowerConnector)

    result = asyncio.run(solar.run_solar_screening(_request()))

    assert len(result.pipeline) == 9
    assert result.pipeline[4].status == PipelineStatus.PARTIAL
    assert result.pipeline[8].status == PipelineStatus.READY
    assert all(stage.status == PipelineStatus.COMPLETED for stage in result.pipeline if stage.step not in (5, 9))
    assert all(stage.evidence for stage in result.pipeline)
    assert result.pipeline[2].duration_ms is not None and result.pipeline[3].duration_ms is not None
    assert result.sites[0].relative_solar_position == 1
    assert result.sites[1].relative_solar_position == 2
    assert {item.variable for item in result.sites[0].variables} == set(SOLAR_VARIABLES)
    solar_series = next(item for item in result.sites[0].variables if item.variable == "ALLSKY_SFC_SW_DWN").annual_series
    assert [item.year for item in solar_series] == list(range(2018, 2024))
    assert [item.value for item in solar_series] == [6.5, 6.6, 6.7, 6.8, 6.9, 7.0]
    assert all(item.source.provenance == Provenance.CACHED for site in result.sites for item in site.variables)
    assert all(gap.status == Provenance.UNAVAILABLE for gap in result.data_gaps)
    assert result.sites[0].finance.model_provenance == Provenance.MODEL
    assert result.sites[0].finance.assumption_provenance == Provenance.ASSUMPTION
    assert "no es una recomendación" in result.comparative_findings[-1]


def test_nasa_questions_quantify_significant_trends(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FakePowerConnector)

    result = asyncio.run(solar.run_solar_screening(_request()))
    questions = {item.key: item for item in result.nasa_questions}

    assert list(questions) == ["what", "where", "how_much", "significant", "so_what"]
    # Rampa sintética de +0.1/año durante 2018–2023: la pendiente de Sen y el cambio deben reproducirla.
    temperature = next(item for item in result.trend_findings if item.variable == "T2M" and item.site == "Moquegua")
    assert temperature.slope_per_year == pytest.approx(0.1)
    assert temperature.change_over_period == pytest.approx(0.5)
    assert temperature.change_percent_of_mean is None  # °C es escala de intervalo
    irradiance = next(item for item in result.trend_findings if item.variable == "ALLSKY_SFC_SW_DWN" and item.site == "Moquegua")
    assert irradiance.change_percent_of_mean == pytest.approx(0.5 / 6.75 * 100, rel=1e-3)
    assert questions["what"].status == QuestionStatus.ANSWERED
    assert "todos los sitios analizados" in questions["where"].answer
    assert questions["so_what"].status == QuestionStatus.PARTIAL
    assert Provenance.UNAVAILABLE in questions["so_what"].provenance


def test_nasa_questions_declare_insufficient_evidence_without_trend(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FlatPowerConnector)

    result = asyncio.run(solar.run_solar_screening(_request()))
    questions = {item.key: item for item in result.nasa_questions}

    assert result.trend_findings == []
    for key in ("what", "where", "how_much", "significant"):
        assert questions[key].status == QuestionStatus.INSUFFICIENT
    assert "Evidencia insuficiente" in questions["significant"].answer
    assert "no prueba que sea constante" in questions["so_what"].answer


def test_terrain_failure_is_declared_without_blocking_solar_screening(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FakePowerConnector)
    monkeypatch.setattr(extraction, "NasademConnector", FailingNasadem)

    result = asyncio.run(solar.run_solar_screening(_request()))
    territorial = result.pipeline[4]

    assert result.terrain is None
    assert territorial.status == PipelineStatus.PARTIAL
    assert any("CMR fuera de servicio" in item.value for item in territorial.evidence)
    assert any(gap.dataset == "Métricas raster NASADEM" for gap in result.data_gaps)


def test_low_coverage_marks_extraction_partial(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", SparsePowerConnector)
    result = asyncio.run(solar.run_solar_screening(_request()))

    assert result.pipeline[2].status == PipelineStatus.PARTIAL
    assert "inferior al umbral" in result.pipeline[2].summary


def test_screening_does_not_replace_provider_failure_with_fake_data(monkeypatch):
    class FailingConnector:
        async def daily_point_multi(self, *args, **kwargs):
            raise PowerConnectorError("fallo NASA controlado")

    monkeypatch.setattr(extraction, "PowerConnector", FailingConnector)

    with pytest.raises(PowerConnectorError, match="fallo NASA controlado"):
        asyncio.run(solar.run_solar_screening(_request()))
