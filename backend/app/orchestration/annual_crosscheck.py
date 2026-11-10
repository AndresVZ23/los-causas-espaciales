"""Contraste de una serie anual con una segunda fuente, compartido por ERA5 (temperatura, radiación, viento) y por
el caudal (GEOGLOWS).

Las tendencias se comparan en los años que tienen las dos fuentes: la pendiente principal se recalcula en esos años
y Benjamini–Hochberg ajusta cada fuente entre los sujetos comparados, igual que en el análisis principal.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ..schemas.analysis import Observation, TrendResult
from ..schemas.pipeline import AnnualObservation, ExtremeCountercheck, VariableSummary
from ..statistics.multiple_testing import benjamini_hochberg
from ..statistics.trends import analyze_trend, decision_p_value
from .analysis import agreement

MIN_COMMON_YEARS = 10


@dataclass
class _Fit:
    """Forma mínima que espera `agreement`: tendencia y significancia tras BH."""

    trend: TrendResult
    adjusted_p_value: float | None = None
    significant_after_bh: bool = False


def _adjust(fits: list[_Fit]) -> None:
    adjusted = benjamini_hochberg([decision_p_value(fit.trend) for fit in fits])
    for fit, value in zip(fits, adjusted, strict=True):
        fit.adjusted_p_value = value
        fit.significant_after_bh = value is not None and value < fit.trend.alpha


def attach_annual_countercheck(pairs: Sequence[tuple[VariableSummary, Sequence[Observation]]], source: str) -> None:
    """Anota en cada resumen su contraste con la serie anual de `source`. `pairs` es la familia BH: la misma variable
    en cada sujeto con su serie de contraste. Un sujeto con menos de diez años comunes queda sin anotar, no en cero."""
    family = []
    for summary, twin_series in pairs:
        primary_by_year = {point.year: point.value for point in summary.annual_series}
        common = [item for item in twin_series if item.timestamp.year in primary_by_year]
        if len(common) < MIN_COMMON_YEARS:
            continue
        primary = [Observation(timestamp=item.timestamp, value=primary_by_year[item.timestamp.year]) for item in common]
        family.append((summary, common, _Fit(analyze_trend(common, already_annual=True)), _Fit(analyze_trend(primary, already_annual=True))))
    if not family:
        return
    _adjust([twin for _, _, twin, _ in family])
    _adjust([primary for _, _, _, primary in family])
    for summary, common, twin, primary in family:
        years = [item.timestamp.year for item in common]
        summary.counterchecks.append(ExtremeCountercheck(
            source=source, valid_years=len(common), direction=twin.trend.direction, slope_per_year=twin.trend.slope_per_year,
            adjusted_p_value=twin.adjusted_p_value, significant_after_bh=twin.significant_after_bh, agreement=agreement(primary, twin),
            annual_series=[AnnualObservation(year=item.timestamp.year, value=item.value) for item in common],
            period=f"{years[0]}–{years[-1]}", primary_slope_per_year=primary.trend.slope_per_year,
        ))
