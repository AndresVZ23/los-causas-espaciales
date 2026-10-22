# Data Sources

| Source | Product | Access | Coverage / resolution | Status |
|---|---|---|---|---|
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) | Daily Point API | Public JSON API | 1981 to near-real-time; native resolution varies by variable | Integrated |
| [NASA EOSDIS GIBS](https://gibs.earthdata.nasa.gov/) | Blue Marble Shaded Relief/Bathymetry | Public WMTS | Global static visual basemap | Integrated for map context; not used as an analytic input |
| [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | IMERG V07 | Earthdata/PPS; registration may be required | From 1998; products down to 0.1° and 30 minutes | Cataloged |
| [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/) | Earth-observation product extraction | Earthdata Login | Product dependent | Cataloged |

NASA POWER limits a point request to 20 parameters and may return HTTP 429. The MVP requests four supported parameters in one multiparameter request per site and caches responses for 24 hours. IMERG differentiates Early, Late, and Final products; the research workflow will prioritize Final after version, units, authentication, and access are verified.

Peruvian sources remain `DATA_UNAVAILABLE` until service availability, licensing, resolution, coverage, and update metadata have been verified. No endpoint has been invented.
