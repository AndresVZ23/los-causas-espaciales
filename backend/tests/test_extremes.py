"""Índices ETCCDI con series sintéticas cuyo resultado se calcula a mano (solo pruebas)."""

from datetime import date, timedelta

import pytest

from backend.app.schemas.analysis import Observation
from backend.app.statistics.extremes import annual_indices, complete_years
from backend.app.statistics.trends import analyze_trend


def _year(year: int, wet: dict[date, float], skip: set[date] = frozenset()) -> list[Observation]:
    day, end, out = date(year, 1, 1), date(year, 12, 31), []
    while day <= end:
        if day not in skip:
            out.append(Observation(timestamp=day, value=wet.get(day, 0.0)))
        day += timedelta(days=1)
    return out


WET_2001 = {
    date(2001, 1, 10): 30.0, date(2001, 1, 11): 5.0, date(2001, 1, 12): 5.0, date(2001, 1, 13): 5.0, date(2001, 1, 14): 5.0,
    date(2001, 2, 1): 12.0, date(2001, 3, 1): 2.0,
}


def test_indices_match_hand_calculation():
    series, threshold, discarded = annual_indices(_year(2001, WET_2001))
    value = {code: items[0].value for code, items in series.items()}
    assert discarded == 0
    assert value["RX1DAY"] == 30.0
    assert value["RX5DAY"] == 50.0                      # 10 al 14 de enero
    assert value["PRCPTOT"] == 64.0                     # 30 + 4×5 + 12 + 2
    assert value["R10MM"] == 2.0                        # 30 y 12 mm
    assert threshold == pytest.approx(24.6)             # P95 lineal de [2, 5, 5, 5, 5, 12, 30]
    assert value["R95P"] == 30.0
    assert value["CDD"] == 305.0                        # del 2 de marzo al 31 de diciembre


def test_incomplete_years_are_discarded_not_filled():
    partial = _year(2002, {})[:200]
    series, _, discarded = annual_indices(_year(2001, WET_2001) + partial)
    assert discarded == 1
    assert [item.timestamp.year for item in series["RX1DAY"]] == [2001]
    assert list(complete_years(partial)) == []


def test_missing_day_breaks_dry_spell():
    gap = date(2001, 7, 1)
    series, _, _ = annual_indices(_year(2001, WET_2001, skip={gap}))
    # Antes del faltante: 2 mar–30 jun = 121 días; después: 2 jul–31 dic = 183 días.
    assert series["CDD"][0].value == 183.0


def test_negative_or_invalid_values_are_ignored():
    observations = _year(2001, WET_2001) + [Observation(timestamp=date(2001, 6, 1), value=-999.0)]
    series, _, _ = annual_indices(observations)
    assert series["RX1DAY"][0].value == 30.0


def test_increasing_extremes_are_detected():
    observations = []
    for index, year in enumerate(range(2001, 2016)):
        observations += _year(year, {date(year, 2, 15): 10.0 + 2.0 * index})
    series, _, _ = annual_indices(observations)
    trend = analyze_trend(series["RX1DAY"], already_annual=True)
    assert trend.significant and trend.direction == "increasing"
    assert trend.slope_per_year == pytest.approx(2.0)
