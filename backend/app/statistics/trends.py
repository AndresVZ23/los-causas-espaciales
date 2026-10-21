from collections import defaultdict
from datetime import date

import numpy as np
from scipy.stats import kendalltau, theilslopes

from ..schemas.analysis import Observation, TrendResult


def annual_means(observations: list[Observation]) -> list[Observation]:
    grouped: dict[int, list[float]] = defaultdict(list)
    for item in observations:
        if np.isfinite(item.value):
            grouped[item.timestamp.year].append(item.value)
    return [
        Observation(timestamp=date(year, 1, 1), value=float(np.mean(values)))
        for year, values in sorted(grouped.items())
        if values
    ]


def analyze_trend(observations: list[Observation], alpha: float = 0.05) -> TrendResult:
    annual = annual_means(observations)
    limitations = [
        "Las estimaciones de grilla para un punto no sustituyen mediciones in situ.",
        "Mann-Kendall sin modificación puede ser sensible a la correlación serial.",
    ]
    if len(annual) < 5:
        return TrendResult(
            method="Mann-Kendall y pendiente de Sen sobre medias anuales",
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
    tau = kendalltau(years, values, nan_policy="omit")
    sen = theilslopes(values, years, alpha=1 - alpha)
    autocorrelation = None
    if len(values) >= 3 and np.std(values[:-1]) > 0 and np.std(values[1:]) > 0:
        autocorrelation = float(np.corrcoef(values[:-1], values[1:])[0, 1])
        if abs(autocorrelation) >= 0.3:
            limitations.append(
                f"La autocorrelación lag-1 es {autocorrelation:.3f}; el p-value sin corrección debe interpretarse con cautela."
            )
    significant = bool(np.isfinite(tau.pvalue) and tau.pvalue < alpha)
    direction = "no_trend"
    if significant:
        direction = "increasing" if sen.slope > 0 else "decreasing" if sen.slope < 0 else "no_trend"
    direction_label = {
        "increasing": "creciente",
        "decreasing": "decreciente",
        "no_trend": "sin tendencia",
    }[direction]
    interpretation = (
        f"Se detectó una tendencia {direction_label} estadísticamente significativa ({sen.slope:.4g} unidades/año, p={tau.pvalue:.3g})."
        if significant and direction != "no_trend"
        else "Evidencia insuficiente para establecer una tendencia estadísticamente significativa."
    )
    return TrendResult(
        method="Mann-Kendall y pendiente de Sen sobre medias anuales",
        direction=direction,
        slope_per_year=float(sen.slope),
        p_value=float(tau.pvalue),
        confidence_interval=(float(sen.low_slope), float(sen.high_slope)),
        significant=significant,
        valid_observations=len(annual),
        autocorrelation_lag1=autocorrelation,
        interpretation=interpretation,
        limitations=limitations,
    )
