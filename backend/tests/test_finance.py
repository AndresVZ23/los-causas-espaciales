from backend.app.finance.engine import calculate_npv
from backend.app.schemas.analysis import FinanceRequest


def test_npv_matches_discounted_cash_flow():
    request = FinanceRequest(initial_capex=100, annual_revenue=60, annual_opex=10, discount_rate=0.1, horizon_years=2)
    result = calculate_npv(request)
    assert result.npv == round(-100 + 50 / 1.1 + 50 / 1.1**2, 2)
    assert result.provenance == "USER_ASSUMPTION"
