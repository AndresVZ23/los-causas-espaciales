"""Catálogo canónico de variables NASA POWER usadas por los sectores.

Ambos agentes pueden agregar entradas (por ejemplo, variables de precipitación extrema para el piloto vial);
ningún sector debe mantener su propio diccionario de etiquetas.
"""

POWER_VARIABLE_LABELS: dict[str, str] = {
    "ALLSKY_SFC_SW_DWN": "Irradiancia solar superficial",
    "T2M": "Temperatura del aire a 2 m",
    "WS10M": "Velocidad del viento a 10 m",
    "PRECTOTCORR": "Precipitación corregida",
    "IMERG_PRECTOT": "Precipitación satelital GPM IMERG",
}


def variable_label(code: str) -> str:
    return POWER_VARIABLE_LABELS.get(code, code)
