"""Caudal diario de ríos GloFAS v4 (Copernicus Emergency Management Service · ECMWF) servido por la Flood API de
Open-Meteo: fuente principal del piloto hidroeléctrico.

GloFAS simula el caudal con LISFLOOD forzado por ERA5, en celdas de 0.05° (~5 km). Open-Meteo entrega la serie
«seamless» (reanálisis consolidado + tiempo casi real) sin cuenta; verificado el 10-nov-2026: datos válidos desde
1997-01-01, nulos antes, unidad m³/s. Licencia de los datos: Copernicus (libre con atribución). El uso gratuito de
la API de Open-Meteo es solo no comercial y con cuota: cada consulta pesa días ÷ 14 ÷ 10 llamadas y el tope es de
600 por minuto, así que la historia cerrada (1997 al año pasado) se pide una sola vez por celda y queda en caché
sin vencimiento.

El cauce del modelo no siempre pasa por la celda del punto pedido (medido: el río Tambo en El Fiscal da 0 m³/s en
su celda y 39 m³/s en la vecina). Regla declarada, que no mira ninguna otra fuente:

1. Se lee el caudal medio del último año completo en el vecindario 3 × 3 del punto.
2. Si la celda del punto lleva al menos el 20 % del máximo del vecindario, se usa esa celda.
3. Si no, se usa la celda más cercana al punto entre las que llevan al menos el 50 % del máximo, y se declara.
4. Si ninguna celda llega a 0.05 m³/s, GloFAS no modela un cauce ahí: se informa, no se devuelve cero.
"""

import asyncio
import json
import weakref
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx

from ...core.config import Settings, get_settings
from ...geospatial.geometry import GEOD
from ...schemas.analysis import Observation, Provenance
from ..cache import RawPayloadCache

API = "https://flood-api.open-meteo.com/v1/flood"
SOURCE = "GloFAS v4 (Copernicus EMS · ECMWF) vía Open-Meteo"
VERSION = "GloFAS v4 seamless (reanálisis consolidado + tiempo casi real)"
FIRST_DAY = date(1997, 1, 1)
CELL_DEGREES = 0.05
CHANNEL_SHARE = 0.2      # la celda del punto «está en el cauce» si lleva al menos el 20 % del máximo vecino
MAIN_SHARE = 0.5         # si no, se busca entre las celdas con al menos el 50 % del máximo
MIN_RIVER_FLOW = 0.05    # m³/s: por debajo, el modelo no tiene un cauce en el vecindario
CONCURRENCY = 2
ATTEMPTS = 2
RATE_WAIT_SECONDS = 20.0
TIMEOUT = httpx.Timeout(connect=20, read=90, write=20, pool=90)
OFFSETS = [(0, 0)] + [(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1) if (i, j) != (0, 0)]


class GlofasError(RuntimeError):
    pass


class NoRiverError(GlofasError):
    """GloFAS no modela un cauce en el vecindario del punto."""


@dataclass(frozen=True)
class FlowCell:
    """La celda de GloFAS que se usó y por qué."""

    latitude: float
    longitude: float
    distance_km: float              # del punto pedido al centro de la celda usada
    moved: bool                     # True si no es la celda del punto
    point_cell_mean: float | None   # caudal medio del año de exploración en la celda del punto
    used_cell_mean: float
    neighborhood_max: float
    scan_year: int


@dataclass
class GlofasSeries:
    observations: list[Observation]
    cell: FlowCell
    provenance: Provenance
    downloaded_at: datetime


_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _limit() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _semaphores:
        _semaphores[loop] = asyncio.Semaphore(CONCURRENCY)
    return _semaphores[loop]


def _km(latitude: float, longitude: float, other_latitude: float, other_longitude: float) -> float:
    return GEOD.inv(longitude, latitude, other_longitude, other_latitude)[2] / 1000


def choose_cell(latitude: float, longitude: float, cells: list[tuple[float, float, float | None]], scan_year: int) -> FlowCell:
    """Aplica la regla del cauce. `cells` = (latitud, longitud, caudal medio) con la celda del punto en primer lugar."""
    valid = [cell for cell in cells if cell[2] is not None]
    top = max((cell[2] for cell in valid), default=0.0)
    if top < MIN_RIVER_FLOW:
        raise NoRiverError(f"GloFAS no modela un cauce a menos de ~8 km del punto ({latitude:.4f}, {longitude:.4f}): "
                           f"el mayor caudal medio del vecindario en {scan_year} es {top:.2f} m³/s. Mueva la toma hacia el río.")
    center = cells[0]
    if center[2] is not None and center[2] >= CHANNEL_SHARE * top:
        chosen, moved = center, False
    else:
        chosen = min((cell for cell in valid if cell[2] >= MAIN_SHARE * top), key=lambda cell: _km(latitude, longitude, cell[0], cell[1]))
        moved = True
    return FlowCell(latitude=chosen[0], longitude=chosen[1], distance_km=round(_km(latitude, longitude, chosen[0], chosen[1]), 2), moved=moved,
                    point_cell_mean=round(center[2], 3) if center[2] is not None else None, used_cell_mean=round(chosen[2], 3),
                    neighborhood_max=round(top, 3), scan_year=scan_year)


