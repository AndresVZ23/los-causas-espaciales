# Scientific Methodology

Status on 10 November 2026. Each rule below is recorded, with the real case that motivated it, in `docs/architecture/DECISION_LOG.md` (ADR numbers in brackets). Sources, versions and licences are in [DATA_SOURCES.md](DATA_SOURCES.md).

## Principles

1. **A second independent source for every data item.** What appears when the two are crossed is published as a «descubrimiento»: a confirmation, a contradiction, a change only one source sees, or a probable artefact [ADR-036].
2. **Not significant is not the same as no change.** Without statistical evidence the platform returns an insufficient-evidence statement instead of a magnitude.
3. **A missing value is never a zero.** A source that does not answer is `DATA_UNAVAILABLE`; zero intersections with a layer do not mean zero risk.
4. **Observation, model and assumption stay apart.** Every figure carries one of six provenance classes.

## Data and roles

| Role | First source | Second source |
|---|---|---|
| Temperature, precipitation, wind at 10 m | NASA POWER Daily (MERRA-2), 0.5° × 0.625°, 2001 to today | ERA5 through JRC PVGIS 5.3, 2005–2023 |
| Solar irradiance | NASA POWER Daily (CERES SYN1deg) | ERA5 through JRC PVGIS 5.3 |
| Rainfall extremes | NASA POWER Daily (MERRA-2) | GPM IMERG and CHIRPS v2.0 (NASA SERVIR ClimateSERV) |
| Elevation and slope | NASADEM, 1 arc-second | Copernicus DEM GLO-30 |
| Vegetation cover | MODIS MOD44B (250 m) and MCD12Q1 (500 m) | ESA WorldCover 2021 (10 m) |
| Landslides | CENEPRED susceptibility (Peru) | NASA Global Landslide Susceptibility, LHASA 2 and COOLR reports |
| Wind at hub height | NASA POWER Hourly (WS50M, WS10M) | Global Wind Atlas 4.0 (250 m) |
| River flow | GloFAS v4 daily discharge (Copernicus EMS), 0.05°, from 1997 | GEOGLOWS v2 annual means |
| Head of a hydro site | NASADEM | Copernicus DEM GLO-30 |
| Energy models | — | Real 2024 production reported by the grid operator COES (validation only) |

