from collections import Counter, defaultdict
from datetime import date

import numpy as np
from scipy.stats import kendalltau, norm, rankdata, theilslopes

from ..schemas.analysis import Observation, TrendResult


MIN_YEAR_COVERAGE = 0.9


def _days_in_year(year: int) -> int:
    return 366 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 365


def annual_means(observations: list[Observation]) -> list[Observation]:
    """Medias anuales de una serie diaria, solo de años con al menos 90 % de días válidos.

    Un año incompleto (como el año en curso) no es comparable: su media depende de qué estaciones cubre.
    """
    grouped: dict[int, list[float]] = defaultdict(list)
    for item in observations:
        if np.isfinite(item.value):
            grouped[item.timestamp.year].append(item.value)
    return [
        Observation(timestamp=date(year, 1, 1), value=float(np.mean(values)))
        for year, values in sorted(grouped.items())
        if len(values) >= MIN_YEAR_COVERAGE * _days_in_year(year)
    ]


def partial_years(observations: list[Observation]) -> list[int]:
    """Años con datos pero sin cobertura suficiente para entrar en la tendencia."""
    counts: dict[int, int] = defaultdict(int)
    for item in observations:
        if np.isfinite(item.value):
            counts[item.timestamp.year] += 1
    return [year for year, count in sorted(counts.items()) if count < MIN_YEAR_COVERAGE * _days_in_year(year)]


def mann_kendall_s(values: np.ndarray) -> int:
    n = len(values)
    return int(sum(np.sign(values[j] - values[i]) for i in range(n - 1) for j in range(i + 1, n)))


def mann_kendall_variance(values: np.ndarray) -> float:
    """Varianza de S con corrección por empates (Kendall, 1975)."""
    n = len(values)
    ties = [count for count in Counter(values.tolist()).values() if count > 1]
    return (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties)) / 18


def _autocorrelation(series: np.ndarray, max_lag: int) -> np.ndarray:
    """Autocorrelación muestral sesgada (normalizada por n), como en Hamed y Rao (1998)."""
    centred = series - series.mean()
    n = len(series)
    autocovariance = np.correlate(centred, centred, "full")[n - 1:] / n
    if autocovariance[0] == 0:
        return np.zeros(max_lag + 1)
    return autocovariance[: max_lag + 1] / autocovariance[0]


def hamed_rao_correction(values: np.ndarray, times: np.ndarray, slope: float, alpha: float) -> tuple[float, float, int]:
    """Factor n/n* de Hamed y Rao (1998) sobre los rangos de la serie sin tendencia.

    Devuelve (factor, autocorrelación lag-1 de los rangos sin tendencia, rezagos significativos).
    Solo cuentan los rezagos fuera de ±z(1-α/2)/√n.
    """
    n = len(values)
    ranks = rankdata(values - slope * times)
    acf = _autocorrelation(ranks, n - 1)
    bound = norm.ppf(1 - alpha / 2) / np.sqrt(n)
    significant = [lag for lag in range(1, n) if abs(acf[lag]) > bound]
    total = sum((n - lag) * (n - lag - 1) * (n - lag - 2) * acf[lag] for lag in significant)
    factor = 1 + 2 / (n * (n - 1) * (n - 2)) * total
    return float(factor), float(acf[1]), len(significant)


def _z_score(s: int, variance: float) -> float:
    if s > 0:
        return (s - 1) / np.sqrt(variance)
    if s < 0:
        return (s + 1) / np.sqrt(variance)
    return 0.0


