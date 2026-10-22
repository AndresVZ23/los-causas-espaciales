"""Verificación de escala de la precipitación NASA POWER (defecto ×24 observado el 2026-10-22). Datos sintéticos."""

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.connectors.nasa.power import PowerConnectorError
from backend.app.orchestration import extraction
from backend.app.schemas.analysis import Observation, Point, Provenance, SourceMetadata

TODAY = date.today()
START = TODAY - timedelta(days=4 * 365)


def _rain(day: date) -> float:
    return 5.0 if day.day in (3, 17) else 0.0


def _source() -> SourceMetadata:
    return SourceMetadata(source_id="nasa-power", dataset="NASA POWER Daily Point", version="test", variable="PRECTOTCORR", unit="mm/day",
                          temporal_resolution="daily", spatial_resolution="grid", downloaded_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
                          source_url="https://power.larc.nasa.gov", provenance=Provenance.REAL)


def connector_with(factor_recent: float, rain=_rain):
    class FakeConnector:
        async def daily_point_multi(self, latitude, longitude, variables, start_date, end_date):
            recent = end_date > TODAY - timedelta(days=20)
            factor = factor_recent if recent else 1.0
            days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
            return {v: ([Observation(timestamp=d, value=rain(d) * factor) for d in days], _source()) for v in variables}
    return FakeConnector


def _extract(monkeypatch, factor, rain=_rain):
    monkeypatch.setattr(extraction, "PowerConnector", connector_with(factor, rain))
    datasets, _ = asyncio.run(extraction.extract_power([Point(latitude=-17.2, longitude=-70.9)], ["PRECTOTCORR", "T2M"], START, TODAY))
    return datasets[0]


def test_scale_defect_is_corrected_and_declared(monkeypatch):
    observations, source = _extract(monkeypatch, 24.0)["PRECTOTCORR"]
    assert max(item.value for item in observations) == pytest.approx(5.0)
    assert any("se dividió por 24" in note for note in source.quality_notes)


def test_consistent_scale_is_left_untouched(monkeypatch):
    observations, source = _extract(monkeypatch, 1.0)["PRECTOTCORR"]
    assert max(item.value for item in observations) == pytest.approx(5.0)
    assert any("verificada" in note for note in source.quality_notes)


def test_unknown_scale_stops_instead_of_guessing(monkeypatch):
    with pytest.raises(PowerConnectorError, match="escala inconsistente"):
        _extract(monkeypatch, 3.0)


def test_without_wet_reference_days_it_is_declared_unverifiable(monkeypatch):
    observations, source = _extract(monkeypatch, 24.0, rain=lambda d: 0.0)["PRECTOTCORR"]
    assert any("no verificable" in note for note in source.quality_notes)


def test_old_periods_skip_the_check(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", connector_with(24.0))
    datasets, _ = asyncio.run(extraction.extract_power([Point(latitude=-17.2, longitude=-70.9)], ["PRECTOTCORR"], date(2010, 1, 1), date(2020, 12, 31)))
    assert datasets[0]["PRECTOTCORR"][1].quality_notes == []


def test_scale_ratio_uses_median_of_wet_days():
    base = {date(2025, 1, d): 2.0 for d in range(1, 6)}
    main = {day: value * 24 for day, value in base.items()}
    main[date(2025, 1, 1)] = 999.0  # un valor atípico no mueve la mediana
    assert extraction.precipitation_scale(main, base) == pytest.approx(24.0)
    assert extraction.precipitation_scale(main, {date(2025, 1, 1): 0.0}) is None
