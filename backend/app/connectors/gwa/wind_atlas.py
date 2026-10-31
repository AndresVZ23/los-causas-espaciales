"""Atlas Eólico Global (Global Wind Atlas 4.0, DTU con ESMAP del Banco Mundial, junio de 2025): segunda fuente del
nivel del viento.

El atlas baja el clima de viento de reanálisis a 250 m con un modelo de microescala (PyWAsP) que usa el relieve de
Copernicus DEM y la rugosidad de ESA WorldCover, y publica la velocidad media de largo plazo a varias alturas. Por
país entrega un BigTIFF en bloques de 512 × 512, float32, ZSTD con predictor de punto flotante y nodata NaN
(verificado el 30-oct-2026 para el Perú: 0.0025°, 94 MB a 100 m, ruta `country_tifs_v4`). Para un punto basta el
encabezado y el bloque que lo contiene (~450 KB), leídos con `connectors/cog.py`. Es un producto cerrado: caché sin
vencimiento. Licencia CC BY 4.0.
"""

import math
import struct
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from ...core.config import Settings, get_settings
from ...schemas.analysis import Provenance
from ..cache import RawPayloadCache
from ..cog import CogError, CogMissing, CogReader

API = "https://globalwindatlas.info/api/gis/country/{country}/wind-speed/{height}"
COUNTRY = "PER"
HEIGHTS = (50, 100)
TIMEOUT = httpx.Timeout(connect=20, read=90, write=20, pool=20)
SOURCE = "Global Wind Atlas 4.0 (DTU · Banco Mundial)"
LICENSE = "CC BY 4.0"


class WindAtlasError(RuntimeError):
    pass


@dataclass
class AtlasPoint:
    speeds: dict[int, float | None]          # altura en m → velocidad media en m/s; None si el píxel es nodata
    urls: list[str]
    provenance: Provenance
    downloaded_at: datetime
    limitations: list[str] = field(default_factory=list)


class WindAtlasConnector:
    def __init__(self, *, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.cache = RawPayloadCache(self.settings.cache_dir, "global-wind-atlas")

    async def point(self, latitude: float, longitude: float) -> AtlasPoint:
        speeds: dict[int, float | None] = {}
        urls = []
        try:
            # El enlace oficial redirige a la CDN del atlas; el rango HTTP se conserva en la redirección.
            async with httpx.AsyncClient(timeout=TIMEOUT, transport=self.transport, follow_redirects=True) as client:
                reader = CogReader(client, self.cache)
                for height in HEIGHTS:
                    url = API.format(country=COUNTRY, height=height)
                    urls.append(url)
                    header = await reader.header(url)
                    level = header.levels[0]
                    (scale_x, scale_y), (west, north) = header.scale, header.origin
                    row, col = int((north - latitude) / scale_y), int((longitude - west) / scale_x)
                    if not (0 <= row < level.height and 0 <= col < level.width):
                        raise WindAtlasError("El punto queda fuera del archivo del Perú del atlas.")
                    index = (row // level.tile_height) * level.tiles_across + col // level.tile_width
                    block = await reader.tile(url, level, index)
                    sample = float(block[row % level.tile_height, col % level.tile_width])
                    speeds[height] = round(sample, 2) if math.isfinite(sample) and 0 < sample < 40 else None
        except CogMissing as exc:
            raise WindAtlasError(f"El atlas no publica el archivo: {exc}") from exc
        except (httpx.HTTPError, CogError, struct.error, KeyError, ValueError) as exc:
            raise WindAtlasError(f"El Atlas Eólico Global no respondió con datos utilizables: {exc}") from exc
        limitations = ["Media de largo plazo a 250 m: no da tendencias ni variación interanual.",
                       "Modelo de microescala sobre reanálisis, no una medición; en relieve complejo su error crece."]
        if any(value is None for value in speeds.values()):
            limitations.append("El píxel del punto no tiene dato (mar o borde del archivo): no se rellena.")
        return AtlasPoint(speeds=speeds, urls=urls, provenance=reader.provenance, downloaded_at=max(reader.stamps), limitations=limitations)
