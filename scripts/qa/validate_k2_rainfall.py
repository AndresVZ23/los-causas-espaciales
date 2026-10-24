r"""Compare K2 RX1DAY and P99 on the 2022 Moquegua–Ilo segment-2 exposure.

Usage:
    .\.venv\Scripts\python.exe scripts\qa\validate_k2_rainfall.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.connectors.nasa.power_regional import RegionalPowerConnector  # noqa: E402
from backend.app.schemas.spatial_sampling import SpatialSamplingRequest  # noqa: E402
from backend.app.sectors.road import PILOT_PATH, _percentile  # noqa: E402


async def main() -> None:
    pilot = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    feature = pilot["features"][1]
    sampled = await RegionalPowerConnector().sample(SpatialSamplingRequest(
        subject=feature,
        variable="PRECTOTCORR",
        start_date=date(2022, 1, 1),
        end_date=date(2022, 12, 31),
        corridor_buffer_km=1,
    ))
    values = [item.value for item in sampled.aggregate]
    maximum = max(values)
    p99 = _percentile(values, 0.99)
    maximum_day = next(item.timestamp for item in sampled.aggregate if item.value == maximum)
    print(json.dumps({
        "subject": sampled.subject.name,
        "period": "2022-01-01/2022-12-31",
        "cells": len(sampled.cells),
        "rx1day_mm": round(maximum, 4),
        "rx1day_date": maximum_day.isoformat(),
        "p99_mm": None if p99 is None else round(p99, 4),
        "score_metric": "p99_mm",
        "provenance": sampled.source.provenance,
    }, ensure_ascii=False, indent=2))


asyncio.run(main())
