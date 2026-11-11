"""GDACS (Global Disaster Alert and Coordination System, ONU y Comisión Europea): eventos con su nivel de alerta.

El nivel lo asigna GDACS: naranja y roja indican que el evento puede requerir, o probablemente requiera, asistencia
humanitaria internacional; verde, que no se espera. Aquí no se recalcula ni se reinterpreta. Verificado el 10-nov-2026:
`geteventlist/SEARCH` responde GeoJSON con `alertlevel`, `iscurrent` (texto «true»/«false»), fechas y un punto por evento.
"""

from datetime import date, datetime, timedelta
from typing import Any

import httpx

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ..cache import RawPayloadCache
from ..http_json import cached_json

API = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
SITE = "https://www.gdacs.org"
MAX_AGE = timedelta(hours=1)
ALL_TYPES = "EQ;TC;FL;VO;DR;WF"
# En el Perú se listan también las alertas verdes, pero solo de los tipos que la plataforma puede contrastar con sus datos.
PERU_TYPES = "TC;FL;VO;DR;WF"
KINDS = {"EQ": ("earthquake", "Sismo"), "TC": ("cyclone", "Ciclón tropical"), "FL": ("flood", "Inundación"),
         "VO": ("volcano", "Erupción volcánica"), "DR": ("drought", "Sequía"), "WF": ("wildfire", "Incendio forestal")}
LEVELS = {"red": "red", "orange": "orange", "green": "green"}


def _day(value: Any) -> date | None:
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def parse_events(payload: Any) -> list[dict[str, Any]]:
    """Eventos normalizados; se descarta el que no trae punto, tipo conocido, nivel o fechas (no se completa nada)."""
    out = []
    for feature in (payload or {}).get("features", []):
        properties, geometry = feature.get("properties") or {}, feature.get("geometry") or {}
        coordinates = geometry.get("coordinates")
        kind = KINDS.get(str(properties.get("eventtype")))
        level = LEVELS.get(str(properties.get("alertlevel", "")).lower())
        started, updated = _day(properties.get("fromdate")), _day(properties.get("todate"))
        if geometry.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) < 2 or not kind or not level or not started or not updated:
            continue
        url = properties.get("url")
        severity = " ".join(str((properties.get("severitydata") or {}).get("severitytext") or "").split())
        if severity.startswith("Magnitude 0"):      # así llega una inundación sin magnitud publicada: no es un dato
            severity = ""
        out.append({
            "id": f"gdacs-{properties.get('eventtype')}-{properties.get('eventid')}", "kind": kind[0], "kind_label": kind[1], "level": level,
            "name": " ".join(str(properties.get("name") or properties.get("eventname") or kind[1]).split()),
            "countries": [item.strip() for item in str(properties.get("country") or "").split(",") if item.strip()],
            "started": started, "updated": updated, "current": str(properties.get("iscurrent")).lower() == "true",
            "longitude": float(coordinates[0]), "latitude": float(coordinates[1]), "severity": severity or None,
            "url": url.get("report") if isinstance(url, dict) and url.get("report") else SITE,
        })
    return out


class GdacsConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "gdacs-events")

    async def _search(self, params: dict[str, str]):
        payload, provenance, stamp, stale = await cached_json(self.cache, API, params, max_age=MAX_AGE, transport=self.transport)
        return parse_events(payload), provenance, stamp, stale

    async def events(self, today: date, window_days: int) -> tuple[list[dict[str, Any]], Provenance, datetime, str | None]:
        """Alertas naranja y roja del mundo y todas las del Perú (tipos hidroclimáticos y volcánicos) en la ventana."""
        span = {"fromdate": (today - timedelta(days=window_days)).isoformat(), "todate": today.isoformat()}
        world, provenance, stamp, stale = await self._search({"alertlevel": "red;orange", "eventlist": ALL_TYPES, **span})
        peru, peru_provenance, peru_stamp, peru_stale = await self._search({"alertlevel": "red;orange;green", "eventlist": PERU_TYPES, "country": "Peru", **span})
        merged = {item["id"]: item for item in [*world, *peru]}
        both_cached = provenance == Provenance.CACHED and peru_provenance == Provenance.CACHED
        return list(merged.values()), Provenance.CACHED if both_cached or stale or peru_stale else Provenance.REAL, min(stamp, peru_stamp), stale or peru_stale
