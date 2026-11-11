# Demo Scenarios

The live demo runs on `http://localhost:3100` (web) and `http://localhost:8000` (API). The interface is in Spanish; button names below are quoted as they appear on screen. The spoken script for each act is in [PITCH.md](PITCH.md).

NASA results are not hard-coded. The figures quoted here come from the rehearsal of 10 November 2026 (NASA POWER data through 8 November 2026) and move when the providers update their series. Say the number the screen shows, not the number written here.

## Before the demo (same day, at most two hours before)

The NASA POWER cache lasts 24 hours and its key includes today's date, so yesterday's cache does not cover today. Warming it on the day is what makes the fallback route possible.

1. Confirm the stack: `docker ps` shows `los-causas-espaciales-web-1` and `los-causas-espaciales-api-1`; `http://localhost:8000/api/v1/health` answers 200.
2. Run the rehearsal: `node scripts/qa/demo_ensayo.cjs dia-demo`. It performs every act below, warms the cache, downloads the PDF and writes timings and screenshots to `.claude-qa/demo/dia-demo/`.
3. Check `ensayo.json`: `errors` and `missedShots` are empty, `overflow` is 0 and the PDF header is `%PDF`.
4. Keep the downloaded PDF and the screenshots open in a second window as the last-resort route.
5. Do not press «Preguntar a Gemini» during the demo. The assistant's «Preguntar» answers by rules at no cost and is enough.
6. Present from the machine that ran the rehearsals. Since 10 November 2026 CENEPRED's service requires a token, so its layers are shown from the last valid copy held in that machine's cache (see «CENEPRED» under fallback routes). Never run `docker compose down -v` on it: that deletes the copies.

## Main route (3–5 minutes)

Run acts 0, 1, one asset act, 3 and 4. Act 1B and the other asset acts are spares for questions.

| Act | Module | Spoken time | Screen wait (warm cache) | What the jury must see |
|---|---|---|---|---|
| 0 · Problem | Opening screen | 30 s | 1–5 s | Console, map, provenance key in the header |
| 1 · Territory, trend and extremes | Clima | 75 s | 25–45 s | Nine warming cells; the 300 mm day that only one model sees |
| 1B · Landslides (spare) | Amenazas | 45 s | 7–10 s | Reported landslides confirm the susceptibility maps |
| 2A · Road corridor | Infraestructura | 90 s | 7 s | The leader is decided by one slope, and two elevation models disagree on it |
| 2B · Solar | Energía · Solar | 90 s | 8 s | A tie called a tie; price, not sun, blocks the project |
| 2C · Wind | Energía · Eólica | 90 s | 8 s | NASA's cell and the wind atlas differ by half; real production settles it |
| 2D · Hydro | Energía · Hidroeléctrica | 90 s | 6–9 s | Two flow models and two elevation models, both in the NPV tornado |
| 3 · Export | Any | 20 s | 1–2 s | Executive PDF |
| 4 · Close | none | 30 s | none | Gaps and next steps |

Rehearsal timing with a warm cache: 66 to 92 s of total screen wait for the eight acts that use the screen. A site that was never queried takes longer the first time: about 40 s for a hydro site, plus a second run to bring the GEOGLOWS flow, which is fetched in the background.

### Opening option · The world, then Peru (map button «Alertas en el mundo»)

A 30-second way to open: it shows that the method is global and why a place is chosen.

1. On the map, press «Alertas en el mundo». The map turns into a 3D globe over South America that spins slowly, and each event appears as a small hopping block: red and orange are GDACS alert levels, green are events in Peru, blue are open NASA EONET events without a level. «Pulsos» switches to round pulses.
2. Point at the list: on 10 November 2026 it held 25 events, among them four red alerts (tropical cyclones in India, the Philippines and Mexico), fourteen orange (droughts across Europe, Central America and Africa, earthquakes, eruptions and floods) and, under «Perú», three floods and a wildfire at green level.
3. Press one event, then «Analizar amenazas aquí». The site moves there and the hazards module runs with the global NASA sources only. Under «Brechas antes de invertir» the platform states that the official layers it connects are Peruvian.
4. Say: the alert level is GDACS's, not ours, and analysing the point shows the background trends and hazards of the place, not the state of the event.

Any other place in the world can be set from «Buscar un lugar del mundo», above the site list.

