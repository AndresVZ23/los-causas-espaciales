"""Copernicus DEM GLO-30 (TanDEM-X) en AWS Open Data: segundo modelo de elevación, independiente de NASADEM (SRTM).

Cada tesela de 1° es un COG público (sin cuenta): float32, DEFLATE con predictor de punto flotante (TIFF predictor 3)
y bloques de 1024 × 1024, verificado el 27-oct-2026. Para un punto basta el encabezado y el bloque que lo contiene
(~2.5 MB): se descomprime con zlib, se deshace la diferencia horizontal por bytes y se reordenan los cuatro planos de
bytes en float32 big-endian. La pendiente se calcula con el método de Horn en la ventana 3 × 3 alrededor del punto.
Es un producto cerrado: encabezados y bloques quedan en caché sin vencimiento.
"""

import math
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime

import httpx
import numpy as np

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ..cache import RawPayloadCache

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
TIMEOUT = httpx.Timeout(connect=20, read=90, write=20, pool=20)
HEADER_BYTES = 65_536
METERS_PER_DEGREE = 111_320.0
SOURCE = "Copernicus DEM GLO-30 (ESA · Airbus, TanDEM-X) vía AWS Open Data"
TAG = {"width": 256, "height": 257, "compression": 259, "predictor": 317, "tile_width": 322, "tile_height": 323,
       "offsets": 324, "counts": 325, "sample_format": 339, "scale": 33550, "tiepoint": 33922}


class CopernicusDemError(RuntimeError):
    pass


@dataclass
class DemPoint:
    elevation_m: float | None
    slope_degrees: float | None
    tile_url: str
    provenance: Provenance
    downloaded_at: datetime
    limitations: list[str]


def tile_name(latitude: float, longitude: float) -> str:
    south, west = math.floor(latitude), math.floor(longitude)
    return f"Copernicus_DSM_COG_10_{'S' if south < 0 else 'N'}{abs(south):02d}_00_{'W' if west < 0 else 'E'}{abs(west):03d}_00_DEM"


def parse_header(head: bytes) -> dict:
    """Primer IFD del COG (resolución completa): tamaño, bloques, georreferencia y codificación."""
    if head[:4] != b"II*\x00":
        raise CopernicusDemError("La tesela no es un TIFF little-endian clásico.")
    offset = struct.unpack("<I", head[4:8])[0]
    count = struct.unpack("<H", head[offset:offset + 2])[0]
    raw = {}
    for i in range(count):
        entry = offset + 2 + 12 * i
        tag, kind, n, value = struct.unpack("<HHII", head[entry: entry + 12])
        raw[tag] = (kind, n, value, entry + 8)

    def scalar(name: str) -> int:
        return raw[TAG[name]][2]

    def array(name: str, fmt: str, size: int) -> tuple:
        # TIFF guarda dentro de la propia entrada los valores que caben en 4 bytes (p. ej. un solo bloque).
        _, n, at, inline = raw[TAG[name]]
        start = inline if n * size <= 4 else at
        return struct.unpack(f"<{n}{fmt}", head[start: start + size * n])
    header = {name: scalar(name) for name in ("width", "height", "compression", "predictor", "tile_width", "tile_height", "sample_format")}
    if (header["compression"], header["predictor"], header["sample_format"]) != (8, 3, 3):
        raise CopernicusDemError(f"Codificación no prevista: compresión {header['compression']}, predictor {header['predictor']}.")
    header.update(offsets=array("offsets", "I", 4), counts=array("counts", "I", 4), scale=array("scale", "d", 8), tiepoint=array("tiepoint", "d", 8))
    return header


def decode_block(raw: bytes, tile_width: int, tile_height: int) -> np.ndarray:
    """DEFLATE + predictor 3 de TIFF: suma acumulada por bytes en cada fila y planos de bytes a float32 big-endian."""
    data = np.frombuffer(zlib.decompress(raw), dtype=np.uint8).reshape(tile_height, tile_width * 4)
    data = np.cumsum(data, axis=1, dtype=np.uint8)
    planes = data.reshape(tile_height, 4, tile_width).transpose(0, 2, 1)
    return np.ascontiguousarray(planes).view(">f4").reshape(tile_height, tile_width).astype(np.float64)


