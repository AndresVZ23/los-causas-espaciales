# Seven-slide submission draft

> Internal English draft prepared on 11-Nov-2026. The team requested seven slides as a working format. **Pending the official Project Submission Guide on 13-Nov-2026:** confirm allowed format, slide count, aspect ratio, file size, language, public-hosting rules, accessibility requirements and whether speaker notes are evaluated. Do not present this draft as compliant until that check is complete.

## Slide 1 — Los Causas Espaciales

**Earth intelligence for decisions that can be audited**

NASA Space Apps Challenge 2026 · *Be An Earth System Trend Detective!*

Team: Christian Venegas Calderon, Nikol Estefany Borja Ugarte, Abel Andres Valle and Mario Alaluna.

Visual: product console with Moquegua selected; no decorative mock data.

Evidence note: product positioning and team text come from `PITCH.md` and `PROJECT_OVERVIEW.md`; confirm every name before submission.

## Slide 2 — The missing step before investment

Infrastructure teams must combine climate records, terrain, hazards, environmental restrictions and commercial assumptions. Today those pieces are fragmented, their uncertainty is hard to trace, and a missing layer is easily mistaken for “no risk.”

Los Causas Espaciales is the screening step before due diligence: it shows what changed, where it changed, how strong the evidence is, whether another source agrees, and which study should be funded next.

It does **not** replace engineering, environmental, archaeological, legal or financial feasibility work.

Evidence note: scope boundary is defined across ADR-004, ADR-015, ADR-026 and ADR-031.

## Slide 3 — One auditable pipeline

**Choose a site, territory or asset geometry → retrieve official Earth data → validate CRS, units and coverage → test trends → compare a second source → score alternatives → run explicit financial assumptions → export the evidence.**

- NASA POWER, GPM IMERG, NASADEM and MODIS provide the primary Earth-observation evidence.
- ERA5, CHIRPS, Copernicus DEM, ESA WorldCover, the Global Wind Atlas and GEOGLOWS act as independent checks.
- Mann–Kendall with Hamed–Rao, Theil–Sen and Benjamini–Hochberg separates signal from autocorrelation and multiple testing.
- The shared C2 contract carries provenance, data gaps, discoveries, assumptions and method validation into the interface and PDF.

Evidence note: statistical method [ADR-014, ADR-019]; shared contract [ADR-015]; second-witness design [ADR-036]; reproducible PDF [ADR-016]; method validation [ADR-045].

## Slide 4 — The detective moment: reject the convenient clue

Across Moquegua, **all 9 NASA POWER cells show significant warming, up to +0.42 °C per decade**. [ADR-025]

But the rainfall evidence contains a trap. For 2022, MERRA-2 reports **300 mm** for the extreme day; IMERG reports **12 mm** and CHIRPS **21 mm**. [ADR-036]

The platform keeps the original value for traceability, labels it a probable artefact, and prevents it from driving a hazard conclusion. Disagreement is a result, not a footnote.

Visual: cell-trend map beside the three-source extreme-rainfall comparison. Caption every source and year.

## Slide 5 — From evidence to an asset decision

**Wind screening in Marcona**

- NASA POWER estimates **6.39 m/s** at hub height; Global Wind Atlas estimates **9.74 m/s**, a **52%** gap. [ADR-041]
- The atlas-based screening model gives a **46.7%** net capacity factor; the MERRA-2 level would give **14.0%**. [ADR-041]
- COES reports **56.5%** for Tres Hermanas and **57.7%** for Marcona in 2024, supporting the atlas as the case-base level while keeping NASA POWER as the adverse resource case. [ADR-041, ADR-045]

The decision is conditional: on-site LiDAR or mast measurements and a manufacturer power curve remain mandatory before investment.

Visual: the two wind levels, model range and dated COES validation in one chart.

## Slide 6 — Trust is visible in the product

- Every result is labelled as observed, cached, model-derived, user-assumed, illustrative or unavailable. [ADR-004]
- A failed official layer never becomes zero. An exact last valid response may be shown for up to **90 days**, with its original date and current failure reason. [ADR-044]
- Wind and hydro publish dated real-production checks in `method_validation`; these are method-level evidence, not site-specific guarantees. [ADR-045]
- Global alerts use provider-issued GDACS levels and NASA EONET as a second witness; the platform does not declare urgency itself. [ADR-046]

Visual: provenance ledger, a declared gap, one discovery and the PDF method section.

## Slide 7 — One method, multiple infrastructure decisions

The same evidence contract now supports climate, renewable energy, natural hazards, environmental baseline, heritage, road-corridor screening and real-estate screening. The platform is global where the sources are global and explicitly Peru-specific where national layers are required. [ADR-015, ADR-032, ADR-034, ADR-041, ADR-042, ADR-046]

**Near-term work:** ground stations and river gauges; production data inside each user analysis; grid distance; communities and social conflicts; expanded national layers beyond Peru.

**Close:** *We do not hide disagreement. We turn it into the next question to investigate.*

Pending 13-Nov-2026: replace this closing area with the official call to action, project URL, repository URL, video/deck URL and any required credits or AI-use label.

## Editorial and verification checklist

- Re-run every displayed figure from the release candidate and update it only with a matching ADR/handoff entry.
- Use provider names and attribution exactly as recorded in `DATA_SOURCES.md`.
- Add alt text or speaker-note descriptions for every chart and screenshot.
- Never paste credentials, tokens, client data or a map without attribution.
- Confirm the official guide before exporting; this file deliberately contains no assumed upload, duration or hosting requirement.
