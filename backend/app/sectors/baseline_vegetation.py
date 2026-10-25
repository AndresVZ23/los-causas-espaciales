"""Vegetación y cobertura anual con MODIS (NASA, servicio ORNL DAAC) dentro de un área de estudio.

Indicadores indirectos de la línea base biológica: proporción de árboles, de vegetación no arbórea y de suelo sin
vegetación (MOD44B), producción primaria neta (MOD17A3HGF) y clase de cobertura IGBP (MCD12Q1). Cada año se
promedia sobre los píxeles cuyo centro cae dentro del área; un año entra solo si al menos la mitad de esos píxeles
tiene un valor válido. La tendencia usa la misma prueba que el clima: Mann–Kendall con Hamed–Rao y Sen.
"""

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from statistics import fmean, pstdev
from typing import Any

from ..connectors.nasa.modis_subsets import ModisBand, ModisSubsetConnector, ModisSubsetError
from ..core.units import display_unit
from ..geospatial.modis_grid import pixels_inside
from ..schemas.analysis import Observation, Point, SourceMetadata
from ..schemas.baseline import LandCoverChange, LandCoverClass
from ..schemas.pipeline import AnnualObservation, VariableSummary
from ..statistics.trends import analyze_trend

MIN_VALID_SHARE = 0.5
MIN_YEARS = 5
SOURCE_ID = "nasa-modis-ornl"
SERVICE = "NASA ORNL DAAC · MODIS Web Service"


@dataclass(frozen=True)
class ModisVariable:
    key: str
    product: str
    band: str
    label: str
    unit: str
    valid: tuple[int, int]
    scale: float
    resolution: str
    fill_note: str


VEGETATION_VARIABLES = (
    ModisVariable("VCF_TREE", "MOD44B", "Percent_Tree_Cover", "Cobertura arbórea", "percent_cover", (0, 100), 1.0, "250 m",
                  "200 = agua y 253 = sin dato se excluyen."),
    ModisVariable("VCF_NONTREE", "MOD44B", "Percent_NonTree_Vegetation", "Vegetación no arbórea", "percent_cover", (0, 100), 1.0, "250 m",
                  "200 = agua y 253 = sin dato se excluyen."),
    ModisVariable("VCF_BARE", "MOD44B", "Percent_NonVegetated", "Suelo sin vegetación", "percent_cover", (0, 100), 1.0, "250 m",
                  "200 = agua y 253 = sin dato se excluyen."),
    ModisVariable("NPP", "MOD17A3HGF", "Npp_500m", "Producción primaria neta anual", "kg_C/m^2", (0, 32700), 0.0001, "500 m",
                  "Valores de relleno (≥ 32 761: suelo desnudo, urbano, agua o sin dato) se excluyen."),
)
LAND_COVER = ("MCD12Q1", "LC_Type1")
IGBP_CLASSES = {
    1: "Bosque perennifolio de coníferas", 2: "Bosque perennifolio latifoliado", 3: "Bosque caducifolio de coníferas",
    4: "Bosque caducifolio latifoliado", 5: "Bosque mixto", 6: "Matorral cerrado", 7: "Matorral abierto", 8: "Sabana arbolada",
    9: "Sabana", 10: "Pastizal", 11: "Humedal permanente", 12: "Cultivos", 13: "Urbano y construido",
    14: "Mosaico de cultivos y vegetación natural", 15: "Nieve y hielo permanentes", 16: "Suelo desnudo o con escasa vegetación", 17: "Agua",
}


@dataclass
class SubjectVegetation:
    summaries: list[VariableSummary] = field(default_factory=list)
    land_cover: LandCoverChange | None = None
    pixels: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _source(band: ModisBand, variable: ModisVariable, pixels: int, fallback: bool) -> SourceMetadata:
    notes = [f"Promedio anual de {pixels} píxeles de {variable.resolution} con centro dentro del área.", variable.fill_note]
    if fallback:
        notes.append("El área es menor que un píxel: se usa el píxel más cercano al punto representativo.")
    return SourceMetadata(
        source_id=SOURCE_ID, dataset=f"{variable.product} · {variable.band}", version="Colección publicada por el servicio ORNL DAAC",
        variable=variable.key, unit=variable.unit, temporal_resolution="Anual", spatial_resolution=variable.resolution,
        downloaded_at=band.downloaded_at, source_url=band.source_url, provenance=band.provenance, quality_notes=notes,
    )


def _annual(band: ModisBand, indices: list[int], variable: ModisVariable) -> list[Observation]:
    low, high = variable.valid
    series = []
    for item in band.dates:
        values = [item.data[i] for i in indices if low <= item.data[i] <= high]
        if values and len(values) >= MIN_VALID_SHARE * len(indices):
            series.append(Observation.model_construct(timestamp=date(item.calendar_date.year, 1, 1), value=fmean(values) * variable.scale))
    return series


