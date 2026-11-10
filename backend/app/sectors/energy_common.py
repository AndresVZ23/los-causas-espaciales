"""Piezas comunes de los pilotos de energía (solar, eólico e hidroeléctrico): formato de factores, notas de equilibrio y escenarios."""

from ..schemas.screening import SubjectSensitivity

BREAK_EVEN_SPAN = 20  # el equilibrio se busca entre 0 y 20 veces el supuesto


def fmt_value(value: float, unit: str) -> str:
    if unit == "USD" or unit == "USD/año":
        amount = f"USD {value / 1e6:,.2f} M" if abs(value) >= 1e6 else f"USD {value:,.0f}"
        return amount + ("/año" if unit == "USD/año" else "")
    if unit == "USD/MW":
        return f"USD {value / 1e6:,.2f} M por MW"
    if unit == "fracción":
        return f"{value * 100:.1f} %"
    return f"{value:,.2f} {unit}".strip()


def break_even_note(value: float | None, assumed: float, unit: str, name: str, *, higher_is_better: bool) -> str:
    if value is None:
        return f"El VAN no cruza cero entre 0 y {BREAK_EVEN_SPAN} veces el supuesto."
    if value == 0:
        return f"El VAN es positivo incluso con {name} cero."
    margin = (assumed - value) / value
    position = "por encima" if margin >= 0 else "por debajo"
    reading = "holgura" if (margin >= 0) == higher_is_better else "déficit"
    return f"{name[:1].upper() + name[1:]} para VAN ≥ 0: {fmt_value(value, unit)}; el supuesto está {abs(margin) * 100:.0f} % {position} ({reading})."


def lower_first(text: str) -> str:
    """Minúscula inicial para usar una etiqueta dentro de una frase, salvo siglas (CAPEX, OPEX)."""
    return text if text[:2].isupper() else text[:1].lower() + text[1:]


def scenario_npv(sensitivity: SubjectSensitivity, key: str) -> float:
    return next(item.npv for item in sensitivity.scenarios if item.key == key)
