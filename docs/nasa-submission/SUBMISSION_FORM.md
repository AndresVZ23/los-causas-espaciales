# Submission form draft

> Working English copy prepared on 11-Nov-2026. **The official 2026 Project Submission Guide and form fields are expected on 13-Nov-2026.** Field names, limits, required links, eligibility declarations and media rules below are placeholders only. Map each section to the official form before submission; do not shorten text to an invented character limit.

> **Update, 15-Nov-2026.** The official Project Submission Guide and Judging & Awards Guide were read on the live site. What they confirm is listed under «Official rules confirmed on 15-Nov-2026»; anything still open keeps its `[PENDING]` marker. The text sections above that list were written on 11-Nov-2026, before the game became the front page (ADR-050), and have not been rewritten here.

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

The 30-second demo (ADR-051) was scripted, animated and edited with AI assistance (Claude) and reviewed by the team; its narration is a synthetic text-to-speech voice (Piper, voices `en_US-ljspeech-high` and `es_MX-claude-high`). A visible mark states this throughout the video («Video made with AI (SI) assistance · synthetic voice») and the file metadata repeats it. The video combines three kinds of footage: 3D animation made for the video, whose code was written with AI assistance and which is drawn with three.js from NASA Blue Marble and Black Marble imagery and from the real terrain of four missions (Copernicus DEM GLO-30 and ESA WorldCover), labelled on screen «Cinematic» or «Animation over real terrain · simulated event»; real screen captures of the application; and a closing shot from the team's trailer. No image-generation model was used and no NASA logo appears.

The official form calls this field «Use of Super Intelligence (SI)»; see the confirmed rules below. Confirm this statement with every team member before submission.

## Team

- Christian Venegas Calderon
- Nikol Estefany Borja Ugarte
- Abel Andres Valle
- Mario Alaluna

Pending 13-Nov-2026: confirm spelling, roles, affiliations, contact details and any required consent fields directly with each member.

## Official rules confirmed on 15-Nov-2026

Read on 15-Nov-2026 in the [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) and the [Judging & Awards Guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/).

- **Form fields:** Project Name; High-Level Project Summary; Link to Project Demo; Link to Final Project; Detailed Project Description; Use of Super Intelligence (SI); NASA Data; Space Agency Partner Data and Other References.
- **Project Demo:** a 7-slide presentation (title and intro slides included) or a video of **30 seconds or less**. «Projects that exceed these limits will not be eligible for Global Judging.»
- **Language:** English on the project page and in any linked materials. A demo video may be spoken in another language only if it includes English subtitles; slide decks must be in English.
- **Links:** publicly accessible, with no login, permission or registration. The site does not host videos or slides.
- **Use of SI** (the 2026 name for AI tools): images and videos «must include a visible watermark to indicate SI generation»; audio, code and data must be acknowledged «in descriptive text and metadata»; generated content may not use NASA branding or design elements. The answer to the SI question is not shown to the judges, but the watermarks, text and metadata are.
- **NASA data:** at least one NASA data or resource is required for Global Award eligibility.
- **Persons under 18:** no images, video, audio or likeness in demos or final projects.
- **Deadline:** «Submit for Judging» before Sunday 15 November 2026, 11:59 p.m., local time of the Local Event.
- **Judging criteria:** Impact, Creativity, Validity, Relevance and Presentation.
- **Suggested structure of the 30-second video:** [0:00] who you are; [0:02] the challenge and why; [0:05] project title and tagline; [0:10] how it works, with NASA and partner data; [0:20–0:30] the future.

## Links and media

- Live project: `[PENDING — official public URL and guide requirements]`
- Source repository: `[PENDING — approved public repository URL]`
- Project Demo: `videos/terra2045_demo30_en.mp4`, English, 29.5 s; the problem, the need and the solution are told through the game's story, a question and the platform's data views (ADR-051). `[PENDING — upload it to a public host and paste the link]`. A Spanish version with English subtitles is in `videos/terra2045_demo30_es.mp4`. The trailer runs 1:39 and cannot be the Project Demo.
- Supporting documentation: `[PENDING — decide which repository paths the form accepts]`

## Final guide-dependent checklist

- [ ] Map these headings to the official form fields and character limits.
- [x] Confirm required language and media duration/slide count: English; 30 seconds or less, or seven slides (15-Nov-2026). The guide states no aspect ratio, file type or size limit.
- [x] Confirm whether public hosting is mandatory: yes, for the demo and the final project, with no login. The guide does not require a public code repository.
- [ ] Confirm accessibility requirements for captions, subtitles, alt text and colour.
- [ ] Confirm team eligibility, consent, location and contact declarations.
- [x] Confirm the required AI-use disclosure wording: the field is «Use of Super Intelligence (SI)»; rules listed above (15-Nov-2026).
- [ ] Reproduce every numeric claim from the release candidate and retain its cited ADR.
- [ ] Run the common quality gate and final browser QA before replacing any `[PENDING]` marker.
