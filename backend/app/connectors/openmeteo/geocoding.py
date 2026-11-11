"""Búsqueda de lugares del mundo por nombre (Open-Meteo Geocoding API, sobre GeoNames).

Solo convierte un nombre en coordenadas para ubicar un sitio; no aporta datos al análisis. El uso gratuito de
Open-Meteo es no comercial, igual que su API de caudales (ADR-042). Verificado el 10-nov-2026.
"""

from datetime import datetime, timedelta
from typing import Any

import httpx

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ..cache import RawPayloadCache
from ..http_json import cached_json

API = "https://geocoding-api.open-meteo.com/v1/search"
SOURCE = "Open-Meteo Geocoding API (GeoNames)"
MAX_AGE = timedelta(days=30)
MAX_RESULTS = 6


def parse_places(payload: Any) -> list[dict[str, Any]]:
    out = []
    for item in (payload or {}).get("results") or []:
        if not isinstance(item.get("latitude"), (int, float)) or not isinstance(item.get("longitude"), (int, float)) or not item.get("name"):
            continue
        detail = ", ".join(dict.fromkeys(str(part) for part in (item.get("admin1"), item.get("country")) if part and part != item["name"]))
        out.append({"name": str(item["name"]), "detail": detail, "country_code": item.get("country_code"), "latitude": float(item["latitude"]),
                    "longitude": float(item["longitude"]), "population": item.get("population") if isinstance(item.get("population"), int) else None})
    return out


class GeocodingConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "openmeteo-geocoding")

    async def search(self, query: str) -> tuple[list[dict[str, Any]], Provenance, datetime, str | None]:
        payload, provenance, stamp, stale = await cached_json(
            self.cache, API, {"name": query, "count": str(MAX_RESULTS), "language": "es", "format": "json"}, max_age=MAX_AGE, transport=self.transport)
        return parse_places(payload), provenance, stamp, stale
