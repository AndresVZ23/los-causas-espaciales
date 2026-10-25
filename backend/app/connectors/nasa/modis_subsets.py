"""Subconjuntos MODIS por punto desde el servicio web del ORNL DAAC (NASA): productos anuales de vegetación y cobertura.

El servicio entrega como máximo 10 fechas por consulta y tarda de 4 a 30 s por consulta (verificado el 2026-10-24),
así que solo se usan productos anuales: una serie 2000–2025 son 3 consultas por banda. Cada tramo de fechas se guarda
con su huella SHA-256; un tramo cerrado (más de 400 días atrás) ya no cambia y se reutiliza sin vencimiento.
"""

import asyncio
import json
import weakref
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ..cache import RawPayloadCache

BASE_URL = "https://modis.ornl.gov/rst/api/v1"
TIMEOUT = httpx.Timeout(connect=20, read=120, write=20, pool=60)
MAX_DATES_PER_REQUEST = 10
CONCURRENCY = 6
MAX_KM = 10
CLOSED_AFTER_DAYS = 400


class ModisSubsetError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModisGrid:
    """Ventana en la proyección sinusoidal MODIS: esquina inferior izquierda, tamaño de celda en metros y filas × columnas."""

    xllcorner: float
    yllcorner: float
    cellsize: float
    nrows: int
    ncols: int


@dataclass(frozen=True)
class ModisDate:
    calendar_date: date
    data: list[int]


@dataclass(frozen=True)
class ModisBand:
    product: str
    band: str
    units: str
    scale: float | None
    grid: ModisGrid
    dates: list[ModisDate]
    provenance: Provenance
    downloaded_at: datetime
    source_url: str


_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _limit() -> asyncio.Semaphore:
    # Un tope de consultas simultáneas por bucle de eventos: el ORNL responde más lento con muchas a la vez.
    loop = asyncio.get_running_loop()
    if loop not in _semaphores:
        _semaphores[loop] = asyncio.Semaphore(CONCURRENCY)
    return _semaphores[loop]


def _scale(raw: object) -> float | None:
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None   # p. ej. "Not Available" en clases de cobertura


class ModisSubsetConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "modis")

    async def _get_json(self, path: str, params: dict[str, object], *, closed: bool) -> tuple[dict, datetime, Provenance]:
        key = self.cache.request_key({"path": path, "params": params, "v": 1})
        cached = self.cache.get(key, max_age=None if closed else timedelta(hours=self.settings.cache_ttl_hours))
        if cached:
            return json.loads(cached.content), cached.downloaded_at, Provenance.CACHED
        async with _limit():
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, headers={"Accept": "application/json"}) as client:
                    response = await client.get(f"{BASE_URL}/{path}", params=params)
                    response.raise_for_status()
                    payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise ModisSubsetError(f"El servicio MODIS del ORNL DAAC no respondió: {exc}") from exc
        stored = self.cache.put(key, response.content, suffix=".json")
        return payload, stored.downloaded_at, Provenance.REAL

    async def band(self, product: str, band: str, latitude: float, longitude: float, km: int) -> ModisBand:
        """Serie completa de una banda en una ventana de ±km alrededor del punto (km entre 0 y 10)."""
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ModisSubsetError("Coordenadas fuera del rango WGS84.")
        km = max(0, min(MAX_KM, int(km)))
        location = {"latitude": round(latitude, 5), "longitude": round(longitude, 5)}
        listing, _, _ = await self._get_json(f"{product}/dates", location, closed=False)
        dates = listing.get("dates") or []
        if not dates:
            raise ModisSubsetError(f"{product} no tiene fechas publicadas para este punto.")
        today = date.today()
        chunks = [dates[i:i + MAX_DATES_PER_REQUEST] for i in range(0, len(dates), MAX_DATES_PER_REQUEST)]
        responses = await asyncio.gather(*(
            self._get_json(f"{product}/subset", {**location, "band": band, "startDate": chunk[0]["modis_date"], "endDate": chunk[-1]["modis_date"],
                                                 "kmAboveBelow": km, "kmLeftRight": km},
                           closed=(today - date.fromisoformat(chunk[-1]["calendar_date"])).days > CLOSED_AFTER_DAYS)
            for chunk in chunks
        ))
        first = responses[0][0]
        try:
            grid = ModisGrid(float(first["xllcorner"]), float(first["yllcorner"]), float(first["cellsize"]), int(first["nrows"]), int(first["ncols"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ModisSubsetError(f"Respuesta MODIS sin la ventana esperada: {exc}") from exc
        series: dict[date, list[int]] = {}
        for payload, _, _ in responses:
            for item in payload.get("subset", []):
                if item.get("band") == band and len(item.get("data", [])) == grid.nrows * grid.ncols:
                    series[date.fromisoformat(item["calendar_date"])] = [int(value) for value in item["data"]]
        provenances = [provenance for _, _, provenance in responses]
        return ModisBand(
            product=product, band=band, units=str(first.get("units", "")), scale=_scale(first.get("scale")), grid=grid,
            dates=[ModisDate(day, series[day]) for day in sorted(series)],
            provenance=Provenance.CACHED if all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
            downloaded_at=max(stamp for _, stamp, _ in responses).astimezone(timezone.utc),
            source_url=f"{BASE_URL}/{product}/subset",
        )
