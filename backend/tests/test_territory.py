import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.app.connectors.cache import STALE_MAX_AGE
from backend.app.connectors.peru.territory import (
    LAYERS,
    TerritoryConnector,
    TerritoryConnectorError,
    _cache_max_age,
    _esri_geometry,
)
from backend.app.core.config import Settings
from backend.app.schemas.analysis import Provenance
from backend.app.schemas.data_sources import TerritorialQueryRequest


@pytest.mark.asyncio
async def test_official_arcgis_query_uses_wgs84_and_content_addressed_cache(tmp_path):
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        assert request.url.host == "sigrid.cenepred.gob.pe"
        body = request.content.decode()
        assert "geometryType=esriGeometryPoint" in body
        assert "inSR=4326" in body and "outSR=4326" in body
        return httpx.Response(200, json={"features": [{"attributes": {"nriesgo_in": "Alto", "ubigeo": "180101"}}]})

    settings = Settings(_env_file=None, cache_dir=tmp_path, cache_ttl_hours=24)
    connector = TerritoryConnector(settings=settings, transport=httpx.MockTransport(handler))
    request = TerritorialQueryRequest(
        geometry={"type": "Point", "coordinates": [-70.934, -17.193]},
        source_ids=["cenepred-flood-risk"],
    )
    first = await connector.query(request)
    second = await connector.query(request)
    assert calls == 1
    assert first.sources[0].provenance == Provenance.REAL
    assert second.sources[0].provenance == Provenance.CACHED
    assert first.sources[0].intersection_count == 1


@pytest.mark.asyncio
async def test_empty_intersection_is_not_described_as_no_risk(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"features": []}))
    connector = TerritoryConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=transport)
    response = await connector.query(TerritorialQueryRequest(
        geometry={"type": "Point", "coordinates": [-70.934, -17.193]}, source_ids=["sernanp-anp"]
    ))
    assert response.sources[0].status == "READY"
    assert response.sources[0].intersection_count == 0
    assert any("no demuestra ausencia" in item for item in response.sources[0].limitations)


def test_corridor_and_polygon_are_encoded_in_lon_lat_order():
    kind, line = _esri_geometry({"type": "LineString", "coordinates": [[-71, -17], [-70, -16]]})
    assert kind == "esriGeometryPolyline"
    assert line["paths"][0][0] == [-71, -17]
    kind, polygon = _esri_geometry({"type": "Polygon", "coordinates": [[[-71, -17], [-70, -17], [-70, -16], [-71, -17]]]})
    assert kind == "esriGeometryPolygon"
    assert polygon["rings"][0][0] == [-71, -17]
    kind, multipolygon = _esri_geometry({
        "type": "MultiPolygon",
        "coordinates": [
            [[[-71, -17], [-70, -17], [-70, -16], [-71, -17]]],
            [[[-69, -17], [-68, -17], [-68, -16], [-69, -17]]],
        ],
    })
    assert kind == "esriGeometryPolygon"
    assert len(multipolygon["rings"]) == 2


@pytest.mark.asyncio
async def test_unknown_source_is_rejected(tmp_path):
    connector = TerritoryConnector(settings=Settings(_env_file=None, cache_dir=tmp_path))
    with pytest.raises(TerritoryConnectorError, match="desconocidas"):
        await connector.query(TerritorialQueryRequest(
            geometry={"type": "Point", "coordinates": [-70.934, -17.193]}, source_ids=["invented-source"]
        ))


def test_cultura_layers_use_seven_day_cache_and_other_sources_keep_default():
    assert _cache_max_age(LAYERS["cultura-archaeology"], 24) == timedelta(days=7)
    assert _cache_max_age(LAYERS["cenepred-flood-risk"], 24) == timedelta(hours=24)


TOKEN_REQUIRED = {"error": {"code": 499, "message": "Token Required", "details": []}}   # lo que SIGRID responde desde nov-2026
POINT_REQUEST = TerritorialQueryRequest(geometry={"type": "Point", "coordinates": [-70.934, -17.193]}, source_ids=["cenepred-flood-risk"])


def _age_copies(cache_dir, days: int) -> None:
    """Envejece las copias de la caché territorial, como si se hubieran descargado hace `days` días."""
    for manifest_path in (cache_dir / "territory" / "manifests").glob("*.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["downloaded_at"] = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.asyncio
async def test_provider_failure_serves_the_last_valid_copy_with_its_original_date(tmp_path):
    answers = [httpx.Response(200, json={"features": [{"attributes": {"nriesgo_in": "Alto"}}]}), httpx.Response(200, json=TOKEN_REQUIRED)]
    connector = TerritoryConnector(settings=Settings(_env_file=None, cache_dir=tmp_path, cache_ttl_hours=24),
                                   transport=httpx.MockTransport(lambda request: answers.pop(0)))
    fresh = (await connector.query(POINT_REQUEST)).sources[0]
    _age_copies(tmp_path, days=14)          # vencida para el uso normal (24 h), válida como última copia
    stale = (await connector.query(POINT_REQUEST)).sources[0]

    assert fresh.stale_note is None and fresh.provenance == Provenance.REAL
    assert answers == []                    # antes de usar la copia se consultó al servicio
    assert stale.status == "READY" and stale.provenance == Provenance.CACHED and stale.intersection_count == 1
    assert "Token Required" in stale.stale_note and "última copia válida" in stale.stale_note
    assert stale.limitations[0] == stale.stale_note
    assert (datetime.now(timezone.utc) - stale.downloaded_at).days == 14     # la fecha informada es la de la copia, no la de hoy


@pytest.mark.asyncio
async def test_without_a_copy_or_with_one_too_old_the_layer_stays_unavailable(tmp_path):
    answers = [httpx.Response(200, json=TOKEN_REQUIRED), httpx.Response(200, json={"features": []}), httpx.Response(200, json=TOKEN_REQUIRED)]
    connector = TerritoryConnector(settings=Settings(_env_file=None, cache_dir=tmp_path, cache_ttl_hours=24),
                                   transport=httpx.MockTransport(lambda request: answers.pop(0)))
    never_seen = (await connector.query(POINT_REQUEST)).sources[0]
    assert never_seen.status == "DATA_UNAVAILABLE" and never_seen.stale_note is None
    assert "Token Required" in never_seen.limitations[0]

    await connector.query(POINT_REQUEST)    # ahora sí queda una copia
    _age_copies(tmp_path, days=STALE_MAX_AGE.days + 1)
    too_old = (await connector.query(POINT_REQUEST)).sources[0]
    assert too_old.status == "DATA_UNAVAILABLE" and too_old.stale_note is None and too_old.intersection_count is None