### Opening option B · Walk into the place («Zonas para recorrer», ADR-047)

A one-minute scene that shows the findings where they are. It needs no live source: the two zones are pre-built and served by the local API. Direct links: `http://localhost:3100/zona/moquegua` and `http://localhost:3100/zona/taal`.

1. Press «Alertas en el mundo». At the top of the panel, under «Zonas para recorrer», press «Moquegua, Perú»: the globe flies to the teal block. Press «Entrar».
2. The screen opens above a block model of the real valley: each block is 30 m of terrain from Copernicus DEM GLO-30, coloured by ESA WorldCover 2021. Say it plainly: it is a scale model with the relief exaggerated ×2, with no real buildings or streets.
3. Press «Empezar el recorrido», then `F` to drop to the ground and `W A S D` to walk. The plate at the bottom left shows the real altitude and slope under your feet.
4. Press `2` to jump to the beacon «El día de 300 mm que solo ve un modelo»: MERRA-2 reports 300.2 mm in one day of 2022 and the two satellite products report 12.1 mm and 17.4 mm. The platform marks it as a probable artefact. This is the team's thesis in one card.
5. Press `P` to paint the real slopes: 15 % of the model is steeper than 15°. Press `6` for the start of the Moquegua–Ilo corridor (the yellow line).
6. Press `Esc`, then «Salir al mapa». For the second zone, open «Volcán Taal, Filipinas»: an active volcano inside a lake, with the GDACS orange alert of 8 October 2026 and, as the last beacon, what the platform does not know there (no official Philippine hazard map is connected).

If the computer cannot start 3D graphics, the screen shows the same findings as a list. Do not describe the model as a view of the place or as a simulation of the eruption.

### Act 1 · Territory, trend and extremes (module «Clima»)

1. Left menu → «Clima».
2. In «Contexto de análisis», press «Quitar» on Arequipa. Moquegua remains as the point site.
3. In the territory search, type `Moquegua` and choose the result marked «Departamento».
4. Press «Ejecutar análisis».
5. Point at:
   - Map: nine coloured cells. Legend: «9 de 9 celdas con evidencia · sube hasta +0.42 °C/década».
   - Status line (header, right): «NASA POWER respondió» or «NASA POWER · copia en caché». Both are honest; the second appears after the warm-up.
   - Scale line under the territory: «Promedio por área de 9 celdas NASA POWER (0.5° × 0.625°) · cobertura 99.6 % · 15,743 km²», with the IGN source and its 2015 date.
   - «Lectura climática»: temperature in 2026 so far, +0.82 °C for the department, third warmest of 26 years (+0.93 °C at the point, second warmest).
   - «Valores atípicos de NASA POWER»: RX1DAY Moquegua 2022 300.2 mm next to IMERG 12.1 mm and CHIRPS 17.4 mm; «Ningún índice ETCCDI conserva significancia tras Benjamini–Hochberg».
6. Optional: the «Lluvia máx. 5 días» tab shows the 2022 spike in the annual series, with the IMERG and CHIRPS lines running flat beneath it.

### Act 1B · Landslides in Lurigancho–Chosica (module «Amenazas», spare)