Official Peruvian layers (CENEPRED, ANA, SERNANP, MINAM, Ministry of Culture and INGEMMET's volcanic hazard maps) are read by intersection or by point sampling. They describe restrictions and declared risk; they are not time series.

## Trend detection

1. Validate coordinates, geometries and dates. Daily observations are requested in UTC up to today; fill values (`<= -900`) are excluded.
2. Trends use complete years only: a year enters with at least 90 % of valid days. The year in progress is reported apart, as an anomaly and a rank against the same calendar window of the complete years [ADR-017].
3. Mann–Kendall with the Hamed and Rao (1998) variance correction decides significance. The series is detrended with the Sen slope and ranked; only lags whose rank autocorrelation lies outside ±z(1−α/2)/√n change Var(S) [ADR-014].
4. The correction can only widen the variance. The factor n/n* has a floor of 1, so the corrected test is never more permissive than the classical one; when the floor applies it is stated [ADR-019].
5. Theil–Sen gives the magnitude with a 95 % confidence interval.
6. Benjamini–Hochberg controls the false discovery rate across the subjects compared (sites, territory cells, road segments or areas), per variable. A trend is reported as significant only when the adjusted p-value is below 0.05; below 0.01 it is called strong evidence [ADR-018].

Each trend reports the classical p-value, the corrected p-value, the adjusted p-value, the variance factor, the raw lag-1 autocorrelation and the lag-1 autocorrelation of the detrended ranks. Raw autocorrelation alone is not used as a caution, because a monotonic trend induces it by itself.

The implementation is checked against frozen reference values from `pymannkendall` 1.4.3, an independent implementation: a detrended-autocorrelated series (factor 1.508421, p = 0.0030427), a series with ties, and an alternating series where `pymannkendall` returns NaN and this engine keeps the classical variance.

**Territories.** A department, province or district is analysed as the area-weighted mean of the NASA POWER cells that cover it, and each cell is also tested on its own, with Benjamini–Hochberg across cells [ADR-025].

## Rainfall extremes

Six ETCCDI indices are computed from daily precipitation: RX1DAY, RX5DAY, R95P, PRCPTOT, R10MM and CDD. Declared adaptations: the 95th percentile is taken over the analysed period, and spells and windows stay within the calendar year [ADR-018].

Years with a robust z above 10 (median and MAD × 1.4826) are marked as atypical. They are not removed: Mann–Kendall works on ranks and does not move with their magnitude, but the annual mean does [ADR-019].

## Guard against a provider defect

On 22 October 2026 the NASA POWER daily API returned the whole `PRECTOTCORR` series multiplied by 24 when the requested range reached the most recent days, while still declaring mm/day. Each recent response is compared with a reference window that ends 60 days earlier: a ratio near 1 is kept, a ratio near 24 is corrected and recorded in the source's quality notes, and any other ratio stops the analysis [ADR-017]. The regional sampler applies the same check cell by cell.

## Cross-check rules

Thresholds are declared constants in `backend/app/orchestration/discoveries.py`. They are screening judgements, stated so that they can be challenged.

| What is crossed | They agree when | They differ when | Real case |
|---|---|---|---|
| Rainfall-extreme trend, MERRA-2 against IMERG and CHIRPS | Both are significant in the same direction | Both are significant in opposite directions; «sin respaldo» if only one sees it | Arequipa: the RX5DAY trend is not repeated by IMERG and is repeated by CHIRPS [ADR-021, ADR-036] |
| A rainfall value | — | Probable artefact: the reanalysis exceeds each satellite product at least five times in the same year | Moquegua 2022: 300 mm against 12 and 17 mm [ADR-036] |
| Trend of temperature, irradiance or wind against ERA5 | Significant in both, same direction, on the common years 2005–2023 | Opposite sign, or the trend does not hold on the common years | Moquegua: +0.039 and +0.042 °C per year [ADR-038] |
| Solar resource level against ERA5 | Under 5 % | From 10 % | Moquegua +1.6 %, Arequipa −4.0 % [ADR-038] |
| Temperature level against ERA5 | — | From 2 °C | Moquegua: 7.4 against 18.0 °C; the reanalysis cell mixes Andean altitudes [ADR-038] |
| Mean wind at 10 m against ERA5 | — | From 30 % | Moquegua: 3.88 against 1.76 m/s [ADR-038] |
| Elevation and slope, NASADEM against Copernicus | Under 50 m and under 5° | Otherwise; flagged apart when the slope crosses 15° | Road segment 5: 17.9° against 12.5° [ADR-039, ADR-043] |
| Cover groups, MODIS against WorldCover | Each group under 10 points | From 20 points | Ilo: 21.8 % against 18.7 % non-tree vegetation [ADR-040] |
| Landslide susceptibility, CENEPRED against NASA, at the same sampling points | At most one class of five apart in at least two thirds of the points | Otherwise | Lurigancho–Chosica: 7 of 9 points [ADR-037] |
| Reported landslides (COOLR) against both maps | Reports fall where a map marks high or very high: «confirmado» | Reports where no map marks high | Lurigancho–Chosica: 6 reports, 2009–2017 [ADR-037] |
| Wind at hub height, NASA POWER against the Global Wind Atlas | Under 10 % | From 20 % | Marcona: 6.39 against 9.74 m/s [ADR-041] |
| Mean river flow, GloFAS against GEOGLOWS | Under 25 % | From 50 %; not compared beyond a factor of ten, where they are not locating the same river | Upper Tambo: 64 % [ADR-042] |
| Head, NASADEM against Copernicus | Under 5 % | From 10 % | Upper Tambo: 146 against 169 m [ADR-042] |

Trends against a second source are always compared on the common years, with the first source's slope recalculated on those years.

## Energy models

All three are pure functions with tests calculated independently. They are screening models: equipment, grid connection and permits are declared gaps.

**Solar.** Annual energy = capacity (MW) × mean daily irradiance × 365 × performance ratio.

**Wind** [ADR-041].
- Each hour of the 50 m wind is taken to hub height with the power law. The exponent comes from the 10 m and 50 m means of the same hours, bounded to [0, 0.5].
- Air density follows the standard atmosphere at the site elevation and the mean 2 m temperature, applied as an equivalent wind speed (IEC 61400-12-1).
- A generic power curve is used: cut-in 3, rated 12 and cut-out 25 m/s, with a cubic ramp. It is an editable assumption.
- The base case scales each NASA POWER hour by the ratio of hub-height means (atlas ÷ NASA POWER). It keeps NASA's hourly shape, year-to-year variation and trend, and takes the level from the 250 m atlas. NASA's own level is the adverse end of the resource factor.

**Run-of-river hydro** [ADR-042].
- Flow: GloFAS daily discharge at the intake. The modelled channel does not always cross the cell of the point, so a declared rule looks at the 3 × 3 neighbourhood: the point's cell is used if it carries at least 20 % of the neighbourhood maximum; otherwise the nearest cell with at least 50 %; if none reaches 0.05 m³/s there is no modelled river and the request is rejected.
- Head: elevation of the intake minus elevation of the powerhouse.
- Ecological flow: a declared fraction of the mean flow (10 % by default) always stays in the river.
- Design flow: the available flow exceeded 30 % of the time, or the value the user declares.
- Each day the plant turbines the available flow up to the design flow; below the technical minimum (20 % of design) it stops. Power = ρ · g · Q · net head · efficiency. Installed capacity is a result, not an assumption.

## Validation against real production

Daily production for 2024 comes from the official COES workbooks; it is used to validate the models, not as an input.

| Case | Real capacity factor, 2024 | Model |
|---|---|---|
| Marcona wind farm (32.1 MW; Tres Hermanas, next to it, 56.5 %) | 57.7 % | 46.7 % net with the atlas level; 14.0 % with NASA POWER's level |
| Machupicchu hydro plant (192.45 MW, 1,252 GWh) | 74.1 % | 64.7 % with a 10 % ecological flow; 71.8 % with 5 %; 77.1 % with none |

- The wind model stays below the real plants, and the comparison shows which source to trust for the level: NASA POWER's cell alone would have discarded a site where wind farms run above 50 % of capacity.
- The real hydro figure falls inside the range opened by the ecological-flow assumption. Modelled power is 163 MW against 192 MW, because the head is read on the terrain between two map points, not at the turbine axis.
- Each model is validated against one real case. That supports the choice of the base-case source; it does not establish accuracy elsewhere.

Both validations are reproduced with `scripts/qa/coes_production.py` and `scripts/qa/validate_hydro.py`.

## Decision layer

**Multicriteria score** [ADR-022].
- A weighted sum of 0–100 scores. Each criterion is scaled against a declared reference scale, not against the minimum and maximum of the subjects compared.
- A criterion without data leaves the calculation for that subject; its weight is redistributed and the coverage is reported.
- Stability: 2,000 Dirichlet weight combinations centred on the chosen weights, with a fixed seed. The score reports how often each subject comes first.
- Practical tie: less than 5 points between first and second, or a leader that wins in less than 75 % of the combinations. The screen and the PDF then say the score does not separate the subjects.
- Where the slope is a criterion, the score is recalculated with the slope of the second elevation model and states whether the first place changes [ADR-043].

**Finance** [ADR-020].
- Net present value over the declared horizon and discount rate, with base, adverse and favourable scenarios.
- A tornado moves one factor at a time. Measured factors take their range from the observed years (10th and 90th percentiles of the annual values) or from the second source; the rest are editable user assumptions.
- Break-even points are solved by bisection; the price break-even was checked against its closed form.

## Answering the challenge questions

Every analysis returns `nasa_questions`, built deterministically from the computed trends (`backend/app/orchestration/nasa_questions.py`); no language model is involved.

1. **What is changing?** Variables whose trend stays significant after Benjamini–Hochberg, out of all tests.
2. **Where is it changing?** Subjects where each variable changes, with WGS84 coordinates, stated as grid cells, not in-situ measurements.
3. **How much is it changing?** Sen slope per year with its 95 % interval and the change over the period. A percentage of the mean is reported only for ratio-scale variables; it is omitted for temperature in °C.
4. **Is the change statistically significant?** Counts before and after Benjamini–Hochberg, the test family, α, and per series the classical, corrected and adjusted p-values, plus what the second source says.
5. **What do these changes mean for investment decisions?** Explicit sector rules per variable and trend direction, plus the NPV range under user assumptions. It stays «partial» while data gaps remain open.

With no significant trend, questions 1–4 return the insufficient-evidence statement instead of a magnitude. Each answer lists its evidence, provenance and the pipeline stages that support it.

## Geospatial methods

GeoJSON Point, LineString, Polygon and MultiPolygon inputs follow RFC 7946 (WGS84, longitude–latitude) and are validated with Shapely. Length, perimeter and area are measured on the WGS84 ellipsoid with PROJ/Geod. Buffers around sites and corridors are geodesic. Rasters are read at pixel centres; nodata is never read as a value.

## When an official layer stops answering

If an official Peruvian service fails and the cache holds an earlier response to the same query, no older than 90 days, the platform shows that copy as `CACHED_DATA` with its original date and the reason, and lists it as a gap. Without a copy the layer is `DATA_UNAVAILABLE`. This is the case of CENEPRED, whose service requires a token since 10 November 2026 [ADR-044].

## Limitations

- NASA POWER, ERA5, GloFAS and GEOGLOWS are gridded reanalyses or models. No ground station or river gauge is connected: rainfall is checked satellite against reanalysis, and river flow model against model, both forced by ERA5 precipitation.
- The two reanalyses share inputs; agreement between them is weaker evidence than agreement with a satellite product or a real plant.
- Terrain values come from one representative point per subject.
- The cross-check thresholds are declared screening judgements, not statistical tests.
- Trends are tested on annual values; seasonality is not modelled. No causal inference is made.
- Wind and hydro are validated against one real case each.

## Reproducibility

Each analysis receives a SHA-256-derived identifier based on its inputs. Results include source, unit, resolution, download date, valid observation count, method, raw and adjusted p-values, slope, autocorrelation diagnostics, limitations and provenance. The executive PDF carries a SHA-256 fingerprint of the content it presents.
