"""Copernicus GLO-30 como segundo modelo de elevación: COG sintético mínimo, sin red, y descubrimientos del relieve."""

import asyncio
import math
import struct
import zlib
from datetime import datetime, timezone

import httpx
import numpy as np
import pytest

from backend.app.connectors.copernicus import dem
from backend.app.core.config import Settings
from backend.app.orchestration.discoveries import terrain_discoveries
from backend.app.schemas.analysis import Point, Provenance
from backend.app.schemas.screening import DiscoveryKind
from backend.app.schemas.terrain import TerrainCrosscheck, TerrainMetrics, TerrainResponse, TerrainSiteResult

SIZE = 8
SCALE = 1 / 3600
TIE = (-71.0, -17.0)          # esquina noroeste de la tesela S18 W071


def _encode(values: np.ndarray) -> bytes:
    """Inverso exacto del decodificador: float32 big-endian en planos de bytes, diferencia horizontal y DEFLATE."""
    rows, cols = values.shape
    planes = values.astype(">f4").view(np.uint8).reshape(rows, cols, 4).transpose(0, 2, 1).reshape(rows, cols * 4)
    deltas = np.diff(planes.astype(np.int16), axis=1, prepend=0).astype(np.uint8)
    return zlib.compress(deltas.tobytes())


def _cog(values: np.ndarray) -> bytes:
    block = _encode(values)
    entries = [(256, 3, 1, SIZE), (257, 3, 1, SIZE), (259, 3, 1, 8), (317, 3, 1, 3), (322, 3, 1, SIZE), (323, 3, 1, SIZE),
               (324, 4, 1, None), (325, 4, 1, len(block)), (339, 3, 1, 3), (33550, 12, 3, None), (33922, 12, 6, None)]
    ifd_size = 2 + 12 * len(entries) + 4
    scale_at = 8 + ifd_size
    tie_at = scale_at + 24
    block_at = tie_at + 48
    values_for = {324: block_at, 33550: scale_at, 33922: tie_at}
    ifd = struct.pack("<H", len(entries)) + b"".join(
        struct.pack("<HHII", tag, kind, n, values_for.get(tag, value) if value is None else value) for tag, kind, n, value in entries) + struct.pack("<I", 0)
    extra = struct.pack("<3d", SCALE, SCALE, 0.0) + struct.pack("<6d", 0.0, 0.0, 0.0, TIE[0], TIE[1], 0.0)
    return b"II*\x00" + struct.pack("<I", 8) + ifd + extra + block


def _transport(blob: bytes | None):
    def handler(request: httpx.Request) -> httpx.Response:
        if blob is None:
            return httpx.Response(404)
        start, end = (int(x) for x in request.headers["Range"].removeprefix("bytes=").split("-"))
        return httpx.Response(206, content=blob[start:end + 1])
    return httpx.MockTransport(handler)


def _surface() -> np.ndarray:
    columns = np.arange(SIZE, dtype=np.float64)
    return np.tile(1000.0 + 10.0 * columns, (SIZE, 1))          # sube 10 m por píxel hacia el este


def test_decoder_inverts_the_floating_point_predictor():
    values = np.random.default_rng(7).uniform(-50, 6000, size=(SIZE, SIZE)).astype(np.float32)
    assert np.array_equal(dem.decode_block(_encode(values), SIZE, SIZE), values.astype(np.float64))


def test_point_reads_elevation_and_horn_slope_from_one_block(tmp_path):
    connector = dem.CopernicusDemConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=_transport(_cog(_surface())))
    latitude, longitude = TIE[1] - 2.5 * SCALE, TIE[0] + 2.5 * SCALE      # fila 2, columna 2
    result = asyncio.run(connector.point(latitude, longitude))
    dx = SCALE * dem.METERS_PER_DEGREE * math.cos(math.radians(latitude))
    assert result.elevation_m == 1020.0 and result.slope_degrees == pytest.approx(math.degrees(math.atan(10 / dx)), abs=0.01)
    assert result.tile_url.endswith("Copernicus_DSM_COG_10_S18_00_W071_00_DEM.tif") and result.provenance == Provenance.REAL
    again = asyncio.run(dem.CopernicusDemConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=_transport(None)).point(latitude, longitude))
    assert again.provenance == Provenance.CACHED and again.elevation_m == 1020.0         # encabezado y bloque desde caché


def test_edge_of_tile_gives_no_slope_and_missing_tile_is_an_error(tmp_path):
    connector = dem.CopernicusDemConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=_transport(_cog(_surface())))
    edge = asyncio.run(connector.point(TIE[1] - 0.5 * SCALE, TIE[0] + 3.5 * SCALE))     # primera fila: falta la vecina del norte
    assert edge.elevation_m == 1030.0 and edge.slope_degrees is None and any("borde" in note for note in edge.limitations)
    with pytest.raises(dem.CopernicusDemError, match="no publica tesela"):
        asyncio.run(dem.CopernicusDemConnector(settings=Settings(_env_file=None, cache_dir=tmp_path / "mar"), transport=_transport(None)).point(-12.0, -80.0))


def _terrain(nasadem: tuple[float, float], copernicus: tuple[float, float]) -> TerrainResponse:
    stamp = datetime(2026, 10, 27, tzinfo=timezone.utc)
    site = TerrainSiteResult(location=Point(latitude=-17.19, longitude=-70.93, label="Moquegua"), status="READY",
                             metrics=TerrainMetrics(elevation_m=nasadem[0], slope_degrees=nasadem[1]), granules=[], provenance=Provenance.CACHED,
                             limitations=[], crosscheck=TerrainCrosscheck(source=dem.SOURCE, elevation_m=copernicus[0], slope_degrees=copernicus[1],
                                                                          tile_url="https://example.org", provenance=Provenance.CACHED, downloaded_at=stamp))
    return TerrainResponse(generated_at=stamp, sites=[site], note="prueba")


def test_terrain_discoveries_agree_differ_and_flag_the_steep_threshold():
    agree = terrain_discoveries(_terrain((1420, 5.47), (1413.3, 6.04)))
    assert agree[0].kind == DiscoveryKind.AGREEMENT and "(-7 m)" in agree[0].detail
    steep = terrain_discoveries(_terrain((2316, 13.0), (2320, 16.5)))
    assert steep[0].kind == DiscoveryKind.CONTRADICTION and "umbral de 15°" in steep[0].title
    apart = terrain_discoveries(_terrain((900, 2.0), (980, 3.0)))
    assert apart[0].kind == DiscoveryKind.CONTRADICTION and apart[0].title == "Moquegua: NASADEM y Copernicus difieren en el relieve"
