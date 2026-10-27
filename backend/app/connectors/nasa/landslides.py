"""Deslizamientos de NASA (Earthdata GIS, carpeta `Landslides`): tres fuentes para cruzar con CENEPRED.

- Susceptibilidad global (Stanley y Kirschbaum 2017, Natural Hazards 87:145–164): ráster de 30″ (~1 km) con clases
  1–5 = Very Low … Very High, cortes difusos 0.11 / 0.49 / 0.67 / 0.75. El servicio devuelve 0 en agua, en el
  océano y en llanos desérticos (verificado el 27-oct-2026 en el Titicaca, frente a Lima y en el desierto de Ica);
  el artículo no define ese 0, así que se trata como «sin clase», nunca como susceptibilidad baja. Nodata = 127.
- LHASA 2 del día (`LHASA_Hazard_Today`): probabilidad de deslizamiento estimada por aprendizaje automático con lluvia
  GPM, humedad del suelo y factores del terreno, a 30″. Flotante de 0 a 1; nodata −9999 (sin valor en Lima, Arequipa
  o Iquitos el 27-oct-2026). NASA no publica umbrales para estas probabilidades ni la fecha del ráster en el servicio:
  se informa la hora de consulta y el valor, sin clasificarlo.
- COOLR (Cooperative Open Online Landslide Repository): reportes de deslizamientos ocurridos (Global Landslide Catalog
  de NASA y Landslide Reporter). En el Perú, 80 reportes entre 1974 y 2020, con precisión de ubicación de 1 a 250 km.

Las dos capas ráster se leen con `getSamples` en los mismos puntos que la susceptibilidad de CENEPRED.
"""

import json
from datetime import timedelta, timezone
from typing import Any

import httpx

from ...core.config import Settings, get_settings
from ...geospatial.sampling import esri_polygon, sample_points
from ...schemas.analysis import Provenance
from ...schemas.data_sources import TerritorialFeature, TerritorialSourceResult
from ..cache import RawPayloadCache

BASE = "https://gis.earthdata.nasa.gov/portal/rest/services/Landslides"
SUSCEPTIBILITY_URL = f"{BASE}/Global_Landslide_Susceptibility/ImageServer"
NOWCAST_URL = f"{BASE}/LHASA_Hazard_Today/ImageServer"
COOLR_URL = f"{BASE}/COOLR_Reports_Points/FeatureServer/0"
TIMEOUT = httpx.Timeout(connect=20, read=60, write=20, pool=20)
SUSCEPTIBILITY_TTL = timedelta(days=30)   # mapa estático
NOWCAST_TTL = timedelta(hours=3)          # NASA lo actualiza dos veces al día
COOLR_TTL = timedelta(days=7)
SUSCEPTIBILITY_NODATA = 127
NOWCAST_NODATA = -9999
LICENSE = "Datos de NASA de libre uso; citar el producto y, en COOLR, la fuente de cada reporte."

SUSCEPTIBILITY_LEVELS = {1: "Muy baja", 2: "Baja", 3: "Moderada", 4: "Alta", 5: "Muy alta"}
CATEGORIES = {"landslide": "deslizamiento", "mudslide": "flujo de lodo", "debris_flow": "flujo de detritos", "rock_fall": "caída de rocas",
              "riverbank_collapse": "colapso de ribera", "complex": "movimiento complejo", "earth_flow": "flujo de tierra",
              "translational_slide": "deslizamiento traslacional", "rotational_slide": "deslizamiento rotacional", "topple": "volcamiento",
              "creep": "reptación", "lahar": "lahar", "snow_avalanche": "avalancha de nieve"}
TRIGGERS = {"downpour": "lluvia intensa", "rain": "lluvia", "continuous_rain": "lluvia continua", "monsoon": "monzón", "earthquake": "sismo",
            "construction": "obra", "mining": "minería", "flooding": "inundación", "snowfall_snowmelt": "deshielo", "freeze_thaw": "congelamiento",
            "unknown": "", "other": ""}
COOLR_FIELDS = "event_date,event_title,location_description,landslide_category,landslide_trigger,fatality_count,location_accuracy,event_import_source,source_name,source_link"


