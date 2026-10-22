"""Acceso trazable a metadatos CMR y archivos NASADEM protegidos por EDL."""

import asyncio
import hashlib
import json
import logging
import os
import zipfile
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

import httpx

from ...core.config import get_settings
from ...schemas.analysis import Point, Provenance
from ...schemas.terrain import (
    TerrainGranule,
    TerrainMetrics,
    TerrainResponse,
    TerrainSiteResult,
)

PRODUCTS = ("NASADEM_HGT", "NASADEM_SC")
DOI_BY_PRODUCT = {
    "NASADEM_HGT": "https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001",
    "NASADEM_SC": "https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_SC.001",
}
GRID_SIZE = 3601
DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_TIMEOUT = httpx.Timeout(connect=30, read=90, write=30, pool=30)
EARTHDATA_DOWNLOAD_HOST = "data.lpdaac.earthdatacloud.nasa.gov"
EARTHDATA_DOWNLOAD_PREFIX = "/lp-prod-protected/"
LOGGER = logging.getLogger(__name__)


class NasademConnectorError(RuntimeError):
    pass


class NasademAccessError(NasademConnectorError):
    """Earthdata rechazó la credencial; no es un fallo transitorio de descarga."""


def _is_valid_archive(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0 and zipfile.is_zipfile(path)
    except OSError:
        return False


def _validate_data_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != EARTHDATA_DOWNLOAD_HOST
        or not parsed.path.startswith(EARTHDATA_DOWNLOAD_PREFIX)
    ):
        raise NasademConnectorError("CMR devolvió una URL de descarga NASADEM fuera del host LP DAAC permitido.")


def tile_origin(tile_id: str) -> tuple[int, int]:
    """Return the south and west integer bounds encoded by a NASADEM tile id."""
    if len(tile_id) != 7 or tile_id[0] not in "ns" or tile_id[3] not in "ew":
        raise ValueError(f"Identificador NASADEM inválido: {tile_id}")
    latitude = int(tile_id[1:3]) * (1 if tile_id[0] == "n" else -1)
    longitude = int(tile_id[4:7]) * (1 if tile_id[3] == "e" else -1)
    return latitude, longitude


def grid_index(tile_id: str, latitude: float, longitude: float) -> tuple[int, int]:
    """Convert WGS84 lon/lat to the nearest NASADEM post in a 1° tile."""
    south, west = tile_origin(tile_id)
    north = south + 1
    if not (south <= latitude <= north and west <= longitude <= west + 1):
        raise ValueError("El punto no se encuentra dentro del mosaico NASADEM localizado.")
    row = round((north - latitude) * (GRID_SIZE - 1))
    column = round((longitude - west) * (GRID_SIZE - 1))
    return min(max(row, 0), GRID_SIZE - 1), min(max(column, 0), GRID_SIZE - 1)


def _decode_two_bytes(raw: bytes, *, signed: bool) -> int:
    if len(raw) != 2:
        raise NasademConnectorError("El archivo NASADEM terminó antes de la celda solicitada.")
    return int.from_bytes(raw, byteorder="big", signed=signed)


def _select_member(archive: zipfile.ZipFile, metric: str) -> str:
    candidates = [name for name in archive.namelist() if not name.endswith("/")]
    lowered = {name: Path(name).name.lower() for name in candidates}
    if metric == "elevation":
        matches = [name for name, base in lowered.items() if base.endswith(".hgt")]
    else:
        matches = [name for name, base in lowered.items() if metric in base and not base.endswith((".xml", ".txt"))]
    if len(matches) != 1:
        raise NasademConnectorError(
            f"No se pudo identificar de forma unívoca la capa {metric} dentro del archivo NASADEM."
        )
    return matches[0]


def _read_cell(archive_path: Path, member: str, row: int, column: int, *, signed: bool) -> int:
    offset = (row * GRID_SIZE + column) * 2
    with zipfile.ZipFile(archive_path) as archive, archive.open(member) as raster:
        raster.seek(offset)
        return _decode_two_bytes(raster.read(2), signed=signed)


