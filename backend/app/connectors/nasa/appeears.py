"""Secure asynchronous AppEEARS tasks for vegetation and surface-water layers."""

import json
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ...core.config import Settings, get_settings
from ...geospatial.geometry import GeometryValidationError, inspect_geometry
from ...schemas.analysis import Provenance
from ...schemas.data_sources import (
    AppEEARSAreaTaskRequest,
    AppEEARSBundleFile,
    AppEEARSBundleResponse,
    AppEEARSPointTaskRequest,
    AppEEARSTaskResponse,
)
from ..cache import RawPayloadCache

LAYERS = (
    {"product": "MOD13Q1.061", "layer": "_250m_16_days_NDVI"},
    {"product": "MOD13Q1.061", "layer": "_250m_16_days_EVI"},
    {"product": "MOD13Q1.061", "layer": "_250m_16_days_VI_Quality"},
    {"product": "MOD44W.061", "layer": "water_mask"},
    {"product": "MOD44W.061", "layer": "water_mask_QA"},
)
TASK_ID = re.compile(r"^[0-9a-fA-F-]{20,64}$")
FILE_ID = re.compile(r"^[0-9a-fA-F-]{20,64}$")
TIMEOUT = httpx.Timeout(connect=20, read=45, write=30, pool=20)
APPEEARS_DOWNLOAD_HOSTS = frozenset({"d2v96idf0qj40l.cloudfront.net"})


class AppEEARSConnectorError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppEEARSFilePayload:
    content: bytes
    file_name: str
    file_type: str
    sha256: str
    provenance: Provenance
    downloaded_at: datetime


