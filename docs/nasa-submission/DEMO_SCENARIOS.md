# Demo Scenarios

The live demo runs on `http://localhost:3100` (web) and `http://localhost:8000` (API) from the `v0.1.0` candidate. The interface is in Spanish; button names below are quoted as they appear on screen. The spoken script for each act is in [PITCH.md](PITCH.md).

NASA results are not hard-coded. The figures quoted here come from the rehearsal of 24 October 2026 (NASA POWER data through 22 October 2026) and move when NASA updates its series.

## Before the demo (same day, at most two hours before)

The NASA POWER cache lasts 24 hours and its key includes today's date, so yesterday's cache does not cover today. Warming it on the day is what makes the fallback route possible.

1. Confirm the stack: `docker ps` shows `los-causas-espaciales-web-1` and `los-causas-espaciales-api-1`; `http://localhost:8000/api/v1/health` answers 200.
2. Run the rehearsal: `node scripts/qa/demo_ensayo.cjs dia-demo`. It performs the main route, warms the cache, downloads the PDF and writes timings and screenshots to `.claude-qa/demo/dia-demo/`.
3. Check `ensayo.json`: `errors` is empty, `overflow` is 0 and the PDF header is `%PDF`.
4. Keep the downloaded PDF and the screenshots open in a second window as the last-resort route.
5. Do not press «Preguntar a Gemini» during the demo. The assistant's «Preguntar» answers by rules at no cost and is enough.

## Main route (3–5 minutes)

| Act | Spoken time | Screen wait (warm cache) | What the jury must see |
|---|---|---|---|
| 0 · Problem | 30 s | 3–5 s page load | Console, map, provenance key in the header |
| 1 · Territory, trend and extremes | 75 s | 18 s | Nine warming cells, IMERG counter-check |
| 2 · Asset decision (2A road or 2B solar) | 90 s | 3 s | Territorial exposure, score that names what separates the options, sensitivity, conditioned reading |
| 3 · Export | 20 s | < 1 s | Six-page executive PDF |
| 4 · Close | 30 s | none | Gaps and next steps |

Rehearsal timing: 25.7 s of total screen wait with a warm cache; cold, the Moquegua department takes about 17 s more at the API (a comparable 11-cell department measured 17 s cold and 6 s warm).

### Act 1 · Territory, trend and extremes (module «Clima»)

1. Left menu → «Clima».
2. In «Contexto de análisis», press «Quitar» on Arequipa. Moquegua remains as the point site.
3. In the territory search, type `Moquegua` and choose the result marked «Departamento».
4. Press «Ejecutar análisis».
5. Point at:
   - Map: nine coloured cells. Legend: «9 de 9 celdas con evidencia · sube hasta +0.42 °C/década».
   - Status line (header, right): «NASA POWER respondió» or «NASA POWER · copia en caché». Both are honest; the second appears after the warm-up.
   - Scale line under the territory: «Promedio por área de 9 celdas NASA POWER (0.5° × 0.625°) · cobertura 99.6 % · 15,743 km²», with the IGN source and its 2015 date.
   - «Lectura climática»: temperature 2026 so far +0.78 °C, third warmest of 26 years.
   - «Valores atípicos de NASA POWER»: RX1DAY Moquegua 2022 300.2 mm next to IMERG 12.1 mm; «Ningún índice ETCCDI conserva significancia tras Benjamini–Hochberg».
6. Optional: the «Lluvia máx. 5 días» tab shows the 2022 spike in the annual series.

### Act 2A · Road corridor Moquegua–Ilo (module «Infraestructura»)

1. Left menu → «Infraestructura». The pilot corridor is preselected.
2. Press «Ejecutar análisis».
3. Point at:
   - «Lectura del corredor»: five segments, 86 km in total.
   - «Capas territoriales oficiales»: CENEPRED flood risk and mass movements per segment, SERNANP and SIGDA with zero objects, INGEMMET «No disponible». Say: zero objects does not prove zero risk.
   - «Puntaje multicriterio»: segment 5 leads (48.5 against 38.7, first in 100 % of 2,000 weightings). Rain does not separate the segments: recent P99 is 2.73 mm/day on four of them and 3.60 on the first. What separates them is the NASADEM slope at segment 5's representative point, 17.9° against 4–7° elsewhere. The priority is geotechnical, not hydrological, and the slope comes from one point that should be checked along the segment.
   - «Escenarios y sensibilidad del VAN»: base, adverse and favourable scenarios; inputs labelled `USER_ASSUMPTION`.

