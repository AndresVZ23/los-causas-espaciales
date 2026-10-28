"""Lectura mínima de Cloud Optimized GeoTIFF públicos por rango HTTP, sin GDAL.

Cubre lo que usan Copernicus DEM y ESA WorldCover (verificado el 27/28-oct-2026): TIFF clásico little-endian, bloques
(tiles), DEFLATE y predictores 1 (ninguno), 2 (diferencia horizontal entera) y 3 (punto flotante). Del encabezado
se leen todos los niveles (resolución completa y overviews); de cada bloque solo se descarga lo que se pide. Los
productos son cerrados: encabezados y bloques quedan en caché sin vencimiento.
"""

import math
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime

import httpx
import numpy as np

from ..schemas.analysis import Provenance
from .cache import RawPayloadCache

HEADER_BYTES = 65_536
TAG = {"width": 256, "height": 257, "bits": 258, "compression": 259, "predictor": 317, "tile_width": 322, "tile_height": 323,
       "offsets": 324, "counts": 325, "sample_format": 339, "scale": 33550, "tiepoint": 33922}
DEFLATE = (8, 32946)


class CogError(RuntimeError):
    pass


class CogMissing(CogError):
    """El archivo no existe en el bucket (mar o fuera de cobertura)."""


@dataclass(frozen=True)
class CogLevel:
    width: int
    height: int
    tile_width: int
    tile_height: int
    bits: int
    compression: int
    predictor: int
    sample_format: int
    offsets: tuple[int, ...]
    counts: tuple[int, ...]

    @property
    def tiles_across(self) -> int:
        return math.ceil(self.width / self.tile_width)


@dataclass(frozen=True)
class CogHeader:
    levels: list[CogLevel]          # 0 = resolución completa; luego cada overview
    scale: tuple[float, float]      # grados por píxel en el nivel 0 (x, y)
    origin: tuple[float, float]     # esquina noroeste (lon, lat) del píxel (0, 0)

    def level_scale(self, level: int) -> tuple[float, float]:
        factor = self.levels[0].width / self.levels[level].width
        return self.scale[0] * factor, self.scale[1] * factor


def parse_header(head: bytes) -> CogHeader:
    if head[:4] != b"II*\x00":
        raise CogError("El archivo no es un TIFF little-endian clásico.")
    offset = struct.unpack("<I", head[4:8])[0]
    levels, scale, origin = [], None, None
    while offset:
        if offset + 2 > len(head):
            raise CogError("El encabezado del COG es más largo que el tramo leído.")
        count = struct.unpack("<H", head[offset:offset + 2])[0]
        raw = {}
        for i in range(count):
            entry = offset + 2 + 12 * i
            tag, kind, n, value = struct.unpack("<HHII", head[entry: entry + 12])
            raw[tag] = (n, value, entry + 8)

        def array(name: str, fmt: str, size: int) -> tuple:
            # TIFF guarda dentro de la propia entrada los valores que caben en 4 bytes (p. ej. un solo bloque).
            n, at, inline = raw[TAG[name]]
            start = inline if n * size <= 4 else at
            if start + size * n > len(head):
                raise CogError("Las tablas de bloques quedan fuera del tramo leído.")
            return struct.unpack(f"<{n}{fmt}", head[start: start + size * n])

        def scalar(name: str, default: int) -> int:
            return raw[TAG[name]][1] if TAG[name] in raw else default
        levels.append(CogLevel(width=scalar("width", 0), height=scalar("height", 0), tile_width=scalar("tile_width", 0),
                               tile_height=scalar("tile_height", 0), bits=scalar("bits", 8), compression=scalar("compression", 1),
                               predictor=scalar("predictor", 1), sample_format=scalar("sample_format", 1),
                               offsets=array("offsets", "I", 4), counts=array("counts", "I", 4)))
        if scale is None:
            scale = array("scale", "d", 8)[:2]
            tie = array("tiepoint", "d", 8)
            origin = (tie[3], tie[4])
        offset = struct.unpack("<I", head[offset + 2 + 12 * count: offset + 6 + 12 * count])[0]
    if not levels or not levels[0].tile_width:
        raise CogError("El COG no tiene bloques.")
    return CogHeader(levels=levels, scale=scale, origin=origin)


def decode_tile(raw: bytes, level: CogLevel) -> np.ndarray:
    """Un bloque como matriz (filas × columnas): DEFLATE y predictor 1, 2 o 3 de TIFF."""
    if level.compression not in DEFLATE:
        raise CogError(f"Compresión no prevista: {level.compression}.")
    data = zlib.decompress(raw)
    rows, cols, width = level.tile_height, level.tile_width, level.bits // 8
    if level.predictor == 3:    # punto flotante: planos de bytes con diferencia horizontal, en big-endian
        planes = np.cumsum(np.frombuffer(data, dtype=np.uint8).reshape(rows, cols * width), axis=1, dtype=np.uint8)
        planes = planes.reshape(rows, width, cols).transpose(0, 2, 1)
        return np.ascontiguousarray(planes).view(f">f{width}").reshape(rows, cols).astype(np.float64)
    kind = {1: "u", 2: "i", 3: "f"}[level.sample_format]
    values = np.frombuffer(data, dtype=np.dtype(f"<{kind}{width}")).reshape(rows, cols)
    if level.predictor == 2:
        values = np.cumsum(values, axis=1, dtype=values.dtype)
    return values


class CogReader:
    """Encabezado y bloques de un COG por rango HTTP, con caché sin vencimiento y procedencia de cada lectura."""

    def __init__(self, client: httpx.AsyncClient, cache: RawPayloadCache):
        self.client = client
        self.cache = cache
        self.provenances: list[Provenance] = []
        self.stamps: list[datetime] = []

    async def _range(self, url: str, start: int, length: int) -> bytes:
        key = self.cache.request_key({"url": url, "start": start, "length": length, "v": 1})
        cached = self.cache.get(key, max_age=None)
        if cached:
            self.provenances.append(Provenance.CACHED)
            self.stamps.append(cached.downloaded_at)
            return cached.content
        response = await self.client.get(url, headers={"Range": f"bytes={start}-{start + length - 1}"})
        if response.status_code in (403, 404):
            raise CogMissing("No hay archivo publicado para este punto (mar o fuera de cobertura).")
        response.raise_for_status()
        stored = self.cache.put(key, response.content, suffix=".bin")
        self.provenances.append(Provenance.REAL)
        self.stamps.append(stored.downloaded_at)
        return response.content

    async def header(self, url: str) -> CogHeader:
        return parse_header(await self._range(url, 0, HEADER_BYTES))

    async def tile(self, url: str, level: CogLevel, index: int) -> np.ndarray:
        return decode_tile(await self._range(url, level.offsets[index], level.counts[index]), level)

    @property
    def provenance(self) -> Provenance:
        return Provenance.CACHED if self.provenances and all(p == Provenance.CACHED for p in self.provenances) else Provenance.REAL
