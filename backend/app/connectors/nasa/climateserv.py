"""CHIRPS diario (UCSB Climate Hazards Center) servido por NASA SERVIR ClimateSERV, para cualquier punto o área del Perú.

CHIRPS combina satélite infrarrojo, una climatología de alta resolución y estaciones: es la tercera fuente de lluvia,
independiente del reanálisis MERRA-2 (NASA POWER) y de GPM IMERG. ClimateSERV trabaja con trabajos asíncronos y tarda
~10 s por año de datos (medido el 26-oct-2026); una serie completa de una vez no terminó en 5 minutos. Por eso se pide
un año por trabajo, en paralelo con tope, y cada año cerrado queda en caché sin vencimiento.
"""

import asyncio
import json
import weakref
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from shapely.geometry import mapping, shape

from ...core.config import Settings, get_settings
from ...schemas.analysis import Observation, Provenance, SourceMetadata
from ..cache import RawPayloadCache

API = "https://climateserv.servirglobal.net/api"
TIMEOUT = httpx.Timeout(connect=20, read=90, write=20, pool=60)
CONCURRENCY = 6
POLL_SECONDS = 2.0
MAX_POLLS = 120          # ~4 minutos por año como máximo
ATTEMPTS = 3             # por año: el servicio devuelve 503 pasajeros bajo carga
RETRY_SECONDS = 5.0
POINT_HALF_CELL = 0.025  # una celda CHIRPS de 0.05° centrada en el punto
CHIRPS_DATATYPE = 0
SOURCE_LABEL = "CHIRPS v2.0 (UCSB CHC) vía NASA SERVIR ClimateSERV"


class ClimateServError(RuntimeError):
    pass


_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _limit() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _semaphores:
        _semaphores[loop] = asyncio.Semaphore(CONCURRENCY)
    return _semaphores[loop]


def request_geometry(geometry: dict[str, Any] | None, longitude: float, latitude: float) -> dict[str, Any]:
    """Polígono para ClimateSERV: el área simplificada o, para un punto, la celda CHIRPS que lo contiene."""
    if geometry and geometry.get("type") in {"Polygon", "MultiPolygon"}:
        area = shape(geometry).simplify(0.002, preserve_topology=True)
        polygon = max(getattr(area, "geoms", [area]), key=lambda item: item.area)  # ClimateSERV promedia un solo polígono
        return {"type": "Polygon", "coordinates": [[[round(x, 5), round(y, 5)] for x, y in mapping(polygon)["coordinates"][0]]]}
    d = POINT_HALF_CELL
    ring = [[longitude - d, latitude - d], [longitude + d, latitude - d], [longitude + d, latitude + d], [longitude - d, latitude + d], [longitude - d, latitude - d]]
    return {"type": "Polygon", "coordinates": [[[round(x, 5), round(y, 5)] for x, y in ring]]}


class ChirpsConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "climateserv")

    async def _year(self, client: httpx.AsyncClient, geometry: dict[str, Any], year: int, end: date) -> tuple[list[dict], Provenance, datetime]:
        last = min(date(year, 12, 31), end)
        form = {"datatype": CHIRPS_DATATYPE, "begintime": f"01/01/{year}", "endtime": last.strftime("%m/%d/%Y"), "intervaltype": 0,
                "operationtype": 5, "dateType_Category": "default", "isZip_CurrentDataType": "false",
                "geometry": json.dumps(geometry, separators=(",", ":"))}
        key = self.cache.request_key({"form": form, "v": 1})
        closed = last.year < date.today().year
        cached = self.cache.get(key, max_age=None if closed else timedelta(hours=self.settings.cache_ttl_hours))
        if cached:
            return json.loads(cached.content).get("data", []), Provenance.CACHED, cached.downloaded_at
        async with _limit():
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    result = await self._job(client, form, year)
                    break
                except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                    # 503/429 y cortes de red son pasajeros en ClimateSERV (medido el 26-oct-2026); un 4xx no se reintenta.
                    retryable = isinstance(exc, httpx.TransportError) or exc.response.status_code in {429, 502, 503, 504}
                    if not retryable or attempt == ATTEMPTS:
                        raise
                    await asyncio.sleep(RETRY_SECONDS * attempt)
        stored = self.cache.put(key, result.content, suffix=".json")
        return result.json().get("data", []), Provenance.REAL, stored.downloaded_at

    async def _job(self, client: httpx.AsyncClient, form: dict[str, Any], year: int) -> httpx.Response:
        response = await client.post(f"{API}/submitDataRequest/", data=form)
        response.raise_for_status()
        job = response.json()
        job = job[0] if isinstance(job, list) else job
        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_SECONDS)
            progress = await client.get(f"{API}/getDataRequestProgress/", params={"id": job})
            progress.raise_for_status()
            value = progress.json()
            value = value[0] if isinstance(value, list) else value
            if value == -1:
                raise ClimateServError(f"ClimateSERV rechazó el trabajo del año {year}.")
            if value >= 100:
                break
        else:
            raise ClimateServError(f"ClimateSERV no terminó el año {year} en {MAX_POLLS * POLL_SECONDS:.0f} s.")
        result = await client.get(f"{API}/getDataFromRequest/", params={"id": job})
        result.raise_for_status()
        return result

    async def daily(self, geometry: dict[str, Any] | None, longitude: float, latitude: float, start: date, end: date) -> tuple[list[Observation], SourceMetadata]:
        """Lluvia diaria (mm/día) promediada sobre el área o la celda del punto; los días sin dato se omiten, no se rellenan."""
        polygon = request_geometry(geometry, longitude, latitude)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as client:
                years = await asyncio.gather(*(self._year(client, polygon, year, end) for year in range(start.year, end.year + 1)))
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ClimateServError(f"CHIRPS (NASA SERVIR ClimateSERV) no respondió: {exc}") from exc
        observations = []
        for rows, _, _ in years:
            for row in rows:
                value = row.get("value", {}).get("avg")
                if value is None or value < 0 or value > 2000:   # -9999 y valores imposibles son faltantes
                    continue
                day = date(int(row["year"]), int(row["month"]), int(row["day"]))
                if start <= day <= end:
                    observations.append(Observation.model_construct(timestamp=day, value=float(value)))
        if not observations:
            raise ClimateServError("CHIRPS no devolvió días válidos para el área.")
        observations.sort(key=lambda item: item.timestamp)
        provenances = [provenance for _, provenance, _ in years]
        source = SourceMetadata(
            source_id="chirps-climateserv", dataset=SOURCE_LABEL, version="CHIRPS 2.0", variable="CHIRPS", unit="mm/day",
            temporal_resolution="Diaria", spatial_resolution="0.05° (≈ 5.5 km); promedio sobre el área o la celda del punto",
            downloaded_at=max(stamp for _, _, stamp in years).astimezone(timezone.utc), source_url=f"{API}/submitDataRequest/",
            provenance=Provenance.CACHED if all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
            quality_notes=["Satélite infrarrojo + climatología + estaciones; suaviza extremos y pierde la garúa costera.",
                           f"Último día publicado: {observations[-1].timestamp.isoformat()} (latencia de unas semanas)."],
        )
        return observations, source
