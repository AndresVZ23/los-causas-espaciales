"""Energía hidroeléctrica de pasada, día por día: funciones puras, sin red.

1. Caudal ecológico: la fracción declarada del caudal medio, que se deja siempre en el río.
2. Caudal de diseño: el caudal aprovechable (río − ecológico) excedido el p % del tiempo, o el que declare el usuario.
3. Caudal turbinado de cada día: el aprovechable con tope en el de diseño; bajo el mínimo técnico la central para.
4. Potencia: P = ρ · g · Q · H_neto · η, con ρ = 1,000 kg/m³ y g = 9.80665 m/s².
5. Factor de planta: caudal turbinado medio ÷ caudal de diseño; la energía anual aplica además la disponibilidad.

Es una central de pasada, sin embalse de regulación: no traslada agua de un día a otro.
"""

import numpy as np

from ..finance.engine import calculate_npv
from ..schemas.analysis import FinanceRequest
from ..schemas.hydro import HydroAssumptions, HydroFinancialProjection

GRAVITY = 9.80665            # m/s²
WATER_DENSITY = 1000.0       # kg/m³
HOURS_PER_YEAR = 8760
DURATION_PERCENTS = (5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95)
FIRM_EXCEEDANCE = 95


def exceedance_flow(flows: np.ndarray, percent: float) -> float:
    """Caudal igualado o excedido el `percent` % de los días."""
    return float(np.percentile(flows, 100 - percent))


def flow_duration(flows: np.ndarray) -> list[tuple[int, float]]:
    return [(percent, exceedance_flow(flows, percent)) for percent in DURATION_PERCENTS]


def design_flow(flows: np.ndarray, ecological: float, exceedance_percent: float) -> float:
    """Caudal aprovechable (río − ecológico, nunca negativo) excedido el `exceedance_percent` % del tiempo."""
    return exceedance_flow(np.maximum(flows - ecological, 0.0), exceedance_percent)


def turbined_flow(flows: np.ndarray, ecological: float, design: float, min_fraction: float) -> np.ndarray:
    available = np.maximum(flows - ecological, 0.0)
    return np.where(available < min_fraction * design, 0.0, np.minimum(available, design))


def power_mw(flow: float, net_head_m: float, efficiency: float) -> float:
    return WATER_DENSITY * GRAVITY * flow * net_head_m * efficiency / 1e6


def plant_factor(flows: np.ndarray, ecological: float, design: float, min_fraction: float, level: float = 1.0) -> float:
    """Caudal turbinado medio ÷ caudal de diseño. `level` escala el caudal del río (p. ej. al de la segunda fuente):
    el ecológico, que es una fracción del medio, escala con él; el de diseño no, porque la central ya está dimensionada."""
    if design <= 0:
        return 0.0
    return float(np.mean(turbined_flow(flows * level, ecological * level, design, min_fraction)) / design)


def annual_energy_mwh(capacity_mw: float, factor: float, availability: float) -> float:
    return capacity_mw * HOURS_PER_YEAR * factor * availability


def calculate_hydro_projection(capacity_mw: float, factor: float, assumptions: HydroAssumptions) -> HydroFinancialProjection:
    energy = annual_energy_mwh(capacity_mw, factor, assumptions.availability)
    capex = capacity_mw * assumptions.capex_usd_per_mw
    opex = capex * assumptions.opex_fraction_of_capex
    revenue = energy * assumptions.energy_price_usd_mwh
    if capex > 0:
        result = calculate_npv(FinanceRequest(
            initial_capex=capex, annual_revenue=revenue, annual_opex=opex, mitigation_capex=assumptions.mitigation_capex_usd,
            annual_interruption_cost=0, discount_rate=assumptions.discount_rate, horizon_years=assumptions.horizon_years,
        ))
        npv, cash_flows = result.npv, result.cash_flows
    else:   # sin caudal aprovechable no hay central que dimensionar: no se invierte ni se genera
        npv, cash_flows = -assumptions.mitigation_capex_usd, [-assumptions.mitigation_capex_usd] + [0.0] * assumptions.horizon_years
    return HydroFinancialProjection(
        capacity_mw=round(capacity_mw, 3), plant_factor_net=round(factor * assumptions.availability, 4), annual_energy_mwh=round(energy, 2),
        initial_capex_usd=round(capex, 2), annual_opex_usd=round(opex, 2), annual_revenue_usd=round(revenue, 2), npv_usd=npv, cash_flows_usd=cash_flows,
        formula="Potencia = ρ · g · caudal de diseño · salto neto · eficiencia; energía anual = potencia × 8,760 h × factor de planta × disponibilidad.",
        limitations=[
            "Central de pasada sin regulación: un embalse cambiaría la energía y su estacionalidad.",
            "El caudal sale de un modelo global (GloFAS, celdas de 5 km), no de un aforo: no descuenta riego, minería ni trasvases aguas arriba.",
            "El salto sale de modelos de elevación de 30 m: su error vertical es de varios metros.",
            "Caudal ecológico, eficiencia, pérdidas, disponibilidad, precio, CAPEX, OPEX, tasa y horizonte son supuestos del usuario.",
        ],
    )
