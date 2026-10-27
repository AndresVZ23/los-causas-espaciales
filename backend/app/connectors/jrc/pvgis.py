"""ERA5 mensual (ECMWF) servido por PVGIS 5.3 del JRC: segunda fuente de temperatura y radiación solar.

Sobre el Perú, PVGIS solo ofrece la base PVGIS-ERA5 (SARAH-3 no cubre esa longitud y NSRDB no se ofrece en la API
5.3; verificado el 27-oct-2026). `MRcalc` devuelve por mes la irradiación global horizontal `H(h)_m` en kWh/m²/mes y
la temperatura media a 2 m `T2m` en °C, de 2005 a 2023. ERA5 es un reanálisis independiente de MERRA-2 (temperatura
de NASA POWER) y de CERES (radiación de NASA POWER). Es un archivo cerrado: la caché no vence.
"""

import asyncio
import json
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from ...core.config import Settings, get_settings
from ...schemas.analysis import Observation, Provenance
from ..cache import RawPayloadCache

API = "https://re.jrc.ec.europa.eu/api/v5_3/MRcalc"
TIMEOUT = httpx.Timeout(connect=20, read=60, write=20, pool=20)
ATTEMPTS = 2
RETRY_SECONDS = 3.0
DATABASE = "PVGIS-ERA5"
FIRST_YEAR, LAST_YEAR = 2005, 2023


class PvgisError(RuntimeError):
    pass


@dataclass
class Era5Annual:
    """Medias anuales de ERA5 en las unidades de NASA POWER: °C y kWh/m²/día (solo años con los 12 meses)."""

    temperature: list[Observation]
    irradiance: list[Observation]
    provenance: Provenance
    downloaded_at: datetime


def annual_from_monthly(monthly: list[dict]) -> tuple[list[Observation], list[Observation]]:
    """Temperatura media ponderada por días y radiación diaria media (suma mensual ÷ días del año); un año incompleto se omite."""
    by_year: dict[int, dict[int, dict]] = {}
    for row in monthly:
        by_year.setdefault(int(row["year"]), {})[int(row["month"])] = row
    temperature, irradiance = [], []
    for year, months in sorted(by_year.items()):
        if len(months) != 12:
            continue
        days = {month: monthrange(year, month)[1] for month in months}
        total_days = sum(days.values())
        temps = [months[m].get("T2m") for m in months]
        sums = [months[m].get("H(h)_m") for m in months]
        stamp = date(year, 7, 1)
        if all(isinstance(value, (int, float)) for value in temps):
            temperature.append(Observation(timestamp=stamp, value=round(sum(months[m]["T2m"] * days[m] for m in months) / total_days, 4)))
        if all(isinstance(value, (int, float)) and value >= 0 for value in sums):
            irradiance.append(Observation(timestamp=stamp, value=round(sum(sums) / total_days, 4)))
    return temperature, irradiance


class PvgisConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "pvgis")

    async def era5_annual(self, latitude: float, longitude: float) -> Era5Annual:
        params = {"lat": f"{latitude:.4f}", "lon": f"{longitude:.4f}", "horirrad": "1", "avtemp": "1", "startyear": str(FIRST_YEAR),
                  "endyear": str(LAST_YEAR), "raddatabase": DATABASE, "outputformat": "json"}
        key = self.cache.request_key({"url": API, "params": params, "v": 1})
        cached = self.cache.get(key, max_age=None)
        if cached:
            payload, provenance, stamp = json.loads(cached.content), Provenance.CACHED, cached.downloaded_at
        else:
            payload = await self._fetch(params)
            stored = self.cache.put(key, json.dumps(payload).encode(), suffix=".json")
            provenance, stamp = Provenance.REAL, stored.downloaded_at
        monthly = payload.get("outputs", {}).get("monthly") or []
        temperature, irradiance = annual_from_monthly(monthly)
        if not temperature and not irradiance:
            raise PvgisError("PVGIS no devolvió ningún año completo de ERA5.")
        return Era5Annual(temperature=temperature, irradiance=irradiance, provenance=provenance, downloaded_at=stamp)

    async def _fetch(self, params: dict[str, str]) -> dict:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as client:
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    response = await client.get(API, params=params)
                except httpx.TransportError as exc:
                    if attempt == ATTEMPTS:
                        raise PvgisError(f"PVGIS no respondió: {exc}") from exc
                    await asyncio.sleep(RETRY_SECONDS)
                    continue
                if response.status_code in (429, 500, 502, 503, 504) and attempt < ATTEMPTS:
                    await asyncio.sleep(RETRY_SECONDS)
                    continue
                if response.status_code >= 400:
                    # PVGIS explica el rechazo en `message` (p. ej. fuera de cobertura); no se reintenta un 4xx.
                    try:
                        message = response.json().get("message", "")
                    except ValueError:
                        message = response.text[:200]
                    raise PvgisError(f"PVGIS respondió {response.status_code}: {message}")
                return response.json()
        raise PvgisError("PVGIS no respondió.")
