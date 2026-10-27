import asyncio
from datetime import date

import httpx
import pytest

from backend.app.connectors.nasa import climateserv
from backend.app.core.config import Settings
from backend.app.orchestration import rainfall_crosscheck as rc
from backend.app.schemas.analysis import Point

from backend.tests.conftest import FlatChirps

START, END = date(2001, 1, 1), date(2025, 12, 31)
LIMA, ICA = Point(latitude=-12.05, longitude=-77.04), Point(latitude=-14.07, longitude=-75.73)


class DesertForOne(FlatChirps):
    """Lima sin un solo día húmedo (como CHIRPS en la costa hiperárida); Ica con lluvia sintética."""

    async def daily(self, geometry, longitude, latitude, start, end):
        observations, source = await super().daily(geometry, longitude, latitude, start, end)
        if latitude == LIMA.latitude:
            observations = [item.model_copy(update={"value": 0.0}) for item in observations]
        return observations, source


class Slow(FlatChirps):
    async def daily(self, *args, **kwargs):
        await asyncio.sleep(5)
        return await super().daily(*args, **kwargs)


def _climateserv(submit_statuses: list[int]):
    calls = {"submit": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/submitDataRequest/"):
            status = submit_statuses[min(calls["submit"], len(submit_statuses) - 1)]
            calls["submit"] += 1
            return httpx.Response(status, json=["job-1"] if status == 200 else {"error": "busy"})
        if request.url.path.endswith("/getDataRequestProgress/"):
            return httpx.Response(200, json=[100])
        return httpx.Response(200, json={"data": [{"year": 2024, "month": 2, "day": 1, "value": {"avg": 12.5}},
                                                  {"year": 2024, "month": 2, "day": 2, "value": {"avg": -9999}}]})
    return httpx.MockTransport(handler), calls


def test_climateserv_retries_a_transient_503_and_skips_missing_days(monkeypatch, tmp_path):
    monkeypatch.setattr(climateserv, "POLL_SECONDS", 0)
    monkeypatch.setattr(climateserv, "RETRY_SECONDS", 0)
    transport, calls = _climateserv([503, 200])
    connector = climateserv.ChirpsConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=transport)
    observations, source = asyncio.run(connector.daily(None, ICA.longitude, ICA.latitude, date(2024, 1, 1), date(2024, 12, 31)))
    assert calls["submit"] == 2
    assert [(item.timestamp, item.value) for item in observations] == [(date(2024, 2, 1), 12.5)]   # -9999 es faltante, no cero
    assert source.variable == "CHIRPS" and source.unit == "mm/day"


def test_climateserv_does_not_retry_a_client_error(monkeypatch, tmp_path):
    monkeypatch.setattr(climateserv, "POLL_SECONDS", 0)
    transport, calls = _climateserv([400])
    connector = climateserv.ChirpsConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=transport)
    with pytest.raises(climateserv.ClimateServError):
        asyncio.run(connector.daily(None, ICA.longitude, ICA.latitude, date(2024, 1, 1), date(2024, 12, 31)))
    assert calls["submit"] == 1


def test_climateserv_down_only_for_the_open_year_keeps_the_closed_years(monkeypatch, tmp_path):
    monkeypatch.setattr(climateserv, "POLL_SECONDS", 0)
    monkeypatch.setattr(climateserv, "RETRY_SECONDS", 0)
    this_year = date.today().year

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/submitDataRequest/"):
            open_year = f"/{this_year}" in request.content.decode().replace("%2F", "/")
            return httpx.Response(503, json={"error": "busy"}) if open_year else httpx.Response(200, json=["job-1"])
        if request.url.path.endswith("/getDataRequestProgress/"):
            return httpx.Response(200, json=[100])
        return httpx.Response(200, json={"data": [{"year": this_year - 1, "month": 3, "day": 1, "value": {"avg": 7.0}}]})
    connector = climateserv.ChirpsConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=httpx.MockTransport(handler))
    observations, source = asyncio.run(connector.daily(None, ICA.longitude, ICA.latitude, date(this_year - 1, 1, 1), date.today()))
    assert [(item.timestamp, item.value) for item in observations] == [(date(this_year - 1, 3, 1), 7.0)]
    assert any(note.startswith(f"El año {this_year} no respondió") for note in source.quality_notes)
    with pytest.raises(climateserv.ClimateServError):           # si falla un año cerrado, la serie sí se declara caída
        asyncio.run(climateserv.ChirpsConnector(settings=Settings(_env_file=None, cache_dir=tmp_path / "otra"),
                                                transport=httpx.MockTransport(lambda r: httpx.Response(503))).daily(
            None, ICA.longitude, ICA.latitude, date(this_year - 1, 1, 1), date.today()))


def test_subject_without_wet_days_does_not_drop_the_others(monkeypatch):
    monkeypatch.setattr(rc, "ChirpsConnector", DesertForOne)
    result = asyncio.run(rc.chirps_extremes([("Lima", None, LIMA), ("Ica", None, ICA)], START, END))
    assert result.extremes[0] is None and result.extremes[1]                      # sin serie útil: None, nunca ceros
    assert len(result.errors) == 1 and result.errors[0].startswith("Lima:")
    assert [gap.dataset for gap in rc.chirps_gaps(result)] == ["CHIRPS · fuente con error"]


def test_download_beyond_the_wait_budget_is_declared_pending(monkeypatch):
    monkeypatch.setattr(rc, "ChirpsConnector", Slow)
    result = asyncio.run(rc.chirps_extremes([("Ica", None, ICA)], START, END, wait=0.05))
    assert result.pending == ["Ica"] and result.extremes == [None]
    gap = rc.chirps_gaps(result)[0]
    assert "descargando" in gap.impact and "Volver a ejecutar" in gap.next_action
