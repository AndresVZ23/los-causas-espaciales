"""Maqueta en bloques de un lugar real: relieve de Copernicus DEM GLO-30 y cobertura de ESA WorldCover (ADR-047).

La maqueta es una cuadrícula regular en grados alrededor de un centro. Cada celda toma la elevación y la clase de
cobertura del píxel más cercano a su centro, sin interpolar. La altura en bloques se mide sobre el punto más bajo y se
exagera por un factor declarado para que el relieve se lea; la pendiente se calcula antes, con las elevaciones reales.

`build_grid` y `place` son funciones puras. `read_window` consulta las teselas públicas con el lector común de COG.
"""

import base64
import math
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import numpy as np

from ..connectors.cache import RawPayloadCache
from ..connectors.cog import CogMissing, CogReader
from ..connectors.copernicus.dem import BUCKET as DEM_BUCKET
from ..connectors.copernicus.dem import tile_name as dem_tile
from ..connectors.esa.worldcover import BUCKET as COVER_BUCKET
from ..connectors.esa.worldcover import VERSION, YEAR
from ..connectors.esa.worldcover import tile_name as cover_tile
from ..core.config import get_settings

METERS_PER_DEGREE = 111_320.0
WATER = 80
MAX_BLOCKS = 65_535
TIMEOUT = httpx.Timeout(connect=20, read=120, write=20, pool=20)


@dataclass(frozen=True)
class Frame:
    """Cuadrícula de la maqueta: centros de celda por filas de norte a sur y columnas de oeste a este."""

    latitude: float
    longitude: float
    size_km: float
    grid: int

    @property
    def cell_m(self) -> float:
        return self.size_km * 1000 / self.grid

    @property
    def half_degrees(self) -> tuple[float, float]:
        half_m = self.size_km * 500
        return half_m / METERS_PER_DEGREE, half_m / (METERS_PER_DEGREE * math.cos(math.radians(self.latitude)))

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        half_lat, half_lon = self.half_degrees
        return (round(self.longitude - half_lon, 6), round(self.latitude - half_lat, 6), round(self.longitude + half_lon, 6), round(self.latitude + half_lat, 6))

    def centers(self) -> tuple[np.ndarray, np.ndarray]:
        """Latitudes y longitudes de los centros de celda, como matrices grid × grid."""
        west, south, east, north = self.bounds
        steps = (np.arange(self.grid) + 0.5) / self.grid
        lats = north - steps * (north - south)
        lons = west + steps * (east - west)
        return np.repeat(lats[:, None], self.grid, axis=1), np.repeat(lons[None, :], self.grid, axis=0)


def place(frame: Frame, latitude: float, longitude: float) -> tuple[int, int] | None:
    """Fila y columna de la celda que contiene el punto; None si cae fuera de la maqueta."""
    west, south, east, north = frame.bounds
    if not (south <= latitude <= north and west <= longitude <= east):
        return None
    row = min(frame.grid - 1, int((north - latitude) / (north - south) * frame.grid))
    col = min(frame.grid - 1, int((longitude - west) / (east - west) * frame.grid))
    return row, col


