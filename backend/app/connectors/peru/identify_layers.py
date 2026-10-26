"""Capas oficiales que no admiten consulta por área y se leen con la operación `identify` de ArcGIS.

- CENEPRED · susceptibilidad por inundaciones y a movimientos en masa (capas ráster 1 y 2 del servicio FEN): se
  muestrea el nivel en una grilla de puntos dentro del área. Códigos 1–5 = Muy Bajo … Muy Alto según la leyenda del
  servicio, verificado el 26-oct-2026 en Bajo Piura (inundación 5) y Chosica (movimientos en masa 4).
- INGEMMET · mapas de peligro volcánico (Misti, Ticsani, Ubinas, Sabancaya, Tutupaca): `identify` con el polígono del
  área, solo en los mapas cuya extensión lo toca. El servidor no envía su certificado intermedio (Sectigo OV R36);
  se agrega ese intermedio a certifi, sin desactivar la validación, y la raíz sigue siendo la pública de certifi.
"""

import json
import ssl
from datetime import timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import certifi
import httpx
from pyproj import Transformer
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import box, shape
from shapely.prepared import prep

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ...schemas.data_sources import TerritorialFeature, TerritorialSourceResult
from ..cache import RawPayloadCache
from .territory import PUBLIC_LICENSE_NOTE

TIMEOUT = httpx.Timeout(connect=20, read=60, write=20, pool=20)
CACHE_TTL = timedelta(days=7)
SAMPLE_GRID = 4          # 4 × 4 puntos sobre la caja del área, más el punto representativo
MAX_VERTICES = 200
CERT_DIR = Path(__file__).parent / "certs"

CENEPRED_FEN = "https://sigrid.cenepred.gob.pe/arcgis/rest/services/FEN/ER_NINO2027_BD/MapServer"
CENEPRED_LEVELS = {"1": "Muy bajo", "2": "Bajo", "3": "Medio", "4": "Alto", "5": "Muy alto"}
CENEPRED_LAYERS = {1: "Susceptibilidad por inundaciones", 2: "Susceptibilidad a movimientos en masa"}

INGEMMET_BASE = "https://geocatminapp.ingemmet.gob.pe/arcgis/rest/services/INTRANET"
# Solo capas de peligro (zonas, lahares, caída de ceniza); la infraestructura de cada mapa no se consulta.
VOLCANIC_MAPS: dict[str, tuple[str, dict[int, str]]] = {
    "Misti": ("SERV_Mapa_Peligros_Misti", {0: "Peligro bajo", 1: "Peligro moderado", 2: "Peligro alto"}),
    "Ticsani": ("Serv_Mapa_Peligros_Ticsani", {18: "Peligro bajo", 19: "Peligro moderado", 20: "Peligro alto"}),
    "Ubinas": ("SERV_MAPA_PELIGRO_UBINAS_2020", {9: "Zona de peligro", 5: "Lahares", 10: "Caída de ceniza moderada", 11: "Caída de ceniza moderada a grande"}),
    "Sabancaya": ("SERV_Mapa_Peligros_Sabancaya", {21: "Peligro proximal alto", 22: "Peligro proximal moderado", 23: "Peligro proximal bajo",
                                                    25: "Caída de ceniza alto", 26: "Caída de ceniza moderado", 27: "Caída de ceniza bajo",
                                                    29: "Lahares alto", 30: "Lahares moderado", 31: "Lahares bajo"}),
    "Tutupaca": ("SERV_PELIGROS_TUTUPACA", {11: "Peligro alto", 12: "Peligro moderado", 13: "Peligro bajo", 15: "Lahares alto",
                                             16: "Lahares moderado", 17: "Lahares bajo", 18: "Caída de ceniza"}),
}
UTM19S_TO_WGS84 = Transformer.from_crs("EPSG:32719", "EPSG:4326", always_xy=True)


@lru_cache(maxsize=1)
def _ingemmet_context() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=str(CERT_DIR / "sectigo-ov-r36.pem"))
    return context