def read_metrics(hgt_archive: Path, sc_archive: Path, tile_id: str, point: Point) -> TerrainMetrics:
    row, column = grid_index(tile_id, point.latitude, point.longitude)
    with zipfile.ZipFile(hgt_archive) as archive:
        elevation_member = _select_member(archive, "elevation")
    with zipfile.ZipFile(sc_archive) as archive:
        slope_member = _select_member(archive, "slope")
        aspect_member = _select_member(archive, "aspect")

    elevation = _read_cell(hgt_archive, elevation_member, row, column, signed=True)
    slope_raw = _read_cell(sc_archive, slope_member, row, column, signed=False)
    aspect_raw = _read_cell(sc_archive, aspect_member, row, column, signed=False)
    if elevation < -32767:
        elevation_value = None
    else:
        elevation_value = float(elevation)
    slope = slope_raw / 100 if 0 <= slope_raw <= 9000 else None
    aspect = aspect_raw / 100 if 0 < aspect_raw <= 36000 else None
    return TerrainMetrics(
        elevation_m=elevation_value,
        slope_degrees=slope,
        aspect_degrees=aspect,
        aspect_cardinal=_aspect_cardinal(aspect),
    )


def _aspect_cardinal(aspect: float | None) -> str | None:
    if aspect is None:
        return None
    directions = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
    return directions[round(aspect / 45) % 8]


