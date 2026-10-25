"""Spatial intersection queries against allow-listed official Peruvian ArcGIS layers."""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from shapely.geometry import shape

from ...core.config import Settings, get_settings
from ...geospatial.geometry import GeometryValidationError, inspect_geometry
from ...schemas.analysis import Provenance
from ...schemas.data_sources import (
    TerritorialFeature,
    TerritorialQueryRequest,
    TerritorialQueryResponse,
    TerritorialSourceResult,
)
from ..cache import RawPayloadCache

TIMEOUT = httpx.Timeout(connect=20, read=45, write=20, pool=20)
CULTURA_CACHE_TTL = timedelta(days=7)


class TerritoryConnectorError(RuntimeError):
    pass


@dataclass(frozen=True)
class OfficialLayer:
    source_id: str
    organization: str
    dataset: str
    base_url: str
    layer_ids: tuple[int, ...]
    coverage: str
    scale_or_resolution: str
    license: str
    limitations: tuple[str, ...] = ()
    unavailable_reason: str | None = None


PUBLIC_LICENSE_NOTE = (
    "Consulta pública con atribución a la entidad; el servicio no publica una licencia explícita de reutilización "
    "en sus metadatos REST. Confirmar condiciones antes de redistribuir datos derivados."
)

LAYERS: dict[str, OfficialLayer] = {
    "cenepred-flood-risk": OfficialLayer(
        "cenepred-flood-risk", "CENEPRED · SIGRID",
        "Escenario de riesgo por inundaciones ante lluvias intensas/FEN",
        "https://sigrid.cenepred.gob.pe/arcgis/rest/services/FEN/ER_NINO2027_BD/MapServer", (4,),
        "Perú; polígonos distritales del escenario El Niño actualizado con Informe Técnico 69-2026 de SENAMHI",
        "Escala no declarada; fuente EPSG:32718 y respuesta reproyectada a EPSG:4326", PUBLIC_LICENSE_NOTE,
        ("Es un escenario prospectivo de riesgo, no un inventario exhaustivo ni una probabilidad predial.",),
    ),
    "cenepred-mass-movement-risk": OfficialLayer(
        "cenepred-mass-movement-risk", "CENEPRED · SIGRID",
        "Escenario de riesgo por movimientos en masa ante lluvias intensas/FEN",
        "https://sigrid.cenepred.gob.pe/arcgis/rest/services/FEN/ER_NINO2027_BD/MapServer", (5,),
        "Perú; polígonos distritales del escenario El Niño actualizado con Informe Técnico 69-2026 de SENAMHI",
        "Escala no declarada; fuente EPSG:32718 y respuesta reproyectada a EPSG:4326", PUBLIC_LICENSE_NOTE,
        ("No reemplaza estudios geotécnicos ni cartografía de detalle de INGEMMET.",),
    ),
    "sernanp-anp": OfficialLayer(
        "sernanp-anp", "SERNANP", "Áreas Naturales Protegidas establecidas",
        "https://geoservicios.sernanp.gob.pe/arcgis/rest/services/servicios_ogc/peru_sernanp_0102/MapServer", (0, 1, 2, 3),
        "Perú; ANP nacionales definitivas/transitorias, regionales y privadas",
        "Vector EPSG:4326; escala de compilación no declarada", PUBLIC_LICENSE_NOTE,
        ("La superposición es una alerta de debida diligencia y no constituye opinión legal de compatibilidad.",),
    ),
    "osinergmin-grid": OfficialLayer(
        "osinergmin-grid", "Osinergmin · GISEM", "Líneas de transmisión y subestaciones en operación",
        "https://gisem.osinergmin.gob.pe/serverosih/rest/services/Electricidad/ELECTRICIDAD/MapServer", (15, 18),
        "Perú; infraestructura publicada por Osinergmin/MINEM/COES/empresas",
        "Vector EPSG:4326; escala de compilación no declarada", PUBLIC_LICENSE_NOTE,
        ("Una intersección no informa capacidad disponible, derecho de conexión ni estado en tiempo real.",),
    ),
    "cultura-archaeology": OfficialLayer(
        "cultura-archaeology", "Ministerio de Cultura · SIGDA",
        "Bienes inmuebles prehispánicos registrados referencialmente",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/registrado_v4/MapServer", (0,),
        "Perú; registros referenciales publicados por DSFL/Geomática",
        "Vector EPSG:4326; escala de levantamiento no declarada", PUBLIC_LICENSE_NOTE,
        ("La ausencia de intersección en SIGDA no prueba ausencia de patrimonio arqueológico.",),
    ),
    "cultura-archaeology-declared": OfficialLayer(
        "cultura-archaeology-declared", "Ministerio de Cultura · SIGDA",
        "Bienes inmuebles prehispánicos declarados",
        "https://sigda.cultura.gob.pe/sigda/rest/services/v_4/declarados_v4/MapServer", (0,),
        "Perú; bienes inmuebles prehispánicos declarados",
        "Vector EPSG:4326; escala de levantamiento no declarada", PUBLIC_LICENSE_NOTE,
        ("La consulta no sustituye un CIRA ni la evaluación formal del Ministerio de Cultura.",),
    ),
    "ingemmet-geohazards": OfficialLayer(
        "ingemmet-geohazards", "INGEMMET · GEOCATMIN", "Peligros geológicos",
        "https://geocatminapp.ingemmet.gob.pe/arcgis/rest/services", (), "Perú",
        "Pendiente de lectura segura de metadatos",
        "INGEMMET declara GEOCATMIN público y de uso gratuito; falta validar la capa concreta.",
        unavailable_reason="El host oficial presenta una cadena TLS no verificable; no se desactiva la validación TLS.",
    ),
    "senamhi-idesep": OfficialLayer(
        "senamhi-idesep", "SENAMHI · IDESEP", "Catálogo oficial WFS meteorológico y climático",
        "https://idesep.senamhi.gob.pe/geoserver/g_05_01/ows", (), "Perú; depende de cada feature type WFS",
        "Depende del producto; catálogo WFS 2.0 accesible", PUBLIC_LICENSE_NOTE,
        unavailable_reason="El catálogo está verificado, pero aún no se seleccionó una capa territorial de amenaza para este contrato.",
    ),
}


