"""Acceso trazable a metadatos CMR y archivos NASADEM protegidos por EDL."""

import asyncio
import hashlib
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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


class NasademConnectorError(RuntimeError):
    pass


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
    def __init__(self):
        self.settings = get_settings()
        self.cache_dir = self.settings.cache_dir / "nasadem"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
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

    async def _download(self, granule: TerrainGranule) -> tuple[Path, Provenance]:
        target = self.cache_dir / f"{granule.title}.zip"
        if target.exists() and target.stat().st_size > 0:
            return target, Provenance.CACHED
        if not self.settings.earthdata_token:
            raise NasademConnectorError("EARTHDATA_TOKEN no está configurado; el raster NASADEM requiere Earthdata Login.")
        temporary = target.with_suffix(".zip.part")
        try:
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                async with client.stream(
                    "GET",
                    granule.data_url,
                    headers={"Authorization": f"Bearer {self.settings.earthdata_token}"},
                ) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as output:
                        async for chunk in response.aiter_bytes():
                            output.write(chunk)
            if not zipfile.is_zipfile(temporary):
                raise NasademConnectorError("Earthdata no devolvió un archivo ZIP NASADEM válido.")
            temporary.replace(target)
        except (httpx.HTTPError, OSError, zipfile.BadZipFile) as exc:
            if temporary.exists():
                temporary.unlink()
            raise NasademConnectorError(f"No se pudo descargar el raster NASADEM autenticado: {exc}") from exc
        return target, Provenance.REAL

    async def point(self, point: Point) -> TerrainSiteResult:
        located = [await self._granule(product, point) for product in PRODUCTS]
        granules = [item[0] for item in located]
        limitations = [
            "NASADEM representa la superficie del terreno en una grilla de aproximadamente 30 m y no sustituye un levantamiento topográfico de ingeniería.",
            "La altura HGT es ortométrica respecto al geoide EGM96; no debe mezclarse con altura elipsoidal sin transformación explícita.",
        ]
        try:
            hgt_archive, hgt_provenance = await self._download(granules[0])
            sc_archive, sc_provenance = await self._download(granules[1])
            metrics = read_metrics(hgt_archive, sc_archive, granules[0].tile_id, point)
            provenance = Provenance.CACHED if hgt_provenance == sc_provenance == Provenance.CACHED else Provenance.REAL
            status = "READY" if all(value is not None for value in (metrics.elevation_m, metrics.slope_degrees)) else "PARTIAL"
            if metrics.aspect_degrees is None:
                limitations.append("La orientación igual a 0° no se informa porque el producto también usa 0 para agua; se requiere validar la máscara SWB.")
        except NasademConnectorError as exc:
            metrics = TerrainMetrics()
            provenance = Provenance.UNAVAILABLE
            status = "METADATA_ONLY"
            limitations.append(str(exc))
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
        ready = sum(site.status == "READY" for site in results)
        note = (
            f"{ready} de {len(results)} ubicaciones tienen métricas raster. "
            "Las demás conservan metadatos y vista previa oficiales sin convertir la ausencia de credenciales en datos ficticios."
        )
        return TerrainResponse(
            generated_at=datetime.now(timezone.utc),
            sites=results,
            note=note,
        )
