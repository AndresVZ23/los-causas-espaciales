"""Energía eólica hora por hora: funciones puras, sin red.

1. Cizalladura: exponente de la ley potencial entre las medias de 10 y 50 m de las mismas horas.
2. Altura del buje: v_buje = v_50 × (h / 50)^α en cada hora.
3. Densidad del aire: atmósfera estándar a la elevación del sitio y temperatura media; la potencia escala con la
   densidad, que se aplica como velocidad equivalente v × (ρ / 1.225)^(1/3) (IEC 61400-12-1).
4. Curva de potencia genérica normalizada: 0 bajo el arranque, (v³ − v_a³) / (v_n³ − v_a³) hasta la nominal,
   1 hasta la parada y 0 desde la parada. Es un supuesto declarado, no la curva de un fabricante.
"""

import math

import numpy as np

from ..finance.engine import calculate_npv
from ..schemas.analysis import FinanceRequest
from ..schemas.wind import WindAssumptions, WindFinancialProjection

REFERENCE_HEIGHT_M = 50.0
REFERENCE_DENSITY = 1.225          # kg/m³, nivel del mar a 15 °C
DEFAULT_SHEAR = 1 / 7               # se usa solo si las medias no permiten calcularla
SHEAR_LIMITS = (0.0, 0.5)
HOURS_PER_YEAR = 8760


def shear_exponent(mean_50m: float, mean_10m: float) -> tuple[float, str]:
    if mean_50m <= 0 or mean_10m <= 0:
        return DEFAULT_SHEAR, "Supuesto 1/7: las medias horarias no permiten calcular la cizalladura."
    raw = math.log(mean_50m / mean_10m) / math.log(REFERENCE_HEIGHT_M / 10)
    value = min(max(raw, SHEAR_LIMITS[0]), SHEAR_LIMITS[1])
    basis = f"ln(v50 / v10) / ln 5 con las medias de las mismas horas ({mean_10m:.2f} y {mean_50m:.2f} m/s)"
    if value != raw:
        basis += f"; el valor {raw:.3f} se acotó a [{SHEAR_LIMITS[0]}, {SHEAR_LIMITS[1]}]"
    return value, basis + "."


def air_density(elevation_m: float, temperature_c: float) -> float:
    pressure = 101_325 * (1 - 2.25577e-5 * elevation_m) ** 5.25588
    return pressure / (287.05 * (temperature_c + 273.15))


def normalized_power(speed: np.ndarray, cut_in: float, rated: float, cut_out: float) -> np.ndarray:
    ramp = (speed ** 3 - cut_in ** 3) / (rated ** 3 - cut_in ** 3)
    return np.where((speed < cut_in) | (speed >= cut_out), 0.0, np.where(speed >= rated, 1.0, ramp))


def hub_speeds(speed_50m: np.ndarray, hub_height_m: float, shear: float) -> np.ndarray:
    return speed_50m * (hub_height_m / REFERENCE_HEIGHT_M) ** shear


def capacity_factor(speed_50m: np.ndarray, assumptions: WindAssumptions, shear: float, density: float, level: float = 1.0) -> float:
    """Factor de planta bruto: media de la potencia normalizada en las horas; `level` escala el viento (p. ej. al atlas)."""
    equivalent = hub_speeds(speed_50m * level, assumptions.hub_height_m, shear) * (density / REFERENCE_DENSITY) ** (1 / 3)
    return float(np.mean(normalized_power(equivalent, assumptions.cut_in_ms, assumptions.rated_ms, assumptions.cut_out_ms)))


def annual_energy_mwh(capacity_factor_gross: float, assumptions: WindAssumptions) -> float:
    return assumptions.capacity_mw * HOURS_PER_YEAR * capacity_factor_gross * (1 - assumptions.losses)


def calculate_wind_projection(capacity_factor_gross: float, assumptions: WindAssumptions) -> WindFinancialProjection:
    energy = annual_energy_mwh(capacity_factor_gross, assumptions)
    revenue = energy * assumptions.energy_price_usd_mwh
    npv = calculate_npv(FinanceRequest(
        initial_capex=assumptions.initial_capex_usd, annual_revenue=revenue, annual_opex=assumptions.annual_opex_usd,
        mitigation_capex=assumptions.mitigation_capex_usd, annual_interruption_cost=0, discount_rate=assumptions.discount_rate,
        horizon_years=assumptions.horizon_years,
    ))
    return WindFinancialProjection(
        capacity_factor_net=round(capacity_factor_gross * (1 - assumptions.losses), 4),
        annual_energy_mwh=round(energy, 2), annual_revenue_usd=round(revenue, 2), npv_usd=npv.npv, cash_flows_usd=npv.cash_flows,
        formula="Energía anual = MW × 8,760 h × factor de planta bruto × (1 − pérdidas); el factor sale de la serie horaria con la curva genérica.",
        limitations=[
            "Curva de potencia genérica: la de la turbina elegida puede mover la energía en ±10 % o más.",
            "MERRA-2 representa una celda de 0.5° × 0.625°: no resuelve la aceleración del viento en lomas, quebradas ni costa.",
            "Sin estela entre turbinas modelada: está dentro de las pérdidas declaradas por el usuario.",
            "Precio, CAPEX, OPEX, pérdidas, tasa y horizonte son supuestos del usuario.",
        ],
    )
