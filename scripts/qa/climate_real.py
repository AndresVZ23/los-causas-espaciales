"""Corre el módulo climático con datos reales de NASA y resume extremos, hallazgos y preguntas.
Uso: .venv\\Scripts\\python.exe scripts\\qa\\climate_real.py [salida.json]"""
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.orchestration.conformance import envelope_violations  # noqa: E402
from backend.app.schemas.analysis import Point  # noqa: E402
from backend.app.schemas.climate import ClimateScreeningRequest  # noqa: E402
from backend.app.sectors.climate import run_climate_screening  # noqa: E402

request = ClimateScreeningRequest(
    sites=[Point(label="Moquegua", latitude=-17.193, longitude=-70.934), Point(label="Arequipa", latitude=-16.409, longitude=-71.537)],
    start_date=date(2001, 1, 1), end_date=date.today(),
)
response = asyncio.run(run_climate_screening(request))
print("conformidad:", envelope_violations(response) or "OK")
extraction = next(stage for stage in response.pipeline if stage.key == "extraction")
for item in extraction.evidence:
    print(f"  {item.label}: {item.value}")
for site in response.sites:
    for variable in site.variables:
        cp = variable.current_period
        if cp:
            pct = f" ({cp.anomaly_percent:+.1f} %)" if cp.anomaly_percent is not None else ""
            print(f"  {site.location.label} {variable.variable}: {cp.year} hasta {cp.through} media {cp.value:.3f} vs {cp.baseline_mean:.3f} ({cp.baseline_years}) anomalía {cp.anomaly:+.3f}{pct} · puesto {cp.rank} de {cp.years_compared}")
for site in response.sites:
    print(f"\n{site.location.label} · P95 días húmedos {site.wet_day_p95_mm:.1f} mm")
    for item in site.extremes:
        t = item.trend
        print(f"  {item.variable:8} media {item.mean:7.1f} {item.unit:5} pendiente {t.slope_per_year:+.3f}/año  p_corr {t.p_value_modified:.3f}  p_BH {item.adjusted_p_value:.3f}  {'SIGNIF' if item.significant_after_bh else ''}")
print("\nTendencias significativas:", [(f.site, f.variable) for f in response.trend_findings])
for question in response.nasa_questions:
    print(f"\n[{question.key}] {question.status}: {question.answer}")
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(response.model_dump_json(indent=2), encoding="utf-8")
