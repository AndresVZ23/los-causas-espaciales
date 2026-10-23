"""Monthly solar-generation labels from the official COES daily XLSX export."""

import asyncio
import calendar
import json
import math
import time
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from itertools import islice
from typing import Any
from urllib.parse import urlparse

import httpx
from openpyxl import load_workbook

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ...schemas.data_sources import (
    COESCapacityReference,
    COESMonthlyObservation,
    COESMonthlyRequest,
    COESMonthlyResponse,
    COESPlantSeries,
)
from ..cache import RawPayloadCache

TIMEOUT = httpx.Timeout(connect=20, read=120, write=30, pool=20)
COES_SOURCE_URL = "https://www.coes.org.pe/Portal/portalinformacion/generacion"
EXPECTED_SHEET = "PRODUCCIÓN DIARIA"
EXPECTED_HEADERS = ("FECHA", "EMPRESA", "GRUPO/CENTRAL", "TIPO GENERACIÓN", "TOTAL")
MAX_XLSX_BYTES = 25 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
LICENSE_NOTE = (
    "El portal público de COES permite exportar la producción, pero no publicó términos ni una licencia abierta "
    "específica en las páginas revisadas el 23-oct-2026. Citar COES-SINAC; no redistribuir el XLSX original sin "
    "confirmar autorización. Christian enviará un correo de cortesía al COES."
)


class COESConnectorError(RuntimeError):
    pass


def _normalize(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.strip()).upper()
        if not unicodedata.combining(character)
    )


def _months(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current = date(current.year + (current.month == 12), 1 if current.month == 12 else current.month + 1, 1)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        cleaned = str(value).strip().replace("\u00a0", "").replace(",", "")
        if not cleaned or cleaned.upper() in {"ND", "N/D", "NULL", "-"}:
            return None
        try:
            number = float(cleaned)
        except ValueError:
            return None
    return number if math.isfinite(number) else None


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    return None


def _validate_xlsx_container(content: bytes) -> None:
    if len(content) > MAX_XLSX_BYTES or not content.startswith(b"PK"):
        raise COESConnectorError("COES no devolvió un XLSX válido dentro del límite de tamaño.")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 5_000 or sum(member.file_size for member in members) > MAX_UNCOMPRESSED_BYTES:
                raise COESConnectorError("El XLSX COES excede los límites seguros de descompresión.")
            if any(".." in member.filename.replace("\\", "/").split("/") for member in members):
                raise COESConnectorError("El XLSX COES contiene una ruta interna no segura.")
    except zipfile.BadZipFile as exc:
        raise COESConnectorError("COES devolvió un contenedor XLSX corrupto.") from exc


def parse_daily_workbook(
    content: bytes, month: date, provenance: Provenance, downloaded_at: datetime
) -> dict[str, dict[str, Any]]:
    """Validate and aggregate exact COES plant names without substituting facilities."""
    _validate_xlsx_container(content)
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True, keep_links=False)
    except Exception as exc:
        raise COESConnectorError("No se pudo leer el XLSX oficial de COES.") from exc
    try:
        if EXPECTED_SHEET not in workbook.sheetnames:
            raise COESConnectorError(f"El XLSX COES no contiene la hoja {EXPECTED_SHEET!r}.")
        sheet = workbook[EXPECTED_SHEET]
        rows = sheet.iter_rows(values_only=True)
        headers: tuple[str, ...] = ()
        for candidate in islice(rows, 25):
            normalized = tuple(str(item or "").strip() for item in candidate)
            if normalized[: len(EXPECTED_HEADERS)] == EXPECTED_HEADERS:
                headers = normalized
                break
        if not headers:
            raise COESConnectorError("La hoja PRODUCCIÓN DIARIA no tiene las columnas oficiales esperadas.")
        totals: dict[str, float] = defaultdict(float)
        companies: dict[str, set[str]] = defaultdict(set)
        observed_dates: dict[str, set[date]] = defaultdict(set)
        for row in rows:
            if len(row) < 5:
                continue
            observed_on, company, plant, generation_type, total = row[:5]
            observed_date = _date(observed_on)
            plant_name = str(plant or "").strip()
            type_name = str(generation_type or "").strip()
            value = _number(total)
            if (
                observed_date is None
                or observed_date.year != month.year
                or observed_date.month != month.month
                or not plant_name
                or _normalize(type_name) != "SOLAR"
                or value is None
            ):
                continue
            totals[plant_name] += value
            observed_dates[plant_name].add(observed_date)
            if str(company or "").strip():
                companies[plant_name].add(str(company).strip())
        return {
            plant: {
                "companies": sorted(companies[plant]),
                "generation_type": "SOLAR",
                "generation_mwh": round(value, 6),
                "days_observed": len(observed_dates[plant]),
                "provenance": provenance,
                "downloaded_at": downloaded_at,
            }
            for plant, value in totals.items()
        }
    finally:
        workbook.close()


