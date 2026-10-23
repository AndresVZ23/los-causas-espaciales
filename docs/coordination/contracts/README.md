# Contrato C2 — `ScreeningEnvelope` v1.0

Todo sector responde con el mismo sobre. La interfaz (pipeline, preguntas NASA), el reporte PDF (C3) y el asistente (C4) leen solo estos campos, así que funcionan para solar, vial e inmobiliario sin cambios.

- Esquema: `screening-envelope-v1.0.schema.json`
- Ejemplo real (Moquegua–Arequipa, 2001–2024, NASADEM con métricas): `screening-envelope-v1.0.example.json`
- Ejemplo real K2 (corredor Moquegua–Ilo, 2018–2023): `road-screening-v1.0.example.json`
- Regenerar ambos: `scripts/export_contract.py` (instrucciones en su encabezado)
- Regenerar K2 sin levantar la API: `scripts/export_road_contract.py`
- Código: `backend/app/schemas/screening.py`

## Campos del sobre

| Campo | Qué lleva |
|---|---|
| `contract_version`, `analysis_id`, `generated_at`, `period` | Identificación reproducible |
| `sector`, `sector_label`, `title` | `solar`, `road` o `real_estate` |
| `subjects` | Sujetos de estudio: `point` (sitio), `segment` (tramo de corredor) o `polygon` (terreno), con GeoJSON RFC 7946 y `representative_point`, donde se consultan POWER y NASADEM |
| `pipeline` | Nueve etapas canónicas con estado derivado, evidencia, procedencia, tiempo y preguntas que sustentan |
| `nasa_questions` | Las cinco respuestas en orden: `what`, `where`, `how_much`, `significant`, `so_what` |
| `trend_findings` | Tendencias significativas tras Hamed–Rao + BH; `site` es la etiqueta del sujeto |
| `terrain` | Respuesta NASADEM o `null` |
| `data_gaps` | Brechas; una `DATA_UNAVAILABLE` impide que la etapa territorial sea `COMPLETADO` |
| `assumption_items` | Supuestos del usuario con etiqueta, valor, unidad y `USER_ASSUMPTION` |
| `financial_sensitivity` | Por sujeto: VAN base, escenarios `base`/`adverso`/`favorable`, tornado (un factor a la vez, con procedencia y origen del rango) y puntos de equilibrio. Vacío si el sector no evalúa finanzas (ADR-020) |
| `scorecard` | Puntaje multicriterio: criterios con escala y fundamento, pesos, puntaje y cobertura por sujeto, estabilidad, sensibilidad de pesos y empate práctico. `null` si el sector no lo usa (ADR-022) |
| `disclaimer` | Alcance y límites |

Los campos propios del sector se agregan **heredando** el sobre (por ejemplo, `SolarScreeningResponse(ScreeningEnvelope)` agrega `sites`, `comparative_findings` y `assumptions`). Así no se rompe ningún consumidor existente. Los cambios al sobre son solo aditivos; uno incompatible exige un ADR y subir `contract_version`.

## Cómo armar un piloto nuevo (K2 vial, K3 inmobiliario)

```python
from backend.app.orchestration.extraction import extract_power, extract_terrain, max_separation_km
from backend.app.orchestration.analysis import analyze_subjects
from backend.app.orchestration.nasa_questions import SectorLens, SubjectSummaries, answer_nasa_questions, collect_trend_findings
from backend.app.orchestration.stages import (selection_stage, configuration_stage, extraction_stage, analysis_stage,
                                              territorial_stage, results_stage, export_stage, stage, assemble_pipeline)
```

1. Construir `subjects` (por ejemplo, los tramos que entrega el muestreo de K1) y sus `representative_point`.
2. `extract_power(points, variables, inicio, fin)` y `extract_terrain(points)` en paralelo.
3. `analyze_subjects(datasets, variables, días_esperados)`: resúmenes por sujeto con Hamed–Rao y BH por variable.
4. `collect_trend_findings` y `answer_nasa_questions(..., lens=SectorLens(readings, stable_notes, economics))`. El lente lo define el sector: qué significa cada tendencia para una carretera o un terreno, y la frase con su escenario económico (por ejemplo, días de interrupción × costo, con supuestos del usuario).
5. Si el sector evalúa finanzas: definir sus `Driver` y su función de VAN, y llamar a `tornado` y `break_even_item` de `backend/app/finance/sensitivity.py` para llenar `financial_sensitivity` (ver `solar_sensitivity`).
6. Etapas 1–5, 8 y 9 con los constructores comunes; las etapas 6 (evaluación) y 7 (impacto económico) con `stage("evaluation", ...)` y `stage("finance", ...)`; unir con `assemble_pipeline`.
7. Una prueba que afirme `envelope_violations(respuesta) == []` (ver `backend/tests/test_contract.py`).

Variables nuevas de NASA POWER se registran en `backend/app/core/variables.py` y sus unidades en `backend/app/core/units.py`; ningún sector mantiene su propio catálogo.
