"""Análisis por territorio (departamento, provincia o distrito): celdas NASA POWER, promedio por área y tendencias por celda.

El endpoint regional de POWER solo acepta 366 días por pedido (verificado el 2026-10-23), así que no sirve para 25 años.
Se usa una vez, con el último año, para descubrir qué celdas cubren el territorio y su peso por área (conector K1 de
Codex). Luego cada celda se pide como punto, que devuelve exactamente esa celda, con todas las variables y todo el
período en una sola consulta, y pasa por la misma verificación de escala de precipitación que los sitios.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from ..connectors.nasa.power import PowerConnectorError
from ..connectors.nasa.power_regional import RegionalPowerConnector, RegionalPowerError, aggregate_cells
from ..connectors.peru.admin_boundaries import PeruTerritoryCatalog, TerritoryCatalogError
from ..schemas.analysis import Observation, Point, Provenance, SourceMetadata
from ..schemas.spatial_sampling import PowerCellSeries, SpatialSamplingRequest
from ..schemas.territory import TerritoryLevel, TerritorySummary
from ..statistics.multiple_testing import benjamini_hochberg
from ..statistics.trends import analyze_trend, decision_p_value
from .extraction import PowerDataset, extract_power

DISCOVERY_DAYS = 365
POINT_BATCH = 4          # pedidos simultáneos a POWER por tanda: evita respuestas 429
MAX_CELLS = 60           # más celdas que esto: se pide elegir un territorio menor


class TerritoryAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class TerritoryCell:
    cell_id: str
    center: Point
    bounds: tuple[float, float, float, float]
    weight: float
    overlap_area_km2: float


@dataclass(frozen=True)
class TerritoryExtraction:
    summary: TerritorySummary
    geometry: dict
    mode: str                      # "REGIONAL" o "POINT" (territorio menor que una celda)
    coverage_percent: float
    grid_degrees: tuple[float, float] | None
    cells: list[TerritoryCell]
    cell_datasets: list[PowerDataset]
    dataset: PowerDataset          # promedio ponderado por área, por variable


def _aggregate(variable: str, cells: Sequence[TerritoryCell], datasets: Sequence[PowerDataset], mode: str) -> tuple[list[Observation], SourceMetadata]:
    series = [PowerCellSeries(cell_id=cell.cell_id, center=cell.center, bounds=cell.bounds, overlap_area_km2=max(cell.overlap_area_km2, 1e-9),
                              weight=cell.weight, observations=data[variable][0]) for cell, data in zip(cells, datasets, strict=True)]
    observations = [Observation.model_construct(timestamp=item.timestamp, value=item.value) for item in aggregate_cells(series)]
    sources = [data[variable][1] for data in datasets]
    base = sources[0]
    provenance = Provenance.REAL if any(source.provenance == Provenance.REAL for source in sources) else Provenance.CACHED
    notes = sorted({note for source in sources for note in source.quality_notes})
    method = ("Promedio diario ponderado por área de intersección de "
              f"{len(cells)} celda(s) NASA POWER, cada una pedida como punto con todo el período.") if mode == "REGIONAL" else \
             "Territorio menor que una celda: se usa el punto representativo."
    return observations, base.model_copy(update={"provenance": provenance, "quality_notes": [method, *notes]})


async def extract_territory(level: TerritoryLevel, ubigeo: str, variables: Sequence[str], start: date, end: date) -> TerritoryExtraction:
    catalog = PeruTerritoryCatalog()
    try:
        geometry = catalog.geometry(level, ubigeo)
    except TerritoryCatalogError as exc:
        raise TerritoryAnalysisError(str(exc)) from exc
    discovery_end = min(end, date.today() - timedelta(days=7))
    request = SpatialSamplingRequest(subject=geometry.feature, variable="T2M", start_date=discovery_end - timedelta(days=DISCOVERY_DAYS - 1), end_date=discovery_end)
    try:
        discovery = await RegionalPowerConnector().sample(request)
    except RegionalPowerError as exc:
        message = f"No se pudieron ubicar las celdas de {geometry.territory.name}: {exc}"
        # Caída o error HTTP del proveedor: es falla de NASA POWER (502), no de la solicitud (422).
        if isinstance(exc.__cause__, httpx.HTTPError):
            raise PowerConnectorError(message) from exc
        raise TerritoryAnalysisError(message) from exc
    if len(discovery.cells) > MAX_CELLS:
        raise TerritoryAnalysisError(f"{geometry.territory.name} abarca {len(discovery.cells)} celdas; el máximo es {MAX_CELLS}. Elija una provincia o un distrito.")
    cells = [TerritoryCell(cell_id=cell.cell_id, center=Point(latitude=cell.center.latitude, longitude=cell.center.longitude, label=cell.cell_id),
                           bounds=cell.bounds, weight=cell.weight, overlap_area_km2=cell.overlap_area_km2) for cell in discovery.cells]
    datasets: list[PowerDataset] = []
    for batch_start in range(0, len(cells), POINT_BATCH):
        batch = cells[batch_start:batch_start + POINT_BATCH]
        batch_data, _ = await extract_power([cell.center for cell in batch], variables, start, end)
        datasets.extend(batch_data)
    dataset = {variable: _aggregate(variable, cells, datasets, discovery.mode) for variable in variables}
    return TerritoryExtraction(
        summary=geometry.territory, geometry=geometry.feature.get("geometry", geometry.feature), mode=discovery.mode,
        coverage_percent=discovery.spatial_coverage_percent, grid_degrees=discovery.grid_spacing_degrees,
        cells=cells, cell_datasets=datasets, dataset=dataset,
    )


@dataclass(frozen=True)
class CellTrendValue:
    cell_id: str
    center: Point
    bounds: tuple[float, float, float, float]
    weight: float
    variable: str
    direction: str
    slope_per_year: float | None
    p_value: float | None
    adjusted_p_value: float | None
    significant: bool
    valid_years: int


def cell_trends(extraction: TerritoryExtraction, variables: Sequence[str]) -> list[CellTrendValue]:
    """Mann–Kendall con Hamed–Rao por celda y Benjamini–Hochberg entre las celdas de cada variable."""
    out: list[CellTrendValue] = []
    for variable in variables:
        trends = [analyze_trend(data[variable][0]) for data in extraction.cell_datasets]
        p_values = [decision_p_value(trend) for trend in trends]
        valid = [(index, p) for index, p in enumerate(p_values) if p is not None]
        adjusted = dict(zip([index for index, _ in valid], benjamini_hochberg([p for _, p in valid]), strict=True)) if valid else {}
        for index, (cell, trend) in enumerate(zip(extraction.cells, trends, strict=True)):
            p_adj = adjusted.get(index)
            significant = p_adj is not None and p_adj < 0.05 and trend.direction in {"increasing", "decreasing"}
            out.append(CellTrendValue(cell_id=cell.cell_id, center=cell.center, bounds=cell.bounds, weight=cell.weight, variable=variable,
                                      direction=trend.direction if significant else "no_trend", slope_per_year=trend.slope_per_year,
                                      p_value=p_values[index], adjusted_p_value=p_adj, significant=significant, valid_years=trend.valid_observations))
    return out


async def extract_territories(refs: Sequence[tuple[TerritoryLevel, str]], variables: Sequence[str], start: date, end: date) -> list[TerritoryExtraction]:
    return list(await asyncio.gather(*(extract_territory(level, ubigeo, variables, start, end) for level, ubigeo in refs)))