def analyze_trend(observations: list[Observation], alpha: float = 0.05, *, already_annual: bool = False) -> TrendResult:
    """Tendencia sobre medias anuales de años completos.

    `already_annual=True` indica que cada observación ya es un valor anual (por ejemplo, un índice ETCCDI).
    """
    annual = sorted(observations, key=lambda item: item.timestamp) if already_annual else annual_means(observations)
    method = "Mann-Kendall modificado (Hamed y Rao, 1998) y pendiente de Sen sobre medias anuales"
    limitations = ["Las estimaciones de grilla para un punto no sustituyen mediciones in situ."]
    if not already_annual:
        excluded = partial_years(observations)
        if excluded:
            limitations.append(f"Años incompletos excluidos de la tendencia: {', '.join(map(str, excluded))}.")
    if len(annual) < 5:
        return TrendResult(
            method=method,
            direction="insufficient_evidence",
            slope_per_year=None,
            p_value=None,
            confidence_interval=None,
            significant=False,
            valid_observations=len(annual),
            autocorrelation_lag1=None,
            interpretation="Evidencia insuficiente para establecer una tendencia estadísticamente significativa.",
            limitations=limitations + ["Existen menos de cinco observaciones anuales completas."],
        )

    years = np.asarray([o.timestamp.year for o in annual], dtype=float)
    values = np.asarray([o.value for o in annual], dtype=float)
    n = len(values)
    tau = kendalltau(years, values, nan_policy="omit")
    sen = theilslopes(values, years, alpha=1 - alpha)

    raw_autocorrelation = None
    if n >= 3 and np.std(values[:-1]) > 0 and np.std(values[1:]) > 0:
        raw_autocorrelation = float(np.corrcoef(values[:-1], values[1:])[0, 1])

    s = mann_kendall_s(values)
    variance = mann_kendall_variance(values)
    # Tiempo relativo (1, 2, …) en lugar del año absoluto: evita error de redondeo al restar la tendencia y respeta años faltantes.
    factor, detrended_lag1, significant_lags = hamed_rao_correction(values, years - years[0] + 1, float(sen.slope), alpha)
    if factor < 1:
        # Criterio conservador (ADR-019): la corrección solo ensancha la varianza. Con autocorrelación negativa, n/n* < 1
        # volvería la prueba más permisiva que la clásica; en series cortas suele venir de un año atípico, no de la física.
        if significant_lags:
            limitations.append(
                f"La serie sin tendencia muestra autocorrelación negativa (factor n/n* = {factor:.3f}); "
                "se conserva la varianza clásica de Mann-Kendall para no exagerar la significancia."
            )
        factor_applied = 1.0
    else:
        factor_applied = factor
    p_modified = float(2 * (1 - norm.cdf(abs(_z_score(s, variance * factor_applied)))))
    if significant_lags and factor > 1:
        limitations.append(
            f"Se detectó autocorrelación significativa en {significant_lags} rezagos de la serie sin tendencia; "
            f"la varianza de S se multiplicó por {factor_applied:.3f}."
        )
    if n < 10:
        limitations.append(f"La serie tiene {n} medias anuales; la potencia de la prueba es baja.")

    significant = bool(np.isfinite(p_modified) and p_modified < alpha)
    direction = "no_trend"
    if significant:
        direction = "increasing" if sen.slope > 0 else "decreasing" if sen.slope < 0 else "no_trend"
    direction_label = {"increasing": "creciente", "decreasing": "decreciente", "no_trend": "sin tendencia"}[direction]
    interpretation = (
        f"Se detectó una tendencia {direction_label} estadísticamente significativa ({sen.slope:.4g} unidades/año, p={p_modified:.3g}, Hamed-Rao)."
        if significant and direction != "no_trend"
        else "Evidencia insuficiente para establecer una tendencia estadísticamente significativa."
    )
    return TrendResult(
        method=method,
        direction=direction,
        slope_per_year=float(sen.slope),
        p_value=float(tau.pvalue),
        p_value_modified=p_modified,
        variance_correction=factor_applied,
        confidence_interval=(float(sen.low_slope), float(sen.high_slope)),
        significant=significant,
        valid_observations=n,
        autocorrelation_lag1=raw_autocorrelation,
        autocorrelation_lag1_detrended=detrended_lag1,
        interpretation=interpretation,
        limitations=limitations,
    )


def decision_p_value(trend: TrendResult) -> float | None:
    """p-value que gobierna la decisión y el ajuste BH: el modificado si existe, si no el clásico."""
    return trend.p_value_modified if trend.p_value_modified is not None else trend.p_value
