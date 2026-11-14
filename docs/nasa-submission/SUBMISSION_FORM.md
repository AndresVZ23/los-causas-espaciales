# Submission form draft

> Working English copy prepared on 11-Nov-2026. **The official 2026 Project Submission Guide and form fields are expected on 13-Nov-2026.** Field names, limits, required links, eligibility declarations and media rules below are placeholders only. Map each section to the official form before submission; do not shorten text to an invented character limit.

## Project title

Los Causas Espaciales

## Challenge

*Be An Earth System Trend Detective!*

Pending 13-Nov-2026: confirm the exact official challenge title and identifier.

## Short description

Los Causas Espaciales turns NASA Earth observations into infrastructure-screening evidence that can be audited. It detects trends, checks each material result against another source, exposes disagreements and missing data, and connects the evidence to transparent scoring, user-defined financial scenarios and an executive PDF.

## The problem

Long-horizon infrastructure decisions rely on environmental information that is fragmented and difficult to verify. A conventional risk map rarely tells an investor which observation produced a value, whether the trend is statistically defensible, whether an independent source agrees, or whether a blank result is truly zero. This makes it hard to decide where limited engineering and due-diligence budgets should go first.

## The solution

Users select a point, an official territory or their own corridor/polygon. A traceable pipeline retrieves Earth data, validates geometry and units, tests trends, compares independent sources and returns discoveries, limitations, a multicriteria score, explicit financial scenarios and a downloadable report. The product is a screening tool, not a substitute for engineering, permitting, fieldwork or investment approval. [ADR-004, ADR-015, ADR-016, ADR-020, ADR-022]

## NASA data and the trend-detective method

NASA POWER supplies climate and renewable-resource series; GPM IMERG and CHIRPS test rainfall extremes; NASADEM supplies elevation and slope; MODIS supplies vegetation evidence; NASA landslide products add susceptibility, nowcast and reported-event context; NASA EONET provides a second witness for global events. Each source retains product identity, date, units, spatial limits and provenance.

The statistical path uses Mann–Kendall with Hamed–Rao variance correction, Theil–Sen slope and Benjamini–Hochberg adjustment across compared subjects. [ADR-014, ADR-019, ADR-025]

One reproducible example shows why the cross-check matters: in Moquegua, MERRA-2 reports a **300 mm** extreme day in 2022, while IMERG reports **12 mm** and CHIRPS **17 mm**; the platform flags a probable artefact instead of treating it as a confirmed hazard. [ADR-036]

## What is innovative

The product treats disagreement as evidence. A second source does not silently replace the first: both values remain visible, a deterministic rule describes whether they agree, and material gaps enter the decision and PDF. In Marcona, NASA POWER estimates **6.39 m/s** at hub height and the Global Wind Atlas **9.74 m/s**; COES production factors of **56.5%** and **57.7%** at operating wind farms support the atlas-based case while NASA remains the adverse resource scenario. [ADR-041, ADR-045]

The same typed C2 contract serves climate, energy, hazards, environmental and heritage baselines, road corridors and real-estate areas, so provenance and limitations do not disappear when the use case changes. [ADR-015, ADR-032, ADR-034]

Findings can also be read where they are. From the world-alerts panel, two places open as a block model that is explored on foot or flying: the city of Moquegua and Taal volcano. Each block is **30 m** or **35 m** of terrain from Copernicus DEM GLO-30, coloured by ESA WorldCover 2021, and each beacon carries a result of the platform with its second source and what to study first. The model declares its vertical exaggeration (×2 and ×3), shows the real altitude and slope under the visitor, and reproduces no real buildings or streets. [ADR-047]

For schools and the general public there is a player mode, «Detectives de la Tierra» (`/jugar`): a hero leaves the Moon, picks one of **56** real places and reads its temperature trend since 2001 before helping the town. The game adds no data and keeps the platform's rules: an atypical rainfall year is a «false clue» only where the reanalysis exceeds the satellite product at least five times (**3** places), a warming label states whether ERA5 confirms it (**15** of **35** places with a trend), «not significant» is taught as «the evidence is not enough», and the disaster events of the game (mudflow, flood, heat, eruption or avalanche) are simulated: the team chose one per place from its known hazards, and the alert card says it is a simulated event. [ADR-048]

## Geographic scope

