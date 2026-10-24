r"""Validate one NASADEM point through the production connector without starting FastAPI.

Usage from the repository root:
    .\.venv\Scripts\python.exe scripts\qa\nasadem_live.py --latitude -16.89871486 --longitude -70.93675947 --label "Moquegua centroide"

The script never prints the Earthdata token. If a tile is cold, it waits for the
background downloads scheduled by ``points`` and then reads the cached rasters.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.connectors.nasa.nasadem import NasademConnector  # noqa: E402
from backend.app.schemas.analysis import Point  # noqa: E402


async def validate(point: Point) -> dict:
    connector = NasademConnector()
    first = await connector.points([point])
    pending = [task for task in connector._inflight_downloads.values() if not task.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    final = await connector.points([point])
    site = final.sites[0]
    return {
        "initial_status": first.sites[0].status,
        "final_status": site.status,
        "tile_ids": sorted({item.tile_id for item in site.granules}),
        "elevation_m": site.metrics.elevation_m,
        "slope_degrees": site.metrics.slope_degrees,
        "aspect_degrees": site.metrics.aspect_degrees,
        "provenance": site.provenance,
        "limitations": site.limitations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--label", default="QA NASADEM")
    args = parser.parse_args()
    result = asyncio.run(validate(Point(latitude=args.latitude, longitude=args.longitude, label=args.label)))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["final_status"] != "READY":
        raise SystemExit("NASADEM did not reach READY")


if __name__ == "__main__":
    main()