def _summary(variable: ModisVariable, series: list[Observation], band: ModisBand, pixels: int, fallback: bool) -> VariableSummary:
    values = [item.value for item in series]
    mean = fmean(values)
    return VariableSummary(
        variable=variable.key, label=variable.label, mean=mean, minimum=min(values), maximum=max(values),
        unit=variable.unit, display_unit=display_unit(variable.unit), valid_observations=len(series),
        completeness_percent=round(len(series) / len(band.dates) * 100, 2),
        annual_variability_percent=round(pstdev(values) / abs(mean) * 100, 3) if len(values) >= 2 and abs(mean) > 1e-12 else None,
        trend=analyze_trend(series, already_annual=True), source=_source(band, variable, pixels, fallback),
        annual_series=[AnnualObservation(year=item.timestamp.year, value=round(item.value, 6)) for item in series],
        last_valid_date=series[-1].timestamp,
    )


def _land_cover(band: ModisBand, indices: list[int]) -> LandCoverChange | None:
    if len(band.dates) < 2:
        return None
    first, last = band.dates[0], band.dates[-1]
    pairs = [(first.data[i], last.data[i]) for i in indices if first.data[i] in IGBP_CLASSES and last.data[i] in IGBP_CLASSES]
    if not pairs:
        return None
    before, after = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    classes = [LandCoverClass(code=code, label=IGBP_CLASSES[code], first_percent=round(before[code] / len(pairs) * 100, 1),
                              last_percent=round(after[code] / len(pairs) * 100, 1))
               for code in sorted(set(before) | set(after), key=lambda c: -(before[c] + after[c]))]
    return LandCoverChange(
        first_year=first.calendar_date.year, last_year=last.calendar_date.year, pixels=len(pairs),
        changed_percent=round(sum(1 for a, b in pairs if a != b) / len(pairs) * 100, 1), classes=classes,
        provenance=band.provenance, downloaded_at=band.downloaded_at, source_url=band.source_url,
        limitations=["Clasificación automática a 500 m: un cambio de clase en pocos píxeles puede ser error de clasificación y no cambio real.",
                     "Compara solo el primer y el último año publicados; no describe la trayectoria intermedia."],
    )


COVERAGE_NOTE_BELOW = 95.0


def _coverage_note(band: ModisBand, pixels: int, area_km2: float) -> str | None:
    """La ventana MODIS tiene un tope de ±10 km: en áreas grandes solo se analiza la parte central."""
    covered = pixels * band.grid.cellsize ** 2 / 1_000_000
    share = min(100.0, covered / area_km2 * 100) if area_km2 > 0 else 100.0
    if share >= COVERAGE_NOTE_BELOW:
        return None
    return (f"La ventana MODIS (±10 km alrededor del punto representativo) cubre {share:.0f} % del área ({covered:,.0f} de {area_km2:,.0f} km²); "
            "los indicadores describen esa parte, no el área completa.")


async def subject_vegetation(point: Point, study_area: dict[str, Any], km: int, area_km2: float) -> SubjectVegetation:
    """Series anuales y cambio de cobertura MODIS para un área; los errores del servicio quedan como notas, no como ceros."""
    out = SubjectVegetation()
    connector = ModisSubsetConnector()
    requests = [(variable.product, variable.band) for variable in VEGETATION_VARIABLES] + [LAND_COVER]
    results = await asyncio.gather(*(connector.band(product, band, point.latitude, point.longitude, km) for product, band in requests),
                                   return_exceptions=True)
    masks: dict[tuple, tuple[list[int], bool]] = {}

    def mask(band: ModisBand) -> tuple[list[int], bool]:
        key = (band.grid.xllcorner, band.grid.yllcorner, band.grid.cellsize, band.grid.nrows, band.grid.ncols)
        if key not in masks:
            masks[key] = pixels_inside(band.grid, study_area, point.longitude, point.latitude)
        return masks[key]

    for variable, result in zip(VEGETATION_VARIABLES, results[:-1], strict=True):
        if isinstance(result, ModisSubsetError):
            out.errors.append(f"{variable.label}: {result}")
            continue
        if isinstance(result, BaseException):
            raise result
        indices, fallback = mask(result)
        if not out.pixels:   # una sola vez: las grillas de 250 y 500 m cubren la misma ventana
            note = _coverage_note(result, len(indices), area_km2)
            if note:
                out.notes.append(note)
        out.pixels[variable.product] = len(indices)
        series = _annual(result, indices, variable)
        if len(series) < MIN_YEARS:
            years = "ningún año tiene" if not series else f"solo {len(series)} años tienen"
            out.notes.append(f"{variable.label}: {years} al menos la mitad de los píxeles con valor medible; no se calcula tendencia. {variable.fill_note}")
            continue
        out.summaries.append(_summary(variable, series, result, len(indices), fallback))
    land = results[-1]
    if isinstance(land, ModisSubsetError):
        out.errors.append(f"Cobertura del suelo: {land}")
    elif isinstance(land, BaseException):
        raise land
    else:
        indices, _ = mask(land)
        out.pixels[LAND_COVER[0]] = len(indices)
        out.land_cover = _land_cover(land, indices)
    return out
