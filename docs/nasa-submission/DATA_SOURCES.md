# Data Sources

| Source | Product | Access | Coverage / resolution | Status |
|---|---|---|---|---|
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) | Daily Point API | Public JSON API | 1981 to near-real-time; native resolution varies by variable | Integrated |
| [NASA EOSDIS GIBS](https://gibs.earthdata.nasa.gov/) | Blue Marble Shaded Relief/Bathymetry | Public WMTS | Global static visual basemap | Integrated for map context; not used as an analytic input |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001) | NASADEM HGT V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; elevation in metres relative to EGM96 | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_SC.001) | NASADEM SC V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; slope and aspect in hundredths of degrees | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | IMERG V07 | Earthdata/PPS; registration may be required | From 1998; products down to 0.1° and 30 minutes; POWER exposes precipitation as daily UTC and documents 3.5 months of latency for Final | Cataloged; designated countercheck for rainfall extremes |
| [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/) | Earth-observation product extraction | Earthdata Login | Product dependent | Cataloged |

NASA POWER limits a point request to 20 parameters and may return HTTP 429. The MVP requests four supported parameters in one multiparameter request per site and caches responses for 24 hours. NASADEM granules are discovered through NASA CMR; the system does not claim terrain metrics unless the protected HGT and SC archives were downloaded and parsed successfully. IMERG differentiates Early, Late, and Final products; the research workflow will prioritize Final after version, units, authentication, and access are verified.

## NASA POWER precipitation: temporal convention and QA finding

The connector explicitly sends `time-standard=UTC` to the NASA POWER Daily Point API. Therefore its operational day boundary is **00:00 UTC**: a dated value covers 00:00–23:59 UTC. In continental Peru (UTC−05:00), that corresponds approximately to 19:00 on the preceding local date through 18:59 on the labelled local date. POWER also supports Local Solar Time (`LST`) and uses LST by default when `time-standard` is omitted; UTC and LST daily bins must not be compared as though they shared the same cutoff.

An atypical provider value was reproduced for Moquegua (`-17.193, -70.934`) on 2026-10-22 using POWER Daily API v2.10.1. The UTC request returned **14.31 mm on 2022-09-12 and 300.21 mm on 2022-09-13: 314.52 mm over the two days**. The default/LST request redistributed essentially the same total as 259.63 mm and 54.88 mm (314.51 mm). The event remains in the analysis and is flagged as atypical; it is not silently removed and requires comparison with GPM IMERG Final and, when accessible, SENAMHI stations.

The original QA comparison appeared to show that the daily cutoff changed when requesting one variable instead of several. A controlled reproduction with identical coordinates, dates and `time-standard` did **not** reproduce a parameter-count effect: single-variable and multi-variable requests returned the same values in both UTC and LST. The reproducible cause of the different allocation is the requested time standard (UTC versus LST), not the number of variables. Request composition remains recorded as an API regression watch item because the earlier response differed, but it is not treated as a proven causal mechanism.

The same reproduction confirmed a separate POWER v2.10.1 scale defect for long requests that include recent dates: `PRECTOTCORR` can arrive multiplied by 24 while still declaring `mm/day` (343.44 and 7205.04 mm for those dates). `orchestration/extraction.py` checks a historical reference window and divides only when the median wet-day ratio is approximately 24; an unknown ratio stops the analysis. After that correction, the underlying 314.52 mm event remains unchanged.

GPM IMERG is the designated independent satellite countercheck for rainfall extremes. NASA POWER's official source documentation describes its IMERG precipitation as daily UTC and reports approximately **3.5 months of latency for the Final product**; this lag must be respected when matching dates. The lower-latency Late product is not interchangeable with Final and must carry its own provenance if used.

Verification sources (accessed 2026-10-22): [POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), [POWER temporal processing](https://power.larc.nasa.gov/docs/methodology/data/processing/), [POWER data sources and IMERG latency](https://power.larc.nasa.gov/docs/methodology/data/sources/), and [GPM IMERG](https://gpm.nasa.gov/data/imerg).

Peruvian sources remain `DATA_UNAVAILABLE` until service availability, licensing, resolution, coverage, and update metadata have been verified. No endpoint has been invented.