1. Left menu → «Amenazas».
2. In the territory search, type `Lurigancho` and choose the district «Lurigancho» (Lima), not San Juan de Lurigancho.
3. Remove the other subjects with «Quitar» so that only the district remains.
4. Press «Ejecutar análisis».
5. Point at:
   - «Lectura de amenazas»: «7 de 9» layers with records, «1 sin respuesta» (INGEMMET's national inventory) and «3 de una copia anterior» (CENEPRED).
   - «Descubrimientos al cruzar fuentes»:
     - «CENEPRED y NASA coinciden en la susceptibilidad a deslizamientos»: in 7 of 9 sampling points the national map and NASA's global map differ by at most one class.
     - «deslizamientos reportados donde los mapas marcan susceptibilidad alta»: NASA's COOLR catalogue records 6 reported landslides between 2009 and 2017, among them the 2017 Chosica El Niño landslide.
     - «NASADEM y Copernicus difieren en el relieve»: 32.2° against 23.0° of slope at the representative point.
   - The CENEPRED rows carry the tag «copia del 27-oct-2026» and the reason, «Token Required».

### Act 2A · Road corridor Moquegua–Ilo (module «Infraestructura»)

1. Left menu → «Infraestructura». The pilot corridor is preselected.
2. Press «Ejecutar análisis».
3. Point at:
   - «Lectura del corredor»: five segments, 86.5 km in total.
   - «Capas territoriales oficiales»: CENEPRED flood risk and mass movements per segment (tagged «copia del 25-oct-2026»), SERNANP and SIGDA with zero objects, INGEMMET «No disponible». Say: zero objects does not prove zero risk.
   - «Puntaje multicriterio»: segment 5 leads (48.5 against 38.7, first in 100 % of 2,000 weightings). Rain does not separate the segments: recent P99 is 2.73 mm/day on four of them and 3.60 on the first. What separates them is the slope at segment 5's representative point.
   - «Descubrimientos al cruzar fuentes»: «Tramo 5 de 5: la pendiente cruza el umbral de 15° según el modelo de elevación». NASADEM measures 17.9° and Copernicus 12.5° at the same point.
   - Last note under the score: with the Copernicus slope the first place does not change, 44.4 against 37.1. The order holds; the magnitude needs a survey.
   - «Escenarios y sensibilidad del VAN»: base NPV between USD 1.48 M and 2.43 M per segment, adverse between −USD 2.51 M and −1.34 M; every input is labelled `USER_ASSUMPTION`.

### Act 2B · Solar screening Moquegua vs Arequipa (module «Energía»)

1. Left menu → «Energía». In «Tecnología», keep «Solar fotovoltaica».
2. Press «Restablecer»: act 1 removed Arequipa and the site list is shared between modules. Moquegua and Arequipa return with the default assumptions.
3. Press «Ejecutar análisis».
4. Point at:
   - «Puntaje multicriterio»: Arequipa 67/100, Moquegua 66/100, 0.3 points apart, Arequipa first in 60 % of 2,000 weightings: «Empate práctico».
   - «Escenarios y sensibilidad del VAN»: base NPV −USD 3.08 M (Moquegua) and −USD 3.04 M (Arequipa).
   - Break-even points: price 64.42 USD/MWh against 55 assumed; CAPEX USD 14.92 M against 18 M; irradiance 7.70 kWh/m²/day, which no observed year reaches (best: 6.88).
   - Message: the resource is not what blocks the project; price and CAPEX are.

### Act 2C · Wind screening Marcona vs Moquegua (module «Energía»)

1. Left menu → «Energía». In «Tecnología», choose «Eólica». The example sites change to Marcona and Moquegua.
2. Press «Ejecutar análisis».
3. Point at:
   - «Lectura comparativa»: Marcona 9.74 m/s at hub height, net capacity factor 46.6 %, NPV USD 21.1 M. Moquegua 2.28 m/s, 0.3 %, −USD 80.27 M: the platform also says no.
   - «Descubrimientos al cruzar fuentes»: «Marcona: el recurso eólico difiere 52 % entre NASA POWER y el Atlas Eólico Global». NASA's reanalysis cell is about 50 km wide and gives 6.4 m/s; the 250 m atlas gives 9.7 m/s.
   - «Método eólico», first note, marked «real»: the wind farms that operate in Marcona produced at 56 % to 58 % of capacity in 2024 according to the grid operator COES; the model gives 46.7 % with the atlas level and 14.0 % with NASA's.
   - Say: real production supports the atlas, so the model uses the atlas level for the mean and NASA's hourly record for the shape, and stays below the real figure. NASA's level remains as the adverse case.
   - «Puntaje multicriterio»: Marcona leads by 50 points, first in 100 % of the weightings.
   - Break-even price 43.62 USD/MWh against 55 assumed.

### Act 2D · Run-of-river hydro, Machupicchu and the upper Tambo (module «Energía»)

1. Left menu → «Energía». In «Tecnología», choose «Hidroeléctrica de pasada». Each site is an intake on the river and a powerhouse downstream.
2. Press «Ejecutar análisis».
3. Point at:
   - «Lectura comparativa»: Machupicchu (Vilcanota river) 156.3 m³/s, 330 m of head, 163.2 MW, 970 GWh per year, NPV −USD 0.88 M. Upper Tambo (Moquegua) 32.3 m³/s, 146 m, 27.9 MW, 115 GWh, −USD 26.35 M.
   - «Caudal» tab: the GloFAS annual series as a solid line and GEOGLOWS dashed above it.
   - «Descubrimientos al cruzar fuentes»:
     - «Tambo alto: el caudal medio difiere 64 % entre GloFAS y GEOGLOWS».
     - «Tambo alto: el salto difiere 23 m según el modelo de elevación» (146 m in NASADEM, 169 m in Copernicus).
     - «Machupicchu: NASADEM y Copernicus coinciden en el salto».
   - «Escenarios y sensibilidad del VAN»: the tornado carries both disagreements as factors, «Caudal (GloFAS ↔ GEOGLOWS)» and «Salto (NASADEM ↔ Copernicus)».
   - «Método hidroeléctrico», first note, marked «real»: the real Machupicchu plant ran at 74.1 % of capacity in 2024 (COES); the model gives 64.7 % to 77.1 % depending on the ecological flow left in the river.
   - Say: the real figure falls inside the model's range. GloFAS is the base case because it is the one the real plant supports.

### Act 3 · Export

1. Press «PDF ejecutivo» (under «Evidencia y decisión»).
2. Open the file: the four challenge questions plus the investment question, sources, versions, download dates, methods, discoveries, gaps and assumptions.

## Fallback routes

| Failure | What the screen shows | What to do |
|---|---|---|
| NASA POWER or Earthdata down, cache warmed today | Status «NASA POWER · copia en caché»; series marked `CACHED_DATA` with the original download date | Continue the main route unchanged. |
| NASA POWER down, no cache for today | Red status «Última consulta con error» and the message «La consulta a NASA POWER falló…» (HTTP 502) | Say that the product refuses to invent data, then open the PDF and screenshots from the morning rehearsal. |
| CENEPRED (requires a token since 10 November 2026) | On the rehearsal machine: the count with the tag «copia del 25-oct-2026», a note with the reason and a gap marked «Copia validada en caché». On any other machine: «No disponible» | Continue. Say it as it is: the official service closed, the product shows its last valid copy with its date and tells you so. |
| Another Peruvian layer down (SERNANP, SIGDA, ANA, MINAM) | The last valid copy with its date if that query was made in the last 90 days; otherwise «No disponible» / `DATA_UNAVAILABLE` | Continue. Use it as proof that a missing layer never becomes a zero. |
| GEOGLOWS slow on a new hydro site | The second flow source reads «en consulta» | Run the analysis again after a minute; the base case does not depend on it. |
| NASA GIBS imagery down | The visual layer does not load; analysis is unaffected | Leave the base map; GIBS layers are visual context only. |
| Laptop or network failure | — | Present from the rehearsal PDF and screenshots in `.claude-qa/demo/dia-demo/`. |

SIGDA (Ministry of Culture) cuts the connection after a burst of queries. Do not run the rehearsal several times in a row before the demo; once is enough.

## Provenance key

| Class | Meaning on screen | Where it appears in the demo |
|---|---|---|
| `REAL_DATA` | Fresh response from the provider | Status line and series after a cold query |
| `CACHED_DATA` | Validated copy of an earlier response, with its original download date | Status line and series after the warm-up; CENEPRED layers |
| `MODEL_ESTIMATE` | Calculated from data: trends, scores, NPV | Readings, score, sensitivity |
| `USER_ASSUMPTION` | Editable input | Financial assumptions, score weights |
| `ILLUSTRATIVE_DEMO` | Example geometry, not a real asset | Example parcels in «Inversión» (~330 m squares, not real lots) |
| `DATA_UNAVAILABLE` | Source pending or not answering | INGEMMET inventory, gaps panel |

## Gaps that stay visible

- CENEPRED's risk layers cannot be queried without a token since 10 November 2026; a place never queried before shows them as unavailable.
- INGEMMET's national geohazard inventory is not published on its server; its volcanic hazard maps are read.
- No ground stations are connected: rainfall is checked satellite against reanalysis (GPM IMERG and CHIRPS), and river flow model against model (GloFAS and GEOGLOWS). No gauging station settles the flow.
- Communities and social conflicts have no queryable geographic source yet.
- IGN boundaries date from 2015 and are not cadastral.
- In «Inversión», territories larger than 200 ha are analysis areas, not real-estate projects; their NPV does not describe a project.
- Zero intersections with an official layer do not mean zero risk.
- Wind and hydro are validated against one real case each (the Marcona wind farms and the Machupicchu plant); more plants are needed before generalising.
