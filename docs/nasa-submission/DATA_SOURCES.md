# Data Sources

| Source | Product | Access | Coverage / resolution | Status |
|---|---|---|---|---|
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) | Daily Point API | Public JSON API | 1981 to near-real-time; native resolution varies by variable | Integrated |
| [NASA EOSDIS GIBS](https://gibs.earthdata.nasa.gov/) | Blue Marble Shaded Relief/Bathymetry | Public WMTS | Global static visual basemap | Integrated for map context; not used as an analytic input |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001) | NASADEM HGT V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; elevation in metres relative to EGM96 | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_SC.001) | NASADEM SC V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; slope and aspect in hundredths of degrees | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | IMERG V07 | Earthdata/PPS; registration may be required | From 1998; products down to 0.1° and 30 minutes | Cataloged |
| [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/) | Earth-observation product extraction | Earthdata Login | Product dependent | Cataloged |

NASA POWER limits a point request to 20 parameters and may return HTTP 429. The MVP requests four supported parameters in one multiparameter request per site and caches responses for 24 hours. NASADEM granules are discovered through NASA CMR; the system does not claim terrain metrics unless the protected HGT and SC archives were downloaded and parsed successfully. IMERG differentiates Early, Late, and Final products; the research workflow will prioritize Final after version, units, authentication, and access are verified.

Peruvian sources remain `DATA_UNAVAILABLE` until service availability, licensing, resolution, coverage, and update metadata have been verified. No endpoint has been invented.
