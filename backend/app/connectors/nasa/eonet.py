"""NASA EONET v3 (Earth Observatory Natural Event Tracker): eventos naturales abiertos, curados por NASA.

Sirve de segundo testigo de las alertas de GDACS y aporta eventos que GDACS no lista. EONET no asigna niveles de
alerta. Verificado el 10-nov-2026: `events?status=open` devuelve una geometría por fecha; se usa el último punto.
"""

from datetime import datetime, timedelta
from typing import Any

import httpx

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ..cache import RawPayloadCache
from ..http_json import cached_json

API = "https://eonet.gsfc.nasa.gov/api/v3/events"
SITE = "https://eonet.gsfc.nasa.gov"
MAX_AGE = timedelta(hours=1)
KINDS = {"severeStorms": ("storm", "Tormenta severa"), "wildfires": ("wildfire", "Incendio forestal"), "volcanoes": ("volcano", "Erupción volcánica"),
         "floods": ("flood", "Inundación"), "drought": ("drought", "Sequía"), "landslides": ("landslide", "Deslizamiento"),
         "earthquakes": ("earthquake", "Sismo")}


def parse_events(payload: Any) -> list[dict[str, Any]]:
    out = []
    for event in (payload or {}).get("events", []):
        kind = next((KINDS[item["id"]] for item in event.get("categories", []) if item.get("id") in KINDS), None)
        points = [item for item in event.get("geometry", []) if item.get("type") == "Point" and isinstance(item.get("coordinates"), list) and item.get("date")]
        if not kind or not points:
            continue
        try:
            first, last = (datetime.fromisoformat(str(item["date"]).replace("Z", "+00:00")).date() for item in (points[0], points[-1]))
        except ValueError:
            continue
        magnitude = points[-1].get("magnitudeValue")
        sources = event.get("sources") or []
        out.append({
            "id": f"eonet-{event.get('id')}", "kind": kind[0], "kind_label": kind[1], "name": " ".join(str(event.get("title") or kind[1]).split()),
            "started": first, "updated": last, "longitude": float(points[-1]["coordinates"][0]), "latitude": float(points[-1]["coordinates"][1]),
            "severity": f"{magnitude:g} {points[-1].get('magnitudeUnit') or ''}".strip() if isinstance(magnitude, (int, float)) else None,
            "url": (sources[0].get("url") if sources and sources[0].get("url") else None) or event.get("link") or SITE,
        })
    return out


class EonetConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "nasa-eonet")

    async def open_events(self, window_days: int) -> tuple[list[dict[str, Any]], Provenance, datetime, str | None]:
        # `days` acota a los eventos con actividad reciente; la vigencia de una hora mantiene la lista al día.
        payload, provenance, stamp, stale = await cached_json(
            self.cache, API, {"status": "open", "days": str(window_days)}, max_age=MAX_AGE, transport=self.transport)
        return parse_events(payload), provenance, stamp, stale