### Act 2B · Solar screening Moquegua vs Arequipa (module «Energía»)

1. Left menu → «Energía».
2. Press «Restablecer»: act 1 removed Arequipa and the site list is shared between modules. Moquegua and Arequipa return with the default assumptions.
3. Press «Ejecutar análisis».
3. Point at:
   - «Puntaje multicriterio»: Arequipa 67/100, Moquegua 66/100; Arequipa first in 59 % of 2,000 weightings: a practical tie.
   - «Escenarios y sensibilidad del VAN»: base NPV −USD 3.08 M (Moquegua) and −USD 3.04 M (Arequipa).
   - Break-even points: price 64.40 USD/MWh against 55 assumed; CAPEX USD 14.92 M against 18 M; irradiance 7.70 kWh/m²/day, which no observed year reaches (best: 6.88).
   - Message: the resource is not what blocks the project; price and CAPEX are.

### Act 3 · Export

1. Press «PDF ejecutivo» (under «Evidencia y decisión»).
2. Open the file: six pages with the four challenge questions plus the investment question, sources, versions, download dates, methods, gaps and assumptions.

## Fallback routes

| Failure | What the screen shows | What to do |
|---|---|---|
| NASA POWER or Earthdata down, cache warmed today | Status «NASA POWER · copia en caché»; series marked `CACHED_DATA` with the original download date | Continue the main route unchanged. Rehearsed on 24-Oct with POWER blocked inside the API container: all three acts ran in 14.4 s with no errors. |
| NASA POWER down, no cache for today | Red status «Última consulta con error» and the message «La consulta a NASA POWER falló…» (HTTP 502) | Say that the product refuses to invent data, then open the PDF and screenshots from the morning rehearsal. |
| A Peruvian layer down (CENEPRED, SERNANP, SIGDA, GISEM) | That layer reads «No disponible» / `DATA_UNAVAILABLE` | Continue. Use it as proof that a missing layer never becomes a zero. |
| NASA GIBS imagery down | The visual layer does not load; analysis is unaffected | Leave the base map; GIBS layers are visual context only. |
| Laptop or network failure | — | Present from the rehearsal PDF and screenshots in `.claude-qa/demo/dia-demo/`. |

## Provenance key

| Class | Meaning on screen | Where it appears in the demo |
|---|---|---|
| `REAL_DATA` | Fresh response from the provider | Status line and series after a cold query |
| `CACHED_DATA` | Validated copy of an earlier response, with its original download date | Status line and series after the warm-up |
| `MODEL_ESTIMATE` | Calculated from data: trends, scores, NPV | Readings, score, sensitivity |
| `USER_ASSUMPTION` | Editable input | Financial assumptions, score weights |
| `ILLUSTRATIVE_DEMO` | Example geometry, not a real asset | Example parcels in «Inversión» (~330 m squares, not real lots) |
| `DATA_UNAVAILABLE` | Source pending or not answering | INGEMMET, pending modules, gaps panel |

## Gaps that stay visible

- INGEMMET remains `DATA_UNAVAILABLE` while its service fails strict TLS validation.
- LHASA has a confirmed official route; the analytical connector is pending.
- IGN boundaries date from 2015 and are not cadastral.
- In «Inversión», territories larger than 200 ha are analysis areas, not real-estate projects; their NPV does not describe a project.
- Zero intersections with an official layer do not mean zero risk.
- Station counter-checks (SENAMHI) are not connected; GPM IMERG is the only independent counter-check.

## Resolved before release: NASA POWER ×24 in the regional sampler (24-Oct-2026)

NASA POWER returns daily precipitation 24 times too large when a request reaches recent days. Points were already guarded; the regional sampler used by the road and real-estate pilots was not. A cell near Ilo gave 1,587.4 mm in the last year against 70.1 mm the year before (1,587.4 / 24 = 66.1).

Codex (K6, `bf20140`) now checks the scale cell by cell before averaging: a ratio near 1 is kept, a ratio near 24 is divided by 24 and any other ratio stops the result. Claude confirmed it on the live road pilot: the four segments that share a cell now report the same P99 (2.73 mm/day) and maximum (6.29 mm/day), where segments 2–4 previously showed 65.51 and 150.96. The «151 mm» day once attributed to MERRA-2 in September 2022 was this defect.