def sample_points(geometry: dict[str, Any], representative: tuple[float, float]) -> list[tuple[float, float]]:
    """Punto representativo más una grilla regular dentro del área (longitud, latitud)."""
    area = shape(geometry)
    inside = prep(area)
    xmin, ymin, xmax, ymax = area.bounds
    points = [representative]
    for i in range(SAMPLE_GRID):
        for j in range(SAMPLE_GRID):
            x = xmin + (i + 0.5) * (xmax - xmin) / SAMPLE_GRID
            y = ymin + (j + 0.5) * (ymax - ymin) / SAMPLE_GRID
            if inside.contains(ShapelyPoint(x, y)):
                points.append((round(x, 5), round(y, 5)))
    return list(dict.fromkeys(points))


def _rings(geometry: dict[str, Any]) -> dict[str, Any]:
    area = shape(geometry)
    tolerance = 0.0005
    while sum(len(polygon.exterior.coords) for polygon in getattr(area, "geoms", [area])) > MAX_VERTICES and tolerance < 0.05:
        area = shape(geometry).simplify(tolerance, preserve_topology=True)
        tolerance *= 2
    polygons = getattr(area, "geoms", [area])
    # 5 decimales ≈ 1 m: suficiente para cruzar con mapas de peligro y mantiene corta la solicitud.
    return {"rings": [[[round(x, 5), round(y, 5)] for x, y in polygon.exterior.coords] for polygon in polygons], "spatialReference": {"wkid": 4326}}


class IdentifyLayersConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "identify")

    async def _identify(self, url: str, params: dict[str, str], *, verify: ssl.SSLContext | bool = True) -> tuple[dict, Provenance, Any]:
        key = self.cache.request_key({"url": url, "params": params, "v": 1})
        cached = self.cache.get(key, max_age=CACHE_TTL)
        if cached:
            return json.loads(cached.content), Provenance.CACHED, cached.downloaded_at
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, verify=verify) as client:
            # Un polígono en la URL supera el largo que acepta INGEMMET (404): va en el cuerpo, como admite ArcGIS.
            if params.get("geometryType") == "esriGeometryPolygon":
                response = await client.post(f"{url}/identify", data={"f": "json", **params})
            else:
                response = await client.get(f"{url}/identify", params={"f": "json", **params})
            response.raise_for_status()
            payload = response.json()
        if payload.get("error"):
            raise httpx.HTTPError(str(payload["error"].get("message", "ArcGIS devolvió un error")))
        stored = self.cache.put(key, response.content, suffix=".json")
        return payload, Provenance.REAL, stored.downloaded_at

    async def cenepred_susceptibility(self, geometry: dict[str, Any], representative: tuple[float, float]) -> TerritorialSourceResult:
        points = sample_points(geometry, representative)
        common = dict(source_id="cenepred-susceptibility", organization="CENEPRED · SIGRID", dataset="Susceptibilidad por inundaciones y a movimientos en masa (muestreo por puntos)",
                      source_url=CENEPRED_FEN, crs="EPSG:4326 en la solicitud", coverage="Perú; escenario El Niño, capas ráster 1 y 2",
                      scale_or_resolution="Ráster; nivel leído en cada punto de muestreo", license=PUBLIC_LICENSE_NOTE)
        limitations = [f"Muestreo de {len(points)} punto(s) dentro del área: describe la distribución, no el área completa.",
                       "Niveles 1–5 = muy bajo a muy alto según la leyenda del servicio; susceptibilidad no es probabilidad de ocurrencia."]
        try:
            responses = []
            for lon, lat in points:   # uno a la vez: el servidor de CENEPRED es compartido con los pilotos
                responses.append(await self._identify(CENEPRED_FEN, {
                    "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": "4326", "layers": "all:1,2", "tolerance": "0",
                    "mapExtent": f"{lon - 0.05},{lat - 0.05},{lon + 0.05},{lat + 0.05}", "imageDisplay": "400,400,96", "returnGeometry": "false"}))
        except (httpx.HTTPError, ValueError) as exc:
            return TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                                           limitations=[f"El servicio oficial no respondió con datos utilizables: {exc}", *limitations], **common)
        features = []
        for (lon, lat), (payload, _, _) in zip(points, responses, strict=True):
            for item in payload.get("results", []):
                level = CENEPRED_LEVELS.get(str(item.get("attributes", {}).get("Pixel Value")))
                if level and item.get("layerId") in CENEPRED_LAYERS:
                    features.append(TerritorialFeature(layer_id=item["layerId"], layer_name=CENEPRED_LAYERS[item["layerId"]],
                                                       attributes={"capa": CENEPRED_LAYERS[item["layerId"]], "nivel": level, "lon": lon, "lat": lat}))
        provenances = [provenance for _, provenance, _ in responses]
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features,
                                       provenance=Provenance.CACHED if all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
                                       downloaded_at=max(stamp for _, _, stamp in responses).astimezone(timezone.utc), limitations=limitations, **common)

    async def volcanic_hazards(self, geometry: dict[str, Any]) -> TerritorialSourceResult:
        area = shape(geometry)
        common = dict(source_id="ingemmet-volcanic-hazards", organization="INGEMMET · GEOCATMIN", dataset="Mapas de peligro volcánico (Misti, Ticsani, Ubinas, Sabancaya, Tutupaca)",
                      source_url=INGEMMET_BASE, crs="EPSG:4326 en la solicitud; mapas en EPSG:32719", coverage="Volcanes activos del sur del Perú con mapa publicado",
                      scale_or_resolution="Vector; escala de cada mapa de peligro", license="INGEMMET declara GEOCATMIN público y de uso gratuito; citar la fuente.")
        limitations = ["Un área fuera de los cinco mapas publicados no queda libre de peligro volcánico: solo no tiene mapa consultable.",
                       "Las zonas de peligro describen escenarios eruptivos del mapa; no son pronóstico de actividad."]
        features, provenances, stamps, consulted = [], [], [], []
        try:
            for volcano, (service, layers) in VOLCANIC_MAPS.items():
                extent = await self._extent(service)
                if extent is None or not extent.intersects(area):
                    continue
                consulted.append(volcano)
                xmin, ymin, xmax, ymax = area.bounds
                payload, provenance, stamp = await self._identify(f"{INGEMMET_BASE}/{service}/MapServer", {
                    "geometry": json.dumps(_rings(geometry), separators=(",", ":")), "geometryType": "esriGeometryPolygon", "sr": "4326",
                    "layers": "all:" + ",".join(map(str, layers)), "tolerance": "0", "mapExtent": f"{xmin},{ymin},{xmax},{ymax}",
                    "imageDisplay": "800,600,96", "returnGeometry": "false"}, verify=_ingemmet_context())
                provenances.append(provenance)
                stamps.append(stamp)
                for item in payload.get("results", []):
                    label = layers.get(item.get("layerId"))
                    if label:
                        attributes = item.get("attributes", {})
                        description = next((str(v) for k, v in attributes.items() if k.lower().startswith("descrip") and v not in (None, "", "Null")), "")
                        features.append(TerritorialFeature(layer_id=item["layerId"], layer_name=label,
                                                           attributes={"volcan": volcano, "zona": label, "descripcion": description[:300]}))
        except (httpx.HTTPError, ValueError, ssl.SSLError) as exc:
            return TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                                           limitations=[f"El servicio oficial no respondió con datos utilizables: {exc}", *limitations], **common)
        limitations.insert(0, f"Mapas que cubren el área: {', '.join(consulted)}." if consulted else "Ningún mapa de peligro volcánico publicado cubre el área.")
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features,
                                       provenance=Provenance.CACHED if provenances and all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
                                       downloaded_at=max(stamps).astimezone(timezone.utc) if stamps else None, limitations=limitations, **common)

    async def _extent(self, service: str):
        key = self.cache.request_key({"extent": service, "v": 1})
        cached = self.cache.get(key, max_age=timedelta(days=30))
        if cached:
            meta = json.loads(cached.content)
        else:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, verify=_ingemmet_context()) as client:
                response = await client.get(f"{INGEMMET_BASE}/{service}/MapServer", params={"f": "json"})
                response.raise_for_status()
                meta = response.json()
            self.cache.put(key, response.content, suffix=".json")
        extent = meta.get("fullExtent") or {}
        if extent.get("spatialReference", {}).get("wkid") not in (32719, 32719.0):
            return None
        west, south = UTM19S_TO_WGS84.transform(extent["xmin"], extent["ymin"])
        east, north = UTM19S_TO_WGS84.transform(extent["xmax"], extent["ymax"])
        return box(west, south, east, north)

