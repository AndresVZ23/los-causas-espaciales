# Pitch

**Los Causas Espaciales** · NASA Space Apps Challenge 2026 · *Be An Earth System Trend Detective!*
Team: Christian Venegas Calderon, Nikol Estefany Borja Ugarte, Abel Andres Valle and Mario Alaluna (each member confirms the spelling of their name before submission).

## One line

We turn NASA Earth observations into evidence an infrastructure investor can audit, for solar, wind, hydro, roads and real estate: what is changing, where, by how much, how sure we are, and what it means for the asset. Every number is checked against a second independent source, and when the two disagree, the report says so.

## What makes it different: a second witness for every number

A trend detective does not convict on one testimony. Each data item enters the platform with an independent source that checks it, and what appears when they are crossed is shown as a «descubrimiento» on screen, in the PDF and in the assistant.

| What is measured | First source | Second source | What the cross-check found in a real case |
|---|---|---|---|
| Temperature trend | NASA POWER (MERRA-2) | ERA5 | Moquegua, 2005–2023: the same warming, +0.039 and +0.042 °C per year. The level differs by 10.6 °C, and the platform says that too. |
| Extreme rainfall | NASA POWER (MERRA-2) | GPM IMERG and CHIRPS | Moquegua, 2022: a 300 mm day that neither satellite product sees (12 and 17 mm). Flagged, not used as a hazard. |
| Solar resource | NASA POWER (CERES) | ERA5 | Moquegua: within 5 % (+1.6 %). |
| Wind at hub height | NASA POWER hourly | Global Wind Atlas | Marcona: 6.4 against 9.7 m/s. Real production supports the atlas. |
| River flow | GloFAS (Copernicus) | GEOGLOWS | Upper Tambo: 64 % apart. At Machupicchu, real production supports GloFAS. |
| Head and slope | NASADEM | Copernicus GLO-30 | Machupicchu: 330 and 335 m. Tambo canyon: 23 m apart. |
| Landslide susceptibility | CENEPRED (Peru) | NASA global map and COOLR reports | Lurigancho–Chosica: the maps agree in 7 of 9 points and 6 reported landslides confirm them. |
| Vegetation cover | MODIS | ESA WorldCover | Ilo: 21.8 % and 18.7 % of non-tree vegetation. |

Two energy models are also checked against what real plants produced in 2024, as reported by the grid operator COES: the Marcona wind farms (56 % to 58 % of capacity; the model gives 47 %) and the Machupicchu hydro plant (74 %; the model gives 65 % to 77 %).

## Spoken narrative (3–5 minutes, live)

Each block matches an act in [DEMO_SCENARIOS.md](DEMO_SCENARIOS.md). Figures below come from the rehearsal of 10 November 2026 (NASA POWER data through 8 November 2026). They are reproduced live and will move when the providers update their series; say the number the screen shows, not the number written here.

### 0 · The problem (≈30 s)

> Infrastructure is financed with thirty-year horizons on climate information that is fragmented, rarely tested, and almost never traceable. A risk map tells you a colour. It does not tell you what was observed, by which instrument, how strong the trend is, whether a second source agrees, or what is still unknown. We built the step in between, for any infrastructure asset: a solar plant, a wind farm, a hydro plant, a road, a piece of land.

### 1 · Detect the trend in a real territory (≈75 s)

> We pick a territory, not a pin: the department of Moquegua, from official IGN boundaries. The platform finds the nine NASA POWER cells that cover it and analyses each one from 2001 to today.
>
> All nine cells are warming, and the evidence survives Mann–Kendall with autocorrelation correction and Benjamini–Hochberg across cells, at up to 0.42 °C per decade. 2026 so far is the third warmest of 26 years. At the city of Moquegua a second reanalysis, ERA5, sees the same warming.
>
> Now the trap. NASA POWER reports a 300 mm rain day in Moquegua in 2022. A naive tool would call that a flood regime. We cross-check against two satellite products, GPM IMERG and CHIRPS, whose wettest days that year were 12 and 17 mm. We keep the value, flag it as a probable artefact, and no rainfall-extreme index stays significant. Being a detective means refusing the convenient clue.

### 2 · Translate it into a decision for an asset (≈90 s)

Use one act; all four are verified. They end on the same idea: a conditioned decision, not a verdict.

**2A · Road corridor Moquegua–Ilo**