class AppEEARSConnector:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "appeears")
        parsed = urlparse(self.settings.appeears_api_base)
        if parsed.scheme != "https" or parsed.hostname != "appeears.earthdatacloud.nasa.gov":
            raise AppEEARSConnectorError("AppEEARS debe usar el host HTTPS oficial de NASA.")

    @property
    def configured(self) -> bool:
        return bool(self.settings.earthdata_username and self.settings.earthdata_password)

    @staticmethod
    def _date(value) -> str:
        return value.strftime("%m-%d-%Y")

    @staticmethod
    def _clean_provider_payload(payload: Any) -> Any:
        """Remove account identifiers before the provider response reaches disk."""
        if isinstance(payload, dict):
            return {
                key: AppEEARSConnector._clean_provider_payload(value)
                for key, value in payload.items()
                if key not in {"user_id", "token", "access_token", "refresh_token"}
            }
        if isinstance(payload, list):
            return [AppEEARSConnector._clean_provider_payload(item) for item in payload]
        return payload

    async def _login(self, client: httpx.AsyncClient) -> tuple[str, datetime]:
        if not self.configured:
            raise AppEEARSConnectorError("EARTHDATA_USERNAME y EARTHDATA_PASSWORD no están configurados.")
        try:
            response = await client.post(
                f"{self.settings.appeears_api_base}/login",
                auth=httpx.BasicAuth(self.settings.earthdata_username or "", self.settings.earthdata_password or ""),
                content=b"",
            )
            response.raise_for_status()
            payload = response.json()
            token = str(payload["token"])
            expiration = datetime.fromisoformat(str(payload["expiration"]).replace("Z", "+00:00"))
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise AppEEARSConnectorError(f"AppEEARS rechazó o no pudo completar el inicio de sesión: {exc}") from exc
        return token, expiration

    async def _logout(self, client: httpx.AsyncClient, token: str | None) -> None:
        if not token:
            return
        try:
            await client.post(
                f"{self.settings.appeears_api_base}/logout",
                headers={"Authorization": f"Bearer {token}"},
                content=b"",
            )
        except httpx.HTTPError:
            # El token se elimina de memoria aunque el proveedor ya lo haya vencido.
            pass

    async def _authorized_json(self, method: str, path: str, *, json_body: Any = None) -> tuple[Any, datetime]:
        token: str | None = None
        expiration: datetime | None = None
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=False) as client:
            try:
                token, expiration = await self._login(client)
                for attempt in range(2):
                    if expiration <= datetime.now(timezone.utc) + timedelta(seconds=30):
                        await self._logout(client, token)
                        token, expiration = await self._login(client)
                    response = await client.request(
                        method,
                        f"{self.settings.appeears_api_base}{path}",
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                        json=json_body,
                    )
                    if response.status_code == 403 and attempt == 0:
                        await self._logout(client, token)
                        token, expiration = await self._login(client)
                        continue
                    response.raise_for_status()
                    return response.json(), datetime.now(timezone.utc)
                raise AppEEARSConnectorError("AppEEARS rechazó el token renovado.")
            except AppEEARSConnectorError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                raise AppEEARSConnectorError(f"La operación AppEEARS falló: {exc}") from exc
            finally:
                await self._logout(client, token)
                token = None

    async def _authorized_file(self, path: str) -> tuple[bytes, datetime]:
        token: str | None = None
        expiration: datetime | None = None
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=False) as client:
            try:
                token, expiration = await self._login(client)
                for attempt in range(2):
                    if expiration <= datetime.now(timezone.utc) + timedelta(seconds=30):
                        await self._logout(client, token)
                        token, expiration = await self._login(client)
                    response = await client.get(
                        f"{self.settings.appeears_api_base}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if response.status_code == 403 and attempt == 0:
                        await self._logout(client, token)
                        token, expiration = await self._login(client)
                        continue
                    if response.is_redirect:
                        location = response.headers.get("location", "")
                        parsed = urlparse(location)
                        trusted = parsed.scheme == "https" and parsed.hostname and (
                            parsed.hostname in APPEEARS_DOWNLOAD_HOSTS
                            or parsed.hostname.endswith(".earthdatacloud.nasa.gov")
                            or parsed.hostname.endswith(".nasa.gov")
                        )
                        if not trusted:
                            raise AppEEARSConnectorError("AppEEARS devolvió una redirección de descarga fuera de hosts permitidos.")
                        # The Earthdata token is deliberately not forwarded to object storage.
                        response = await client.get(location, headers={})
                    response.raise_for_status()
                    return response.content, datetime.now(timezone.utc)
                raise AppEEARSConnectorError("AppEEARS rechazó el token renovado.")
            except AppEEARSConnectorError:
                raise
            except httpx.HTTPError as exc:
                raise AppEEARSConnectorError(f"La descarga AppEEARS falló: {exc}") from exc
            finally:
                await self._logout(client, token)
                token = None

    @staticmethod
    def _unavailable(task_type: str | None = None) -> AppEEARSTaskResponse:
        return AppEEARSTaskResponse(
            status="DATA_UNAVAILABLE",
            task_type=task_type,
            checked_at=datetime.now(timezone.utc),
            layers=[f"{item['product']}:{item['layer']}" for item in LAYERS],
            provenance=Provenance.UNAVAILABLE,
            source_url="https://appeears.earthdatacloud.nasa.gov/api/",
            limitations=["EARTHDATA_USERNAME y EARTHDATA_PASSWORD deben configurarse fuera del repositorio."],
        )

    async def _submit(self, payload: dict[str, Any]) -> AppEEARSTaskResponse:
        if not self.configured:
            return self._unavailable(payload["task_type"])
        provider_payload, checked_at = await self._authorized_json("POST", "/task", json_body=payload)
        provider_payload = self._clean_provider_payload(provider_payload)
        task_id = str(provider_payload.get("task_id", ""))
        if not TASK_ID.fullmatch(task_id):
            raise AppEEARSConnectorError("AppEEARS no devolvió un task_id válido.")
        cache_key = self.cache.request_key({"task_id": task_id, "kind": "submission"})
        self.cache.put(cache_key, json.dumps(provider_payload, sort_keys=True).encode(), suffix=".json")
        return AppEEARSTaskResponse(
            task_id=task_id,
            status="PENDING",
            provider_status=str(provider_payload.get("status", "pending")),
            task_type=payload["task_type"],
            submitted_at=checked_at,
            checked_at=checked_at,
            layers=[f"{item['product']}:{item['layer']}" for item in LAYERS],
            provenance=Provenance.REAL,
            source_url=f"{self.settings.appeears_api_base}/task/{task_id}",
            limitations=["PENDING significa que NASA aceptó la tarea; todavía no existen resultados descargables."],
        )

    async def submit_points(self, request: AppEEARSPointTaskRequest) -> AppEEARSTaskResponse:
        payload = {
            "task_type": "point",
            "task_name": request.task_name,
            "params": {
                "dates": [{"startDate": self._date(request.start_date), "endDate": self._date(request.end_date)}],
                "layers": list(LAYERS),
                "coordinates": [
                    {
                        "latitude": point.latitude,
                        "longitude": point.longitude,
                        "id": point.label or f"p{index + 1}",
                    }
                    for index, point in enumerate(request.points)
                ],
            },
        }
        return await self._submit(payload)

    async def submit_area(self, request: AppEEARSAreaTaskRequest) -> AppEEARSTaskResponse:
        try:
            inspected = inspect_geometry(request.geometry)
        except GeometryValidationError as exc:
            raise AppEEARSConnectorError(str(exc)) from exc
        if inspected.geometry_type != "Polygon":
            raise AppEEARSConnectorError("Las tareas de área AppEEARS requieren un Polygon GeoJSON válido.")
        feature_collection = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": request.geometry, "properties": {}}],
            "fileName": request.task_name,
        }
        payload = {
            "task_type": "area",
            "task_name": request.task_name,
            "params": {
                "dates": [{"startDate": self._date(request.start_date), "endDate": self._date(request.end_date)}],
                "layers": list(LAYERS),
                "geo": feature_collection,
                "output": {"format": {"type": "geotiff", "filename_date": "calendar"}, "projection": "geographic"},
            },
        }
        return await self._submit(payload)

    async def task(self, task_id: str) -> AppEEARSTaskResponse:
        if not TASK_ID.fullmatch(task_id):
            raise AppEEARSConnectorError("task_id de AppEEARS inválido.")
        if not self.configured:
            return self._unavailable()
        provider_payload, checked_at = await self._authorized_json("GET", f"/task/{task_id}")
        provider_payload = self._clean_provider_payload(provider_payload)
        cache_key = self.cache.request_key({"task_id": task_id, "kind": "status"})
        cached = self.cache.put(cache_key, json.dumps(provider_payload, sort_keys=True).encode(), suffix=".json")
        provider_status = str(provider_payload.get("status", "unknown")).lower()
        status: str
        if provider_status == "done":
            status = "READY"
        elif provider_status in {"pending", "processing", "queued"}:
            status = "PENDING"
        else:
            status = "FAILED"
        return AppEEARSTaskResponse(
            task_id=task_id,
            status=status,
            provider_status=provider_status,
            task_type=provider_payload.get("task_type"),
            submitted_at=provider_payload.get("created"),
            checked_at=checked_at,
            layers=[f"{item['product']}:{item['layer']}" for item in LAYERS],
            provenance=Provenance.REAL,
            source_url=f"{self.settings.appeears_api_base}/task/{task_id}",
            limitations=[
                "Los metadatos de estado se cachean sin user_id ni credenciales.",
                f"Respuesta oficial preservada por SHA-256 desde {cached.downloaded_at.isoformat()}.",
            ],
        )

    async def bundle(self, task_id: str) -> AppEEARSBundleResponse:
        if not TASK_ID.fullmatch(task_id):
            raise AppEEARSConnectorError("task_id de AppEEARS inválido.")
        if not self.configured:
            raise AppEEARSConnectorError("EARTHDATA_USERNAME y EARTHDATA_PASSWORD no están configurados.")
        provider_payload, checked_at = await self._authorized_json("GET", f"/bundle/{task_id}")
        provider_payload = self._clean_provider_payload(provider_payload)
        files = [AppEEARSBundleFile(**item) for item in provider_payload.get("files", [])]
        cache_key = self.cache.request_key({"task_id": task_id, "kind": "bundle"})
        self.cache.put(cache_key, json.dumps(provider_payload, sort_keys=True).encode(), suffix=".json")
        return AppEEARSBundleResponse(
            task_id=task_id,
            files=files,
            checked_at=checked_at,
            provenance=Provenance.REAL,
            source_url=f"{self.settings.appeears_api_base}/bundle/{task_id}",
            limitations=[
                "Este contrato enumera archivos y checksums oficiales; la descarga binaria autenticada se mantiene separada.",
                "Los archivos derivados deben conservar producto, versión, QA, escala, nodata y procedencia.",
            ],
        )

    async def download(self, task_id: str, file_id: str) -> AppEEARSFilePayload:
        if not TASK_ID.fullmatch(task_id) or not FILE_ID.fullmatch(file_id):
            raise AppEEARSConnectorError("task_id o file_id de AppEEARS inválido.")
        bundle = await self.bundle(task_id)
        metadata = next((item for item in bundle.files if item.file_id == file_id), None)
        if metadata is None:
            raise AppEEARSConnectorError("El file_id no pertenece al bundle solicitado.")
        safe_name = Path(metadata.file_name).name
        if (
            safe_name != metadata.file_name
            or safe_name in {"", ".", ".."}
            or any(character in safe_name for character in {'"', "\r", "\n"})
        ):
            raise AppEEARSConnectorError("AppEEARS devolvió un nombre de archivo no seguro.")
        cache_key = self.cache.request_key({"task_id": task_id, "file_id": file_id, "sha256": metadata.sha256})
        cached = self.cache.get(cache_key)
        if cached:
            if hashlib.sha256(cached.content).hexdigest() != metadata.sha256:
                raise AppEEARSConnectorError("El archivo AppEEARS cacheado no coincide con el checksum oficial.")
            return AppEEARSFilePayload(cached.content, safe_name, metadata.file_type, metadata.sha256,
                Provenance.CACHED, cached.downloaded_at)
        content, downloaded_at = await self._authorized_file(f"/bundle/{task_id}/{file_id}")
        if hashlib.sha256(content).hexdigest() != metadata.sha256:
            raise AppEEARSConnectorError("La descarga AppEEARS no coincide con el checksum oficial.")
        suffix = Path(safe_name).suffix.lower()
        if suffix not in {".csv", ".json", ".txt", ".xml", ".tif", ".tiff", ".nc"}:
            suffix = ".bin"
        raw = self.cache.put(cache_key, content, suffix=suffix)
        return AppEEARSFilePayload(raw.content, safe_name, metadata.file_type, metadata.sha256,
            Provenance.REAL, downloaded_at)
