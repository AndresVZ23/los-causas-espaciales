"""Análisis de tendencias común a todos los sectores.

Resume cada variable por sujeto (media, extremos, cobertura, variabilidad, Mann–Kendall corregido, Sen) y
ajusta con Benjamini–Hochberg cada variable entre los sujetos comparados.
"""

from collections import defaultdict
from collections.abc import Sequence
from math import isfinite
from statistics import fmean, pstdev

from ..connectors.nasa.power import PowerConnectorError
from ..core.units import display_unit, is_ratio_scale
from ..core.variables import variable_label
from ..schemas.analysis import Observation, SourceMetadata
from ..schemas.climate import Agreement, AtypicalYear, ExtremeCountercheck, ExtremeIndexSummary
from ..schemas.pipeline import AnnualObservation, CurrentPeriod, VariableSummary
from ..statistics.extremes import INDEX_DEFINITIONS, annual_indices, atypical_years
from ..statistics.multiple_testing import benjamini_hochberg
from ..statistics.trends import analyze_trend, annual_means, decision_p_value, partial_years
from .extraction import PowerDataset

PRECIPITATION = "PRECTOTCORR"


def current_period(observations: list[Observation], unit: str) -> CurrentPeriod | None:
    """Compara el año en curso, si está incompleto, con la misma ventana del calendario en los años completos."""
    valid = [item for item in observations if isfinite(item.value)]
    if not valid:
        return None
    last = max(item.timestamp for item in valid)
    incomplete = partial_years(valid)
    if not incomplete or incomplete[-1] != last.year:
        return None
    complete = {item.timestamp.year for item in annual_means(valid)}
    window: dict[int, list[float]] = defaultdict(list)
    for item in valid:
        if (item.timestamp.month, item.timestamp.day) <= (last.month, last.day) and (item.timestamp.year in complete or item.timestamp.year == last.year):
            window[item.timestamp.year].append(item.value)
    baseline = [fmean(values) for year, values in window.items() if year in complete and values]
    current = window.get(last.year)
    if not baseline or not current:
        return None
    value, baseline_mean = fmean(current), fmean(baseline)
    anomaly = value - baseline_mean
    ranked = sorted([*baseline, value], reverse=True)
    years = sorted(complete)
    return CurrentPeriod(
        year=last.year, through=last, days=len(current), value=round(value, 4), baseline_mean=round(baseline_mean, 4),
        baseline_years=f"{years[0]}–{years[-1]}", anomaly=round(anomaly, 4),
        anomaly_percent=round(anomaly / abs(baseline_mean) * 100, 2) if is_ratio_scale(unit) and abs(baseline_mean) > 1e-12 else None,
        rank=ranked.index(value) + 1, years_compared=len(ranked),
    )


def summarize_variable(variable: str, observations: list[Observation], source: SourceMetadata, expected_days: int) -> VariableSummary:
    if not observations:
        raise PowerConnectorError(f"NASA POWER no devolvió observaciones válidas para {variable}.")
    values = [observation.value for observation in observations]
    annual_observations = annual_means(observations)
    annual_values = [observation.value for observation in annual_observations]
    annual_variability = None
    if len(annual_values) >= 2 and abs(fmean(annual_values)) > 1e-12:
        annual_variability = pstdev(annual_values) / abs(fmean(annual_values)) * 100
    return VariableSummary(
        variable=variable,
        label=variable_label(variable),
        mean=fmean(values),
        minimum=min(values),
        maximum=max(values),
        unit=source.unit,
        display_unit=display_unit(source.unit),
        valid_observations=len(values),
        completeness_percent=round(len(values) / expected_days * 100, 2),
        annual_variability_percent=round(annual_variability, 3) if annual_variability is not None else None,
        trend=analyze_trend(observations),
        source=source,
        annual_series=[
            AnnualObservation(year=observation.timestamp.year, value=round(observation.value, 6))
            for observation in annual_observations
        ],
        last_valid_date=max(observation.timestamp for observation in observations),
        current_period=current_period(observations, source.unit),
    )


def _adjust_by_column(by_subject: list[list], columns: int) -> None:
    """Benjamini–Hochberg por variable (columna) entre los sujetos comparados."""
    for index in range(columns):
        family = [subject[index] for subject in by_subject]
        adjusted = benjamini_hochberg([decision_p_value(item.trend) for item in family])
        for item, adjusted_p in zip(family, adjusted, strict=True):
            item.adjusted_p_value = adjusted_p
            item.significant_after_bh = adjusted_p is not None and adjusted_p < item.trend.alpha


