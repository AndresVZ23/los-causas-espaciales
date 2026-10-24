"""Índices de extremos de precipitación del ETCCDI sobre series diarias.

Definiciones del Expert Team on Climate Change Detection and Indices (Zhang et al., 2011, WIREs Climate Change 2:851-870;
Karl et al., 1999), con dos adaptaciones declaradas en `METHOD_NOTES`: el percentil 95 se calcula sobre los días húmedos
del propio período analizado (no sobre 1961-1990) y las rachas secas no cruzan el cambio de año.
Funciones puras: no consultan fuentes externas.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from ..schemas.analysis import Observation

WET_DAY_MM = 1.0
MIN_YEAR_COVERAGE = 0.9
# z robusto (mediana y MAD escalada) a partir del cual un valor anual se marca para revisión; no se excluye.
ATYPICAL_ROBUST_Z = 10.0
MAD_SCALE = 1.4826

METHOD_NOTES = (
    "Día húmedo: precipitación ≥ 1 mm. Solo se usan años con al menos 90 % de días válidos.",
    "El percentil 95 de días húmedos se calcula sobre el período analizado, no sobre el período base estándar 1961–1990.",
    "Las rachas secas (CDD) y las ventanas de 5 días (RX5DAY) se cuentan dentro de cada año y no cruzan el 31 de diciembre.",
    "Un año con z robusto mayor que 10 (mediana y MAD) se marca como atípico para contrastarlo con estaciones; no se excluye. "
    "Mann–Kendall usa rangos y no cambia por su magnitud, pero la media anual sí.",
)


@dataclass(frozen=True)
class IndexDefinition:
    code: str
    label: str
    unit: str
    description: str


INDEX_DEFINITIONS: dict[str, IndexDefinition] = {
    "RX1DAY": IndexDefinition("RX1DAY", "Lluvia máxima en 1 día", "mm", "Máximo anual de precipitación diaria."),
    "RX5DAY": IndexDefinition("RX5DAY", "Lluvia máxima en 5 días", "mm", "Máximo anual de la suma de 5 días consecutivos."),
    "R95P": IndexDefinition("R95P", "Lluvia de días muy húmedos", "mm", "Total anual de los días húmedos sobre el percentil 95."),
    "PRCPTOT": IndexDefinition("PRCPTOT", "Lluvia anual en días húmedos", "mm", "Total anual de precipitación en días con al menos 1 mm."),
    "R10MM": IndexDefinition("R10MM", "Días de lluvia intensa", "días", "Número anual de días con al menos 10 mm."),
    "CDD": IndexDefinition("CDD", "Racha seca más larga", "días", "Máximo anual de días consecutivos con menos de 1 mm."),
}


def linear_percentile(values: list[float], probability: float) -> float | None:
    """Percentil lineal determinista sobre valores finitos ya validados, sin depender del default de NumPy."""
    if not values:
        return None
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between 0 and 1")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _days_in_year(year: int) -> int:
    return 366 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 365


def complete_years(observations: list[Observation]) -> dict[int, dict[date, float]]:
    """Agrupa por año y conserva solo los años con cobertura suficiente; nunca rellena faltantes."""
    by_year: dict[int, dict[date, float]] = defaultdict(dict)
    for item in observations:
        if np.isfinite(item.value) and item.value >= 0:
            by_year[item.timestamp.year][item.timestamp] = float(item.value)
    return {year: days for year, days in sorted(by_year.items()) if len(days) >= MIN_YEAR_COVERAGE * _days_in_year(year)}


def wet_day_percentile(years: dict[int, dict[date, float]], percentile: float = 95.0) -> float | None:
    wet = [value for days in years.values() for value in days.values() if value >= WET_DAY_MM]
    return float(np.percentile(wet, percentile)) if wet else None


def _max_run(days: dict[date, float], year: int) -> int:
    """Racha más larga de días secos consecutivos; un día faltante corta la racha."""
    longest = current = 0
    day, end = date(year, 1, 1), date(year, 12, 31)
    while day <= end:
        value = days.get(day)
        current = current + 1 if value is not None and value < WET_DAY_MM else 0
        longest = max(longest, current)
        day += timedelta(days=1)
    return longest


def _max_window_sum(days: dict[date, float], window: int) -> float | None:
    """Máxima suma de `window` días calendario consecutivos con datos completos."""
    best = None
    for start in sorted(days):
        span = [days.get(start + timedelta(days=offset)) for offset in range(window)]
        if all(value is not None for value in span):
            total = float(sum(span))
            best = total if best is None or total > best else best
    return best


def atypical_years(series: list[Observation], threshold: float = ATYPICAL_ROBUST_Z) -> list[tuple[int, float, float]]:
    """Años cuyo valor supera la mediana en más de `threshold` MAD escaladas: (año, valor, z robusto).

    Solo cola superior: los artefactos de reanálisis en lluvia aparecen como picos. Con MAD nula no se marca nada.
    """
    values = np.asarray([item.value for item in series], dtype=float)
    if len(values) < 5:
        return []
    median = float(np.median(values))
    spread = MAD_SCALE * float(np.median(np.abs(values - median)))
    if spread == 0:
        return []
    return [(item.timestamp.year, float(item.value), (item.value - median) / spread) for item in series if (item.value - median) / spread > threshold]


def annual_indices(observations: list[Observation]) -> tuple[dict[str, list[Observation]], float | None, int]:
    """Devuelve las series anuales de cada índice, el umbral del percentil 95 y los años descartados por cobertura."""
    all_years = {item.timestamp.year for item in observations}
    years = complete_years(observations)
    threshold = wet_day_percentile(years)
    series: dict[str, list[Observation]] = {code: [] for code in INDEX_DEFINITIONS}
    for year, days in years.items():
        values = list(days.values())
        stamp = date(year, 1, 1)
        rx5 = _max_window_sum(days, 5)
        computed = {
            "RX1DAY": max(values),
            "RX5DAY": rx5,
            "R95P": float(sum(v for v in values if threshold is not None and v >= WET_DAY_MM and v > threshold)) if threshold is not None else None,
            "PRCPTOT": float(sum(v for v in values if v >= WET_DAY_MM)),
            "R10MM": float(sum(1 for v in values if v >= 10.0)),
            "CDD": float(_max_run(days, year)),
        }
        for code, value in computed.items():
            if value is not None:
                series[code].append(Observation(timestamp=stamp, value=value))
    return series, threshold, len(all_years) - len(years)
