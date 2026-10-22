"""Publica el contrato C2: esquema JSON del sobre común y un ejemplo de una ejecución real.

Uso (desde la raíz del repo, con la caché y el token del contenedor):
    docker compose run --rm -v "${PWD}/backend:/app/backend" -v "${PWD}/scripts:/app/scripts" \
        -v "${PWD}/docs:/app/docs" api python scripts/export_contract.py

El ejemplo conserva solo los campos del sobre; los propios del sector (como las series anuales solares) quedan fuera.
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.orchestration.conformance import envelope_violations  # noqa: E402
from backend.app.schemas.analysis import Point  # noqa: E402
from backend.app.schemas.pipeline import SolarScreeningRequest  # noqa: E402
from backend.app.schemas.screening import CONTRACT_VERSION, ScreeningEnvelope  # noqa: E402
from backend.app.sectors.solar import run_solar_screening  # noqa: E402

OUT = ROOT / "docs" / "coordination" / "contracts"


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    schema_path = OUT / f"screening-envelope-v{CONTRACT_VERSION}.schema.json"
    schema_path.write_text(json.dumps(ScreeningEnvelope.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")

    request = SolarScreeningRequest(
        sites=[Point(label="Moquegua", latitude=-17.193, longitude=-70.934), Point(label="Arequipa", latitude=-16.409, longitude=-71.537)],
        start_date=date(2001, 1, 1),
        end_date=date(2024, 12, 31),
    )
    response = await run_solar_screening(request)
    problems = envelope_violations(response)
    if problems:
        raise SystemExit("La respuesta real no cumple el contrato:\n- " + "\n- ".join(problems))
    envelope = ScreeningEnvelope.model_validate(json.loads(response.model_dump_json()))
    example_path = OUT / f"screening-envelope-v{CONTRACT_VERSION}.example.json"
    example_path.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")
    print(f"Esquema: {schema_path.relative_to(ROOT)}")
    print(f"Ejemplo real ({response.analysis_id}): {example_path.relative_to(ROOT)} · conformidad OK")


asyncio.run(main())
