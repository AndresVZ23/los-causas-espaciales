from datetime import date

import numpy as np
import pytest

from backend.app.schemas.analysis import Observation
from backend.app.statistics.trends import analyze_trend, mann_kendall_s, mann_kendall_variance


def series(values):
    return [Observation(timestamp=date(2000 + i, 1, 1), value=v) for i, v in enumerate(values)]


def test_detects_increasing_trend():
    result = analyze_trend(series(list(range(15))))
    assert result.significant
    assert result.direction == "increasing"
    assert result.slope_per_year == 1


def test_detects_decreasing_trend():
    result = analyze_trend(series(list(range(15, 0, -1))))
    assert result.significant
    assert result.direction == "decreasing"


def test_short_series_is_insufficient():
    result = analyze_trend(series([1, 2, 3]))
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
    result = analyze_trend(series(OSCILLATING))
    assert result.variance_correction == pytest.approx(1.508421, rel=1e-5)
    assert result.p_value_modified == pytest.approx(0.0030427075, rel=1e-6)
    assert result.significant and result.direction == "increasing"
    assert any("varianza de S se multiplicó" in item for item in result.limitations)


def test_trend_alone_does_not_trigger_correction():
    # Una rampa con ruido pequeño tiene autocorrelación bruta alta, pero no en los rangos sin tendencia.
    noise = np.random.default_rng(7).normal(0, 0.05, 20)
    result = analyze_trend(series([0.1 * i + e for i, e in enumerate(noise)]))
    assert result.autocorrelation_lag1 > 0.9
    assert abs(result.autocorrelation_lag1_detrended) < 0.5
    assert result.variance_correction == 1
    assert result.significant


def test_negative_corrected_variance_falls_back_and_is_declared():
    # pymannkendall devuelve p = NaN en este caso; aquí se conserva la varianza clásica y se declara la limitación.
    result = analyze_trend(series(ALTERNATING))
    assert result.variance_correction == 1
    assert result.p_value_modified == pytest.approx(0.8906603480, rel=1e-6)
    assert not result.significant
    assert any("varianza no positiva" in item for item in result.limitations)