class NasademConnector:
    _download_locks: ClassVar[dict[tuple[int, str], asyncio.Lock]] = {}
    _inflight_downloads: ClassVar[dict[tuple[int, str], asyncio.Task[tuple[Path, Provenance]]]] = {}
    _access_failures: ClassVar[dict[tuple[str, str], str]] = {}

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = get_settings()
        self.cache_dir = self.settings.cache_dir / "nasadem"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.transport = transport

    def _metadata_cache(self, product: str, latitude: float, longitude: float) -> Path:
        key = hashlib.sha256(f"{product}:001:{longitude:.6f},{latitude:.6f}".encode()).hexdigest()
        return self.cache_dir / f"cmr-{key}.json"

    async def _cmr_payload(self, product: str, point: Point) -> tuple[dict[str, Any], Provenance]:
        cache = self._metadata_cache(product, point.latitude, point.longitude)
        now = datetime.now(timezone.utc)
        if cache.exists() and now - datetime.fromtimestamp(cache.stat().st_mtime, timezone.utc) < timedelta(days=7):
            return json.loads(cache.read_text(encoding="utf-8")), Provenance.CACHED
        params = {
            "short_name": product,
            "version": "001",
            "point": f"{point.longitude},{point.latitude}",
            "page_size": "1",
        }
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, transport=self.transport) as client:
                response = await client.get(f"{self.settings.cmr_api_base}/granules.json", params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NasademConnectorError(f"La consulta al catálogo CMR de NASA falló: {exc}") from exc
        cache.write_text(json.dumps(payload), encoding="utf-8")
        return payload, Provenance.REAL

    async def _granule(self, product: str, point: Point) -> tuple[TerrainGranule, Provenance]:
        payload, metadata_provenance = await self._cmr_payload(product, point)
        entries = payload.get("feed", {}).get("entry", [])
        if not entries:
            raise NasademConnectorError(f"CMR no localizó un gránulo {product}.001 para el punto solicitado.")
        entry = entries[0]
        links = entry.get("links", [])
        data_url = next((item.get("href") for item in links if "data#" in item.get("rel", "") and str(item.get("href", "")).startswith("https://")), None)
        preview_url = next((item.get("href") for item in links if "browse#" in item.get("rel", "") and str(item.get("href", "")).startswith("https://")), None)
        title = str(entry.get("title", ""))
        tile_id = title.rsplit("_", 1)[-1]
        boxes = entry.get("boxes", [])
        if not data_url or not boxes:
            raise NasademConnectorError("CMR devolvió metadatos NASADEM incompletos.")
        _validate_data_url(str(data_url))
        south, west, north, east = (float(value) for value in str(boxes[0]).split())
        granule = TerrainGranule(
            short_name=product,
            granule_id=str(entry.get("id", "")),
            title=title,
            tile_id=tile_id,
            bounding_box=(west, south, east, north),
            updated_at=datetime.fromisoformat(str(entry["updated"]).replace("Z", "+00:00")),
            data_url=str(data_url),
            preview_url=str(preview_url) if preview_url else None,
            doi_url=DOI_BY_PRODUCT[product],
            catalogue_url=f"https://search.earthdata.nasa.gov/search/granules?p={entry.get('collection_concept_id', '')}",
        )
        return granule, metadata_provenance

    def _target(self, granule: TerrainGranule) -> Path:
        title = granule.title
        if not title or Path(title).name != title or title in (".", ".."):
            raise NasademConnectorError("El título NASADEM no es un nombre de caché seguro.")
        return self.cache_dir / f"{title}.zip"

    def _token_fingerprint(self) -> str:
        token = self.settings.earthdata_token or ""
        return hashlib.sha256(token.encode()).hexdigest()[:12]

    def _access_key(self, granule: TerrainGranule) -> tuple[str, str]:
        return str(self._target(granule).resolve()), self._token_fingerprint()

    @classmethod
    def _runtime_key(cls, target: Path) -> tuple[int, str]:
        return id(asyncio.get_running_loop()), str(target.resolve())

    @classmethod
    def _download_lock(cls, target: Path) -> asyncio.Lock:
        key = cls._runtime_key(target)
        lock = cls._download_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            cls._download_locks[key] = lock
        return lock

    async def _stream_to_partial(self, granule: TerrainGranule, temporary: Path) -> None:
        offset = temporary.stat().st_size if temporary.exists() else 0
        _validate_data_url(granule.data_url)
        headers = {
            "Authorization": f"Bearer {self.settings.earthdata_token}",
            "Accept-Encoding": "identity",
        }
        if offset:
            headers["Range"] = f"bytes={offset}-"

        async with httpx.AsyncClient(
            timeout=DOWNLOAD_TIMEOUT,
            follow_redirects=True,
            transport=self.transport,
        ) as client:
            async with client.stream("GET", granule.data_url, headers=headers) as response:
                if response.status_code in (401, 403):
                    raise NasademAccessError(
                        f"Earthdata rechazó el acceso al raster NASADEM con HTTP {response.status_code}."
                    )
                if response.status_code == 416:
                    if offset and await asyncio.to_thread(_is_valid_archive, temporary):
                        return
                    if temporary.exists():
                        temporary.unlink()
                    raise NasademConnectorError(
                        "Earthdata rechazó el rango guardado; la siguiente tentativa reiniciará la descarga."
                    )
                response.raise_for_status()

                if response.status_code == 206:
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith(f"bytes {offset}-"):
                        raise NasademConnectorError(
                            "Earthdata devolvió un Content-Range incompatible con el archivo parcial."
                        )
                    mode = "ab" if offset else "wb"
                else:
                    # Algunos servidores ignoran Range. Un 200 reinicia de forma segura el parcial.
                    mode = "wb"

                with temporary.open(mode) as output:
                    async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                        if chunk:
                            output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())

    async def _download(self, granule: TerrainGranule) -> tuple[Path, Provenance]:
        target = self._target(granule)
        async with self._download_lock(target):
            if await asyncio.to_thread(_is_valid_archive, target):
                return target, Provenance.CACHED
            if not self.settings.earthdata_token:
                raise NasademAccessError(
                    "EARTHDATA_TOKEN no está configurado; el raster NASADEM requiere Earthdata Login."
                )

            temporary = target.with_suffix(".zip.part")
            last_error: Exception | None = None
            for attempt in range(DOWNLOAD_ATTEMPTS):
                try:
                    await self._stream_to_partial(granule, temporary)
                    if not await asyncio.to_thread(_is_valid_archive, temporary):
                        if temporary.exists():
                            temporary.unlink()
                        raise NasademConnectorError(
                            "Earthdata no devolvió un archivo ZIP NASADEM válido; se reiniciará la descarga."
                        )
                    await asyncio.to_thread(temporary.replace, target)
                    return target, Provenance.REAL
                except NasademAccessError:
                    raise
                except asyncio.CancelledError:
                    # El parcial se conserva para que la siguiente tarea continúe con Range.
                    raise
                except (httpx.HTTPError, OSError, NasademConnectorError) as exc:
                    last_error = exc
                    if attempt + 1 < DOWNLOAD_ATTEMPTS:
                        await asyncio.sleep(0.25 * (2**attempt))

            raise NasademConnectorError(
                f"No se pudo completar el raster NASADEM tras {DOWNLOAD_ATTEMPTS} intentos: {last_error}"
            ) from last_error

    @classmethod
    def _finish_background_download(
        cls,
        task: asyncio.Task[tuple[Path, Provenance]],
        runtime_key: tuple[int, str],
        access_key: tuple[str, str],
    ) -> None:
        if cls._inflight_downloads.get(runtime_key) is task:
            cls._inflight_downloads.pop(runtime_key, None)
        if task.cancelled():
            return
        try:
            task.result()
            cls._access_failures.pop(access_key, None)
        except NasademAccessError as exc:
            cls._access_failures[access_key] = str(exc)
            LOGGER.warning("NASADEM no tiene acceso al gránulo %s", Path(runtime_key[1]).name)
        except Exception as exc:  # noqa: BLE001 - la tarea no debe dejar excepciones sin consumir
            LOGGER.warning("Descarga NASADEM en segundo plano incompleta: %s", exc)

    def _schedule_download(self, granule: TerrainGranule) -> asyncio.Task[tuple[Path, Provenance]] | None:
        target = self._target(granule)
        if _is_valid_archive(target) or not self.settings.earthdata_token:
            return None
        access_key = self._access_key(granule)
        if access_key in self._access_failures:
            return None
        runtime_key = self._runtime_key(target)
        current = self._inflight_downloads.get(runtime_key)
        if current and not current.done():
            return current
        task = asyncio.create_task(self._download(granule), name=f"nasadem:{granule.short_name}:{granule.tile_id}")
        self._inflight_downloads[runtime_key] = task
        task.add_done_callback(
            lambda completed: self._finish_background_download(completed, runtime_key, access_key)
        )
        return task

    async def _located_granules(self, point: Point) -> list[TerrainGranule]:
        located = await asyncio.gather(*(self._granule(product, point) for product in PRODUCTS))
        return [item[0] for item in located]

    @staticmethod
    def _base_limitations() -> list[str]:
        return [
            "NASADEM representa la superficie del terreno en una grilla de aproximadamente 30 m y no sustituye un levantamiento topográfico de ingeniería.",
            "La altura HGT es ortométrica respecto al geoide EGM96; no debe mezclarse con altura elipsoidal sin transformación explícita.",
        ]

    async def point(self, point: Point) -> TerrainSiteResult:
        granules = await self._located_granules(point)
        limitations = self._base_limitations()
        targets = [self._target(granule) for granule in granules]

        if all(_is_valid_archive(target) for target in targets):
            metrics = await asyncio.to_thread(read_metrics, targets[0], targets[1], granules[0].tile_id, point)
            provenance = Provenance.CACHED
            status = "READY" if all(value is not None for value in (metrics.elevation_m, metrics.slope_degrees)) else "PARTIAL"
            if metrics.aspect_degrees is None:
                limitations.append("La orientación igual a 0° no se informa porque el producto también usa 0 para agua; se requiere validar la máscara SWB.")
        elif not self.settings.earthdata_token:
            metrics = TerrainMetrics()
            provenance = Provenance.UNAVAILABLE
            status = "METADATA_ONLY"
            limitations.append("EARTHDATA_TOKEN no está configurado; el raster NASADEM requiere Earthdata Login.")
        else:
            access_errors = [
                self._access_failures[self._access_key(granule)]
                for granule in granules
                if self._access_key(granule) in self._access_failures
            ]
            if access_errors:
                metrics = TerrainMetrics()
                provenance = Provenance.UNAVAILABLE
                status = "METADATA_ONLY"
                limitations.extend(dict.fromkeys(access_errors))
            else:
                for granule, target in zip(granules, targets, strict=True):
                    if not _is_valid_archive(target):
                        self._schedule_download(granule)
                metrics = TerrainMetrics()
                provenance = Provenance.UNAVAILABLE
                status = "PENDING"
                limitations.append(
                    "La tesela fue localizada y su descarga autenticada continúa en segundo plano; vuelva a ejecutar para leer las métricas cacheadas."
                )
        return TerrainSiteResult(
            location=point,
            status=status,
            metrics=metrics,
            granules=granules,
            provenance=provenance,
            limitations=limitations,
        )

    async def points(self, sites: list[Point]) -> TerrainResponse:
        results = list(await asyncio.gather(*(self.point(site) for site in sites)))
        ready = sum(site.status in ("READY", "PARTIAL") for site in results)
        pending = sum(site.status == "PENDING" for site in results)
        metadata_only = sum(site.status == "METADATA_ONLY" for site in results)
        note = (
            f"{ready} de {len(results)} ubicaciones tienen métricas raster; "
            f"{pending} descargan teselas en segundo plano y {metadata_only} permanecen solo con metadatos. "
            "Ningún estado pendiente o sin acceso se convierte en datos ficticios."
        )
        return TerrainResponse(
            generated_at=datetime.now(timezone.utc),
            sites=results,
            note=note,
        )

    async def prefetch(self, points: Sequence[Point]) -> None:
        """Localiza teselas y dispara descargas deduplicadas sin esperar a que terminen."""

        async def schedule(point: Point) -> None:
            granules = await self._located_granules(point)
            if not self.settings.earthdata_token:
                return
            for granule in granules:
                self._schedule_download(granule)

        await asyncio.gather(*(schedule(point) for point in points))
