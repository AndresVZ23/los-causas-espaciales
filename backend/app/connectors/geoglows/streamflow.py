"""GEOGLOWS River Forecast System v2 (Group on Earth Observations, con ECMWF, NASA, NOAA y BYU): segunda opinión
del caudal medio anual, sobre una red de ríos y un modelo distintos de GloFAS. NASA SERVIR-Amazonía lo usa en alerta
temprana para el Perú. Datos con licencia CC BY 4.0 (registro de datos abiertos de AWS).

API pública sin cuenta (verificada el 10-nov-2026): `getriverid` devuelve un tramo de río cercano a un punto y
`annualaverages/{id}` el caudal medio de cada año desde 1940 (m³/s, ~3 KB, 8–12 s por consulta). No es una fuente
independiente del clima: igual que GloFAS, la simulación histórica se fuerza con ERA5. Lo que cambia es el modelo de
tránsito (RAPID) y la red de ríos (TDX-Hydro de la NGA, vectorial, ~7 millones de tramos).

Límite medido: `getriverid` no devuelve el tramo cuya línea pasa por el punto. En el río Tambo (El Fiscal), con el
punto exacto del cauce según OpenStreetMap, devuelve una quebrada con 0.00 m³/s; el cauce principal (73 m³/s)
aparece consultando a 2–4 km. Lo mismo en el Tambo alto y en el Majes. Regla declarada, que no mira a GloFAS: se
consulta una malla de 5 × 5 puntos cada 0.02° (±4.4 km) alrededor de la toma y se toma el tramo de mayor caudal
medio. Son hasta 25 búsquedas y una serie por tramo distinto (~1 minuto por punto nuevo), con pocas conexiones a la
vez porque el servicio corta las ráfagas; todo queda en caché.
"""

import asyncio
import json
import weakref
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx

from ...core.config import Settings, get_settings
from ...schemas.analysis import Observation, Provenance
from ..cache import RawPayloadCache

BASE = "https://geoglows.ecmwf.int/api/v2"
SOURCE = "GEOGLOWS v2 (GEO con ECMWF, NASA, NOAA y BYU)"
SEARCH_DEGREES = 0.02
SEARCH_STEPS = 2             # malla de (2 × 2 + 1)² = 25 puntos: ±0.04° ≈ ±4.4 km
SEARCH_OFFSETS = [(0, 0)] + [(i, j) for i in range(-SEARCH_STEPS, SEARCH_STEPS + 1) for j in range(-SEARCH_STEPS, SEARCH_STEPS + 1) if (i, j) != (0, 0)]
SEARCH_KM = SEARCH_DEGREES * SEARCH_STEPS * 111.2
ANNUAL_MAX_AGE = timedelta(days=30)
CONCURRENCY = 3              # con seis conexiones el servicio cortó la sesión (medido el 10-nov-2026)
ATTEMPTS = 3
RETRY_SECONDS = 3.0
TIMEOUT = httpx.Timeout(connect=20, read=60, write=20, pool=300)


class GeoglowsError(RuntimeError):
    pass


@dataclass
class RiverChoice:
    river_id: int                   # tramo elegido: el de mayor caudal medio entre los candidatos
    nearest_river_id: int           # tramo que devuelve el servicio para el punto pedido
    candidates: int                 # tramos distintos evaluados
    annual: list[Observation]       # caudal medio de cada año completo, m³/s
    nearest_mean: float | None      # caudal medio del tramo del punto pedido, para declarar si se cambió de tramo
    provenance: Provenance
    downloaded_at: datetime


_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _limit() -> asyncio.Semaphore:
    """Tope de conexiones simultáneas a GEOGLOWS para todo el proceso (por bucle de eventos)."""
    loop = asyncio.get_running_loop()
    if loop not in _semaphores:
        _semaphores[loop] = asyncio.Semaphore(CONCURRENCY)
    return _semaphores[loop]