def _empty_capacity(source_url: str, limitation: str) -> COESCapacityReference:
    return COESCapacityReference(
        status="DATA_UNAVAILABLE",
        source_url=source_url,
        provenance=Provenance.UNAVAILABLE,
        limitations=[limitation],
    )


class COESConnector:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        request_interval_seconds: float = 0.75,
    ):
        self.settings = settings or get_settings()
        self.transport = transport
        self.request_interval_seconds = max(0.0, request_interval_seconds)
        self.cache = RawPayloadCache(self.settings.cache_dir, "coes-daily-generation")
        self.gisem_cache = RawPayloadCache(self.settings.cache_dir, "gisem-solar-capacity")
        self._request_lock = asyncio.Lock()
        self._last_request_at: float | None = None
        for url, hosts, label in (
            (self.settings.coes_export_url, {"www.coes.org.pe", "coes.org.pe"}, "COES"),
            (self.settings.gisem_solar_url, {"gisem.osinergmin.gob.pe"}, "GISEM"),
        ):
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in hosts:
                raise COESConnectorError(f"{label} debe usar su host HTTPS oficial.")

    async def _throttle(self) -> None:
        async with self._request_lock:
            if self._last_request_at is not None:
                remaining = self.request_interval_seconds - (time.monotonic() - self._last_request_at)
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_request_at = time.monotonic()

    async def _download_month(self, month: date):
        last_day = calendar.monthrange(month.year, month.month)[1]
        end = month.replace(day=last_day)
        descriptor = {"month": month.strftime("%Y-%m"), "indicator": 1, "dataset": "daily-generation", "v": 2}
        cache_key = self.cache.request_key(descriptor)
        cached = self.cache.get(cache_key, max_age=timedelta(hours=self.settings.cache_ttl_hours))
        if cached:
            return cached.content, cached.downloaded_at, Provenance.CACHED
        await self._throttle()
        params = {
            "fechaInicial": month.strftime("%d/%m/%Y"),
            "fechaFinal": end.strftime("%d/%m/%Y"),
            "indicador": "1",
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=False) as client:
                response = await client.get(self.settings.coes_export_url, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise COESConnectorError(f"La descarga mensual oficial de COES falló: {exc}") from exc
        content_type = response.headers.get("content-type", "").lower()
        if "spreadsheet" not in content_type and "excel" not in content_type and "octet-stream" not in content_type:
            raise COESConnectorError("COES no devolvió el XLSX oficial esperado.")
        _validate_xlsx_container(response.content)
        raw = self.cache.put(cache_key, response.content, suffix=".xlsx")
        return raw.content, raw.downloaded_at, Provenance.REAL

    async def _gisem_capacity(self) -> tuple[dict[str, COESCapacityReference], str | None]:
        descriptor = {"layer": 20, "dataset": "MapaSEIN_Operacion/Solar", "v": 1}
        cache_key = self.gisem_cache.request_key(descriptor)
        cached = self.gisem_cache.get(cache_key, max_age=timedelta(hours=self.settings.cache_ttl_hours))
        payload: dict[str, Any]
        provenance = Provenance.CACHED
        if cached:
            payload = json.loads(cached.content)
        else:
            params = {
                "where": "1=1",
                "outFields": "EMPRESA,NOMBRE,POT_INST,POT_EFEC,PUEST_OPER,DEPARTAMENTO,PROVINCIA,DISTRITO,ESTADO",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
            }
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=False) as client:
                    response = await client.get(self.settings.gisem_solar_url, params=params)
                    response.raise_for_status()
                    payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                return {}, f"GISEM no estuvo disponible para el cruce de potencia y coordenadas: {exc}"
            if payload.get("error"):
                return {}, f"GISEM rechazó la consulta de la capa Solar: {payload['error'].get('message', 'error no detallado')}"
            raw = self.gisem_cache.put(cache_key, json.dumps(payload, ensure_ascii=False).encode(), suffix=".json")
            provenance = Provenance.REAL
            payload = json.loads(raw.content)
        result: dict[str, COESCapacityReference] = {}
        for feature in payload.get("features", []):
            properties = feature.get("properties") or feature.get("attributes") or {}
            name = str(properties.get("NOMBRE") or "").strip()
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []
            installed = _number(properties.get("POT_INST"))
            effective = _number(properties.get("POT_EFEC"))
            if not name or installed is None or installed <= 0:
                continue
            longitude = _number(coordinates[0]) if len(coordinates) >= 2 else None
            latitude = _number(coordinates[1]) if len(coordinates) >= 2 else None
            key = _normalize(name)
            if key in result:
                continue
            result[key] = COESCapacityReference(
                status="READY",
                provider_name=name,
                installed_capacity_mw=installed,
                effective_capacity_mw=effective,
                latitude=latitude,
                longitude=longitude,
                source_url=self.settings.gisem_solar_url,
                provenance=provenance,
                limitations=["Cruce por nombre normalizado exacto; no se aceptan coincidencias difusas ni sustituciones."],
            )
        return result, None

    async def monthly_generation(self, request: COESMonthlyRequest) -> COESMonthlyResponse:
        start = date.fromisoformat(f"{request.start_month}-01")
        end = date.fromisoformat(f"{request.end_month}-01")
        month_list = list(_months(start, end))
        downloads = []
        for month in month_list:
            downloads.append((month, await self._download_month(month)))

        capacity_by_name, gisem_error = await self._gisem_capacity()
        parsed_months: list[tuple[date, datetime, Provenance, dict[str, dict[str, Any]]]] = []
        all_plants: set[str] = set()
        provenances: list[Provenance] = []
        downloaded_at: list[datetime] = []
        for month, (content, stamp, provenance) in downloads:
            provenances.append(provenance)
            downloaded_at.append(stamp)
            parsed = parse_daily_workbook(content, month, provenance, stamp)
            parsed_months.append((month, stamp, provenance, parsed))
            all_plants.update(parsed)

        by_plant: dict[str, dict[str, Any]] = {
            plant: {"companies": set(), "observations": [], "missing": []} for plant in all_plants
        }
        for month, stamp, provenance, parsed in parsed_months:
            expected_days = calendar.monthrange(month.year, month.month)[1]
            for plant in all_plants:
                entry = by_plant[plant]
                data = parsed.get(plant)
                if data is None:
                    entry["missing"].append(month.strftime("%Y-%m"))
                    entry["observations"].append(COESMonthlyObservation(
                        month=month.strftime("%Y-%m"),
                        generation_mwh=None,
                        days_expected=expected_days,
                        days_observed=0,
                        completeness_percent=0,
                        capacity_factor_percent=None,
                        provenance=Provenance.UNAVAILABLE,
                        downloaded_at=stamp,
                    ))
                    continue
                entry["companies"].update(data["companies"])
                capacity = capacity_by_name.get(_normalize(plant))
                capacity_factor = None
                if capacity and capacity.installed_capacity_mw:
                    capacity_factor = data["generation_mwh"] / (capacity.installed_capacity_mw * expected_days * 24) * 100
                entry["observations"].append(COESMonthlyObservation(
                    month=month.strftime("%Y-%m"),
                    generation_mwh=data["generation_mwh"],
                    days_expected=expected_days,
                    days_observed=data["days_observed"],
                    completeness_percent=round(data["days_observed"] / expected_days * 100, 3),
                    capacity_factor_percent=round(capacity_factor, 4) if capacity_factor is not None else None,
                    provenance=provenance,
                    downloaded_at=stamp,
                ))

        plants: list[COESPlantSeries] = []
        for plant, data in sorted(by_plant.items()):
            capacity = capacity_by_name.get(_normalize(plant))
            if capacity is None:
                reason = gisem_error or (
                    "La capa Solar de GISEM no contiene una coincidencia exacta para este nombre COES; no se sustituyó por otra central."
                )
                capacity = _empty_capacity(self.settings.gisem_solar_url, reason)
            plants.append(COESPlantSeries(
                plant=plant,
                companies=sorted(data["companies"]),
                generation_type="SOLAR",
                status="PARTIAL" if data["missing"] else ("READY" if data["observations"] else "DATA_UNAVAILABLE"),
                capacity_reference=capacity,
                observations=data["observations"],
                limitations=[
                    "TOTAL se usa directamente como energía diaria en MWh; no se integra potencia de 15 minutos.",
                    "El factor de planta solo se calcula con coincidencia exacta y potencia instalada positiva de GISEM.",
                ] + ([
                    f"La central no apareció con ese nombre exacto en: {', '.join(data['missing'])}; no se usó otra central como reemplazo."
                ] if data["missing"] else []),
            ))

        overall = Provenance.CACHED if provenances and all(item == Provenance.CACHED for item in provenances) else Provenance.REAL
        latest = max(downloaded_at) if downloaded_at else datetime.now(timezone.utc)
        return COESMonthlyResponse(
            generated_at=datetime.now(timezone.utc),
            provenance=overall,
            source_url=COES_SOURCE_URL,
            downloaded_at=latest,
            plants=plants,
            license=LICENSE_NOTE,
            methodology=(
                "Se solicita indicador=1 (medidores) al exportador COES, un mes por vez y con pausa entre pedidos. "
                "Se valida la hoja PRODUCCIÓN DIARIA, se filtra TIPO GENERACIÓN=SOLAR y se suma TOTAL por mes y "
                "GRUPO/CENTRAL. COES identifica la unidad del portal como MWh. El XLSX se conserva por SHA-256."
            ),
            limitations=[
                "Una ausencia en el archivo o en GISEM no demuestra ausencia de generación o infraestructura.",
                "Las etiquetas son mediciones publicadas por COES-SINAC, no estimaciones ni garantías futuras.",
                "La licencia abierta no está publicada; el archivo original no se redistribuye.",
            ],
        )
