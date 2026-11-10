"""Capas leídas con `identify`: la última copia válida cuando el servicio deja de responder (sin red)."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.app.connectors.peru.identify_layers import IdentifyLayersConnector
from backend.app.core.config import Settings
from backend.app.schemas.analysis import Provenance

SQUARE = {"type": "Polygon", "coordinates": [[[-76.75, -11.95], [-76.65, -11.95], [-76.65, -11.85], [-76.75, -11.85], [-76.75, -11.95]]]}
CENTER = (-76.70, -11.90)
TOKEN_REQUIRED = {"error": {"code": 499, "message": "Token Required", "details": []}}


def _age_copies(cache_dir, days: int) -> None:
    for manifest_path in (cache_dir / "identify" / "manifests").glob("*.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["downloaded_at"] = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _connector(tmp_path, state):
    def handler(request: httpx.Request):
        state["calls"] += 1
        if state["closed"]:
            return httpx.Response(200, json=TOKEN_REQUIRED)
        return httpx.Response(200, json={"results": [{"layerId": 2, "attributes": {"Pixel Value": "4"}}, {"layerId": 1, "attributes": {"Pixel Value": "1"}}]})

    return IdentifyLayersConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_cenepred_sampling_uses_last_valid_copies_and_stops_insisting_after_the_first_failure(tmp_path):
    state = {"calls": 0, "closed": False}
    connector = _connector(tmp_path, state)
    fresh = await connector.cenepred_susceptibility(SQUARE, CENTER)
    points = state["calls"]
    assert points == 17 and fresh.stale_note is None and fresh.provenance == Provenance.REAL     # 4 × 4 puntos más el representativo

    _age_copies(tmp_path, days=10)          # vencidas para el uso normal (7 días), válidas como última copia
    state["closed"] = True
    stale = await connector.cenepred_susceptibility(SQUARE, CENTER)

    assert state["calls"] == points + 1     # una sola consulta rechazada; en los demás puntos no se insiste
    assert stale.status == "READY" and stale.provenance == Provenance.CACHED
    assert stale.intersection_count == fresh.intersection_count == 2 * points
    assert "Token Required" in stale.stale_note and stale.limitations[0] == stale.stale_note
    assert (datetime.now(timezone.utc) - stale.downloaded_at).days == 10


@pytest.mark.asyncio
async def test_cenepred_sampling_without_copies_is_unavailable_not_empty(tmp_path):
    state = {"calls": 0, "closed": True}
    result = await _connector(tmp_path, state).cenepred_susceptibility(SQUARE, CENTER)
    assert state["calls"] == 1
    assert result.status == "DATA_UNAVAILABLE" and result.intersection_count is None and result.stale_note is None
    assert "Token Required" in result.limitations[0]