def analyze_subjects(datasets: Sequence[PowerDataset], variables: Sequence[str], expected_days: int) -> list[list[VariableSummary]]:
    """Devuelve, por sujeto y en el orden de `variables`, el resumen con significancia ajustada por BH."""
    by_subject = [[summarize_variable(variable, *dataset[variable], expected_days) for variable in variables] for dataset in datasets]
    _adjust_by_column(by_subject, len(variables))
    return by_subject


def analyze_extremes(datasets: Sequence[PowerDataset], variable: str = PRECIPITATION) -> tuple[list[list[ExtremeIndexSummary]], list[float | None]]:
    """Índices ETCCDI de precipitación por sujeto, con Mann–Kendall corregido y BH por índice entre sujetos.

    `variable` elige la serie diaria (PRECTOTCORR por defecto; IMERG_PRECTOT para el contraste satelital).
    Devuelve los resúmenes por sujeto (en el orden de INDEX_DEFINITIONS) y el umbral P95 de cada sujeto.
    """
    by_subject: list[list[ExtremeIndexSummary]] = []
    thresholds: list[float | None] = []
    for dataset in datasets:
        observations, _source = dataset[variable]
        series, threshold, discarded = annual_indices(observations)
        thresholds.append(threshold)
        summaries = []
        for code, definition in INDEX_DEFINITIONS.items():
            values = [item.value for item in series[code]]
            if not values:
                raise PowerConnectorError(f"No hay años completos para calcular {code}.")
            summaries.append(ExtremeIndexSummary(
                variable=code,
                label=definition.label,
                description=definition.description,
                unit=definition.unit,
                display_unit=definition.unit,
                mean=fmean(values),
                minimum=min(values),
                maximum=max(values),
                valid_years=len(values),
                discarded_years=discarded,
                trend=analyze_trend(series[code], already_annual=True),
                annual_series=[AnnualObservation(year=item.timestamp.year, value=round(item.value, 4)) for item in series[code]],
                atypical_years=[AtypicalYear(year=year, value=round(value, 2), robust_z=round(z, 1)) for year, value, z in atypical_years(series[code])],
            ))
        by_subject.append(summaries)
    _adjust_by_column(by_subject, len(INDEX_DEFINITIONS))
    return by_subject, thresholds


def agreement(primary: ExtremeIndexSummary, other: ExtremeIndexSummary) -> Agreement:
    """Acuerdo entre dos fuentes para el mismo índice y sujeto, ya ajustadas por BH en su propia familia."""
    a, b = primary.significant_after_bh, other.significant_after_bh
    if a and b:
        return Agreement.COINCIDE if primary.trend.direction == other.trend.direction else Agreement.CONTRADICE
    if a:
        return Agreement.SIN_RESPALDO
    return Agreement.SOLO_CONTRASTE if b else Agreement.SIN_TENDENCIA


def attach_countercheck(primary: list[list[ExtremeIndexSummary]], other: list[list[ExtremeIndexSummary] | None], source: str,
                        legacy_slot: bool = True) -> None:
    """Anota en cada índice principal su contraste con otra fuente y el valor de esa fuente en sus años atípicos.

    Se puede llamar una vez por fuente (IMERG, CHIRPS…): todas quedan en `counterchecks`. Solo la fuente con
    `legacy_slot` (IMERG) ocupa además `countercheck`, por compatibilidad: si IMERG falta, ese campo queda vacío en
    vez de mostrar otra fuente con su nombre. Un sujeto sin serie de contraste (None) queda sin anotar, no en cero.
    """
    for primary_site, other_site in zip(primary, other, strict=True):
        if other_site is None:
            continue
        other_by_code = {item.variable: item for item in other_site}
        for item in primary_site:
            twin = other_by_code[item.variable]
            twin_by_year = {point.year: point.value for point in twin.annual_series}
            check = ExtremeCountercheck(
                source=source, valid_years=twin.valid_years, direction=twin.trend.direction, slope_per_year=twin.trend.slope_per_year,
                adjusted_p_value=twin.adjusted_p_value, significant_after_bh=twin.significant_after_bh,
                agreement=agreement(item, twin), annual_series=twin.annual_series,
            )
            item.counterchecks.append(check)
            first = legacy_slot and item.countercheck is None
            if first:
                item.countercheck = check
            for atypical in item.atypical_years:
                value = twin_by_year.get(atypical.year)
                if value is not None:
                    atypical.countercheck_values[source] = value
                if first:
                    atypical.countercheck_value = value
