"""Monthly PV-generation labels derived from COES public 15-minute active-power exports."""

import asyncio
import calendar
import csv
import io
import math
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ...schemas.data_sources import (
    COESMonthlyObservation,
    COESMonthlyRequest,
    COESMonthlyResponse,
    COESPlantSeries,
)
from ..cache import RawPayloadCache

TIMEOUT = httpx.Timeout(connect=20, read=90, write=30, pool=20)
LICENSE_NOTE = (
    "El portal COES ofrece exportación pública CSV/Excel y una Web API, pero no publica una licencia específica de "
    "reutilización en la ficha consultada el 22-oct-2026. Usar con atribución a COES, sin alterar la fuente, y "
    "confirmar autorización antes de redistribuir el archivo original."
)

# Sufijos exactos observados en el CSV oficial; no se sustituyen por plantas parecidas.
PLANT_SUFFIXES = {
    "Rubí": ("-RUBI_CIRCUITO_1-5", "-RUBI_CIRCUITO_6-10"),
    "Intipampa": ("-INTIPAMPA_SOLAR",),
    "Moquegua FV": ("-MOQUEGUA_SOLAR",),
    "Majes": ("-GTSMAJES",),
    "Repartición": ("-GTSREPAR",),
    "Panamericana": ("-PANAM_SOLAR",),
}


class COESConnectorError(RuntimeError):
    pass


def _normalize(value: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKD", value.strip()).upper()
        if not unicodedata.combining(character)
    )


