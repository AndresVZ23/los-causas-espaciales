"""ESA WorldCover 10 m (Sentinel-1 y Sentinel-2) en AWS Open Data: cobertura del suelo independiente de MODIS.

Teselas de 3° × 3° nombradas por su esquina suroeste (`ESA_WorldCover_10m_2021_v200_S18W072_Map.tif`), COG uint8
con DEFLATE sin predictor, bloques de 1024 × 1024 y seis overviews (verificado el 28-oct-2026). Se publican dos
años, 2020 (v100) y 2021 (v200); no hay serie para tendencias. Clases: 10 árboles, 20 matorral, 30 pastizal,
40 cultivo, 50 construido, 60 suelo desnudo o vegetación escasa, 70 nieve y hielo, 80 agua, 90 humedal herbáceo,
95 manglar, 100 musgo y liquen; 0 = sin dato.

Para un área se elige el nivel de mayor detalle que quepa en `MAX_TILES` bloques por tesela, se descargan solo esos
bloques y se cuentan las clases en los centros de píxel dentro del área (muestreo regular hasta `MAX_SAMPLES`).
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
import numpy as np
import shapely
from shapely.geometry import box, shape

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ..cache import RawPayloadCache
from ..cog import CogError, CogMissing, CogReader

BUCKET = "https://esa-worldcover.s3.eu-central-1.amazonaws.com"
YEAR, VERSION = 2021, "v200"
TIMEOUT = httpx.Timeout(connect=20, read=90, write=20, pool=20)
MAX_TILES = 16
MAX_SAMPLES = 250_000
TILE_DEGREES = 3
METERS_PER_DEGREE = 111_320.0
SOURCE = "ESA WorldCover 10 m 2021 v200 (Sentinel-1/2) vía AWS Open Data"
CLASSES = {10: "Árboles", 20: "Matorral", 30: "Pastizal", 40: "Cultivo", 50: "Construido", 60: "Suelo desnudo o vegetación escasa",
           70: "Nieve y hielo", 80: "Agua", 90: "Humedal herbáceo", 95: "Manglar", 100: "Musgo y liquen"}


class WorldCoverError(RuntimeError):
    pass


@dataclass
class Composition:
    counts: Counter
    resolution_m: float
    urls: list[str]
    provenance: Provenance
    downloaded_at: datetime
    notes: list[str] = field(default_factory=list)

    @property
    def pixels(self) -> int:
        return sum(self.counts.values())


def tile_name(latitude: float, longitude: float) -> str:
    south = math.floor(latitude / TILE_DEGREES) * TILE_DEGREES
    west = math.floor(longitude / TILE_DEGREES) * TILE_DEGREES
    return f"ESA_WorldCover_10m_{YEAR}_{VERSION}_{'S' if south < 0 else 'N'}{abs(south):02d}{'W' if west < 0 else 'E'}{abs(west):03d}_Map"


def _tiles(bounds: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    """Esquinas suroeste de las teselas de 3° que toca la caja (oeste, sur, este, norte)."""
    west, south, east, north = bounds
    # El borde norte o este que cae justo en el límite de una tesela no la incluye: sus píxeles empiezan del otro lado.
    lats = range(math.floor(south / TILE_DEGREES) * TILE_DEGREES, max(math.ceil(north / TILE_DEGREES) * TILE_DEGREES,
                                                                      math.floor(south / TILE_DEGREES) * TILE_DEGREES + TILE_DEGREES), TILE_DEGREES)
    lons = range(math.floor(west / TILE_DEGREES) * TILE_DEGREES, max(math.ceil(east / TILE_DEGREES) * TILE_DEGREES,
                                                                     math.floor(west / TILE_DEGREES) * TILE_DEGREES + TILE_DEGREES), TILE_DEGREES)
    return [(lat + 0.5, lon + 0.5) for lat in lats for lon in lons]


class WorldCoverConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "esa-worldcover")

    async def composition(self, geometry: dict[str, Any]) -> Composition:
        """Conteo de clases WorldCover 2021 en los centros de píxel dentro del área (WGS84)."""
        area = shape(geometry)
        if area.is_empty:
            raise WorldCoverError("El área está vacía.")
        counts: Counter = Counter()
        urls, resolutions, notes = [], [], []
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as client:
                reader = CogReader(client, self.cache)
                for lat, lon in _tiles(area.bounds):
                    name = tile_name(lat, lon)
                    url = f"{BUCKET}/{VERSION}/{YEAR}/map/{name}.tif"
                    try:
                        header = await reader.header(url)
                    except CogMissing:
                        notes.append(f"Sin tesela {name} (mar o fuera de cobertura).")
                        continue
                    west, north = header.origin
                    tile_box = box(west, north - header.levels[0].height * header.scale[1], west + header.levels[0].width * header.scale[0], north)
                    clip = area.intersection(tile_box)
                    if clip.is_empty:
                        continue
                    level_index, window = self._window(header, clip.bounds)
                    level = header.levels[level_index]
                    sx, sy = header.level_scale(level_index)
                    r0, r1, c0, c1 = window
                    mosaic = np.zeros((r1 - r0 + 1, c1 - c0 + 1), dtype=np.uint8)
                    for tile_row in range(r0 // level.tile_height, r1 // level.tile_height + 1):
                        for tile_col in range(c0 // level.tile_width, c1 // level.tile_width + 1):
                            block = await reader.tile(url, level, tile_row * level.tiles_across + tile_col)
                            top, left = tile_row * level.tile_height, tile_col * level.tile_width
                            rs, re_ = max(r0, top), min(r1, top + level.tile_height - 1)
                            cs, ce = max(c0, left), min(c1, left + level.tile_width - 1)
                            mosaic[rs - r0: re_ - r0 + 1, cs - c0: ce - c0 + 1] = block[rs - top: re_ - top + 1, cs - left: ce - left + 1]
                    stride = max(1, math.ceil(math.sqrt(mosaic.size / MAX_SAMPLES)))
                    rows = np.arange(r0, r1 + 1, stride)
                    cols = np.arange(c0, c1 + 1, stride)
                    xs, ys = np.meshgrid(west + (cols + 0.5) * sx, north - (rows + 0.5) * sy)
                    inside = shapely.contains_xy(clip, xs, ys)
                    values = mosaic[::stride, ::stride][inside]
                    counts.update({int(code): int(n) for code, n in zip(*np.unique(values[values > 0], return_counts=True))})
                    urls.append(url)
                    resolutions.append(sx * METERS_PER_DEGREE * stride)
                    if level_index or stride > 1:
                        notes.append(f"{name}: nivel {level_index} y muestreo cada {stride} píxel(es) (~{resolutions[-1]:.0f} m) para no descargar de más.")
        except (httpx.HTTPError, CogError, ValueError, KeyError) as exc:
            raise WorldCoverError(f"ESA WorldCover no respondió con datos utilizables: {exc}") from exc
        if not counts:
            raise WorldCoverError("ESA WorldCover no tiene píxeles con clase dentro del área.")
        return Composition(counts=counts, resolution_m=round(max(resolutions), 1), urls=urls, provenance=reader.provenance,
                           downloaded_at=max(reader.stamps), notes=notes)

    @staticmethod
    def _window(header, bounds: tuple[float, float, float, float]) -> tuple[int, tuple[int, int, int, int]]:
        """El nivel más detallado cuya ventana sobre la caja cabe en `MAX_TILES` bloques; filas y columnas inclusivas."""
        west, north = header.origin
        for index, level in enumerate(header.levels):
            sx, sy = header.level_scale(index)
            c0 = max(0, int((bounds[0] - west) / sx))
            c1 = min(level.width - 1, int((bounds[2] - west) / sx))
            r0 = max(0, int((north - bounds[3]) / sy))
            r1 = min(level.height - 1, int((north - bounds[1]) / sy))
            blocks = (r1 // level.tile_height - r0 // level.tile_height + 1) * (c1 // level.tile_width - c0 // level.tile_width + 1)
            if blocks <= MAX_TILES:
                return index, (r0, r1, c0, c1)
        raise WorldCoverError("El área es demasiado grande para leerla por bloques.")