> The same evidence now runs along an 86.5 km corridor split into five segments, with the official layers read per segment. Zero objects does not mean zero risk, and a service that does not answer is shown as unavailable, not as clean.
>
> One segment leads the priority score under every weighting, and the reason is not rain: rainfall is low and almost identical along the corridor. It is the terrain. NASA's elevation model gives segment 5 a slope of almost 18 degrees. So we asked a second elevation model, Copernicus, and it says 12 and a half. Both agree it is by far the steepest segment, and we recompute the score with the second one: the leader does not change. The first study to fund is geotechnical, and it starts with a survey of that slope.

**2B · Solar screening Moquegua vs Arequipa**

> Two candidate solar sites. The score says Arequipa 67, Moquegua 66, and Arequipa leads in only 60 % of 2,000 weightings. That is a tie, and we print the word tie.
>
> The net present value is negative in both, about minus 3 million dollars. Is it the sun? No. The break-even irradiance is 7.7 kWh/m²/day and the best year NASA ever observed there is 6.88. What moves the decision is the energy price: it would need 64 dollars per MWh, against the 55 assumed.

**2C · Wind screening in Marcona**

> NASA's reanalysis gives Marcona 6.4 metres per second at hub height. The Global Wind Atlas, at 250 metres, gives 9.7. Half as much again. Which one do you finance on?
>
> We went to the witness that cannot be argued with: the wind farms already operating there. In 2024 they produced at 56 to 58 % of capacity. That is the atlas, not the reanalysis. So the model takes its level from the atlas and its hour-by-hour shape from NASA, lands at 47 %, below the real plants, and keeps NASA's level as the adverse scenario. The same screen tells you that a second site, Moquegua, does not have the wind: 0.3 %.

**2D · Run-of-river hydro, Machupicchu and the upper Tambo**

> A hydro plant is water times height. For the water we use the daily river flow of GloFAS, from Copernicus, and a second model, GEOGLOWS. For the height, NASA's elevation model and Copernicus.
>
> At Machupicchu the two elevation models agree: 330 and 335 metres. In the Tambo canyon they are 23 metres apart, and the two flow models differ by 64 %. We do not hide that in a footnote. Both disagreements are bars in the sensitivity chart, next to price and cost.
>
> And the check against reality: the real Machupicchu plant ran at 74 % of capacity in 2024. Our model gives 65 to 77 %, depending on how much water is left in the river.

### 3 · Leave with evidence (≈20 s)

> One click exports an executive PDF: the four challenge questions plus our fifth, sources, versions, download dates, methods, what the cross-checks found, open data gaps and every assumption. Anyone can rerun it with the same inputs and the same data release and land on the same numbers.

### 4 · Why it matters and what is next (≈30 s)

> We do not replace engineering, environmental, archaeological, financial or legal due diligence. We tell you where to spend that budget first, we tell you when two sources disagree, and we never turn a missing layer into a zero. This week an official risk service closed its public access: the platform shows its last valid copy, with its date, and says so.
>
> Next: ground stations and river gauges, real production inside the product, the distance to the power grid, communities and social conflicts, and more territories across the Andes.

## Thirty-second cut (Global Judging video)

Target ≤ 30 s with English subtitles; the interface is in Spanish, so the subtitles carry the meaning.

1. (0–6 s) Department of Moquegua selected → nine warming cells on the map. *"NASA data, tested trend by trend: all nine cells are warming."*
2. (6–13 s) The 300 mm value next to IMERG and CHIRPS. *"300 mm in one product, 12 and 17 in two others. We flag it instead of trusting it."*
3. (13–22 s) Wind in Marcona: the discovery row and the reading. *"Two sources half apart. Real wind farms settle it."*
4. (22–30 s) PDF downloading. *"Every number has a second witness and a source. Los Causas Espaciales."*

## Seven-slide outline (alternative to the video)

1. Title: product, team, challenge.
2. Problem: long-horizon infrastructure, fragmented and untraceable climate information.
3. How it works: territory or asset → NASA POWER, GPM IMERG, NASADEM, MODIS, GIBS → Mann–Kendall + Hamed–Rao + Benjamini–Hochberg → a second source for every number → asset decision.
4. Detective moment: nine warming cells and the refuted 300 mm day.
5. Decision moment: one asset (wind in Marcona or hydro at Machupicchu), with the two sources and the real production.
6. Trust: six provenance classes, discoveries, visible gaps, reproducible PDF.
7. Impact and next steps: one method for solar, wind, hydro, roads and real estate.

The demo format above follows the published Project Submission Guide (video ≤ 30 s or ≤ 7 slides, in English, hosted publicly). Check both limits against the guide in force before uploading.