Global NASA, ERA5, Copernicus, ESA, GloFAS, GEOGLOWS and wind-atlas sources allow site-level screening outside Peru. Search by place name only positions a point; it is not evidence. National administrative, risk, heritage and protected-area layers are currently connected only for Peru, and the response states that limitation rather than returning a false zero. Global events use GDACS provider levels with NASA EONET as a second witness and are explicitly informational, not an early-warning service. [ADR-046]

## Users and impact

The intended users are infrastructure investors, developers, engineers, environmental teams and public institutions deciding where to spend investigation budget. The platform can shorten the path from a broad region to a defensible next study while keeping uncertainty visible. It does not claim bankability, safety, legal status or permit approval.

## Technical implementation

The application uses Next.js, MapLibre and Recharts over a FastAPI/OpenAPI backend. Provider-specific connectors feed content-addressed caches and typed Pydantic contracts. Statistical, geospatial, scoring, finance and report-generation engines are separate. The same contract drives the console and executive PDF. [ADR-015, ADR-016]

The last-valid-copy mechanism serves only the exact prior request, preserves its original timestamp and marks it `CACHED_DATA`; official territorial copies expire after **90 days**. [ADR-044] `method_validation` carries dated wind and hydro checks against real COES production without presenting those checks as a guarantee for the user's site. [ADR-045]

## Scientific validation

- Moquegua territory: **9** NASA POWER cells show significant warming, reaching **+0.42 °C per decade**. [ADR-025]
- Temperature at Moquegua, common period: MERRA-2 **+0.039 °C/year** and ERA5 **+0.042 °C/year**; their absolute levels differ by **10.6 °C**. [ADR-038]
- Lurigancho-Chosica landslides: national and NASA susceptibility maps agree at **7 of 9** sample points, with **6** COOLR reports supporting the mapped context. [ADR-037]
- Machupicchu validation: COES reports a **74.1%** 2024 plant factor; the run-of-river model spans **64.7%–77.1%** as the declared ecological-flow assumption changes. [ADR-042, ADR-045]

These are bounded case validations and discoveries, not universal accuracy claims.

## Data provenance, licensing and safety

Each output distinguishes real data, cached data, model estimates, user assumptions, illustrative material and unavailable data. A non-response never means “no risk.” Provider licences, attribution text, coverage, resolution and access dates are recorded in `DATA_SOURCES.md`. The alert view preserves GDACS and NASA disclaimers and never replaces competent local authorities. [ADR-004, ADR-044, ADR-046]

## Use of artificial intelligence

Claude Code and Codex assisted with code, tests, reviews and documentation under team direction. The product does not use generative AI to create or alter observations, calculations or deterministic discoveries. Classical statistics performs trend analysis. The rules-based assistant is the default; an optional Gemini action runs only after an explicit user request and is constrained to the current analysis. NASA LHASA is itself a published machine-learning product and remains labelled as provider model output. [ADR-007, ADR-023, ADR-037]

Pending 13-Nov-2026: copy the exact disclosure terminology and any mandatory AI label from the official guide. Confirm this statement with every team member before submission.

## Team

- Christian Venegas Calderon
- Nikol Estefany Borja Ugarte
- Abel Andres Valle
- Mario Alaluna

Pending 13-Nov-2026: confirm spelling, roles, affiliations, contact details and any required consent fields directly with each member.

## Links and media

- Live project: `[PENDING — official public URL and guide requirements]`
- Source repository: `[PENDING — approved public repository URL]`
- Demo video or slide deck: `[PENDING — official format and hosting rules on 13-Nov-2026]`
- Supporting documentation: `[PENDING — decide which repository paths the form accepts]`

## Final guide-dependent checklist

- [ ] Map these headings to the official form fields and character limits.
- [ ] Confirm required language, media duration/slide count, aspect ratio, file type and maximum size.
- [ ] Confirm whether public hosting, repository visibility, licences or source-code access are mandatory.
- [ ] Confirm accessibility requirements for captions, subtitles, alt text and colour.
- [ ] Confirm team eligibility, consent, location and contact declarations.
- [ ] Confirm the required AI-use disclosure wording.
- [ ] Reproduce every numeric claim from the release candidate and retain its cited ADR.
- [ ] Run the common quality gate and final browser QA before replacing any `[PENDING]` marker.
