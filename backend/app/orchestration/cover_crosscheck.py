"""Cobertura del suelo: MOD44B (MODIS) frente a ESA WorldCover 2021 en la misma ventana del análisis.

MOD44B estima la fracción de árboles, vegetación no arbórea y suelo sin vegetación dentro de cada píxel de 250 m;
WorldCover asigna una sola clase dominante a cada píxel de 10 m. Se agrupan las clases de WorldCover en esos tres
grupos (el agua queda fuera en ambos) y se comparan en 2021. En vegetación rala la clase dominante y la fracción
difieren por definición: un píxel de matorral abierto cuenta entero como matorral en WorldCover.
"""

import math
from collections.abc import Sequence
from typing import Any

from shapely.geometry import box, mapping, shape

from ..connectors.esa.worldcover import CLASSES, SOURCE, YEAR, Composition, WorldCoverConnector, WorldCoverError
from ..schemas.analysis import Point
from ..schemas.baseline import CoverGroupCheck, LandCoverCrosscheck, LandCoverShare
from ..schemas.pipeline import VariableSummary

WATER = 80
GROUPS = {"VCF_TREE": ("Árboles", {10, 95}), "VCF_NONTREE": ("Vegetación no arbórea", {20, 30, 40, 90, 100}),
          "VCF_BARE": ("Sin vegetación (suelo desnudo, construido, nieve)", {50, 60, 70})}
KM_PER_DEGREE = 111.32
COVER_NOTE = (
    "Cobertura: MOD44B (fracción por píxel de 250 m) frente a ESA WorldCover 2021 (clase dominante por píxel de 10 m, Sentinel-1/2), "
    "en la misma ventana MODIS y sin el agua. En vegetación rala difieren por definición; el acuerdo pesa más en zonas de cobertura densa o nula."
)


def modis_window(geometry: dict[str, Any], point: Point, km: int) -> dict[str, Any]:
    """El área recortada a la ventana ±km del servicio MODIS, para comparar la misma superficie."""
    dlat = km / KM_PER_DEGREE
    dlon = km / (KM_PER_DEGREE * max(math.cos(math.radians(point.latitude)), 1e-6))
    clipped = shape(geometry).intersection(box(point.longitude - dlon, point.latitude - dlat, point.longitude + dlon, point.latitude + dlat))
    return mapping(clipped) if not clipped.is_empty else geometry


def build_crosscheck(composition: Composition, vegetation: Sequence[VariableSummary], notes: Sequence[str] = ()) -> LandCoverCrosscheck:
    land = {code: count for code, count in composition.counts.items() if code != WATER}
    total = sum(land.values())
    classes = [LandCoverShare(code=code, label=CLASSES.get(code, str(code)), percent=round(count / total * 100, 1))
               for code, count in sorted(land.items(), key=lambda kv: -kv[1])] if total else []
    by_variable = {item.variable: item for item in vegetation}
    groups = []
    for variable, (label, codes) in GROUPS.items():
        same_year = next((point.value for point in by_variable[variable].annual_series if point.year == YEAR), None) if variable in by_variable else None
        groups.append(CoverGroupCheck(variable=variable, label=label, modis_percent=round(same_year, 1) if same_year is not None else None,
                                      worldcover_percent=round(sum(land.get(code, 0) for code in codes) / total * 100, 1) if total else 0.0))
    return LandCoverCrosscheck(
        source=SOURCE, year=YEAR, pixels=composition.pixels, resolution_m=composition.resolution_m, classes=classes, groups=groups,
        provenance=composition.provenance, downloaded_at=composition.downloaded_at, source_urls=composition.urls,
        limitations=["Clase dominante a 10 m frente a fracción a 250 m: no son la misma medida; se comparan grupos, no clases.",
                     "WorldCover publica 2020 y 2021: sirve para el nivel actual, no para tendencias.", *composition.notes, *notes],
    )


async def worldcover_composition(geometry: dict[str, Any], point: Point, km: int) -> Composition | str:
    """Composición WorldCover de la ventana MODIS del área; un fallo vuelve como texto para declararlo, nunca como ceros."""
    try:
        return await WorldCoverConnector().composition(modis_window(geometry, point, km))
    except WorldCoverError as exc:
        return f"Sin contraste ESA WorldCover: {exc}"
