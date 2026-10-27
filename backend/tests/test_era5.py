"""ERA5 vía PVGIS como segunda fuente de temperatura y radiación: conector, años comunes y descubrimientos, sin red."""

import asyncio
from datetime import date, datetime, timezone

import httpx
import pytest

from backend.app.connectors.jrc import pvgis
from backend.app.connectors.jrc.pvgis import Era5Annual, PvgisError, annual_from_monthly
from backend.app.core.config import Settings
from backend.app.orchestration.discoveries import variable_discoveries
from backend.app.orchestration.era5_crosscheck import ERA5_SOURCE, Era5Result, attach_era5
from backend.app.schemas.analysis import Observation, Provenance, SourceMetadata
from backend.app.schemas.pipeline import Agreement, AnnualObservation, VariableSummary
from backend.app.schemas.screening import DiscoveryKind
from backend.app.statistics.trends import analyze_trend

STAMP = datetime(2026, 10, 27, tzinfo=timezone.utc)


def _wobble(year: int) -> float:
    return ((year * 7) % 5 - 2) * 0.01


def _observations(years, value_for) -> list[Observation]:
    return [Observation(timestamp=date(year, 7, 1), value=round(value_for(year), 4)) for year in years]


def _summary(code: str, value_for, unit: str = "°C", significant: bool | None = None) -> VariableSummary:
    observations = _observations(range(2001, 2026), value_for)
    trend = analyze_trend(observations, already_annual=True)
    values = [item.value for item in observations]
    return VariableSummary(
        variable=code, label="Temperatura del aire a 2 m" if code == "T2M" else "Irradiancia solar superficial", mean=sum(values) / len(values),
        minimum=min(values), maximum=max(values), unit=unit, display_unit=unit, valid_observations=len(values) * 365, completeness_percent=100,
        annual_variability_percent=None, trend=trend, significant_after_bh=trend.significant if significant is None else significant,
        source=SourceMetadata(source_id="power", dataset="NASA POWER", version="prueba", variable=code, unit=unit, temporal_resolution="Diaria",
                              spatial_resolution="0.5°", downloaded_at=STAMP, source_url="https://power.larc.nasa.gov", provenance=Provenance.CACHED),
        annual_series=[AnnualObservation(year=item.timestamp.year, value=item.value) for item in observations],
    )


def _era5(temperature_for, irradiance_for) -> Era5Annual:
    years = range(2005, 2024)
    return Era5Annual(temperature=_observations(years, temperature_for), irradiance=_observations(years, irradiance_for), provenance=Provenance.REAL, downloaded_at=STAMP)


def test_monthly_rows_become_day_weighted_annual_means_and_incomplete_years_drop():
    rows = [{"year": 2020, "month": m, "H(h)_m": 186.0 if m == 1 else 150.0, "T2m": 20.0 if m == 1 else 10.0} for m in range(1, 13)]
    rows += [{"year": 2021, "month": m, "H(h)_m": 150.0, "T2m": 10.0} for m in range(1, 12)]   # sin diciembre
    temperature, irradiance = annual_from_monthly(rows)
    assert [item.timestamp.year for item in temperature] == [2020]
    assert temperature[0].value == pytest.approx((20 * 31 + 10 * 335) / 366, abs=1e-4)       # 2020 es bisiesto
    assert irradiance[0].value == pytest.approx((186 + 150 * 11) / 366, abs=1e-4)


def test_pvgis_out_of_coverage_is_an_error_not_a_retry(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400, json={"message": "Location out of the spatial coverage", "status": 400})
    connector = pvgis.PvgisConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=httpx.MockTransport(handler))
    with pytest.raises(PvgisError, match="400: Location out of the spatial coverage"):
        asyncio.run(connector.era5_annual(-17.19, -70.93))
    assert calls["n"] == 1


