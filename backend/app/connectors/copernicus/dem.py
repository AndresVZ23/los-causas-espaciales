"""Copernicus DEM GLO-30 (TanDEM-X) en AWS Open Data: segundo modelo de elevación, independiente de NASADEM (SRTM).

Cada tesela de 1° es un COG público (sin cuenta): float32, DEFLATE con predictor de punto flotante (TIFF predictor 3)
y bloques de 1024 × 1024, verificado el 27-oct-2026. Para un punto basta el encabezado y el bloque que lo contiene
(~2.5 MB), leídos con `connectors/cog.py`. La pendiente se calcula con el método de Horn en la ventana 3 × 3
alrededor del punto. Es un producto cerrado: encabezados y bloques quedan en caché sin vencimiento.
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
from ..cog import CogError, CogMissing, CogReader

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
TIMEOUT = httpx.Timeout(connect=20, read=90, write=20, pool=20)
METERS_PER_DEGREE = 111_320.0
SOURCE = "Copernicus DEM GLO-30 (ESA · Airbus, TanDEM-X) vía AWS Open Data"


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


def horn_slope(window: np.ndarray, dx: float, dy: float) -> float:
    dzdx = ((window[0, 2] + 2 * window[1, 2] + window[2, 2]) - (window[0, 0] + 2 * window[1, 0] + window[2, 0])) / (8 * dx)
    dzdy = ((window[2, 0] + 2 * window[2, 1] + window[2, 2]) - (window[0, 0] + 2 * window[0, 1] + window[0, 2])) / (8 * dy)
    return math.degrees(math.atan(math.hypot(dzdx, dzdy)))


class CopernicusDemConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "copernicus-dem")

    async def point(self, latitude: float, longitude: float) -> DemPoint:
        name = tile_name(latitude, longitude)
        url = f"{BUCKET}/{name}/{name}.tif"
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport) as client:
                reader = CogReader(client, self.cache)
                header = await reader.header(url)
                level = header.levels[0]
                if (level.compression, level.predictor, level.sample_format) != (8, 3, 3):
                    raise CopernicusDemError(f"Codificación no prevista: compresión {level.compression}, predictor {level.predictor}.")
                (scale_x, scale_y), (west, north) = header.scale, header.origin
                row, col = int((north - latitude) / scale_y), int((longitude - west) / scale_x)
                blocks: dict[int, np.ndarray] = {}

                async def value(r: int, c: int) -> float | None:
                    if not (0 <= r < level.height and 0 <= c < level.width):
                        return None
                    index = (r // level.tile_height) * level.tiles_across + c // level.tile_width
                    if index not in blocks:
                        blocks[index] = await reader.tile(url, level, index)
                    sample = float(blocks[index][r % level.tile_height, c % level.tile_width])
                    return sample if math.isfinite(sample) and -500 < sample < 9000 else None

                center = await value(row, col)
                window = [[await value(row + i, col + j) for j in (-1, 0, 1)] for i in (-1, 0, 1)]
        except CogMissing as exc:
            raise CopernicusDemError(f"Copernicus no publica tesela para este punto: {exc}") from exc
        except (httpx.HTTPError, CogError, zlib.error, struct.error, KeyError, ValueError) as exc:
            raise CopernicusDemError(f"Copernicus DEM no respondió con datos utilizables: {exc}") from exc
        limitations = ["Modelo de superficie (DSM): incluye edificios y vegetación; NASADEM también es de superficie (SRTM banda C)."]
        slope = None
        if all(item is not None for line in window for item in line):
            dx = scale_x * METERS_PER_DEGREE * math.cos(math.radians(latitude))
            slope = round(horn_slope(np.array(window, dtype=np.float64), dx, scale_y * METERS_PER_DEGREE), 2)
        else:
            limitations.append("El punto cae en el borde de la tesela o junto a un vacío: sin pendiente, no se rellena.")
        return DemPoint(elevation_m=round(center, 1) if center is not None else None, slope_degrees=slope, tile_url=url,
                        provenance=reader.provenance, downloaded_at=max(reader.stamps), limitations=limitations)