def magnitude(probability: float) -> str:
    """Orden de magnitud de una probabilidad LHASA; describe el valor, no es un umbral de alerta."""
    if probability < 0.001:
        return "menor que 0.001"
    if probability < 0.01:
        return "entre 0.001 y 0.01"
    if probability < 0.1:
        return "entre 0.01 y 0.1"
    return "0.1 o más"


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class NasaLandslidesConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "nasa-landslides")

    async def _post(self, url: str, form: dict[str, str], ttl: timedelta):
        key = self.cache.request_key({"url": url, "form": form, "v": 1})
        cached = self.cache.get(key, max_age=ttl)
        if cached:
            return json.loads(cached.content), Provenance.CACHED, cached.downloaded_at
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as client:
            response = await client.post(url, data={"f": "json", **form})
            response.raise_for_status()
            payload = response.json()
        if payload.get("error"):
            raise httpx.HTTPError(str(payload["error"].get("message", "ArcGIS devolvió un error")))
        stored = self.cache.put(key, response.content, suffix=".json")
        return payload, Provenance.REAL, stored.downloaded_at

    async def _samples(self, url: str, points: list[tuple[float, float]], ttl: timedelta):
        multipoint = {"points": [[lon, lat] for lon, lat in points], "spatialReference": {"wkid": 4326}}
        payload, provenance, stamp = await self._post(f"{url}/getSamples", {
            "geometry": json.dumps(multipoint, separators=(",", ":")), "geometryType": "esriGeometryMultipoint", "returnFirstValueOnly": "true"}, ttl)
        values: dict[int, float | None] = {}
        for sample in payload.get("samples", []):
            values[int(sample["locationId"])] = _number(sample.get("value"))
        return values, provenance, stamp

    @staticmethod
    def _unavailable(common: dict, exc: Exception, limitations: list[str]) -> TerritorialSourceResult:
        return TerritorialSourceResult(status="DATA_UNAVAILABLE", provenance=Provenance.UNAVAILABLE,
                                       limitations=[f"El servicio oficial no respondió con datos utilizables: {exc}", *limitations], **common)

    async def susceptibility(self, geometry: dict[str, Any], representative: tuple[float, float]) -> TerritorialSourceResult:
        points = sample_points(geometry, representative)
        common = dict(source_id="nasa-landslide-susceptibility", organization="NASA · Earthdata GIS",
                      dataset="Susceptibilidad global a deslizamientos (NASA, muestreo por puntos)", source_url=SUSCEPTIBILITY_URL,
                      crs="EPSG:4326", coverage="Global, 56°S a 72°N", scale_or_resolution="30″ (~1 km); clase leída en cada punto de muestreo", license=LICENSE)
        limitations = [f"Muestreo de {len(points)} punto(s) dentro del área, los mismos que CENEPRED: describe la distribución, no el área completa.",
                       "Mapa global heurístico (Stanley y Kirschbaum 2017): pendiente, geología, fallas, pérdida de bosque y vías. "
                       "Susceptibilidad no es probabilidad; a escala local manda el mapa nacional."]
        try:
            values, provenance, stamp = await self._samples(SUSCEPTIBILITY_URL, points, SUSCEPTIBILITY_TTL)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return self._unavailable(common, exc, limitations)
        features, unclassified = [], 0
        for index, (lon, lat) in enumerate(points):
            value = values.get(index)
            level = SUSCEPTIBILITY_LEVELS.get(int(value)) if value is not None and value != SUSCEPTIBILITY_NODATA else None
            if level is None:
                unclassified += 1
                continue
            features.append(TerritorialFeature(layer_id=0, layer_name="Global_Landslide_Susceptibility",
                                               attributes={"clase": int(value), "nivel": level, "lon": lon, "lat": lat}))
        if unclassified:
            limitations.insert(1, f"{unclassified} punto(s) sin clase (agua, océano o llano desértico según el servicio): no se cuentan como susceptibilidad baja.")
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features, provenance=provenance,
                                       downloaded_at=stamp.astimezone(timezone.utc), limitations=limitations, **common)

    async def nowcast(self, geometry: dict[str, Any], representative: tuple[float, float]) -> TerritorialSourceResult:
        points = sample_points(geometry, representative)
        common = dict(source_id="nasa-lhasa-nowcast", organization="NASA · Earthdata GIS",
                      dataset="LHASA 2 · probabilidad de deslizamiento del día (muestreo por puntos)", source_url=NOWCAST_URL,
                      crs="EPSG:4326", coverage="Global, 60°S a 60°N", scale_or_resolution="30″ (~1 km); dos actualizaciones al día según NASA", license=LICENSE)
        limitations = ["Estimación de un modelo de aprendizaje automático (lluvia GPM, humedad del suelo y terreno) para alerta temprana, no un mapa de amenaza local.",
                       "NASA no publica umbrales para estas probabilidades: los rangos son órdenes de magnitud, no niveles de alerta.",
                       "El servicio no informa la fecha del ráster: la fecha mostrada es la de consulta."]
        try:
            values, provenance, stamp = await self._samples(NOWCAST_URL, points, NOWCAST_TTL)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return self._unavailable(common, exc, limitations)
        features, missing = [], 0
        for index, (lon, lat) in enumerate(points):
            value = values.get(index)
            if value is None or value == NOWCAST_NODATA or not 0 <= value <= 1:
                missing += 1
                continue
            features.append(TerritorialFeature(layer_id=0, layer_name="LHASA_Hazard_Today",
                                               attributes={"probabilidad": value, "rango": magnitude(value), "lon": lon, "lat": lat}))
        if features:
            top = max(features, key=lambda f: f.attributes["probabilidad"]).attributes
            limitations.insert(0, f"Máximo en el área: {top['probabilidad']:.4f} en {top['lat']:.3f}, {top['lon']:.3f}.")
        if missing:
            limitations.insert(1 if features else 0, f"{missing} de {len(points)} punto(s) sin valor del servicio (nodata): no se leen como cero.")
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features, provenance=provenance,
                                       downloaded_at=stamp.astimezone(timezone.utc), limitations=limitations, **common)

    async def reports(self, geometry: dict[str, Any]) -> TerritorialSourceResult:
        common = dict(source_id="nasa-coolr-reports", organization="NASA · Earthdata GIS",
                      dataset="Deslizamientos reportados (NASA COOLR · Global Landslide Catalog)", source_url=COOLR_URL,
                      crs="EPSG:4326", coverage="Global; en el Perú, reportes de 1974 a 2020", scale_or_resolution="Puntos con precisión declarada de 1 a 250 km", license=LICENSE)
        limitations = ["Catálogo armado con noticias y reportes ciudadanos: registra lo que se publicó, no todos los deslizamientos ocurridos.",
                       "Cada punto lleva su precisión de ubicación; un reporte a 5–25 km puede corresponder a una quebrada vecina.",
                       "Cero reportes no prueba que no haya habido deslizamientos."]
        try:
            payload, provenance, stamp = await self._post(f"{COOLR_URL}/query", {
                "geometry": json.dumps(esri_polygon(geometry), separators=(",", ":")), "geometryType": "esriGeometryPolygon", "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects", "outFields": COOLR_FIELDS, "orderByFields": "event_date DESC", "returnGeometry": "false"}, COOLR_TTL)
        except (httpx.HTTPError, ValueError) as exc:
            return self._unavailable(common, exc, limitations)
        features = []
        for item in payload.get("features", []):
            a = item.get("attributes", {})
            category = str(a.get("landslide_category") or "")
            trigger = str(a.get("landslide_trigger") or "")
            features.append(TerritorialFeature(layer_id=0, layer_name="COOLR_Reports_Points", attributes={
                "titulo": a.get("event_title") or a.get("location_description") or "", "fecha": a.get("event_date"),
                "categoria": CATEGORIES.get(category, category.replace("_", " ")), "detonante": TRIGGERS.get(trigger, trigger.replace("_", " ")),
                "fallecidos": a.get("fatality_count"), "precision": a.get("location_accuracy") or "", "origen": a.get("event_import_source") or "",
                "enlace": a.get("source_link") or ""}))
        if payload.get("exceededTransferLimit"):
            limitations.insert(0, "La consulta superó el máximo de registros del servicio; se muestran los más recientes.")
        return TerritorialSourceResult(status="READY", intersection_count=len(features), features=features, provenance=provenance,
                                       downloaded_at=stamp.astimezone(timezone.utc), limitations=limitations, **common)
