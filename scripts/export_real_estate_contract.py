r"""Generate the typed K3 example from NASA/public sources without starting the API server.

The three small polygons are explicit USER_ASSUMPTION screening areas near Moquegua, Samegua and Cerro Colorado;
they are not cadastral parcels or client data. Run from the repository root:
    .\.venv\Scripts\python.exe scripts\export_real_estate_contract.py
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.orchestration.conformance import envelope_violations  # noqa: E402
from backend.app.schemas.real_estate import RealEstateScreeningRequest, RealEstateSiteInput  # noqa: E402
from backend.app.sectors.real_estate import run_real_estate_screening  # noqa: E402

OUT = ROOT / "docs" / "coordination" / "contracts" / "real-estate-screening-v1.0.example.json"


def square(west: float, south: float, size: float = 0.003) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south], [west + size, south], [west + size, south + size],
            [west, south + size], [west, south],
        ]],
    }


async def main() -> None:
    response = await run_real_estate_screening(RealEstateScreeningRequest(
        sites=[
            RealEstateSiteInput(id="moquegua-area", label="Área de análisis Moquegua", geometry=square(-70.920, -17.210)),
            RealEstateSiteInput(id="samegua-area", label="Área de análisis Samegua", geometry=square(-70.885, -17.190)),
            RealEstateSiteInput(id="cerro-colorado-area", label="Área de análisis Cerro Colorado", geometry=square(-71.585, -16.365)),
        ],
        start_date=date(2018, 1, 1),
        end_date=date(2023, 12, 31),
    ))
    problems = envelope_violations(response)
    if problems:
        raise SystemExit("La respuesta K3 no cumple C2:\n- " + "\n- ".join(problems))
    OUT.write_text(response.model_dump_json(indent=2), encoding="utf-8")
    print(f"Ejemplo K3 ({response.analysis_id}): {OUT.relative_to(ROOT)} · conformidad C2 OK")


asyncio.run(main())