def horn_slope(window: np.ndarray, dx: float, dy: float) -> float:
    dzdx = ((window[0, 2] + 2 * window[1, 2] + window[2, 2]) - (window[0, 0] + 2 * window[1, 0] + window[2, 0])) / (8 * dx)
    dzdy = ((window[2, 0] + 2 * window[2, 1] + window[2, 2]) - (window[0, 0] + 2 * window[0, 1] + window[0, 2])) / (8 * dy)
    return math.degrees(math.atan(math.hypot(dzdx, dzdy)))


class CopernicusDemConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "copernicus-dem")

    async def _range(self, client: httpx.AsyncClient, url: str, start: int, length: int) -> tuple[bytes, Provenance, datetime]:
        key = self.cache.request_key({"url": url, "start": start, "length": length, "v": 1})
        cached = self.cache.get(key, max_age=None)
        if cached:
            return cached.content, Provenance.CACHED, cached.downloaded_at
        response = await client.get(url, headers={"Range": f"bytes={start}-{start + length - 1}"})
        if response.status_code in (403, 404):
            raise CopernicusDemError("Copernicus no publica tesela para este punto (mar o fuera de cobertura).")
        response.raise_for_status()
        stored = self.cache.put(key, response.content, suffix=".bin")
        return response.content, Provenance.REAL, stored.downloaded_at

    async def point(self, latitude: float, longitude: float) -> DemPoint:
        name = tile_name(latitude, longitude)
        url = f"{BUCKET}/{name}/{name}.tif"
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as client:
                head, provenance, stamp = await self._range(client, url, 0, HEADER_BYTES)
                header = parse_header(head)
                scale, tie = header["scale"], header["tiepoint"]
                row, col = int((tie[4] - latitude) / scale[1]), int((longitude - tie[3]) / scale[0])
                blocks: dict[int, np.ndarray] = {}
                provenances, stamps = [provenance], [stamp]

                async def value(r: int, c: int) -> float | None:
                    if not (0 <= r < header["height"] and 0 <= c < header["width"]):
                        return None
                    across = math.ceil(header["width"] / header["tile_width"])
                    index = (r // header["tile_height"]) * across + c // header["tile_width"]
                    if index not in blocks:
                        raw, block_provenance, block_stamp = await self._range(client, url, header["offsets"][index], header["counts"][index])
                        blocks[index] = decode_block(raw, header["tile_width"], header["tile_height"])
                        provenances.append(block_provenance)
                        stamps.append(block_stamp)
                    sample = float(blocks[index][r % header["tile_height"], c % header["tile_width"]])
                    return sample if math.isfinite(sample) and -500 < sample < 9000 else None

                center = await value(row, col)
                window = [[await value(row + i, col + j) for j in (-1, 0, 1)] for i in (-1, 0, 1)]
        except (httpx.HTTPError, zlib.error, struct.error, KeyError, ValueError) as exc:
            raise CopernicusDemError(f"Copernicus DEM no respondió con datos utilizables: {exc}") from exc
        limitations = ["Modelo de superficie (DSM): incluye edificios y vegetación; NASADEM también es de superficie (SRTM banda C)."]
        slope = None
        if all(item is not None for line in window for item in line):
            dx = scale[0] * METERS_PER_DEGREE * math.cos(math.radians(latitude))
            slope = round(horn_slope(np.array(window, dtype=np.float64), dx, scale[1] * METERS_PER_DEGREE), 2)
        else:
            limitations.append("El punto cae en el borde de la tesela o junto a un vacío: sin pendiente, no se rellena.")
        return DemPoint(elevation_m=round(center, 1) if center is not None else None, slope_degrees=slope, tile_url=url,
                        provenance=Provenance.CACHED if all(p == Provenance.CACHED for p in provenances) else Provenance.REAL,
                        downloaded_at=max(stamps), limitations=limitations)
