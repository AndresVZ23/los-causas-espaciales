"""ESA WorldCover como contraste de la cobertura MODIS: COG uint8 sintético con overview, sin red, y descubrimientos."""

import asyncio
import struct
import zlib
from collections import Counter
from datetime import datetime, timezone

import httpx
import numpy as np
import pytest
from shapely.geometry import box, mapping

from backend.app.connectors.esa import worldcover
from backend.app.connectors.esa.worldcover import Composition, WorldCoverError
from backend.app.core.config import Settings
from backend.app.orchestration.cover_crosscheck import build_crosscheck
from backend.app.orchestration.discoveries import cover_discoveries
from backend.app.schemas.analysis import Provenance
from backend.app.schemas.baseline import SubjectBaseline
from backend.tests.test_era5 import _summary

SCALE = 1 / 12000
ORIGIN = (-72.0, -15.0)        # esquina noroeste de la tesela S18W072
STAMP = datetime(2026, 10, 28, tzinfo=timezone.utc)


def _image() -> np.ndarray:
    """16 × 16: mitad oeste suelo desnudo (60), mitad este pastizal (30) y la primera fila sin dato (0)."""
    image = np.full((16, 16), 60, dtype=np.uint8)
    image[:, 8:] = 30
    image[0, :] = 0
    return image


def _cog(full: np.ndarray, tile: int = 8) -> bytes:
    """COG mínimo: nivel completo en bloques de `tile` y un overview de un solo bloque; DEFLATE sin predictor."""
    levels = [full, full[::2, ::2]]
    blobs, layouts = [], []
    for image in levels:
        rows, cols = image.shape
        blocks = []
        for r in range(0, rows, tile):
            for c in range(0, cols, tile):
                piece = np.zeros((tile, tile), dtype=np.uint8)
                part = image[r:r + tile, c:c + tile]
                piece[:part.shape[0], :part.shape[1]] = part
                blocks.append(zlib.compress(piece.tobytes()))
        layouts.append((rows, cols, blocks))
    header_size = 4096
    data_at, table, body = header_size, [], b""
    for rows, cols, blocks in layouts:
        offsets = []
        for block in blocks:
            offsets.append(data_at + len(body))
            body += block
        table.append((rows, cols, offsets, [len(b) for b in blocks]))
    head = bytearray(header_size)
    head[:8] = b"II*\x00" + struct.pack("<I", 8)
    cursor, extra = 8, 2048
    for index, (rows, cols, offsets, counts) in enumerate(table):
        def put_array(fmt: str, values) -> int:
            nonlocal extra
            at = extra
            packed = struct.pack(f"<{len(values)}{fmt}", *values)
            head[at:at + len(packed)] = packed
            extra += len(packed) + (len(packed) % 2)
            return at
        entries = [(256, 3, 1, cols), (257, 3, 1, rows), (258, 3, 1, 8), (259, 3, 1, 8), (317, 3, 1, 1), (322, 3, 1, tile), (323, 3, 1, tile),
                   (324, 4, len(offsets), offsets[0] if len(offsets) == 1 else put_array("I", offsets)),
                   (325, 4, len(counts), counts[0] if len(counts) == 1 else put_array("I", counts)), (339, 3, 1, 1)]
        if index == 0:
            entries += [(33550, 12, 3, put_array("d", (SCALE, SCALE, 0.0))), (33922, 12, 6, put_array("d", (0.0, 0.0, 0.0, ORIGIN[0], ORIGIN[1], 0.0)))]
        ifd = struct.pack("<H", len(entries)) + b"".join(struct.pack("<HHII", *entry) for entry in entries)
        next_at = cursor + len(ifd) + 4 if index + 1 < len(table) else 0
        head[cursor:cursor + len(ifd) + 4] = ifd + struct.pack("<I", next_at)
        cursor += len(ifd) + 4
    return bytes(head) + body


