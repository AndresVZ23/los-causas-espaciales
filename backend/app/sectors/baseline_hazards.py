"""Amenazas naturales (módulo 3): lluvia anual y extremos ETCCDI con contraste GPM IMERG en cada área.

Reutiliza la extracción y la estadística del módulo Clima sobre el punto representativo de cada área: NASA POWER
(con la verificación de escala ×24) e IMERG servido por la misma API. Un área grande se describe por su punto
representativo y así se declara; para el promedio areal por celdas está el módulo Clima.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..connectors.nasa.power import PowerConnectorError
from ..orchestration.analysis import PRECIPITATION, analyze_extremes, analyze_subjects, attach_countercheck
from ..orchestration.extraction import extract_power
from ..orchestration.rainfall_crosscheck import ChirpsResult, attach_chirps, chirps_extremes
from ..schemas.analysis import Point
from ..schemas.climate import ExtremeIndexSummary
from ..schemas.pipeline import VariableSummary
from .climate import COUNTERCHECK, COUNTERCHECK_SOURCE

START = date(2001, 1, 1)
REQUEST_VARIABLES = [PRECIPITATION, COUNTERCHECK]


@dataclass
class AreaRainfall:
    climate: list[VariableSummary] = field(default_factory=list)
    extremes: list[ExtremeIndexSummary] = field(default_factory=list)
    wet_day_p95_mm: float | None = None


@dataclass
class RainfallResult:
    areas: list[AreaRainfall]
    power_error: str | None = None          # sin serie: las preguntas de tendencia quedan sin respuesta
    countercheck_error: str | None = None   # sin IMERG: los extremos quedan sin contraste independiente
    chirps: ChirpsResult | None = None      # tercer contraste (CHIRPS sobre el polígono del área)


async def rainfall_extremes(subjects: Sequence[tuple[str, dict[str, Any] | None, Point]]) -> RainfallResult:
    """Lluvia y extremos por área: NASA POWER e IMERG en el punto representativo, CHIRPS promediado sobre el área."""
    end = date.today()
    points = [point for _, _, point in subjects]

    async def power():
        datasets, _ = await extract_power(points, REQUEST_VARIABLES, START, end)
        return datasets

    power_result, chirps = await asyncio.gather(power(), chirps_extremes(subjects, START, end), return_exceptions=True)
    if isinstance(chirps, BaseException):
        raise chirps
    try:
        if isinstance(power_result, BaseException):
            raise power_result
        climate = analyze_subjects(power_result, [PRECIPITATION], (end - START).days + 1)
        extremes, thresholds = analyze_extremes(power_result)
    except PowerConnectorError as exc:
        return RainfallResult(areas=[AreaRainfall() for _ in points], power_error=str(exc), chirps=chirps)
    countercheck_error = None
    try:
        countercheck, _ = analyze_extremes(power_result, COUNTERCHECK)
        attach_countercheck(extremes, countercheck, COUNTERCHECK_SOURCE)
    except PowerConnectorError as exc:
        countercheck_error = str(exc)
    attach_chirps(extremes, chirps)
    areas = [AreaRainfall(climate=c, extremes=e, wet_day_p95_mm=t) for c, e, t in zip(climate, extremes, thresholds, strict=True)]
    return RainfallResult(areas=areas, countercheck_error=countercheck_error, chirps=chirps)
