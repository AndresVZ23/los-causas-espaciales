"""Sensibilidad genérica del VAN: tornado, escenarios y puntos de equilibrio.

No conoce ningún sector. Recibe la función de VAN del sector (`NpvModel`) y los factores con su rango, así la fórmula
vive en un solo lugar. Funciones puras: no consultan fuentes externas.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ..schemas.analysis import Provenance
from ..schemas.screening import BreakEven, SensitivityBar

NpvModel = Callable[[Mapping[str, float]], float]
BISECTION_STEPS = 200


@dataclass(frozen=True)
class Driver:
    """Factor del VAN con su rango de sensibilidad declarado."""

    key: str
    label: str
    unit: str
    low: float
    high: float
    provenance: Provenance
    basis: str


def tornado(model: NpvModel, base: Mapping[str, float], drivers: list[Driver]) -> list[SensitivityBar]:
    """Mueve un factor a la vez a su extremo; ordena de mayor a menor efecto sobre el VAN."""
    bars = []
    for driver in drivers:
        npv_low = model({**base, driver.key: driver.low})
        npv_high = model({**base, driver.key: driver.high})
        bars.append(SensitivityBar(
            key=driver.key, label=driver.label, unit=driver.unit, base_value=base[driver.key],
            low_value=driver.low, high_value=driver.high, npv_at_low=round(npv_low, 2), npv_at_high=round(npv_high, 2),
            swing=round(abs(npv_high - npv_low), 2), provenance=driver.provenance, basis=driver.basis,
        ))
    return sorted(bars, key=lambda bar: bar.swing, reverse=True)


def break_even(model: NpvModel, base: Mapping[str, float], key: str, lower: float, upper: float) -> float | None:
    """Valor de `key` en [lower, upper] con VAN = 0 por bisección; None si el VAN no cambia de signo en el intervalo.

    Supone que el VAN es monótono en ese factor, como ocurre con precio, CAPEX o recurso.
    """
    f_lower, f_upper = model({**base, key: lower}), model({**base, key: upper})
    if f_lower == 0:
        return lower
    if f_upper == 0:
        return upper
    if (f_lower > 0) == (f_upper > 0):
        return None
    for _ in range(BISECTION_STEPS):
        middle = (lower + upper) / 2
        f_middle = model({**base, key: middle})
        if (f_middle > 0) == (f_lower > 0):
            lower, f_lower = middle, f_middle
        else:
            upper = middle
        if upper - lower <= 1e-9 * max(1.0, abs(upper)):
            break
    return (lower + upper) / 2


def break_even_item(model: NpvModel, base: Mapping[str, float], key: str, label: str, unit: str,
                    lower: float, upper: float, describe: Callable[[float | None], str]) -> BreakEven:
    value = break_even(model, base, key, lower, upper)
    return BreakEven(key=key, label=label, unit=unit, assumed_value=base[key],
                     break_even_value=None if value is None else round(value, 4), note=describe(value))