def test_pvgis_retries_a_503_and_then_serves_from_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(pvgis, "RETRY_SECONDS", 0)
    statuses = iter([503, 200])
    rows = [{"year": y, "month": m, "H(h)_m": 180.0, "T2m": 18.0} for y in (2005, 2006) for m in range(1, 13)]

    def handler(request):
        assert request.url.params["raddatabase"] == "PVGIS-ERA5" and request.url.params["startyear"] == "2005"
        status = next(statuses)
        return httpx.Response(status, json={"outputs": {"monthly": rows}} if status == 200 else {"message": "busy"})
    settings = Settings(_env_file=None, cache_dir=tmp_path)
    first = asyncio.run(pvgis.PvgisConnector(settings=settings, transport=httpx.MockTransport(handler)).era5_annual(-17.19, -70.93))
    assert first.provenance == Provenance.REAL and [o.timestamp.year for o in first.temperature] == [2005, 2006]
    again = asyncio.run(pvgis.PvgisConnector(settings=settings, transport=httpx.MockTransport(lambda r: httpx.Response(500))).era5_annual(-17.19, -70.93))
    assert again.provenance == Provenance.CACHED and again.downloaded_at == first.downloaded_at


def test_rising_temperature_confirmed_in_common_years_and_solar_level_compared():
    warming = lambda year: 18.0 + 0.03 * (year - 2001) + _wobble(year)        # noqa: E731
    temperature = _summary("T2M", warming)
    sun = _summary("ALLSKY_SFC_SW_DWN", lambda year: 6.0 + _wobble(year), unit="kWh/m²/día")
    attach_era5([[temperature, sun]], Era5Result(series=[_era5(lambda y: warming(y) - 2.5, lambda y: 6.72 + _wobble(y))]))
    check = temperature.counterchecks[0]
    assert check.source == ERA5_SOURCE and check.period == "2005–2023" and check.valid_years == 19
    assert check.agreement == Agreement.COINCIDE and check.primary_slope_per_year == pytest.approx(0.03, abs=0.005)
    found = variable_discoveries([("Moquegua", [temperature, sun])])
    kinds = {item.title: item.kind for item in found}
    assert kinds["Moquegua: temperatura del aire a 2 m: la tendencia se confirma con ERA5"] == DiscoveryKind.CONFIRMED
    solar = next(item for item in found if "recurso solar" in item.title)
    assert solar.kind == DiscoveryKind.CONTRADICTION and solar.title == "Moquegua: el recurso solar difiere 12 % entre CERES y ERA5"
    assert "CERES (NASA POWER) 6.00" in solar.detail and "ERA5 6.72" in solar.detail
    level = kinds["Moquegua: la temperatura media difiere 2.5 °C entre MERRA-2 y ERA5"]                # misma tendencia, otro nivel
    assert level == DiscoveryKind.CONTRADICTION


def test_a_trend_that_vanishes_in_the_common_years_is_declared_and_a_missing_site_stays_empty():
    late_jump = lambda year: 18.0 + (0.4 if year >= 2024 else 0.0) + _wobble(year)   # noqa: E731 — solo cambia fuera de 2005–2023
    temperature = _summary("T2M", late_jump, significant=True)
    sun = _summary("ALLSKY_SFC_SW_DWN", lambda year: 6.0 + _wobble(year), unit="kWh/m²/día")
    alone = _summary("T2M", late_jump, significant=True)
    attach_era5([[temperature, sun], [alone]], Era5Result(series=[_era5(lambda y: 18.0 + _wobble(y), lambda y: 6.1 + _wobble(y)), None]))
    assert alone.counterchecks == []                                                     # sin ERA5: sin contraste, nunca ceros
    found = variable_discoveries([("Ilo", [temperature, sun]), ("Sin ERA5", [alone])])
    vanished = next(item for item in found if "no se sostiene" in item.title)
    assert vanished.kind == DiscoveryKind.UNBACKED and "Ilo: temperatura del aire a 2 m: la tendencia de MERRA-2 no se sostiene en 2005–2023" == vanished.title
    agree = next(item for item in found if "coinciden en el recurso solar" in item.title)
    assert agree.kind == DiscoveryKind.AGREEMENT and "(+1.7 %)" in agree.detail
    assert all("Sin ERA5" not in item.title for item in found)
