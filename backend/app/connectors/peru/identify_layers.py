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
from shapely.geometry import box, shape

from ...core.config import Settings, get_settings
from ...geospatial.sampling import esri_polygon, sample_points
from ...schemas.analysis import Provenance
from ...schemas.data_sources import TerritorialFeature, TerritorialSourceResult
from ..cache import RawPayloadCache, stale_copy_note
from .territory import PUBLIC_LICENSE_NOTE

TIMEOUT = httpx.Timeout(connect=20, read=60, write=20, pool=20)
CACHE_TTL = timedelta(days=7)
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


def _stale(responses: list[tuple[dict, Provenance, Any, str | None]]) -> tuple[str | None, Any]:
    """Nota de «última copia válida» y la fecha que debe informarse: la de la copia más antigua si alguna respuesta lo es."""
    stale = [(stamp, reason) for _, _, stamp, reason in responses if reason]
    if not stale:
        return None, max(stamp for _, _, stamp, _ in responses)
    oldest = min(stamp for stamp, _ in stale)
    return stale_copy_note(stale[0][1], oldest), oldest


@lru_cache(maxsize=1)
def _ingemmet_context() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=str(CERT_DIR / "sectigo-ov-r36.pem"))
    return context


class IdentifyLayersConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "identify")

    async def _identify(self, url: str, params: dict[str, str], *, verify: ssl.SSLContext | bool = True,
                        offline: str | None = None) -> tuple[dict, Provenance, Any, str | None]:
        """Respuesta de `identify`, su procedencia, su fecha y, si viene de la última copia válida, el motivo.

        `offline` es el motivo de una falla ya vista en esta misma consulta: no se vuelve a llamar al servidor y se
        busca directamente la copia. Sin copia, la falla se propaga y la capa queda como no disponible.
        """
        key = self.cache.request_key({"url": url, "params": params, "v": 1})
        cached = self.cache.get(key, max_age=CACHE_TTL)
        if cached:
            return json.loads(cached.content), Provenance.CACHED, cached.downloaded_at, None
        try:
            if offline:
                raise httpx.HTTPError(offline)
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
        except (httpx.HTTPError, ValueError, ssl.SSLError) as exc:
            stale = self.cache.last_valid(key)
            if stale is None:
                raise
            return json.loads(stale.content), Provenance.CACHED, stale.downloaded_at, str(exc) or type(exc).__name__
        stored = self.cache.put(key, response.content, suffix=".json")
        return payload, Provenance.REAL, stored.downloaded_at, None

    async def cenepred_susceptibility(self, geometry: dict[str, Any], representative: tuple[float, float]) -> TerritorialSourceResult:
        points = sample_points(geometry, representative)
        common = dict(source_id="cenepred-susceptibility", organization="CENEPRED · SIGRID", dataset="Susceptibilidad por inundaciones y a movimientos en masa (muestreo por puntos)",
                      source_url=CENEPRED_FEN, crs="EPSG:4326 en la solicitud", coverage="Perú; escenario El Niño, capas ráster 1 y 2",
                      scale_or_resolution="Ráster; nivel leído en cada punto de muestreo", license=PUBLIC_LICENSE_NOTE)
        limitations = [f"Muestreo de {len(points)} punto(s) dentro del área: describe la distribución, no el área completa.",
                       "Niveles 1–5 = muy bajo a muy alto según la leyenda del servicio; susceptibilidad no es probabilidad de ocurrencia."]
        try:
            responses = []
            offline: str | None = None
            for lon, lat in points:   # uno a la vez: el servidor de CENEPRED es compartido con los pilotos
                response = await self._identify(CENEPRED_FEN, {
                    "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": "4326", "layers": "all:1,2", "tolerance": "0",
                    "mapExtent": f"{lon - 0.05},{lat - 0.05},{lon + 0.05},{lat + 0.05}", "imageDisplay": "400,400,96", "returnGeometry": "false"},
                    offline=offline)
                offline = offline or response[3]   # tras la primera falla no se insiste con el servidor en los demás puntos
                responses.append(response)
        except (httpx.HTTPError, ValueError) as exc:
            return TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                                           limitations=[f"El servicio oficial no respondió con datos utilizables: {exc}", *limitations], **common)
        features = []
        for (lon, lat), (payload, _, _, _) in zip(points, responses, strict=True):
            for item in payload.get("results", []):
                level = CENEPRED_LEVELS.get(str(item.get("attributes", {}).get("Pixel Value")))
                if level and item.get("layerId") in CENEPRED_LAYERS:
                    features.append(TerritorialFeature(layer_id=item["layerId"], layer_name=CENEPRED_LAYERS[item["layerId"]],
                                                       attributes={"capa": CENEPRED_LAYERS[item["layerId"]], "nivel": level, "lon": lon, "lat": lat}))
        provenances = [provenance for _, provenance, _, _ in responses]
        note, stamp = _stale(responses)
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features,
                                       provenance=Provenance.CACHED if note or all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
                                       downloaded_at=stamp.astimezone(timezone.utc), limitations=[*([note] if note else []), *limitations],
                                       stale_note=note, **common)

    async def volcanic_hazards(self, geometry: dict[str, Any]) -> TerritorialSourceResult:
        area = shape(geometry)
        common = dict(source_id="ingemmet-volcanic-hazards", organization="INGEMMET · GEOCATMIN", dataset="Mapas de peligro volcánico (Misti, Ticsani, Ubinas, Sabancaya, Tutupaca)",
                      source_url=INGEMMET_BASE, crs="EPSG:4326 en la solicitud; mapas en EPSG:32719", coverage="Volcanes activos del sur del Perú con mapa publicado",
                      scale_or_resolution="Vector; escala de cada mapa de peligro", license="INGEMMET declara GEOCATMIN público y de uso gratuito; citar la fuente.")
        limitations = ["Un área fuera de los cinco mapas publicados no queda libre de peligro volcánico: solo no tiene mapa consultable.",
                       "Las zonas de peligro describen escenarios eruptivos del mapa; no son pronóstico de actividad."]
        features, provenances, responses, consulted = [], [], [], []
        try:
            for volcano, (service, layers) in VOLCANIC_MAPS.items():
                extent = await self._extent(service)
                if extent is None or not extent.intersects(area):
                    continue
                consulted.append(volcano)
                xmin, ymin, xmax, ymax = area.bounds
                response = await self._identify(f"{INGEMMET_BASE}/{service}/MapServer", {
                    "geometry": json.dumps(esri_polygon(geometry), separators=(",", ":")), "geometryType": "esriGeometryPolygon", "sr": "4326",
                    "layers": "all:" + ",".join(map(str, layers)), "tolerance": "0", "mapExtent": f"{xmin},{ymin},{xmax},{ymax}",
                    "imageDisplay": "800,600,96", "returnGeometry": "false"}, verify=_ingemmet_context())
                payload, provenance = response[0], response[1]
                provenances.append(provenance)
                responses.append(response)
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
        note, stamp = _stale(responses) if responses else (None, None)
        if note:
            limitations.insert(0, note)
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features,
                                       provenance=Provenance.CACHED if note or (provenances and all(p == Provenance.CACHED for p in provenances)) else Provenance.REAL,
                                       downloaded_at=stamp.astimezone(timezone.utc) if stamp else None, limitations=limitations, stale_note=note, **common)

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
