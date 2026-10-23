# Data Sources

| Source | Product | Access | Coverage / resolution | Status |
|---|---|---|---|---|
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) | Daily Point API | Public JSON API | 1981 to near-real-time; native resolution varies by variable | Integrated |
| [NASA EOSDIS GIBS](https://gibs.earthdata.nasa.gov/) | Blue Marble Shaded Relief/Bathymetry | Public WMTS | Global static visual basemap | Integrated for map context; not used as an analytic input |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001) | NASADEM HGT V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; elevation in metres relative to EGM96 | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_SC.001) | NASADEM SC V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; slope and aspect in hundredths of degrees | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | IMERG V07 | Earthdata/PPS; registration may be required | From 1998; products down to 0.1° and 30 minutes; POWER exposes precipitation as daily UTC and documents 3.5 months of latency for Final | Cataloged; designated countercheck for rainfall extremes |
| [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/api/) | MOD13Q1.061 NDVI/EVI + QA; MOD44W.061 water mask + QA | Earthdata Login; asynchronous point/area tasks | 250 m; MOD13Q1 every 16 days, MOD44W yearly | Integrated; live task and checksummed downloads verified 23-Oct-2026 |

NASA POWER limits a point request to 20 parameters and may return HTTP 429. The MVP requests four supported parameters in one multiparameter request per site and caches responses for 24 hours. NASADEM granules are discovered through NASA CMR; the system does not claim terrain metrics unless the protected HGT and SC archives were downloaded and parsed successfully. IMERG differentiates Early, Late, and Final products; the research workflow will prioritize Final after version, units, authentication, and access are verified.

## NASA POWER precipitation: temporal convention and QA finding

The connector explicitly sends `time-standard=UTC` to the NASA POWER Daily Point API. Therefore its operational day boundary is **00:00 UTC**: a dated value covers 00:00–23:59 UTC. In continental Peru (UTC−05:00), that corresponds approximately to 19:00 on the preceding local date through 18:59 on the labelled local date. POWER also supports Local Solar Time (`LST`) and uses LST by default when `time-standard` is omitted; UTC and LST daily bins must not be compared as though they shared the same cutoff.

An atypical provider value was reproduced for Moquegua (`-17.193, -70.934`) on 2026-10-22 using POWER Daily API v2.10.1. The UTC request returned **14.31 mm on 2022-09-12 and 300.21 mm on 2022-09-13: 314.52 mm over the two days**. The default/LST request redistributed essentially the same total as 259.63 mm and 54.88 mm (314.51 mm). The event remains in the analysis and is flagged as atypical; it is not silently removed and requires comparison with GPM IMERG Final and, when accessible, SENAMHI stations.

The original QA comparison appeared to show that the daily cutoff changed when requesting one variable instead of several. A controlled reproduction with identical coordinates, dates and `time-standard` did **not** reproduce a parameter-count effect: single-variable and multi-variable requests returned the same values in both UTC and LST. The reproducible cause of the different allocation is the requested time standard (UTC versus LST), not the number of variables. Request composition remains recorded as an API regression watch item because the earlier response differed, but it is not treated as a proven causal mechanism.

The same reproduction confirmed a separate POWER v2.10.1 scale defect for long requests that include recent dates: `PRECTOTCORR` can arrive multiplied by 24 while still declaring `mm/day` (343.44 and 7205.04 mm for those dates). `orchestration/extraction.py` checks a historical reference window and divides only when the median wet-day ratio is approximately 24; an unknown ratio stops the analysis. After that correction, the underlying 314.52 mm event remains unchanged.

GPM IMERG is the designated independent satellite countercheck for rainfall extremes. NASA POWER's official source documentation describes its IMERG precipitation as daily UTC and reports approximately **3.5 months of latency for the Final product**; this lag must be respected when matching dates. The lower-latency Late product is not interchangeable with Final and must carry its own provenance if used.

Verification sources (accessed 2026-10-22): [POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), [POWER temporal processing](https://power.larc.nasa.gov/docs/methodology/data/processing/), [POWER data sources and IMERG latency](https://power.larc.nasa.gov/docs/methodology/data/sources/), and [GPM IMERG](https://gpm.nasa.gov/data/imerg).

## AppEEARS: authenticated task contract

AppEEARS is integrated through its official HTTPS API. `POST /api/login` uses Earthdata Basic Auth, and the returned Bearer token remains only in process memory. The connector proactively renews an expiring token, retries once after HTTP 403 as required by NASA, and invokes `POST /api/logout` in a `finally` block after every submission, status, bundle or download operation. Tokens, passwords and `user_id` are removed before any provider response reaches the content-addressed cache. Downloads follow only HTTPS redirects to NASA domains or the exact CloudFront distribution observed from the official bundle API; the Bearer token is never forwarded to object storage.

Selected products and layers, verified against the live catalog on 22-Oct-2026:

| Product | Layers used | Native cadence / resolution | Quality handling |
|---|---|---|---|
| [MOD13Q1.061](https://doi.org/10.5067/MODIS/MOD13Q1.061) | `_250m_16_days_NDVI`, `_250m_16_days_EVI` | 16 days / 250 m | `_250m_16_days_VI_Quality`; scale factor 0.0001; fill -3000; valid scaled range -0.2 to 1.0 |
| [MOD44W.061](https://doi.org/10.5067/MODIS/MOD44W.061) | `water_mask` | yearly / 250 m | `water_mask_QA`; fill 253; categorical values must not be treated as continuous measurements |

Live evidence: task `975994a2-f686-4742-9805-714ad035c0c8` was accepted as `pending`, progressed through `processing`, and reached `done`. Its official bundle contains seven files (`csv`, `json`, `txt`, and `xml`) and every file includes a 64-character SHA-256 checksum. On 23-Oct-2026 the connector downloaded and independently rehashed both result CSVs: MOD13Q1, 1,775 bytes, SHA-256 `e6bb8c294237347f5ae0ace8351dc5a01034b320192107f63d01138bbf6a2040`; MOD44W, 318 bytes, SHA-256 `c7466b67304c84f6e4bde6bb6e06e8b8788d4537854733e436f079e4d227b73b`. The MOD13Q1 output contains two observations, scaled NDVI/EVI values and decoded VI-quality fields; the first Moquegua observation is NDVI 0.0832, EVI 0.0575 and `MODLAND=good quality`. The MOD44W output contains the expected categorical water-mask and QA fields for the same point. These values demonstrate transport, schema and QA availability; they are not generalized into a land-cover or risk conclusion from one point.

## Official Peruvian territorial layers

All application requests use GeoJSON RFC 7946 in WGS84 longitude/latitude. ArcGIS receives `inSR=4326`, applies `esriSpatialRelIntersects`, and returns attributes without geometry. Raw responses are preserved by SHA-256 before normalization. A zero-feature response means only **no intersection returned by that service**; it never means “no risk”, “no protected area” or “no archaeological heritage”.

| Source | Dataset / service | Coverage, CRS, scale | Access and reuse status (reviewed 22-Oct-2026) | Connector status |
|---|---|---|---|---|
| [CENEPRED SIGRID](https://sigrid.cenepred.gob.pe/arcgis/rest/services/FEN/ER_NINO2027_BD/MapServer) | Layers 4 and 5: risk from flooding and mass movements under intense rains / El Niño | Peru; source EPSG:32718, requested as EPSG:4326; scale not declared | Public ArcGIS REST; metadata does not state a reuse license. Scenario references SENAMHI Technical Report 69-2026 | Active for point, corridor and polygon. It is a prospective district-level scenario, not parcel risk |
| [SERNANP](https://geoservicios.sernanp.gob.pe/arcgis/rest/services/servicios_ogc/peru_sernanp_0102/MapServer) | National definitive/transitional, regional and private protected areas (layers 0–3) | Peru; vector EPSG:4326; compilation scale not declared | Public REST/WMS/WFS with SERNANP attribution; `licenseInfo` is empty | Active for point, corridor and polygon; legal compatibility still requires SERNANP review |
| [Osinergmin GISEM](https://gisem.osinergmin.gob.pe/serverosih/rest/services/Electricidad/ELECTRICIDAD/MapServer) | Transmission in operation (15) and substations in operation (18) | Peru; vector EPSG:4326; scale not declared | Public ArcGIS REST; copyright credits MINEM, COES, Osinergmin and sector companies; no explicit reuse license in REST metadata | Active for point, corridor and polygon; intersection says nothing about available connection capacity |
| [Ministerio de Cultura SIGDA](https://sigda.cultura.gob.pe/sigda/rest/services) | Registered-reference (`v_4/registrado_v4`) and declared (`v_4/declarados_v4`) pre-Hispanic real estate | Peru; vector EPSG:4326; survey scale not declared | Public ArcGIS REST; attribution DSFL/Geomática; no explicit reuse license in REST metadata | Active for point, corridor and polygon. Absence is not proof of no heritage and does not replace a CIRA |
| [INGEMMET GEOCATMIN](https://geocatminapp.ingemmet.gob.pe/arcgis/rest/services) | Geological hazards to be selected from the official catalog | Peru | INGEMMET describes GEOCATMIN data as public and free to use, but both official hosts failed strict TLS certificate validation in the runtime | `DATA_UNAVAILABLE`; TLS verification is not disabled |
| [SENAMHI IDESEP](https://idesep.senamhi.gob.pe/portalidesep/idesep_componente_catalogo_geoservicios_wfs.jsp) | Official WFS catalog | Peru; product-dependent | WFS 2.0 capabilities responded successfully; explicit reuse license not found in the catalog page | Catalog verified; `DATA_UNAVAILABLE` in the territorial endpoint until a specific hazard layer is selected |

The active Peru services have live response evidence for Moquegua (`-17.193, -70.934`). CENEPRED returned one district feature in each scenario; SERNANP, Osinergmin and both Cultura layers returned zero features at that exact point. On 23-Oct-2026 the same connector was exercised with a Moquegua–Ilo corridor and a small Moquegua polygon: CENEPRED flood risk returned 5 and 3 features respectively, while Osinergmin returned 16 and 3; SERNANP and registered SIGDA returned zero for both geometries. Every source returned `READY` and `REAL_DATA`. All zeros are retained as neutral query results, not as claims of absence. ANA, SENACE, Defensoría and community layers remain pending and are not represented by substitutes.

## COES generation labels (`in-coes`)

The source is the official [COES Medidores de Generación](https://www.coes.org.pe/Portal/mediciones/medidoresgeneracion) page. Its public interface explicitly offers CSV and Excel export and constrains each export to at most one month. The public [Web API help](https://appserver.coes.org.pe/waMediciones/Help) documents 96 quarter-hour measurements per day. Before downloading, the COES policies and footer were reviewed: COES publishes general, occupational, personal-data and WhatsApp policies, but no specific data-reuse license or website terms were found. Therefore the connector:

- uses the portal's own monthly CSV export, with at most three concurrent requests;
- attributes COES and preserves each original CSV by SHA-256;
- does not redistribute the original export and records the licensing caveat;
- requests only `SOLAR` and `Potencia Activa (MW)`;
- calculates monthly energy as `sum(MW × 0.25 h)` without clipping negative readings;
- marks a requested plant `DATA_UNAVAILABLE` if its exact official column is absent, rather than substituting another plant.

All six requested plants were present in the September 2026 export under these exact provider columns:

| Requested label | Exact COES column(s) | Sep-2026 MWh | Completeness |
|---|---|---:|---:|
| Rubí | `ORYGEN PERU S.A.A. -RUBI_CIRCUITO_1-5` + `ORYGEN PERU S.A.A. -RUBI_CIRCUITO_6-10` | 37,891.383250 | 100% |
| Intipampa | `ENGIE ENERGIA PERU S.A.A. -INTIPAMPA_SOLAR` | 9,650.763435 | 100% |
| Moquegua FV | `MOQUEGUA FV S.A.C. -MOQUEGUA_SOLAR` | 3,717.629000 | 100% |
| Majes | `MAJES ARCUS S.A.C. -GTSMAJES` | 3,909.259913 | 100% |
| Repartición | `REPARTICIÓN ARCUS S.A.C. -GTSREPAR` | 3,871.879248 | 100% |
| Panamericana | `PANAMERICANA  SOLAR SAC. -PANAM_SOLAR` | 4,685.059750 | 100% |

Downloaded at `2026-10-23T03:12:18Z` (`2026-10-22` in Peru). These are `REAL_DATA` labels from the provider, not model estimates. Installed capacity, curtailment and outage flags are still needed before converting generation into a neural-network target such as capacity factor.
