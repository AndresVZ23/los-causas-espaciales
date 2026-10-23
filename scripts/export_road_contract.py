r"""Generate the typed K2 example from official/public sources without starting the API server.

Run from the repository root:
    .\.venv\Scripts\python.exe scripts\export_road_contract.py

The command uses the existing raw caches when available and never enables Gemini.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.orchestration.conformance import envelope_violations  # noqa: E402
from backend.app.schemas.road import RoadScreeningRequest  # noqa: E402
from backend.app.sectors.road import run_road_screening  # noqa: E402

OUT = ROOT / "docs" / "coordination" / "contracts" / "road-screening-v1.0.example.json"


async def main() -> None:
    response = await run_road_screening(RoadScreeningRequest(
        start_date=date(2018, 1, 1),
        end_date=date(2023, 12, 31),
    ))
    problems = envelope_violations(response)
    if problems:
        raise SystemExit("La respuesta K2 no cumple C2:\n- " + "\n- ".join(problems))
    OUT.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    print(f"Ejemplo K2 ({response.analysis_id}): {OUT.relative_to(ROOT)} · conformidad C2 OK")


asyncio.run(main())
