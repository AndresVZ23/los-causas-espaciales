"""Amenazas naturales (módulo 3): lluvia anual y extremos ETCCDI con contraste GPM IMERG en cada área.

Reutiliza la extracción y la estadística del módulo Clima sobre el punto representativo de cada área: NASA POWER
(con la verificación de escala ×24) e IMERG servido por la misma API. Un área grande se describe por su punto
representativo y así se declara; para el promedio areal por celdas está el módulo Clima.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from ..connectors.nasa.power import PowerConnectorError
from ..orchestration.analysis import PRECIPITATION, analyze_extremes, analyze_subjects, attach_countercheck
from ..orchestration.extraction import extract_power
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


async def rainfall_extremes(points: Sequence[Point]) -> RainfallResult:
    end = date.today()
    try:
        datasets, _ = await extract_power(points, REQUEST_VARIABLES, START, end)
        climate = analyze_subjects(datasets, [PRECIPITATION], (end - START).days + 1)
        extremes, thresholds = analyze_extremes(datasets)
    except PowerConnectorError as exc:
        return RainfallResult(areas=[AreaRainfall() for _ in points], power_error=str(exc))
    countercheck_error = None
    try:
        countercheck, _ = analyze_extremes(datasets, COUNTERCHECK)
        attach_countercheck(extremes, countercheck, COUNTERCHECK_SOURCE)
    except PowerConnectorError as exc:
        countercheck_error = str(exc)
    areas = [AreaRainfall(climate=c, extremes=e, wet_day_p95_mm=t) for c, e, t in zip(climate, extremes, thresholds, strict=True)]
    return RainfallResult(areas=areas, countercheck_error=countercheck_error)