def _cache_max_age(source: OfficialLayer, default_hours: int) -> timedelta:
    """Use a courteous longer TTL for rate-sensitive Ministerio de Cultura SIGDA layers."""
    if source.source_id.startswith("cultura-"):
        return CULTURA_CACHE_TTL
    return timedelta(hours=default_hours)


def _esri_geometry(geojson: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    kind, coords = geojson["type"], geojson["coordinates"]
    sr = {"wkid": 4326}
    if kind == "Point":
        return "esriGeometryPoint", {"x": coords[0], "y": coords[1], "spatialReference": sr}
    if kind == "LineString":
        return "esriGeometryPolyline", {"paths": [coords], "spatialReference": sr}
    rings = [ring for polygon in coords for ring in polygon] if kind == "MultiPolygon" else coords
    return "esriGeometryPolygon", {"rings": rings, "spatialReference": sr}


def _safe_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[str(key)] = value[:1000] if isinstance(value, str) else value
    return cleaned


class TerritoryConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "territory")

    async def _layer_query(self, source: OfficialLayer, layer_id: int, geometry_type: str, geometry: dict[str, Any]):
        descriptor = {"source": source.source_id, "layer": layer_id, "type": geometry_type, "geometry": geometry, "v": 1}
        cache_key = self.cache.request_key(descriptor)
        cached = self.cache.get(cache_key, max_age=_cache_max_age(source, self.settings.cache_ttl_hours))
        if cached:
            return json.loads(cached.content), cached.downloaded_at, Provenance.CACHED
        endpoint = f"{source.base_url}/{layer_id}/query"
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or parsed.hostname is None:
            raise TerritoryConnectorError("La capa territorial no usa un endpoint HTTPS válido.")
        form = {
            "f": "json", "where": "1=1", "geometry": json.dumps(geometry, separators=(",", ":")),
            "geometryType": geometry_type, "inSR": "4326", "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "false",
            "resultRecordCount": "100",
        }
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=False) as client:
            response = await client.post(endpoint, data=form)
            response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise TerritoryConnectorError(str(payload["error"].get("message", "ArcGIS devolvió un error")))
        raw = self.cache.put(cache_key, response.content, suffix=".json")
        return payload, raw.downloaded_at, Provenance.REAL

    async def _source_query(self, source: OfficialLayer, geometry_type: str, geometry: dict[str, Any]):
        limitations = [*source.limitations,
            "Cero intersecciones significa solo que el servicio no devolvió objetos; no demuestra ausencia de riesgo o restricción."]
        common = dict(source_id=source.source_id, organization=source.organization, dataset=source.dataset,
            source_url=source.base_url, crs="EPSG:4326 en la solicitud", coverage=source.coverage,
            scale_or_resolution=source.scale_or_resolution, license=source.license)
        if source.unavailable_reason:
            return TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                limitations=[source.unavailable_reason, *limitations], **common)
        try:
            payloads = await asyncio.gather(
                *(self._layer_query(source, layer_id, geometry_type, geometry) for layer_id in source.layer_ids))
        except (httpx.HTTPError, ValueError, TerritoryConnectorError) as exc:
            return TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                limitations=[f"El servicio oficial no respondió con datos utilizables: {exc}", *limitations], **common)
        features, timestamps, provenances = [], [], []
        exceeded = False
        for layer_id, (payload, downloaded_at, provenance) in zip(source.layer_ids, payloads, strict=True):
            timestamps.append(downloaded_at); provenances.append(provenance)
            exceeded = exceeded or bool(payload.get("exceededTransferLimit"))
            layer_name = payload.get("name") or f"layer-{layer_id}"
            for feature in payload.get("features", []):
                features.append(TerritorialFeature(layer_id=layer_id, layer_name=str(layer_name),
                    attributes=_safe_attributes(feature.get("attributes", {}))))
        if exceeded:
            limitations.append("La respuesta superó 100 objetos; el detalle se truncó y no es un conteo exhaustivo.")
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features,
            provenance=Provenance.CACHED if provenances and all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
            downloaded_at=max(timestamps).astimezone(timezone.utc) if timestamps else None,
            limitations=limitations, **common)

    async def query(self, request: TerritorialQueryRequest) -> TerritorialQueryResponse:
        try:
            inspected = inspect_geometry(request.geometry)
            shape(request.geometry)
        except (GeometryValidationError, ValueError) as exc:
            raise TerritoryConnectorError(str(exc)) from exc
        geometry_type, geometry = _esri_geometry(request.geometry)
        source_ids = request.source_ids or list(LAYERS)
        unknown = sorted(set(source_ids) - set(LAYERS))
        if unknown:
            raise TerritoryConnectorError(f"Fuentes territoriales desconocidas: {', '.join(unknown)}")
        sources = await asyncio.gather(*(self._source_query(LAYERS[item], geometry_type, geometry) for item in source_ids))
        return TerritorialQueryResponse(generated_at=datetime.now(timezone.utc), geometry_type=inspected.geometry_type,
            sources=list(sources), note="Intersecciones WGS84 contra servicios oficiales; una respuesta vacía no prueba ausencia de amenaza o restricción.")