def horn_slopes(elevation: np.ndarray, cell_m: float) -> np.ndarray:
    """Pendiente de Horn en grados para cada celda; los bordes repiten la celda vecina."""
    z = np.pad(elevation, 1, mode="edge")
    dzdx = ((z[:-2, 2:] + 2 * z[1:-1, 2:] + z[2:, 2:]) - (z[:-2, :-2] + 2 * z[1:-1, :-2] + z[2:, :-2])) / (8 * cell_m)
    dzdy = ((z[2:, :-2] + 2 * z[2:, 1:-1] + z[2:, 2:]) - (z[:-2, :-2] + 2 * z[:-2, 1:-1] + z[:-2, 2:])) / (8 * cell_m)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def build_grid(elevation: np.ndarray, cover: np.ndarray, cell_m: float, exaggeration: float) -> dict[str, object]:
    """Alturas en bloques, pendiente real y elevaciones de referencia.

    Una celda sin elevación toma la del vecino válido más bajo de la maqueta y queda como «sin dato» en la cobertura:
    así no abre un hueco en el suelo ni se presenta como terreno medido. El agua queda plana por cuerpo: cada celda
    de agua baja a la elevación más baja de las celdas de agua de su vecindario de 5 × 5, que quita el ruido del
    modelo de elevación sobre lagos y mar.
    """
    valid = np.isfinite(elevation)
    if not valid.any():
        raise ValueError("La maqueta no tiene ninguna celda con elevación.")
    base = float(elevation[valid].min())
    filled = np.where(valid, elevation, base)
    cover = np.where(valid, cover, 0).astype(np.uint8)
    water = cover == WATER
    if water.any():
        padded = np.pad(np.where(water, filled, np.inf), 2, mode="constant", constant_values=np.inf)
        lowest = np.min(np.stack([padded[i:i + filled.shape[0], j:j + filled.shape[1]] for i in range(5) for j in range(5)]), axis=0)
        filled = np.where(water, lowest, filled)
    slopes = np.where(water, 0.0, horn_slopes(filled, cell_m))
    blocks = np.rint((filled - base) * exaggeration / cell_m)
    return {
        "heights": np.clip(blocks, 0, MAX_BLOCKS).astype("<u2"), "cover": cover, "slope": np.clip(np.rint(slopes), 0, 90).astype(np.uint8),
        "base_elevation_m": round(base, 1), "min_elevation_m": round(float(filled.min()), 1), "max_elevation_m": round(float(filled.max()), 1),
    }


def encode(values: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(values).tobytes()).decode("ascii")


async def _sample(reader: CogReader, lats: np.ndarray, lons: np.ndarray, url_for: Callable[[float, float], str], fill: float) -> tuple[np.ndarray, list[str], list[str]]:
    """Valor del píxel más cercano a cada centro de celda, leyendo solo los bloques necesarios de cada tesela."""
    out = np.full(lats.shape, fill, dtype=np.float64)
    urls = np.array([[url_for(float(lat), float(lon)) for lat, lon in zip(lat_row, lon_row, strict=True)] for lat_row, lon_row in zip(lats, lons, strict=True)])
    used, missing = [], []
    for url in dict.fromkeys(urls.ravel().tolist()):
        mask = urls == url
        try:
            header = await reader.header(url)
        except CogMissing:
            missing.append(url)
            continue
        used.append(url)
        level = header.levels[0]
        (scale_x, scale_y), (west, north) = header.scale, header.origin
        rows = np.clip(((north - lats[mask]) / scale_y).astype(int), 0, level.height - 1)
        cols = np.clip(((lons[mask] - west) / scale_x).astype(int), 0, level.width - 1)
        indices = (rows // level.tile_height) * level.tiles_across + cols // level.tile_width
        values = np.full(rows.shape, fill, dtype=np.float64)
        for index in np.unique(indices):
            block = await reader.tile(url, level, int(index))
            here = indices == index
            values[here] = block[rows[here] % level.tile_height, cols[here] % level.tile_width]
        out[mask] = values
    return out, used, missing


async def read_window(frame: Frame) -> tuple[np.ndarray, np.ndarray, dict[str, list[str]]]:
    """Elevación (NaN sin dato) y clase de cobertura (0 sin dato) de cada celda de la maqueta."""
    lats, lons = frame.centers()
    settings = get_settings()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        dem_reader = CogReader(client, RawPayloadCache(settings.cache_dir, "copernicus-dem"))
        elevation, dem_urls, dem_missing = await _sample(dem_reader, lats, lons, lambda lat, lon: f"{DEM_BUCKET}/{dem_tile(lat, lon)}/{dem_tile(lat, lon)}.tif", math.nan)
        cover_reader = CogReader(client, RawPayloadCache(settings.cache_dir, "esa-worldcover"))
        cover, cover_urls, cover_missing = await _sample(
            cover_reader, lats, lons, lambda lat, lon: f"{COVER_BUCKET}/{VERSION}/{YEAR}/map/{cover_tile(lat, lon)}.tif", 0.0)
    elevation = np.where((elevation > -500) & (elevation < 9000), elevation, math.nan)
    return elevation, cover.astype(np.uint8), {"dem": dem_urls, "dem_missing": dem_missing, "cover": cover_urls, "cover_missing": cover_missing}
