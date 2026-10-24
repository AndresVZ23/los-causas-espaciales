r"""Independently recompute K3 area and NPV from the versioned contract example.

Run from repository root:
    .\.venv\Scripts\python.exe scripts\qa\validate_k3_finance.py

This script intentionally does not import the K3 sector implementation.
"""

import json
from pathlib import Path

from pyproj import Geod
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "docs" / "coordination" / "contracts" / "real-estate-screening-v1.0.example.json"
GEOD = Geod(ellps="WGS84")


def main() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assumptions = payload["assumptions"]
    by_id = {item["subject_id"]: item for item in payload["sites"]}
    checks = []
    for subject in payload["subjects"]:
        result = by_id[subject["id"]]
        polygon = shape(subject["geometry"])
        area_m2 = abs(GEOD.geometry_area_perimeter(polygon)[0])
        saleable = area_m2 * assumptions["developable_fraction"] * assumptions["floor_area_ratio"]
        flows = [-(area_m2 * assumptions["land_cost_usd_m2"] + area_m2 * assumptions["mitigation_cost_usd_m2_land"])]
        remaining = 1.0
        for _year in range(1, assumptions["horizon_years"] + 1):
            fraction = min(assumptions["annual_absorption_fraction"], remaining)
            sold_area = saleable * fraction
            revenue = sold_area * assumptions["sale_price_usd_m2"]
            flows.append(
                revenue
                - sold_area * assumptions["construction_cost_usd_m2"]
                - revenue * assumptions["selling_cost_fraction"]
            )
            remaining -= fraction
        npv = sum(value / (1 + assumptions["discount_rate"]) ** year for year, value in enumerate(flows))
        area_error = abs(area_m2 - result["finance"]["land_area_m2"])
        npv_error = abs(npv - result["finance"]["npv_usd"])
        if area_error > 0.02 or npv_error > 0.02:
            raise SystemExit(f"{subject['label']}: area error={area_error}, NPV error={npv_error}")
        checks.append({
            "subject": subject["label"],
            "area_m2": round(area_m2, 2),
            "npv_usd": round(npv, 2),
            "difference_usd": round(npv_error, 4),
        })
    print(json.dumps({"ok": True, "method": "independent geodesic area and discounted cash flow", "checks": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
