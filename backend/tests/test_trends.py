from datetime import date

from backend.app.schemas.analysis import Observation
from backend.app.statistics.trends import analyze_trend


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