def _months(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current = date(current.year + (current.month == 12), 1 if current.month == 12 else current.month + 1, 1)


def _decode_csv(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252")


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace("\u00a0", "")
    if not cleaned or cleaned.upper() in {"ND", "N/D", "NULL", "-"}:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def aggregate_month(content: bytes, month: date, provenance: Provenance, downloaded_at: datetime):
    reader = csv.DictReader(io.StringIO(_decode_csv(content)), skipinitialspace=True)
    if not reader.fieldnames or not reader.fieldnames[0].strip().lower().startswith("fechahora"):
        raise COESConnectorError("El CSV COES no contiene la columna fechahora esperada.")
    headers = [header.strip() for header in reader.fieldnames[1:]]
    normalized = {_normalize(header): header for header in headers}
    matches: dict[str, list[str]] = {}
    for plant, suffixes in PLANT_SUFFIXES.items():
        selected = []
        for suffix in suffixes:
            suffix_normalized = _normalize(suffix)
            found = [original for norm, original in normalized.items() if norm.endswith(suffix_normalized)]
            if len(found) == 1:
                selected.extend(found)
        matches[plant] = selected

    totals = {plant: 0.0 for plant in PLANT_SUFFIXES}
    observed = {plant: 0 for plant in PLANT_SUFFIXES}
    for row in reader:
        for plant, columns in matches.items():
            if len(columns) != len(PLANT_SUFFIXES[plant]):
                continue
            values = [_parse_number(row.get(column)) for column in columns]
            if all(value is not None for value in values):
                totals[plant] += sum(value for value in values if value is not None) * 0.25
                observed[plant] += 1

    expected = calendar.monthrange(month.year, month.month)[1] * 96
    result: dict[str, tuple[list[str], COESMonthlyObservation | None]] = {}
    for plant in PLANT_SUFFIXES:
        columns = matches[plant]
        if len(columns) != len(PLANT_SUFFIXES[plant]):
            result[plant] = (columns, None)
            continue
        result[plant] = (
            columns,
            COESMonthlyObservation(
                month=month.strftime("%Y-%m"),
                generation_mwh=round(totals[plant], 6),
                intervals_expected=expected,
                intervals_observed=observed[plant],
                completeness_percent=round(observed[plant] / expected * 100, 3),
                provenance=provenance,
                downloaded_at=downloaded_at,
            ),
        )
    return result


class COESConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "coes")
        parsed = urlparse(self.settings.coes_export_url)
        if parsed.scheme != "https" or parsed.hostname not in {"www.coes.org.pe", "coes.org.pe"}:
            raise COESConnectorError("COES debe usar el exportador HTTPS oficial.")

    async def _download_month(self, month: date):
        last_day = calendar.monthrange(month.year, month.month)[1]
        end = month.replace(day=last_day)
        descriptor = {"month": month.strftime("%Y-%m"), "parameter": "active-power", "generation": "solar", "v": 1}
        cache_key = self.cache.request_key(descriptor)
        cached = self.cache.get(cache_key, max_age=timedelta(hours=self.settings.cache_ttl_hours))
        if cached:
            return cached.content, cached.downloaded_at, Provenance.CACHED
        params = {
            "fechaInicial": month.strftime("%d/%m/%Y"),
            "fechaFinal": end.strftime("%d/%m/%Y"),
            "tiposEmpresa": "",
            "empresas": "",
            "tiposGeneracion": "3",
            "central": "1",
            "parametros": "1",
            "tipo": "3",
        }
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=False) as client:
            response = await client.get(self.settings.coes_export_url, params=params)
            response.raise_for_status()
        if "csv" not in response.headers.get("content-type", "").lower():
            raise COESConnectorError("COES no devolvió el CSV oficial esperado.")
        raw = self.cache.put(cache_key, response.content, suffix=".csv")
        return raw.content, raw.downloaded_at, Provenance.REAL

    async def monthly_generation(self, request: COESMonthlyRequest) -> COESMonthlyResponse:
        start = date.fromisoformat(f"{request.start_month}-01")
        end = date.fromisoformat(f"{request.end_month}-01")
        month_list = list(_months(start, end))
        semaphore = asyncio.Semaphore(3)

        async def limited(month):
            async with semaphore:
                return month, await self._download_month(month)

        try:
            downloads = await asyncio.gather(*(limited(month) for month in month_list))
        except httpx.HTTPError as exc:
            raise COESConnectorError(f"La descarga oficial de COES falló: {exc}") from exc

        by_plant: dict[str, dict[str, Any]] = {
            plant: {"columns": [], "observations": [], "missing": []} for plant in PLANT_SUFFIXES
        }
        provenances: list[Provenance] = []
        downloaded_at: list[datetime] = []
        for month, (content, stamp, provenance) in downloads:
            provenances.append(provenance); downloaded_at.append(stamp)
            aggregate = aggregate_month(content, month, provenance, stamp)
            for plant, (columns, observation) in aggregate.items():
                for column in columns:
                    if column not in by_plant[plant]["columns"]:
                        by_plant[plant]["columns"].append(column)
                if observation is None:
                    by_plant[plant]["missing"].append(month.strftime("%Y-%m"))
                else:
                    by_plant[plant]["observations"].append(observation)

        plants = []
        for plant, data in by_plant.items():
            missing = data["missing"]
            limitations = [
                "MWh se calcula integrando potencia activa de intervalos de 15 minutos: suma(MW × 0.25 h).",
                "Los valores negativos del medidor se conservan; no se recortan a cero.",
            ]
            if missing:
                limitations.append(
                    f"COES no publicó las columnas exactas esperadas para {plant} en: {', '.join(missing)}; no se usó otra central como reemplazo."
                )
            plants.append(COESPlantSeries(
                plant=plant, provider_columns=data["columns"],
                status="DATA_UNAVAILABLE" if missing else "READY",
                observations=data["observations"], limitations=limitations,
            ))
        overall = Provenance.CACHED if provenances and all(item == Provenance.CACHED for item in provenances) else Provenance.REAL
        latest = max(downloaded_at) if downloaded_at else datetime.now(timezone.utc)
        return COESMonthlyResponse(
            generated_at=datetime.now(timezone.utc), provenance=overall,
            source_url="https://www.coes.org.pe/Portal/mediciones/medidoresgeneracion",
            downloaded_at=latest, plants=plants, license=LICENSE_NOTE,
            methodology="Cada mes se solicita al exportador público con tipo de generación SOLAR y Potencia Activa (MW); se preserva el CSV por SHA-256 y se integra a MWh.",
            limitations=[
                "COES limita su exportador a un mes por solicitud; este conector respeta ese límite y usa máximo tres solicitudes concurrentes.",
                "Las etiquetas son mediciones publicadas por COES, no estimaciones del modelo ni garantías de producción futura.",
            ],
        )
