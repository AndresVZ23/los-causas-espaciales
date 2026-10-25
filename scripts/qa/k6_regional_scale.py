"""Live K6 check: recent POWER regional precipitation must be scale-verified before use."""

import asyncio
from datetime import date

from backend.app.connectors.nasa.power_regional import RegionalPowerConnector
from backend.app.schemas.spatial_sampling import SpatialSamplingRequest


async def main() -> None:
    subjects = {
        "reported-small-area": [[
            [-71.40, -17.70], [-71.20, -17.70], [-71.20, -17.55],
            [-71.40, -17.55], [-71.40, -17.70],
        ]],
        "regional-area": [[
            [-71.75, -18.00], [-70.25, -18.00], [-70.25, -16.75],
            [-71.75, -16.75], [-71.75, -18.00],
        ]],
    }
    connector = RegionalPowerConnector()
    for name, coordinates in subjects.items():
        request = SpatialSamplingRequest(
            subject={"type": "Polygon", "coordinates": coordinates},
            variable="PRECTOTCORR",
            start_date=date(2025, 10, 25),
            end_date=date(2026, 10, 24),
        )
        result = await connector.sample(request)
        values = [item.value for item in result.aggregate]
        notes = [
            item for item in result.source.quality_notes
            if "PRECTOTCORR" in item or "precipitación" in item.lower()
        ]
        assert values and max(values) < 25, f"K6 failed: implausible corrected maximum {max(values):.2f} mm/day"
        assert notes, "K6 failed: missing per-cell scale-verification evidence"
        print({
            "subject": name,
            "mode": result.mode,
            "days": len(values),
            "cells": len(result.cells),
            "sum_mm": round(sum(values), 2),
            "max_mm_day": round(max(values), 2),
            "scale_notes": notes,
        })


if __name__ == "__main__":
    asyncio.run(main())
