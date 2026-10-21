import math


def benjamini_hochberg(p_values: list[float | None]) -> list[float | None]:
    """Return monotonic Benjamini-Hochberg adjusted p-values, preserving missing positions."""
    valid = [(index, value) for index, value in enumerate(p_values) if value is not None and math.isfinite(value)]
    adjusted: list[float | None] = [None] * len(p_values)
    if not valid:
        return adjusted

    ordered = sorted(valid, key=lambda item: item[1])
    count = len(ordered)
    running_min = 1.0
    for reverse_rank, (index, value) in enumerate(reversed(ordered), start=1):
        rank = count - reverse_rank + 1
        candidate = min(1.0, value * count / rank)
        running_min = min(running_min, candidate)
        adjusted[index] = running_min
    return adjusted