def _transport(blob: bytes | None):
    def handler(request: httpx.Request) -> httpx.Response:
        if blob is None:
            return httpx.Response(404)
        start, end = (int(x) for x in request.headers["Range"].removeprefix("bytes=").split("-"))
        return httpx.Response(206, content=blob[start:end + 1])
    return httpx.MockTransport(handler)


AREA = mapping(box(ORIGIN[0], ORIGIN[1] - 16 * SCALE, ORIGIN[0] + 16 * SCALE, ORIGIN[1]))   # las 16 × 16 celdas


def test_composition_counts_classes_inside_the_area_and_skips_nodata(tmp_path):
    connector = worldcover.WorldCoverConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=_transport(_cog(_image())))
    result = asyncio.run(connector.composition(AREA))
    assert result.counts == Counter({60: 120, 30: 120})                 # la fila sin dato (0) no se cuenta
    assert result.urls[0].endswith("ESA_WorldCover_10m_2021_v200_S18W072_Map.tif") and result.provenance == Provenance.REAL
    assert result.notes == []                                            # nivel completo, sin submuestreo


def test_large_areas_fall_back_to_an_overview(tmp_path, monkeypatch):
    monkeypatch.setattr(worldcover, "MAX_TILES", 1)
    connector = worldcover.WorldCoverConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=_transport(_cog(_image())))
    result = asyncio.run(connector.composition(AREA))
    assert result.counts == Counter({60: 28, 30: 28}) and "nivel 1" in result.notes[0]


def test_missing_tile_is_an_error_not_an_empty_cover(tmp_path):
    connector = worldcover.WorldCoverConnector(settings=Settings(_env_file=None, cache_dir=tmp_path), transport=_transport(None))
    with pytest.raises(WorldCoverError, match="no tiene píxeles"):
        asyncio.run(connector.composition(AREA))


def _vcf(code: str, value: float):
    return _summary(code, lambda year: value + ((year * 7) % 5 - 2) * 0.01, unit="%")


def test_crosscheck_groups_exclude_water_and_pair_the_same_year():
    composition = Composition(counts=Counter({60: 600, 30: 300, 10: 100, 80: 500}), resolution_m=9.3, urls=["u"], provenance=Provenance.REAL, downloaded_at=STAMP)
    check = build_crosscheck(composition, [_vcf("VCF_BARE", 62.0), _vcf("VCF_NONTREE", 30.0)])
    groups = {group.variable: group for group in check.groups}
    assert groups["VCF_BARE"].worldcover_percent == 60.0 and groups["VCF_NONTREE"].worldcover_percent == 30.0   # el agua no entra al total
    assert groups["VCF_TREE"].modis_percent is None and groups["VCF_TREE"].worldcover_percent == 10.0       # sin serie MODIS: None, nunca cero
    assert groups["VCF_BARE"].modis_percent == pytest.approx(62.0, abs=0.05)                                 # valor de 2021


def _baseline(check) -> SubjectBaseline:
    return SubjectBaseline(subject="Ilo (dist.)", origin="prueba", area_km2=293, study_area=AREA, land_cover_check=check)


def test_cover_discoveries_agree_and_differ():
    close = Composition(counts=Counter({60: 780, 30: 220}), resolution_m=9.3, urls=["u"], provenance=Provenance.REAL, downloaded_at=STAMP)
    found = cover_discoveries([_baseline(build_crosscheck(close, [_vcf("VCF_BARE", 80.0), _vcf("VCF_NONTREE", 20.0)]))])
    assert found[0].kind.value == "coincidencia" and "MOD44B 80.0 %, WorldCover 78.0 %" in found[0].detail
    lomas = Composition(counts=Counter({60: 500, 30: 500}), resolution_m=9.3, urls=["u"], provenance=Provenance.REAL, downloaded_at=STAMP)
    found = cover_discoveries([_baseline(build_crosscheck(lomas, [_vcf("VCF_BARE", 85.0), _vcf("VCF_NONTREE", 15.0)]))])
    assert found[0].kind.value == "contradiccion" and "35 puntos)" in found[0].detail
