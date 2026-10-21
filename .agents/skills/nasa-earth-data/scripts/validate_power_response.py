#!/usr/bin/env python3
"""Validar la estructura y completitud básica de una respuesta JSON de NASA POWER."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("response", type=Path)
    parser.add_argument("--parameters", required=True, help="Lista separada por comas")
    parser.add_argument("--missing", type=float, default=-999.0)
    args = parser.parse_args()
    data = json.loads(args.response.read_text(encoding="utf-8"))
    parameter_data = data.get("properties", {}).get("parameter")
    if not isinstance(parameter_data, dict):
        print(json.dumps({"ok": False, "errors": ["Falta properties.parameter"]}))
        return 1
    errors: list[str] = []
    summaries: dict[str, dict] = {}
    for code in [item.strip() for item in args.parameters.split(",") if item.strip()]:
        series = parameter_data.get(code)
        if not isinstance(series, dict) or not series:
            errors.append(f"Parámetro ausente o vacío: {code}")
            continue
        valid: list[float] = []
        missing = 0
        for stamp, raw in series.items():
            try:
                datetime.strptime(stamp, "%Y%m%d")
            except ValueError:
                errors.append(f"Fecha no YYYYMMDD en {code}: {stamp}")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                errors.append(f"Valor no numérico en {code}:{stamp}")
                continue
            if value == args.missing:
                missing += 1
            elif math.isfinite(value):
                valid.append(value)
            else:
                errors.append(f"Valor no finito en {code}:{stamp}")
        if not valid:
            errors.append(f"{code} no contiene observaciones válidas")
        total = len(series)
        summaries[code] = {"total": total, "valid": len(valid), "missing": missing, "completeness_percent": round(100 * len(valid) / total, 3), "minimum": min(valid) if valid else None, "maximum": max(valid) if valid else None}
    print(json.dumps({"ok": not errors, "errors": errors, "parameters": summaries}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