def parse_annual(payload: dict, river_id: int) -> list[Observation]:
    """Medias anuales de los años cerrados; un valor ausente se omite, no se vuelve cero."""
    values, stamps = payload.get(str(river_id)), payload.get("datetime")
    if not isinstance(values, list) or not isinstance(stamps, list) or len(values) != len(stamps):
        raise GeoglowsError("GEOGLOWS devolvió las medias anuales con una estructura inesperada.")
    current = date.today().year
    out = []
    for stamp, value in zip(stamps, values):
        year = int(str(stamp)[:4])
        if isinstance(value, (int, float)) and value >= 0 and year < current:
            out.append(Observation(timestamp=date(year, 7, 1), value=float(value)))
    return out


def _mean(series: list[Observation]) -> float | None:
    return sum(item.value for item in series) / len(series) if series else None


class GeoglowsConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "geoglows")
        self._stamps: list[datetime] = []
        self._provenances: list[Provenance] = []

    async def river_near(self, latitude: float, longitude: float) -> RiverChoice:
        """El río de mayor caudal medio entre los que el servicio devuelve en la malla alrededor del punto."""
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=True) as client:
            found = await asyncio.gather(*(self._river_id(client, latitude + i * SEARCH_DEGREES, longitude + j * SEARCH_DEGREES) for i, j in SEARCH_OFFSETS),
                                         return_exceptions=True)
            if isinstance(found[0], BaseException):
                raise GeoglowsError(f"GEOGLOWS no ubicó un río en el punto: {found[0]}") from found[0]
            nearest = found[0]
            river_ids = list(dict.fromkeys(item for item in found if isinstance(item, int)))
            series = await asyncio.gather(*(self._annual(client, river_id) for river_id in river_ids), return_exceptions=True)
        by_river = {river_id: item for river_id, item in zip(river_ids, series, strict=True) if isinstance(item, list) and item}
        if not by_river:
            problem = next((item for item in series if isinstance(item, BaseException)), None)
            raise GeoglowsError(f"GEOGLOWS no devolvió medias anuales para ningún tramo cercano: {problem or 'series vacías'}")
        chosen = max(by_river, key=lambda river_id: _mean(by_river[river_id]) or 0.0)
        return RiverChoice(
            river_id=chosen, nearest_river_id=nearest, candidates=len(river_ids), annual=by_river[chosen], nearest_mean=_mean(by_river.get(nearest, [])),
            provenance=Provenance.CACHED if all(item == Provenance.CACHED for item in self._provenances) else Provenance.REAL,
            downloaded_at=max(self._stamps),
        )

    async def _river_id(self, client: httpx.AsyncClient, latitude: float, longitude: float) -> int:
        payload = await self._get(client, "/getriverid", {"lat": f"{latitude:.5f}", "lon": f"{longitude:.5f}"}, None)
        river_id = payload.get("river_id")
        if not isinstance(river_id, int):
            raise GeoglowsError("GEOGLOWS no devolvió un identificador de río.")
        return river_id

    async def _annual(self, client: httpx.AsyncClient, river_id: int) -> list[Observation]:
        return parse_annual(await self._get(client, f"/annualaverages/{river_id}", {"format": "json"}, ANNUAL_MAX_AGE), river_id)

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict[str, str], max_age: timedelta | None) -> dict:
        key = self.cache.request_key({"url": BASE + path, "params": params, "v": 1})
        cached = self.cache.get(key, max_age=max_age)
        if cached:
            self._provenances.append(Provenance.CACHED)
            self._stamps.append(cached.downloaded_at)
            return json.loads(cached.content)
        async with _limit():
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    response = await client.get(BASE + path, params=params)
                except httpx.TransportError as exc:
                    if attempt == ATTEMPTS:
                        raise GeoglowsError(f"GEOGLOWS no respondió: {exc}") from exc
                    await asyncio.sleep(RETRY_SECONDS)
                    continue
                if response.status_code >= 500 and attempt < ATTEMPTS:
                    await asyncio.sleep(RETRY_SECONDS)
                    continue
                if response.status_code >= 400:
                    raise GeoglowsError(f"GEOGLOWS respondió {response.status_code}: {response.text[:200]}")
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise GeoglowsError("GEOGLOWS devolvió una respuesta que no es JSON.") from exc
                stored = self.cache.put(key, json.dumps(payload).encode(), suffix=".json")
                self._provenances.append(Provenance.REAL)
                self._stamps.append(stored.downloaded_at)
                return payload
        raise GeoglowsError("GEOGLOWS no respondió.")
