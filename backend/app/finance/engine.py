from ..schemas.analysis import FinanceRequest, FinanceResponse


def calculate_npv(request: FinanceRequest) -> FinanceResponse:
    cash_flows = [-(request.initial_capex + request.mitigation_capex)]
    annual_net = request.annual_revenue - request.annual_opex - request.annual_interruption_cost
    cash_flows.extend([annual_net] * request.horizon_years)
    npv = sum(value / ((1 + request.discount_rate) ** year) for year, value in enumerate(cash_flows))
    return FinanceResponse(
        npv=round(npv, 2),
        cash_flows=[round(v, 2) for v in cash_flows],
        note="Escenario calculado exclusivamente con supuestos del usuario; no es un pronóstico ni una opinión de valorización.",
    )
