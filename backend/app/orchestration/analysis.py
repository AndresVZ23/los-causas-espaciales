"""Análisis de tendencias común a todos los sectores.

Resume cada variable por sujeto (media, extremos, cobertura, variabilidad, Mann–Kendall corregido, Sen) y
ajusta con Benjamini–Hochberg cada variable entre los sujetos comparados.
"""

from collections.abc import Sequence
from statistics import fmean, pstdev

from ..connectors.nasa.power import PowerConnectorError
from ..core.units import display_unit
from ..core.variables import variable_label
from ..schemas.analysis import Observation, SourceMetadata
from ..schemas.pipeline import AnnualObservation, VariableSummary
from ..statistics.multiple_testing import benjamini_hochberg
from ..statistics.trends import analyze_trend, annual_means, decision_p_value
from .extraction import PowerDataset


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
    )


def analyze_subjects(datasets: Sequence[PowerDataset], variables: Sequence[str], expected_days: int) -> list[list[VariableSummary]]:
    """Devuelve, por sujeto y en el orden de `variables`, el resumen con significancia ajustada por BH."""
    by_subject = [[summarize_variable(variable, *dataset[variable], expected_days) for variable in variables] for dataset in datasets]
    for index, _ in enumerate(variables):
        family = [subject[index] for subject in by_subject]
        adjusted = benjamini_hochberg([decision_p_value(item.trend) for item in family])
        for item, adjusted_p in zip(family, adjusted, strict=True):
            item.adjusted_p_value = adjusted_p
            item.significant_after_bh = adjusted_p is not None and adjusted_p < item.trend.alpha
    return by_subject
