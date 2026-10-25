import json
from datetime import timedelta

import httpx
import pytest

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
