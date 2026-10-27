"""Contraste de temperatura y radiación con ERA5 (vía PVGIS), compartido por Clima y Energía.

NASA POWER entrega la temperatura de MERRA-2 y la radiación de CERES; ERA5 es un reanálisis independiente de ambos.
Las tendencias se comparan en los años que tienen las dos fuentes (2005–2023): la pendiente principal se recalcula
en esos años y Benjamini–Hochberg ajusta cada fuente entre sitios, igual que en el análisis principal. ERA5 se pide
en el punto representativo; un territorio que en NASA POWER es promedio de celdas se compara con ese punto.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..connectors.jrc.pvgis import Era5Annual, PvgisConnector, PvgisError
from ..schemas.analysis import Observation, Point, TrendResult
from ..schemas.pipeline import AnnualObservation, DataGap, ExtremeCountercheck, VariableSummary
from ..statistics.multiple_testing import benjamini_hochberg
from ..statistics.trends import analyze_trend, decision_p_value
from .analysis import agreement

ERA5_SOURCE = "ERA5 (ECMWF) vía PVGIS (JRC)"
# Variable de NASA POWER → serie anual de ERA5 y nombre de la fuente principal en las frases.
ERA5_VARIABLES = {"T2M": "temperature", "ALLSKY_SFC_SW_DWN": "irradiance", "WS10M": "wind"}
PRIMARY_NAMES = {"T2M": "MERRA-2", "ALLSKY_SFC_SW_DWN": "CERES", "WS10M": "MERRA-2"}
MIN_COMMON_YEARS = 10
CONCURRENCY = 3
WIND_WAIT_SECONDS = 45.0     # el viento horario de un punto nuevo tarda ~17 s; varios puntos, más de un minuto
_inflight: dict[str, asyncio.Task] = {}
ERA5_NOTE = (
    "Contraste de temperatura, radiación y viento: ERA5 (ECMWF, ~31 km) vía PVGIS del JRC, independiente de MERRA-2 y de CERES. Las "
    "tendencias se comparan en los años que tienen ambas fuentes (2005–2023), con la pendiente de NASA POWER recalculada en esos mismos "
    "años; ERA5 se lee en el punto representativo de cada sujeto y el viento se promedia desde su serie horaria."
)


@dataclass
class Era5Result:
    series: list[Era5Annual | None]
    errors: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)   # sujetos cuyo viento horario sigue descargándose


def _wind_task(point: Point) -> asyncio.Task:
    """Una descarga de viento por punto, compartida entre consultas simultáneas y que sobrevive al presupuesto de espera."""
    key = f"{point.latitude:.4f},{point.longitude:.4f}"
    task = _inflight.get(key)
    if task is None or (task.done() and (task.cancelled() or task.exception() is not None)):
        task = asyncio.get_running_loop().create_task(PvgisConnector().era5_wind(point.latitude, point.longitude))
        _inflight[key] = task
        task.add_done_callback(lambda t, k=key: _inflight.pop(k, None) if not t.cancelled() and t.exception() is None else None)
    return task


@dataclass
class _Fit:
    """Forma mínima que espera `agreement`: tendencia y significancia tras BH."""

    trend: TrendResult
    adjusted_p_value: float | None = None
    significant_after_bh: bool = False


async def era5_series(subjects: Sequence[tuple[str, Point]], wait: float = WIND_WAIT_SECONDS) -> Era5Result:
    """Serie anual ERA5 por sujeto (etiqueta, punto representativo); un sujeto sin respuesta queda en None, no en cero.

    Temperatura y radiación llegan en una consulta mensual corta. El viento sale de la serie horaria: si no termina
    dentro de `wait`, se declara «descargándose» y la descarga sigue en segundo plano para la siguiente ejecución.
    """
    connector = PvgisConnector()
    limit = asyncio.Semaphore(CONCURRENCY)
    result = Era5Result(series=[None] * len(subjects))
    wind_tasks = [_wind_task(point) for _, point in subjects]

    async def one(index: int, label: str, point: Point) -> None:
        async with limit:
            try:
                result.series[index] = await connector.era5_annual(point.latitude, point.longitude)
            except PvgisError as exc:
                result.errors.append(f"{label}: {exc}")

    await asyncio.gather(*(one(index, label, point) for index, (label, point) in enumerate(subjects)))
    done, _ = await asyncio.wait(wind_tasks, timeout=wait) if wind_tasks else (set(), set())
    for (label, _), series, task in zip(subjects, result.series, wind_tasks, strict=True):
        if series is None:
            continue
        if task not in done:
            result.pending.append(label)
        elif task.exception() is not None:
            result.errors.append(f"{label}: viento · {task.exception()}")
        else:
            series.wind = task.result()
    return result


def _adjust(fits: list[_Fit]) -> None:
    adjusted = benjamini_hochberg([decision_p_value(fit.trend) for fit in fits])
    for fit, value in zip(fits, adjusted, strict=True):
        fit.adjusted_p_value = value
        fit.significant_after_bh = value is not None and value < fit.trend.alpha


def attach_era5(variables_by_site: Sequence[Sequence[VariableSummary]], era5: Era5Result) -> None:
    """Anota en temperatura y radiación de cada sitio su contraste ERA5 en los años comunes."""
    for code, attribute in ERA5_VARIABLES.items():
        family = []
        for variables, series in zip(variables_by_site, era5.series, strict=True):
            summary = next((item for item in variables if item.variable == code), None)
            if summary is None or series is None:
                continue
            primary_by_year = {point.year: point.value for point in summary.annual_series}
            common = [item for item in getattr(series, attribute) if item.timestamp.year in primary_by_year]
            if len(common) < MIN_COMMON_YEARS:
                continue
            primary = [Observation(timestamp=item.timestamp, value=primary_by_year[item.timestamp.year]) for item in common]
            family.append((summary, common, _Fit(analyze_trend(common, already_annual=True)), _Fit(analyze_trend(primary, already_annual=True))))
        if not family:
            continue
        _adjust([twin for _, _, twin, _ in family])
        _adjust([primary for _, _, _, primary in family])
        for summary, common, twin, primary in family:
            years = [item.timestamp.year for item in common]
            summary.counterchecks.append(ExtremeCountercheck(
                source=ERA5_SOURCE, valid_years=len(common), direction=twin.trend.direction, slope_per_year=twin.trend.slope_per_year,
                adjusted_p_value=twin.adjusted_p_value, significant_after_bh=twin.significant_after_bh, agreement=agreement(primary, twin),
                annual_series=[AnnualObservation(year=item.timestamp.year, value=item.value) for item in common],
                period=f"{years[0]}–{years[-1]}", primary_slope_per_year=primary.trend.slope_per_year,
            ))


def era5_gaps(era5: Era5Result) -> list[DataGap]:
    gaps = []
    if era5.pending:
        gaps.append(DataGap(dataset="ERA5 · viento horario (PVGIS)",
                            impact=f"La serie horaria de viento se está descargando para: {', '.join(era5.pending)}. Esta ejecución contrasta solo temperatura y radiación en esos sujetos.",
                            next_action="Volver a ejecutar en uno o dos minutos: la descarga continúa en segundo plano y queda en caché."))
    if era5.errors:
        gaps.append(DataGap(dataset="ERA5 vía PVGIS (contraste de temperatura, radiación y viento)", impact="; ".join(era5.errors)[:400],
                            next_action="Reintentar; un sitio sin ERA5 queda sin ese contraste, no con ceros."))
    return gaps
