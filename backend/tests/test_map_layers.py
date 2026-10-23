"""Catálogo de capas GIBS con capacidades WMTS sintéticas (solo pruebas; sin red)."""

import asyncio
from datetime import date

import httpx
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.maplayers import catalog

CAPABILITIES = b"""<?xml version="1.0"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:ows="http://www.opengis.net/ows/1.1" xmlns:xlink="http://www.w3.org/1999/xlink">
 <Contents>
  <Layer>
   <ows:Identifier>GHRSST_L4_MUR_Sea_Surface_Temperature</ows:Identifier>
   <Style><LegendURL xlink:href="https://gibs.earthdata.nasa.gov/legends/GHRSST_Sea_Surface_Temperature_H.svg"/>
          <LegendURL xlink:href="https://gibs.earthdata.nasa.gov/legends/GHRSST_Sea_Surface_Temperature_V.svg"/></Style>
   <Format>image/png</Format>
   <Dimension><ows:Identifier>Time</ows:Identifier><Default>2026-10-22</Default>
    <Value>2002-06-01/2025-12-31/P1D</Value><Value>2026-01-01/2026-10-22/P1D</Value></Dimension>
   <TileMatrixSetLink><TileMatrixSet>GoogleMapsCompatible_Level7</TileMatrixSet></TileMatrixSetLink>
  </Layer>
  <Layer>
   <ows:Identifier>AMSRU_L3_Ocean_Wind_Speed_Daily</ows:Identifier>
   <Format>image/png</Format>
   <Dimension><ows:Identifier>Time</ows:Identifier><Default>2025-09-01</Default><Value>2012-07-02/2025-09-01/P1D</Value></Dimension>
   <TileMatrixSetLink><TileMatrixSet>GoogleMapsCompatible_Level6</TileMatrixSet></TileMatrixSetLink>
  </Layer>
  <Layer>
   <ows:Identifier>MODIS_Terra_CorrectedReflectance_TrueColor</ows:Identifier>
   <Format>image/jpeg</Format>
   <Dimension><ows:Identifier>Time</ows:Identifier><Default>2026-10-23</Default><Value>2000-02-24/2026-10-23/P1D</Value></Dimension>
   <TileMatrixSetLink><TileMatrixSet>GoogleMapsCompatible_Level9</TileMatrixSet></TileMatrixSetLink>
  </Layer>
 </Contents>
</Capabilities>"""


def test_parse_reads_dates_zoom_format_and_horizontal_legend():
    layers = {layer.id: layer for layer in catalog.parse_capabilities(CAPABILITIES, date(2026, 10, 23))}
    sst = layers["sst"]
    assert sst.max_zoom == 7 and sst.latest_date == date(2026, 10, 22) and sst.first_date == date(2002, 6, 1) and sst.period_days == 1
    assert sst.legend_url.endswith("_H.svg")
    assert sst.tile_url.endswith("/GHRSST_L4_MUR_Sea_Surface_Temperature/default/{time}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png")
    assert sst.notice is None
    assert layers["true-color"].tile_url.endswith(".jpg") and layers["true-color"].max_zoom == 9


def test_stopped_series_is_flagged_and_missing_layers_are_not_offered():
    layers = {layer.id: layer for layer in catalog.parse_capabilities(CAPABILITIES, date(2026, 10, 23))}
    assert "01-09-2025" in layers["ocean-wind"].notice
    assert "rain" not in layers  # ausente en estas capacidades: no se ofrece una capa sin teselas


class DownGibs:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        raise httpx.ConnectError("sin red")


def test_unreachable_gibs_falls_back_without_dates(monkeypatch):
    monkeypatch.setattr(catalog, "_cache", {})
    monkeypatch.setattr(catalog.httpx, "AsyncClient", DownGibs)
    result = asyncio.run(catalog.map_layers())
    assert result.capabilities_read_at is None and result.layers
    assert all(layer.latest_date is None and "sin verificar" in layer.notice for layer in result.layers)


class GibsWithMissingDefault(DownGibs):
    """Capacidades sintéticas; las teselas del 01-09-2025 de viento no existen (como en GIBS real), el resto sí."""

    async def get(self, url, *args, **kwargs):
        request = httpx.Request("GET", url)
        if url == catalog.CAPABILITIES_URL:
            return httpx.Response(200, content=CAPABILITIES, request=request)
        status = 404 if "AMSRU_L3_Ocean_Wind_Speed_Daily/default/2025-09-01" in url else 200
        return httpx.Response(status, content=b"png", request=request)


def test_declared_date_without_tiles_steps_back(monkeypatch):
    monkeypatch.setattr(catalog, "_cache", {})
    monkeypatch.setattr(catalog.httpx, "AsyncClient", GibsWithMissingDefault)
    layers = {layer.id: layer for layer in asyncio.run(catalog.map_layers()).layers}
    wind = layers["ocean-wind"]
    assert wind.latest_date == date(2025, 8, 31)
    assert "no tiene teselas" in wind.notice and "Serie detenida" in wind.notice
    assert layers["sst"].latest_date == date(2026, 10, 22) and layers["sst"].notice is None


def test_endpoint_serves_cached_catalog(monkeypatch):
    class OkGibs(DownGibs):
        async def get(self, url, *args, **kwargs):
            content = CAPABILITIES if url == catalog.CAPABILITIES_URL else b"png"
            return httpx.Response(200, content=content, request=httpx.Request("GET", url))

    monkeypatch.setattr(catalog, "_cache", {})
    monkeypatch.setattr(catalog.httpx, "AsyncClient", OkGibs)
    body = TestClient(app).get("/api/v1/map/layers").json()
    assert {layer["id"] for layer in body["layers"]} == {"sst", "ocean-wind", "true-color"}
    assert body["capabilities_read_at"] is not None and "no entran" in body["note"]
