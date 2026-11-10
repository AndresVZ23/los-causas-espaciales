# Project Overview

Status on 10 November 2026. Challenge: *Be An Earth System Trend Detective!*

## Problem

Infrastructure is financed with thirty-year horizons on environmental information that is fragmented, rarely tested and almost never traceable. A risk map shows a colour; it does not say what was observed, by which instrument, how strong the trend is, whether a second source agrees, or what is still unknown. Investors cannot tell observed evidence from assumptions, and cannot tell where to spend their study budget first.

## Solution

Los Causas Espaciales turns NASA Earth observations into investment evidence for infrastructure. The user chooses a site, an official territory, or draws the asset. The platform:

- measures what has changed in climate and territory since 2001;
- tests whether each change is statistically significant;
- checks every data item against a second independent source and publishes what the comparison shows;
- ends in a multicriteria score, a net present value with scenarios and sensitivity, and an executive PDF.

It is a screening tool: it tells where to look first. It does not replace engineering, environmental, archaeological, financial or legal due diligence.

## One method, seven modules

| Module | What it does | Second source |
|---|---|---|
| 1 · Climate | Temperature, rainfall, wind and irradiance trends, rainfall extremes and the year in progress, for a site or a whole territory | ERA5; GPM IMERG and CHIRPS for rainfall |
| 2 · Energy | Solar, wind and run-of-river hydro: resource, energy, NPV and score | ERA5, Global Wind Atlas, GEOGLOWS and Copernicus DEM; wind and hydro validated against real production |
| 3 · Hazards | Extreme rainfall, terrain, official risk layers and landslides | NASA landslide susceptibility, LHASA and reported events |
| 4 · Environment | Baseline inputs: MODIS vegetation with trend, water, ecosystems and protected areas | ESA WorldCover |
| 5 · Territory | Registered and declared heritage and prior-consultation areas | None yet; communities and conflicts remain an open gap |
| 6 · Infrastructure | Road corridor by segments: rainfall, official layers, mitigation NPV and priority score | Copernicus DEM for the terrain |
| 7 · Investment | Parcels or official territories: rainfall, terrain, official layers, NPV and score | Copernicus DEM for the terrain |

All modules share one response contract, a visible nine-stage pipeline, the answers to the challenge questions, the discoveries, the declared data gaps and the PDF.

## Users and value

Investment funds, asset managers, project developers, engineers, environmental specialists and public institutions get the same thing: evidence they can audit before committing budget. Each figure states its source, its date and whether it is an observation, a model estimate or the user's own assumption.

## What is new

- **Four scientific questions and a fifth.** What is changing, where, by how much and with what statistical evidence; and then what it could mean for a real asset. The platform does not confuse correlation, causality and prediction.
- **A second witness for every number.** In Moquegua, NASA's reanalysis reports a 300 mm rain day in 2022 that two satellite products put at 12 and 17 mm: it is flagged, not used. In Marcona, the reanalysis and the wind atlas differ by half, and the wind farms operating there settle which one to finance on.
- **Disagreement goes into the decision.** When two sources differ on river flow or on the height of a hydro site, both ends become bars in the NPV sensitivity chart, next to price and cost.
- **Honest outcomes.** A tie is called a tie. A layer that does not answer is shown as unavailable, never as zero. When an official service closed its public access in November 2026, the platform kept its last valid copy with its date and said so.

## Architecture

Next.js, MapLibre and Recharts consume a FastAPI service. One connector per provider feeds normalised contracts, with a content-addressed cache that preserves each raw response and its download date. Statistical, geospatial, scoring and financial engines are separate and tested on their own. Details in [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) and [SCIENTIFIC_METHODOLOGY.md](SCIENTIFIC_METHODOLOGY.md).
