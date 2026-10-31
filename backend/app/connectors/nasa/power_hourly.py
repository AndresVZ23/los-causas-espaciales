"""NASA POWER horario: viento a 10 y 50 m (MERRA-2) para estimar la energía eólica hora por hora.

La energía de una turbina depende del cubo del viento: una media diaria esconde las horas fuertes, por eso el piloto
eólico usa la serie horaria. Un año por consulta (~300 KB, ~3 s medido el 30-oct-2026 en Arequipa, API v2.10.3),
cuatro a la vez. Solo se piden años completos y cerrados: la caché no vence. El relleno -999 se descarta, no se
vuelve cero.
"""

import asyncio
import json
import weakref
from dataclasses import dataclass
from datetime import datetime

import httpx
import numpy as np

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ..cache import RawPayloadCache
from .power import PowerConnectorError

PARAMETERS = ("WS50M", "WS10M")
CONCURRENCY = 4
TIMEOUT = httpx.Timeout(connect=20, read=90, write=20, pool=60)
MIN_HOURS = 8760 * 0.9
SOURCE_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"


@dataclass
class HourlyWind:
    """Horas válidas por año (m/s): ambas alturas en las mismas horas para que la cizalladura sea comparable."""

    by_year: dict[int, tuple[np.ndarray, np.ndarray]]    # año → (WS50M, WS10M)
    provenance: Provenance
    downloaded_at: datetime
    version: str


_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _limit() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _semaphores:
        _semaphores[loop] = asyncio.Semaphore(CONCURRENCY)
    return _semaphores[loop]


def parse_year(payload: dict) -> tuple[np.ndarray, np.ndarray] | None:
    """Pares (50 m, 10 m) de las horas en que ambas alturas tienen dato; un año con menos del 90 % se omite."""
    parameters = payload.get("properties", {}).get("parameter", {})
    high, low = parameters.get("WS50M"), parameters.get("WS10M")
    if not isinstance(high, dict) or not isinstance(low, dict):
        raise PowerConnectorError("NASA POWER horario no devolvió WS50M y WS10M.")
    pairs = [(high[hour], low[hour]) for hour in high
             if isinstance(high[hour], (int, float)) and isinstance(low.get(hour), (int, float)) and 0 <= high[hour] < 100 and 0 <= low[hour] < 100]
    if len(pairs) < MIN_HOURS:
        return None
    values = np.array(pairs, dtype=np.float64)
    return values[:, 0], values[:, 1]


class PowerHourlyConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "power-hourly")

    async def wind(self, latitude: float, longitude: float, years: range) -> HourlyWind:
        stamps: list[datetime] = []
        provenances: list[Provenance] = []
        versions: set[str] = set()

        async def one(client: httpx.AsyncClient, year: int):
            params = {"parameters": ",".join(PARAMETERS), "community": "RE", "latitude": f"{latitude:.4f}", "longitude": f"{longitude:.4f}",
                      "start": f"{year}0101", "end": f"{year}1231", "format": "JSON", "time-standard": "UTC"}
            key = self.cache.request_key({"url": SOURCE_URL, "params": params, "v": 1})
            cached = self.cache.get(key, max_age=None)
            if cached:
                payload = json.loads(cached.content)
                provenances.append(Provenance.CACHED)
                stamps.append(cached.downloaded_at)
            else:
                async with _limit():
                    try:
                        response = await client.get(SOURCE_URL, params=params)
                        response.raise_for_status()
                        payload = response.json()
                    except (httpx.HTTPError, ValueError) as exc:
                        raise PowerConnectorError(f"NASA POWER horario falló en {year}: {exc}") from exc
                stored = self.cache.put(key, json.dumps(payload).encode(), suffix=".json")
                provenances.append(Provenance.REAL)
                stamps.append(stored.downloaded_at)
            versions.add(str(payload.get("header", {}).get("api", {}).get("version", "versión no informada")))
            return year, parse_year(payload)

        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=True) as client:
            results = await asyncio.gather(*(one(client, year) for year in years))
        by_year = {year: values for year, values in results if values is not None}
        if not by_year:
            raise PowerConnectorError("NASA POWER horario no devolvió ningún año con al menos 90 % de horas válidas.")
        return HourlyWind(by_year=by_year, provenance=Provenance.CACHED if all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
                          downloaded_at=max(stamps), version=", ".join(sorted(versions)))
