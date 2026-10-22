"""Catálogo canónico de unidades de presentación.

Los códigos originales de NASA POWER se conservan en `SourceMetadata.unit`; aquí solo se define
cómo se leen en la interfaz y en los textos que redacta el backend.
"""

DISPLAY_UNITS: dict[str, str] = {
    "kW-hr/m^2/day": "kWh/m²/día",
    "kWh/m2/day": "kWh/m²/día",
    "mm/day": "mm/día",
    "C": "°C",
    "deg C": "°C",
    "m/s": "m/s",
}

# Escalas de intervalo: un porcentaje sobre la media no tiene sentido físico (0 °C no es ausencia de magnitud).
INTERVAL_SCALE_UNITS = {"C", "deg C"}


def display_unit(raw: str) -> str:
    return DISPLAY_UNITS.get(raw, raw)


def is_ratio_scale(raw: str) -> bool:
    return raw not in INTERVAL_SCALE_UNITS
