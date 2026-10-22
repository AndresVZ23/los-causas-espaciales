import asyncio
from datetime import date, datetime, timezone

import pytest

from backend.app.connectors.nasa.power import PowerConnectorError
from backend.app.schemas.analysis import Observation, Point, Provenance, SourceMetadata
from backend.app.schemas.pipeline import PipelineStatus, SolarAssumptions, SolarScreeningRequest
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
    async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
        solar_base = 6.5 if latitude < -17 else 5.5
        output = {}
        for variable in variables:
            base = solar_base if variable == "ALLSKY_SFC_SW_DWN" else 10.0
            observations = [
                Observation(timestamp=date(year, 1, 1), value=base + (year - 2018) * 0.1)
                for year in range(2018, 2024)
            ]
            output[variable] = (observations, _source(variable))
        return output


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
    monkeypatch.setattr(solar, "PowerConnector", FakePowerConnector)

    result = asyncio.run(solar.run_solar_screening(_request()))

    assert len(result.pipeline) == 9
    assert result.pipeline[4].status == PipelineStatus.PARTIAL
    assert all(stage.status == PipelineStatus.COMPLETED for stage in result.pipeline if stage.step != 5)
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


def test_screening_does_not_replace_provider_failure_with_fake_data(monkeypatch):
    class FailingConnector:
        async def daily_point_multi(self, *args, **kwargs):
            raise PowerConnectorError("fallo NASA controlado")

    monkeypatch.setattr(solar, "PowerConnector", FailingConnector)

    with pytest.raises(PowerConnectorError, match="fallo NASA controlado"):
        asyncio.run(solar.run_solar_screening(_request()))
