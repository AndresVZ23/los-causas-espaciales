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
    "m3/s": "m³/s",
    "percent_cover": "% del área",
    "kg_C/m^2": "kg C/m²",
}

# Sin porcentaje sobre la media: escalas de intervalo (0 °C no es ausencia de magnitud) y fracciones de área, cuyo
# cambio se lee en puntos porcentuales y no como porcentaje de un porcentaje.
INTERVAL_SCALE_UNITS = {"C", "deg C", "percent_cover"}


def display_unit(raw: str) -> str:
    return DISPLAY_UNITS.get(raw, raw)


def is_ratio_scale(raw: str) -> bool:
    return raw not in INTERVAL_SCALE_UNITS
