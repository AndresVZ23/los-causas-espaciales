#!/usr/bin/env python3
"""Verificar un VAN a partir de flujos explícitos, sin supuestos ocultos."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", help="Ruta JSON o - para stdin")
    args = parser.parse_args()
    raw = sys.stdin.read() if args.scenario == "-" else Path(args.scenario).read_text(encoding="utf-8")
    data = json.loads(raw)
    rate = float(data["discount_rate"])
    cashflows = [float(value) for value in data["cashflows"]]
    errors: list[str] = []
    if rate <= -1:
        errors.append("discount_rate debe ser mayor que -1")
    if not cashflows:
        errors.append("cashflows no puede estar vacío")
    if not all(math.isfinite(value) for value in [rate, *cashflows]):
        errors.append("Las entradas deben ser finitas")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False))
        return 1
    discounted = [value / ((1 + rate) ** period) for period, value in enumerate(cashflows)]
    print(json.dumps({"ok": True, "discount_rate": rate, "periods": len(cashflows) - 1, "npv": sum(discounted), "discounted_cashflows": discounted}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

