#!/usr/bin/env python3
"""Contraste independiente de S de Mann-Kendall, p normal, Sen y lag-1."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import json
import math
from pathlib import Path
from statistics import median
import sys


def sign(value: float) -> int:
    return (value > 0) - (value < 0)


def lag1(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    left, right = values[:-1], values[1:]
    ml, mr = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - ml) * (b - mr) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - ml) ** 2 for a in left) * sum((b - mr) ** 2 for b in right))
    return numerator / denominator if denominator else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file", help="Ruta CSV o - para stdin")
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()
    raw = sys.stdin.read() if args.csv_file == "-" else Path(args.csv_file).read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(raw.splitlines()))
    points = sorted((float(row["year"]), float(row["value"])) for row in rows if row.get("year") and row.get("value"))
    years, values = [p[0] for p in points], [p[1] for p in points]
    if len(points) < 5 or not all(math.isfinite(v) for v in years + values):
        print(json.dumps({"ok": False, "error": "Se requieren al menos cinco puntos finitos"}, ensure_ascii=False))
        return 1
    s_value = sum(sign(values[j] - values[i]) for i in range(len(values)) for j in range(i + 1, len(values)))
    n = len(values)
    ties = Counter(values)
    variance = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties.values() if t > 1)) / 18
    z_value = (s_value - 1) / math.sqrt(variance) if s_value > 0 and variance else (s_value + 1) / math.sqrt(variance) if s_value < 0 and variance else 0.0
    p_value = math.erfc(abs(z_value) / math.sqrt(2))
    slopes = [(values[j] - values[i]) / (years[j] - years[i]) for i in range(n) for j in range(i + 1, n) if years[j] != years[i]]
    result = {"ok": True, "n": n, "s": s_value, "variance_s": variance, "z": z_value, "p_value_two_sided": p_value, "sen_slope_per_year": median(slopes), "autocorrelation_lag1": lag1(values), "significant": p_value < args.alpha, "alpha": args.alpha}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
