from datetime import date, timedelta

import numpy as np
import pytest
from scipy.stats import norm

from backend.app.orchestration.analysis import current_period
from backend.app.schemas.analysis import Observation
from backend.app.statistics.trends import analyze_trend, annual_means, mann_kendall_s, mann_kendall_variance


def series(values):
    return [Observation(timestamp=date(2000 + i, 1, 1), value=v) for i, v in enumerate(values)]


def test_detects_increasing_trend():
    result = analyze_trend(series(list(range(15))), already_annual=True)
    assert result.significant
    assert result.direction == "increasing"
    assert result.slope_per_year == 1


def test_detects_decreasing_trend():
    result = analyze_trend(series(list(range(15, 0, -1))), already_annual=True)
    assert result.significant
    assert result.direction == "decreasing"


def test_short_series_is_insufficient():
    result = analyze_trend(series([1, 2, 3]), already_annual=True)
    assert not result.significant
    assert result.direction == "insufficient_evidence"


# Referencias independientes calculadas con pymannkendall 1.4.3 (MIT) el 2026-10-22 y congeladas aquí,
# para contrastar la implementación sin añadir la librería como dependencia. Series sintéticas: solo pruebas.
OSCILLATING = (0.05 * np.arange(30) + 0.6 * np.sin(2 * np.pi * np.arange(30) / 12)).round(6).tolist()
TIES = [1, 2, 2, 3, 3, 3, 4, 5, 5, 6, 6, 7, 8, 8, 9, 9, 10, 10, 11, 12]
ALTERNATING = [0.0, 0.3, -0.2, 0.1, -0.3, 0.2, 0.05, -0.1, 0.25, -0.15, 0.1, -0.05]


def test_s_and_variance_match_reference_with_ties():
    values = np.asarray(TIES, dtype=float)
    assert mann_kendall_s(values) == 181
    assert mann_kendall_variance(values) == pytest.approx(940.333333, rel=1e-6)


def test_hamed_rao_corrects_variance_when_detrended_series_is_autocorrelated():
    result = analyze_trend(series(OSCILLATING), already_annual=True)
    assert result.variance_correction == pytest.approx(1.508421, rel=1e-5)
    assert result.p_value_modified == pytest.approx(0.0030427075, rel=1e-6)
    assert result.significant and result.direction == "increasing"
    assert any("varianza de S se multiplicó" in item for item in result.limitations)


def test_trend_alone_does_not_trigger_correction():
    # Una rampa con ruido pequeño tiene autocorrelación bruta alta, pero no en los rangos sin tendencia.
    noise = np.random.default_rng(7).normal(0, 0.05, 20)
    result = analyze_trend(series([0.1 * i + e for i, e in enumerate(noise)]), already_annual=True)
    assert result.autocorrelation_lag1 > 0.9
    assert abs(result.autocorrelation_lag1_detrended) < 0.5
    assert result.variance_correction == 1
    assert result.significant


def _daily(start: date, end: date, value) -> list[Observation]:
    out, day = [], start
    while day <= end:
        out.append(Observation(timestamp=day, value=value(day) if callable(value) else value))
        day += timedelta(days=1)
    return out


def test_incomplete_current_year_stays_out_of_the_trend():
    observations = _daily(date(2015, 1, 1), date(2023, 12, 31), lambda d: 10 + (d.year - 2015) * 0.5) + _daily(date(2024, 1, 1), date(2024, 3, 31), 99.0)
    assert [item.timestamp.year for item in annual_means(observations)] == list(range(2015, 2024))
    result = analyze_trend(observations)
    assert result.slope_per_year == pytest.approx(0.5)
    assert any("2024" in item and "excluidos" in item for item in result.limitations)


def test_current_period_compares_same_calendar_window():
    observations = _daily(date(2018, 1, 1), date(2022, 12, 31), lambda d: 10.0 if d.month <= 3 else 50.0) + _daily(date(2023, 1, 1), date(2023, 3, 31), 12.0)
    period = current_period(observations, "mm/day")
    assert period.year == 2023 and period.through == date(2023, 3, 31) and period.days == 90
    # La ventana enero–marzo de los años completos promedia 10, no 40: la estacionalidad no contamina la comparación.
    assert period.baseline_mean == pytest.approx(10.0)
    assert period.anomaly == pytest.approx(2.0) and period.anomaly_percent == pytest.approx(20.0)
    assert period.rank == 1 and period.years_compared == 6
    assert current_period(observations, "C").anomaly_percent is None
    assert current_period(_daily(date(2018, 1, 1), date(2022, 12, 31), 10.0), "C") is None


def test_negative_corrected_variance_falls_back_and_is_declared():
    # pymannkendall devuelve p = NaN en este caso; aquí se conserva la varianza clásica y se declara la limitación.
    result = analyze_trend(series(ALTERNATING), already_annual=True)
    assert result.variance_correction == 1
    assert result.p_value_modified == pytest.approx(0.8906603480, rel=1e-6)
    assert not result.significant
    assert any("autocorrelación negativa" in item for item in result.limitations)


# RX1DAY anual de NASA POWER en Moquegua (2001–2025), con el año atípico 2022: los rangos sin tendencia alternan.
MOQUEGUA_RX1DAY = [7.3, 10.9, 8.8, 8.8, 7.8, 8.9, 5.6, 9.6, 8.4, 2.6, 9.3, 8.6, 6.6, 11.2, 6.1, 12.3, 8.8, 18.2, 6.7, 20.9, 4.6, 300.2, 43.2, 5.1, 24.7]


def test_negative_autocorrelation_never_shrinks_the_variance():
    # Sin el piso, n/n* ≈ 0.15 llevaba p de 0.21 a 0.001 y declaraba «fuerte» una tendencia cuyo IC de Sen cruza el cero.
    values = np.asarray(MOQUEGUA_RX1DAY)
    result = analyze_trend(series(MOQUEGUA_RX1DAY), already_annual=True)
    classical = 2 * (1 - norm.cdf(abs(mann_kendall_s(values) - 1) / np.sqrt(mann_kendall_variance(values))))
    assert result.autocorrelation_lag1_detrended < -0.4
    assert result.variance_correction == 1
    assert result.p_value_modified == pytest.approx(classical, rel=1e-9)
    assert not result.significant
    assert result.confidence_interval[0] < 0 < result.confidence_interval[1]