def _daily(payload: dict) -> list[tuple[date, float]]:
    """Pares (día, m³/s) válidos de una respuesta; los nulos se descartan, nunca se vuelven cero."""
    daily = payload.get("daily") or {}
    times, values = daily.get("time") or [], daily.get("river_discharge") or []
    if len(times) != len(values):
        raise GlofasError("Open-Meteo devolvió una serie de caudal con largos distintos de fechas y valores.")
    return [(date.fromisoformat(day), float(value)) for day, value in zip(times, values) if isinstance(value, (int, float)) and value >= 0]


class GlofasConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "glofas-openmeteo")

    async def discharge(self, latitude: float, longitude: float, start: date, end: date) -> GlofasSeries:
        """Caudal diario entre `start` y `end` en la celda del cauce más cercana al punto."""
        today = date.today()
        closed_end = date(today.year - 1, 12, 31)
        cell, scan_provenance, scan_stamp = await self._scan(latitude, longitude, closed_end.year)
        where = {"latitude": f"{cell.latitude:.4f}", "longitude": f"{cell.longitude:.4f}", "daily": "river_discharge"}
        chunks = []
        if start <= closed_end:
            # Siempre la historia cerrada completa: una sola entrada de caché por celda, sin importar el período pedido.
            chunks.append(self._fetch({**where, "start_date": FIRST_DAY.isoformat(), "end_date": closed_end.isoformat()}, None))
        if end > closed_end:
            open_start = max(start, date(today.year, 1, 1))
            chunks.append(self._fetch({**where, "start_date": open_start.isoformat(), "end_date": min(end, today).isoformat()},
                                      timedelta(hours=self.settings.cache_ttl_hours)))
        results = await asyncio.gather(*chunks)
        rows = [row for payload, _, _ in results for row in _daily(payload) if start <= row[0] <= end]
        if not rows:
            raise GlofasError(f"GloFAS no devolvió caudal válido entre {start} y {end} en la celda {cell.latitude:.3f}, {cell.longitude:.3f}.")
        provenances = [scan_provenance, *(provenance for _, provenance, _ in results)]
        return GlofasSeries(
            observations=[Observation.model_construct(timestamp=day, value=value) for day, value in sorted(rows)], cell=cell,
            provenance=Provenance.CACHED if all(item == Provenance.CACHED for item in provenances) else Provenance.REAL,
            downloaded_at=max([scan_stamp, *(stamp for _, _, stamp in results)]),
        )

    async def _scan(self, latitude: float, longitude: float, year: int) -> tuple[FlowCell, Provenance, datetime]:
        """Caudal medio del año `year` en el vecindario 3 × 3 del punto, en una sola consulta."""
        params = {
            "latitude": ",".join(f"{latitude + i * CELL_DEGREES:.4f}" for i, _ in OFFSETS),
            "longitude": ",".join(f"{longitude + j * CELL_DEGREES:.4f}" for _, j in OFFSETS),
            "daily": "river_discharge", "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
        }
        payload, provenance, stamp = await self._fetch(params, None)
        locations = payload if isinstance(payload, list) else [payload]
        if len(locations) != len(OFFSETS):
            raise GlofasError("Open-Meteo no devolvió las nueve celdas del vecindario.")
        cells = []
        for location in locations:
            values = [value for _, value in _daily(location)]
            cells.append((float(location["latitude"]), float(location["longitude"]), sum(values) / len(values) if values else None))
        return choose_cell(latitude, longitude, cells, year), provenance, stamp

    async def _fetch(self, params: dict[str, str], max_age: timedelta | None) -> tuple[dict | list, Provenance, datetime]:
        key = self.cache.request_key({"url": API, "params": params, "v": 1})
        cached = self.cache.get(key, max_age=max_age)
        if cached:
            return json.loads(cached.content), Provenance.CACHED, cached.downloaded_at
        async with _limit():
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=True) as client:
                for attempt in range(1, ATTEMPTS + 1):
                    try:
                        response = await client.get(API, params=params)
                    except httpx.TransportError as exc:
                        if attempt == ATTEMPTS:
                            raise GlofasError(f"Open-Meteo (GloFAS) no respondió: {exc}") from exc
                        continue
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < ATTEMPTS:
                            await asyncio.sleep(RATE_WAIT_SECONDS if response.status_code == 429 else 2.0)
                            continue
                        reason = "alcanzó su cuota por minuto; vuelva a ejecutar en un minuto" if response.status_code == 429 else f"respondió {response.status_code}"
                        raise GlofasError(f"Open-Meteo (GloFAS) {reason}.")
                    if response.status_code >= 400:
                        try:
                            reason = response.json().get("reason", "")
                        except ValueError:
                            reason = response.text[:200]
                        raise GlofasError(f"Open-Meteo (GloFAS) respondió {response.status_code}: {reason}")
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise GlofasError("Open-Meteo (GloFAS) devolvió una respuesta que no es JSON.") from exc
                    stored = self.cache.put(key, json.dumps(payload).encode(), suffix=".json")
                    return payload, Provenance.REAL, stored.downloaded_at
        raise GlofasError("Open-Meteo (GloFAS) no respondió.")
