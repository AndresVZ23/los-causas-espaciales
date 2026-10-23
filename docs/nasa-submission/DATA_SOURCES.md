# Data Sources

| Source | Product | Access | Coverage / resolution | Status |
|---|---|---|---|---|
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) | Daily Point API | Public JSON API | 1981 to near-real-time; native resolution varies by variable | Integrated |
| [NASA EOSDIS GIBS](https://gibs.earthdata.nasa.gov/) | Blue Marble Shaded Relief/Bathymetry | Public WMTS | Global static visual basemap | Integrated for map context; not used as an analytic input |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001) | NASADEM HGT V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; elevation in metres relative to EGM96 | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_SC.001) | NASADEM SC V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; slope and aspect in hundredths of degrees | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | IMERG V07 | Earthdata/PPS; registration may be required | From 1998; products down to 0.1° and 30 minutes; POWER exposes precipitation as daily UTC and documents 3.5 months of latency for Final | Cataloged; designated countercheck for rainfall extremes |
| [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/) | Earth-observation product extraction | Earthdata Login | Product dependent | Cataloged |
| [Peru COD-AB](https://data.humdata.org/dataset/cod-ab-per) | IGN administrative boundaries v01 via OCHA/HDX | Public GeoJSON; CC BY-IGO | 25 departments, 196 provinces, 1,873 districts; CRS84 | Integrated as pinned, simplified web-reference assets |

NASA POWER limits a point request to 20 parameters and may return HTTP 429. The MVP requests four supported parameters in one multiparameter request per site and caches responses for 24 hours. NASADEM granules are discovered through NASA CMR; the system does not claim terrain metrics unless the protected HGT and SC archives were downloaded and parsed successfully. IMERG differentiates Early, Late, and Final products; the research workflow will prioritize Final after version, units, authentication, and access are verified.

## NASA POWER precipitation: temporal convention and QA finding

The connector explicitly sends `time-standard=UTC` to the NASA POWER Daily Point API. Therefore its operational day boundary is **00:00 UTC**: a dated value covers 00:00–23:59 UTC. In continental Peru (UTC−05:00), that corresponds approximately to 19:00 on the preceding local date through 18:59 on the labelled local date. POWER also supports Local Solar Time (`LST`) and uses LST by default when `time-standard` is omitted; UTC and LST daily bins must not be compared as though they shared the same cutoff.

An atypical provider value was reproduced for Moquegua (`-17.193, -70.934`) on 2026-10-22 using POWER Daily API v2.10.1. The UTC request returned **14.31 mm on 2022-09-12 and 300.21 mm on 2022-09-13: 314.52 mm over the two days**. The default/LST request redistributed essentially the same total as 259.63 mm and 54.88 mm (314.51 mm). The event remains in the analysis and is flagged as atypical; it is not silently removed and requires comparison with GPM IMERG Final and, when accessible, SENAMHI stations.

The original QA comparison appeared to show that the daily cutoff changed when requesting one variable instead of several. A controlled reproduction with identical coordinates, dates and `time-standard` did **not** reproduce a parameter-count effect: single-variable and multi-variable requests returned the same values in both UTC and LST. The reproducible cause of the different allocation is the requested time standard (UTC versus LST), not the number of variables. Request composition remains recorded as an API regression watch item because the earlier response differed, but it is not treated as a proven causal mechanism.

The same reproduction confirmed a separate POWER v2.10.1 scale defect for long requests that include recent dates: `PRECTOTCORR` can arrive multiplied by 24 while still declaring `mm/day` (343.44 and 7205.04 mm for those dates). `orchestration/extraction.py` checks a historical reference window and divides only when the median wet-day ratio is approximately 24; an unknown ratio stops the analysis. After that correction, the underlying 314.52 mm event remains unchanged.

GPM IMERG is the designated independent satellite countercheck for rainfall extremes. NASA POWER's official source documentation describes its IMERG precipitation as daily UTC and reports approximately **3.5 months of latency for the Final product**; this lag must be respected when matching dates. The lower-latency Late product is not interchangeable with Final and must carry its own provenance if used.

Verification sources (accessed 2026-10-22): [POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), [POWER temporal processing](https://power.larc.nasa.gov/docs/methodology/data/processing/), [POWER data sources and IMERG latency](https://power.larc.nasa.gov/docs/methodology/data/sources/), and [GPM IMERG](https://gpm.nasa.gov/data/imerg).

Other Peruvian sources remain `DATA_UNAVAILABLE` until service availability, licensing, resolution, coverage, and update metadata have been verified. No endpoint has been invented.

## Peru administrative territories (K5)

The selector uses **Peru - Subnational Administrative Boundaries (COD-AB) v01**, sourced from Peru's Instituto Geográfico Nacional (IGN), contributed through OCHA ROLAC, quality-assured by OCHA Field Information Services and published by HDX under **CC BY-IGO**. HDX reports 25 admin-1 departments, 196 admin-2 provinces and 1,873 admin-3 districts. The boundaries were created on 24-Jul-2015, accepted for humanitarian use on 14-Jul-2020 and reviewed on 30-Oct-2025. Districts created after the 2015 source snapshot are absent; these are reference boundaries, not cadastral or legal demarcations.

The exact GeoJSON ZIP downloaded on 23-Oct-2026 is pinned by SHA-256 `2f0ec51b7a0899b407546aa644621e1c3255cba59fdda76fcde6975ca6baafb3`. The reproducible builder validates CRS84 (longitude/latitude), counts, unique P-codes/derived ubigeos and every source geometry. It simplifies in EPSG:3857 using a maximum tolerance by level (1,500 m / 750 m / 250 m), then adaptively reduces the tolerance per feature until geodesic area change is at most 1%. Output returns to EPSG:4326.

| Level | Count | Vertex reduction | Maximum geodesic area change | Web GeoJSON size |
|---|---:|---:|---:|---:|
| Department | 25 | 98.587% | 0.8461% | 182,217 bytes |
| Province | 196 | 97.214% | 0.9502% | 849,234 bytes |
| District | 1,873 | 92.655% | 0.9969% | 5,451,565 bytes |

Each generated asset and the search index has its own SHA-256 in `backend/data/territory/manifest.json`. The API exposes accent-insensitive name search, exact/partial ubigeo search, department → province → district hierarchy, and one simplified GeoJSON feature per territory. Simplification is for web visualization and subject selection; later analytical sampling must explicitly state whether it uses these display geometries or a higher-fidelity official source.

## NASA POWER regional spatial sampling (K1)

`POST /api/v1/spatial-sampling/power/daily` accepts a GeoJSON geometry or Feature. Features exported by the geometry panel may include `properties.kind`, `name`, and `origin`; those fields are preserved in the response. Line strings are buffered in a local azimuthal-equidistant CRS by the explicit `corridor_buffer_km`. Polygons and COD-AB territories larger than a nominal 0.5° cell use the official `/api/temporal/daily/regional` endpoint with exactly one POWER parameter per request. A polygon smaller than one nominal cell is explicitly returned as `POINT` mode at an interior representative point, rather than implying unsupported internal spatial variation.

Regional responses are deduplicated by returned cell center. Cell footprints are inferred halfway between the centers actually returned, intersected with the subject, and weighted by geodesic overlap area. The contract returns every cell series plus a daily weighted mean, weighted standard deviation, minimum, maximum and contributing-cell count. Missing cell-days are excluded and the available weights are renormalized for that date; no missing value becomes zero. The raw response is cached by request hash and retains `REAL_DATA`/`CACHED_DATA` provenance.

NASA's documentation describes regional output on a 0.5° × 0.5° grid and limits a regional request to one parameter. The live `T2M` response reflects the native MERRA-2 grid: **0.5° latitude × 0.625° longitude**. K1 therefore records the actual center spacing instead of hard-coding 0.5° in both axes.

Live checks on 23-Oct-2026, UTC daily data for 1–3 Jan 2026:

- Moquegua department (COD-AB): `REGIONAL`, 9 intersecting cells, 99.5833% inferred spatial coverage, spacing 0.5° × 0.625°, weighted T2M 13.0592 / 11.9289 / 13.5450 °C, with per-day dispersion and cell series retained.
- La Punta district, Callao (0.773019 km² simplified geometry): `POINT`, one representative point because the district is smaller than one nominal cell; T2M 19.18 / 19.02 / 19.03 °C.

These checks validate transport and aggregation, not local climate suitability. POWER remains a gridded product and does not replace station or site measurements.
