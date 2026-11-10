"""El modelo hidroeléctrico frente a la producción real de la C.H. Machupicchu (ADR-042). No forma parte del producto.

Datos reales:
- Producción 2024: 1,252,221 MWh (COES, `python scripts/qa/coes_production.py 2024 MACHUPICCHU`).
- Potencia instalada 192.45 MW y caudal de diseño 61 m³/s (30 + 31), según las fuentes citadas en ADR-042.
- Represa (toma) y casa de máquinas: OpenStreetMap.

Modelo: caudal diario de GloFAS en la toma y salto bruto de NASADEM entre los dos puntos (330 m, leído en la app).
Imprime el factor de planta del modelo con tres supuestos de caudal ecológico y la potencia que resulta.

    python scripts/qa/validate_hydro.py
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.connectors.copernicus.glofas import GlofasConnector  # noqa: E402
from backend.app.sectors.hydro_energy import plant_factor, power_mw  # noqa: E402

INTAKE = (-13.18291, -72.53356)
REAL_MWH_2024, REAL_MW, DESIGN_FLOW = 1_252_221, 192.45, 61.0
GROSS_HEAD_NASADEM = 330.0
HEAD_LOSS, MIN_TURBINE = 0.05, 0.20


async def main() -> None:
    series = await GlofasConnector().discharge(*INTAKE, date(2001, 1, 1), date(2025, 12, 31))
    by_year: dict[int, list[float]] = {}
    for item in series.observations:
        by_year.setdefault(item.timestamp.year, []).append(item.value)
    flows = np.array([value for year in sorted(by_year) for value in by_year[year]])
    y2024 = np.array(by_year[2024])
    print(f"Real 2024: {REAL_MWH_2024:,} MWh · factor de planta {REAL_MWH_2024 / (REAL_MW * 8784):.3f} con {REAL_MW} MW")
    print(f"GloFAS 2024: media {y2024.mean():.1f} m³/s · días bajo {DESIGN_FLOW:g} m³/s: {(y2024 < DESIGN_FLOW).mean() * 100:.0f} % · mínimo {y2024.min():.1f}")
    for fraction in (0.10, 0.05, 0.0):
        ecological = flows.mean() * fraction
        for label, data in (("2024", y2024), ("2001–2025", flows)):
            factor = plant_factor(data, ecological, DESIGN_FLOW, MIN_TURBINE)
            print(f"  ecológico {fraction:.0%} ({ecological:.1f} m³/s) · {label}: factor de planta {factor * 0.95:.3f} con disponibilidad 0.95 · {factor:.3f} sin ella")
    net = GROSS_HEAD_NASADEM * (1 - HEAD_LOSS)
    model_mw = power_mw(DESIGN_FLOW, net, 0.87)
    print(f"Potencia del modelo: {model_mw:.1f} MW con salto {GROSS_HEAD_NASADEM:.0f} m, pérdidas {HEAD_LOSS:.0%} y eficiencia 0.87 (real {REAL_MW})")
    factor = plant_factor(y2024, flows.mean() * 0.10, DESIGN_FLOW, MIN_TURBINE) * 0.95
    model_mwh = model_mw * 8784 * factor
    print(f"Energía 2024 del modelo con los supuestos por defecto: {model_mwh:,.0f} MWh ({(model_mwh / REAL_MWH_2024 - 1) * 100:+.0f} % frente a lo real)")


if __name__ == "__main__":
    asyncio.run(main())
