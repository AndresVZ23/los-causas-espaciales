"""Catálogo curado de capas visuales NASA GIBS, con fechas, zoom y leyenda leídos de las capacidades WMTS oficiales.

La lista es fija (qué capas ofrece la consola y cómo se llaman); fechas, nivel máximo y leyenda salen de GIBS y se
guardan en memoria unas horas. Si GIBS no responde, se sirve la lista sin fechas y la consola pide la fecha por defecto.
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

from ..schemas.map_layers import MapLayer, MapLayersResponse

CAPABILITIES_URL = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml"
TILE_ROOT = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
TIMEOUT_SECONDS = 60
CACHE_HOURS = 6
STALE_AFTER_DAYS = 30  # una serie cuyo último dato tiene más de un mes se avisa como detenida
NS = {"w": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1", "xlink": "http://www.w3.org/1999/xlink"}


@dataclass(frozen=True)
class CuratedLayer:
    id: str
    gibs_id: str
    label: str
    group: str
    description: str


CURATED = [
    CuratedLayer("true-color", "MODIS_Terra_CorrectedReflectance_TrueColor", "Color real del día", "Imagen",
                 "Imagen MODIS Terra del día: nubes, polvo, nieve y estado del terreno."),
    CuratedLayer("sst", "GHRSST_L4_MUR_Sea_Surface_Temperature", "Temperatura del mar", "Océano",
                 "Temperatura superficial del mar, análisis diario multisensor MUR (GHRSST L4)."),
    CuratedLayer("sst-anomaly", "GHRSST_L4_MUR_Sea_Surface_Temperature_Anomalies", "Anomalía de temperatura del mar", "Océano",
                 "Diferencia frente al promedio del mismo día: muestra el calentamiento costero de tipo El Niño."),
    CuratedLayer("ocean-wind", "AMSRU_L3_Ocean_Wind_Speed_Daily", "Viento sobre el mar", "Océano",
                 "Velocidad del viento sobre el océano (AMSR2). No cubre tierra firme."),
    CuratedLayer("rain", "IMERG_Precipitation_Rate", "Lluvia (GPM IMERG)", "Atmósfera",
                 "Tasa de precipitación satelital GPM IMERG; la misma fuente del contraste de extremos."),
    CuratedLayer("land-temp", "MODIS_Terra_L3_Land_Surface_Temp_Daily_Day", "Temperatura de la superficie (día)", "Tierra",
                 "Temperatura de la superficie terrestre de día (MODIS Terra); no es la temperatura del aire."),
    CuratedLayer("ndvi", "MODIS_Terra_L3_NDVI_16Day", "Vegetación (NDVI)", "Tierra",
                 "Índice de vegetación MODIS, compuesto de 16 días."),
    CuratedLayer("fires", "VIIRS_NOAA20_Thermal_Anomalies_375m_All", "Focos de calor (VIIRS)", "Tierra",
                 "Focos de calor detectados por VIIRS (NOAA-20) en un día: incendios, quemas y otras fuentes de calor; no todo foco es un incendio forestal."),
    CuratedLayer("soil-moisture", "SMAP_L4_Analyzed_Root_Zone_Soil_Moisture", "Humedad del suelo (SMAP)", "Tierra",
                 "Humedad de la zona de raíces, análisis SMAP L4 con modelo."),
]

_cache: dict[str, object] = {}


def _parse_dimension(layer: ET.Element) -> tuple[date | None, date | None, int | None]:
    """Primera y última fecha y paso en días a partir de los valores «inicio/fin/PnD» de la dimensión Time."""
    dimension = layer.find("w:Dimension", NS)
    if dimension is None:
        return None, None, None
    starts, ends, periods = [], [], []
    for value in dimension.findall("w:Value", NS):
        parts = (value.text or "").split("/")
        try:
            starts.append(date.fromisoformat(parts[0][:10]))
            ends.append(date.fromisoformat((parts[1] if len(parts) > 1 else parts[0])[:10]))
        except ValueError:
            continue
        if len(parts) > 2 and (match := re.fullmatch(r"P(\d+)D", parts[2])):
            periods.append(int(match.group(1)))
    default = dimension.find("w:Default", NS)
    latest = None
    if default is not None and default.text:
        try:
            latest = date.fromisoformat(default.text[:10])
        except ValueError:
            latest = None
    return (min(starts) if starts else None), (latest or (max(ends) if ends else None)), (min(periods) if periods else None)


def parse_capabilities(xml_bytes: bytes, today: date) -> list[MapLayer]:
    root = ET.fromstring(xml_bytes)
    found = {layer.find("ows:Identifier", NS).text: layer for layer in root.iter(f"{{{NS['w']}}}Layer")}
    layers = []
    for curated in CURATED:
        layer = found.get(curated.gibs_id)
        if layer is None:
            continue  # GIBS retiró la capa: no se ofrece en vez de mostrar teselas vacías
        matrix = layer.find("w:TileMatrixSetLink/w:TileMatrixSet", NS).text
        level = int(re.search(r"Level(\d+)", matrix).group(1))
        extension = "jpg" if (layer.find("w:Format", NS).text or "").endswith("jpeg") else "png"
        first, latest, period = _parse_dimension(layer)
        legends = [link.get(f"{{{NS['xlink']}}}href") for style in layer.findall("w:Style", NS) for link in style.findall("w:LegendURL", NS)]
        legend = next((url for url in legends if url and url.endswith("_H.svg")), None)
        notice = None
        if latest and (today - latest).days > STALE_AFTER_DAYS:
            notice = f"Serie detenida: el último dato publicado es del {latest:%d-%m-%Y}."
        layers.append(MapLayer(
            id=curated.id, label=curated.label, group=curated.group, description=curated.description, gibs_id=curated.gibs_id,
            tile_url=f"{TILE_ROOT}/{curated.gibs_id}/default/{{time}}/{matrix}/{{z}}/{{y}}/{{x}}.{extension}",
            max_zoom=level, latest_date=latest, first_date=first, period_days=period, legend_url=legend, notice=notice,
        ))
    return layers


def fallback_layers() -> list[MapLayer]:
    """Sin capacidades: se sirven las capas con la fecha «default» de GIBS y sin leyenda verificada."""
    return [MapLayer(
        id=c.id, label=c.label, group=c.group, description=c.description, gibs_id=c.gibs_id,
        tile_url=f"{TILE_ROOT}/{c.gibs_id}/default/{{time}}/GoogleMapsCompatible_Level6/{{z}}/{{y}}/{{x}}.png",
        max_zoom=6, latest_date=None, first_date=None, period_days=None, legend_url=None,
        notice="No se pudo leer el catálogo de GIBS: fecha y leyenda sin verificar.",
    ) for c in CURATED if c.id != "true-color"]


# Tesela de prueba z=2 que cubre el Perú (fila 2, columna 1 en GoogleMapsCompatible).
PROBE_TILE = {"z": "2", "y": "2", "x": "1"}
PROBE_STEPS = 6


async def verify_latest(client: httpx.AsyncClient, layer: MapLayer) -> MapLayer:
    """La fecha «Default» de GIBS a veces no tiene teselas (visto con AMSR2: 01-09-2025 da 404 y 31-08-2025 no).
    Se prueba una tesela sobre el Perú y se retrocede período a período hasta encontrar una publicada."""
    if layer.latest_date is None:
        return layer
    step = timedelta(days=layer.period_days or 1)
    for attempt in range(PROBE_STEPS):
        candidate = layer.latest_date - step * attempt
        url = layer.tile_url.replace("{time}", candidate.isoformat())
        for key, value in PROBE_TILE.items():
            url = url.replace(f"{{{key}}}", value)
        try:
            response = await client.get(url)
        except httpx.HTTPError:
            return layer  # sin red para verificar: se conserva la fecha declarada
        if response.status_code == 200:
            if attempt == 0:
                return layer
            note = f"GIBS declara el {layer.latest_date:%d-%m-%Y} pero esa fecha no tiene teselas; se muestra el {candidate:%d-%m-%Y}."
            return layer.model_copy(update={"latest_date": candidate, "notice": " ".join(filter(None, [layer.notice, note]))})
    return layer.model_copy(update={"notice": " ".join(filter(None, [layer.notice, "No se encontraron teselas recientes sobre el Perú."]))})


async def map_layers() -> MapLayersResponse:
    now = datetime.now(timezone.utc)
    cached = _cache.get("response")
    if isinstance(cached, MapLayersResponse) and cached.capabilities_read_at and now - cached.capabilities_read_at < timedelta(hours=CACHE_HOURS):
        return cached
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True, headers={"User-Agent": "LosCausasEspaciales/0.1"}) as client:
            response = await client.get(CAPABILITIES_URL)
            response.raise_for_status()
            parsed = await asyncio.to_thread(parse_capabilities, response.content, now.date())
            layers = list(await asyncio.gather(*(verify_latest(client, layer) for layer in parsed)))
    except (httpx.HTTPError, ET.ParseError, AttributeError):
        return MapLayersResponse(layers=fallback_layers(), capabilities_read_at=None)
    result = MapLayersResponse(layers=layers, capabilities_read_at=now)
    _cache["response"] = result
    return result
