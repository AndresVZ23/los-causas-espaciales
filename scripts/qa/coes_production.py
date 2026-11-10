"""Producción real de centrales del COES en un año, a partir de los XLSX oficiales (hoja PRODUCCIÓN DIARIA).

Sirve para validar los pilotos de energía contra la operación real (ADR-041 y ADR-042). No forma parte del producto:
descarga los doce meses con el conector del COES (pausa entre consultas y caché) y suma el total diario por central.

    python scripts/qa/coes_production.py 2024 --tipo EOL              # todas las centrales cuyo tipo contiene «EOL»
    python scripts/qa/coes_production.py 2024 MACHUPICCHU "SAN GABAN"  # centrales por nombre

Para el factor de planta: MWh ÷ (potencia instalada en MW × horas del año). La potencia no está en este archivo:
se toma de una fuente citada (Osinergmin, la empresa operadora).
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import date
from io import BytesIO
from itertools import islice
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from openpyxl import load_workbook  # noqa: E402

from backend.app.connectors.energy.coes import COESConnector, _normalize, _number  # noqa: E402

SHEET = "PRODUCCIÓN DIARIA"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("year", type=int)
    parser.add_argument("names", nargs="*", help="Fragmentos del nombre de la central (sin tildes, en mayúsculas).")
    parser.add_argument("--tipo", default="", help="Fragmento del tipo de generación, por ejemplo EOL, HIDRO o SOLAR.")
    args = parser.parse_args()
    names, kind = [_normalize(item) for item in args.names], _normalize(args.tipo)
    if not names and not kind:
        parser.error("Indique al menos un nombre de central o un --tipo.")

    connector = COESConnector()
    totals, days, kinds = defaultdict(float), defaultdict(set), {}
    for month in range(1, 13):
        content, _, provenance = await connector._download_month(date(args.year, month, 1))
        rows = load_workbook(BytesIO(content), read_only=True, data_only=True)[SHEET].iter_rows(values_only=True)
        for row in islice(rows, 25):
            if tuple(str(item or "").strip() for item in row[:2]) == ("FECHA", "EMPRESA"):
                break
        for row in rows:
            if len(row) < 5:
                continue
            plant, plant_kind, value = str(row[2] or "").strip(), str(row[3] or "").strip(), _number(row[4])
            matches = (names and any(name in _normalize(plant) for name in names)) or (kind and kind in _normalize(plant_kind))
            if matches and value is not None:
                totals[plant] += value
                days[plant].add(row[0])
                kinds[plant] = plant_kind
        print(f"{args.year}-{month:02d} {provenance}", flush=True)
    for plant, mwh in sorted(totals.items(), key=lambda item: -item[1]):
        print(f"{plant} [{kinds[plant]}]: {mwh:,.0f} MWh en {len(days[plant])} días")


if __name__ == "__main__":
    asyncio.run(main())
