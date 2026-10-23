"""Sensibilidad del VAN: motor genérico con modelos lineales y piloto solar contra fórmula cerrada (solo pruebas)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.finance.sensitivity import Driver, break_even, tornado
from backend.app.schemas.analysis import Provenance
from backend.app.schemas.pipeline import AnnualObservation, SolarAssumptions, VariableSummary
from backend.app.sectors.solar import calculate_solar_projection, solar_npv, solar_sensitivity

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / ".agents" / "skills" / "infrastructure-investment" / "scripts" / "verify_cashflow.py"


def linear(inputs):
    return 10 * inputs["price"] - inputs["capex"]


def test_tornado_moves_one_factor_and_sorts_by_swing():
    base = {"price": 10.0, "capex": 100.0}
    drivers = [
        Driver("capex", "CAPEX", "USD", 110.0, 90.0, Provenance.ASSUMPTION, "±10 %"),
        Driver("price", "Precio", "USD", 8.0, 12.0, Provenance.ASSUMPTION, "±20 %"),
    ]
    bars = tornado(linear, base, drivers)
    assert [bar.key for bar in bars] == ["price", "capex"]
    assert (bars[0].npv_at_low, bars[0].npv_at_high, bars[0].swing) == (-20.0, 20.0, 40.0)
    assert (bars[1].npv_at_low, bars[1].npv_at_high) == (-10.0, 10.0)


def test_break_even_finds_root_or_declares_none():
    base = {"price": 10.0, "capex": 100.0}
    assert break_even(linear, base, "price", 0.0, 200.0) == pytest.approx(10.0, abs=1e-6)
    assert break_even(linear, base, "price", 50.0, 200.0) is None   # siempre positivo en ese intervalo
    assert break_even(linear, base, "capex", 0.0, 1000.0) == pytest.approx(100.0, abs=1e-6)


def _irradiance(values, mean=None):
    series = [AnnualObservation(year=2001 + index, value=value) for index, value in enumerate(values)]
    return VariableSummary.model_construct(variable="ALLSKY_SFC_SW_DWN", mean=mean or sum(values) / len(values),
                                           display_unit="kWh/m²/día", annual_series=series)


OBSERVED = [6.40, 6.45, 6.50, 6.52, 6.55, 6.58, 6.60, 6.62, 6.65, 6.70]


def test_solar_break_even_price_matches_closed_form():
    a = SolarAssumptions()
    result = solar_sensitivity("Sitio", _irradiance(OBSERVED), a)
    price = next(item for item in result.break_evens if item.key == "energy_price_usd_mwh")
    energy = calculate_solar_projection(_irradiance(OBSERVED).mean, a).annual_energy_mwh
    annuity = sum(1 / (1 + a.discount_rate) ** year for year in range(1, a.horizon_years + 1))
    closed = ((a.initial_capex_usd + a.mitigation_capex_usd) / annuity + a.annual_opex_usd) / energy
    assert price.break_even_value == pytest.approx(closed, rel=1e-4)


def test_solar_scenarios_bracket_the_base_and_resource_range_is_observed():
    result = solar_sensitivity("Sitio", _irradiance(OBSERVED), SolarAssumptions())
    npv = {item.key: item.npv for item in result.scenarios}
    assert npv["adverso"] < npv["base"] < npv["favorable"]
    assert result.base_npv == npv["base"]
    resource = next(bar for bar in result.tornado if bar.key == "irradiance")
    assert resource.provenance == Provenance.MODEL
    assert resource.low_value == pytest.approx(6.445) and resource.high_value == pytest.approx(6.655)   # percentiles 10 y 90
    assert all(bar.npv_at_low <= bar.npv_at_high for bar in result.tornado)   # de desfavorable a favorable
    assert [bar.swing for bar in result.tornado] == sorted((bar.swing for bar in result.tornado), reverse=True)


def test_short_series_has_no_resource_driver():
    result = solar_sensitivity("Sitio", _irradiance([6.5, 6.6, 6.4]), SolarAssumptions())
    assert "irradiance" not in {bar.key for bar in result.tornado}
    assert {item.key for item in result.scenarios} == {"base", "adverso", "favorable"}


def test_solar_npv_matches_independent_cashflow_verifier():
    # verify_cashflow.py (skill infrastructure-investment) descuenta flujos explícitos sin conocer el backend.
    a = SolarAssumptions(mitigation_capex_usd=500_000)
    irradiance = 6.55
    flows = calculate_solar_projection(irradiance, a).cash_flows_usd
    run = subprocess.run([sys.executable, "-I", str(VERIFY), "-"], input=json.dumps({"discount_rate": a.discount_rate, "cashflows": flows}),
                         capture_output=True, text=True, check=True)
    independent = json.loads(run.stdout)["npv"]
    assert solar_npv({"irradiance": irradiance}, a) == pytest.approx(independent, abs=0.01)
