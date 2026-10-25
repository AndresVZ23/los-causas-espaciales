"""Shared guard for the observed NASA POWER recent-precipitation scale defect."""

from datetime import date, timedelta

PRECIPITATION = "PRECTOTCORR"
RECENT_DAYS = 60
REFERENCE_DAYS = 730
KNOWN_SCALE = 24.0
SCALE_TOLERANCE = 0.02


class PrecipitationScaleError(ValueError):
    """Raised when POWER precipitation has an unknown scale relative to its reference."""


def reference_period(start: date, end: date, *, today: date | None = None) -> tuple[date, date]:
    cutoff = (today or date.today()) - timedelta(days=RECENT_DAYS)
    reference_end = min(end, cutoff)
    return max(start, reference_end - timedelta(days=REFERENCE_DAYS)), reference_end


def precipitation_scale(main: dict[date, float], reference: dict[date, float]) -> float | None:
    """Median main/reference ratio on at least three common wet days."""
    ratios = [main[day] / value for day, value in reference.items() if value >= 0.1 and day in main]
    if len(ratios) < 3:
        return None
    ratios.sort()
    return ratios[len(ratios) // 2]


def precipitation_divisor(main: dict[date, float], reference: dict[date, float]) -> tuple[float | None, float | None]:
    """Return observed ratio and safe divisor; reject scales other than 1 or the known ×24 defect."""
    scale = precipitation_scale(main, reference)
    if scale is None:
        return None, None
    if abs(scale - 1) <= SCALE_TOLERANCE:
        return scale, 1.0
    if abs(scale - KNOWN_SCALE) / KNOWN_SCALE <= SCALE_TOLERANCE:
        return scale, KNOWN_SCALE
    raise PrecipitationScaleError(
        f"La precipitación de NASA POWER llegó con una escala inconsistente "
        f"(razón {scale:.2f} frente a la referencia); no se usa."
    )
