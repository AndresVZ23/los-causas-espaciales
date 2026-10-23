# Data Sources

| Source | Product | Access | Coverage / resolution | Status |
|---|---|---|---|---|
| [NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) | Daily Point API | Public JSON API | 1981 to near-real-time; native resolution varies by variable | Integrated |
| [NASA EOSDIS GIBS](https://gibs.earthdata.nasa.gov/) | Blue Marble Shaded Relief/Bathymetry | Public WMTS | Global static visual basemap | Integrated for map context; not used as an analytic input |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001) | NASADEM HGT V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; elevation in metres relative to EGM96 | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA LP DAAC](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_SC.001) | NASADEM SC V001 | Public CMR metadata; raster via Earthdata Login | Global land, approximately 30 m / 1 arc-second; slope and aspect in hundredths of degrees | Metadata and public preview integrated; raster values require `EARTHDATA_TOKEN` |
| [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | IMERG V07 | Earthdata/PPS; registration may be required | From 1998; products down to 0.1° and 30 minutes; POWER exposes precipitation as daily UTC and documents 3.5 months of latency for Final | Cataloged; designated countercheck for rainfall extremes |
| [NASA AppEEARS](https://appeears.earthdatacloud.nasa.gov/api/) | MOD13Q1.061 NDVI/EVI + QA; MOD44W.061 water mask + QA | Earthdata Login; asynchronous point/area tasks | 250 m; MOD13Q1 every 16 days, MOD44W yearly | Integrated; live task and checksummed downloads verified 23-Oct-2026 |
| [NASA LHASA](https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/LHASA_Hazard_Today/ImageServer) | LHASA 2.x near-real-time landslide hazard | Public NASA ArcGIS ImageServer | Global 60°S–60°N; EPSG:4326; 30 arcseconds (~1 km); updated twice daily | Current service route verified 23-Oct-2026; connector and value semantics pending |
| [Peru COD-AB](https://data.humdata.org/dataset/cod-ab-per) | IGN administrative boundaries v01 via OCHA/HDX | Public GeoJSON; CC BY-IGO | 25 departments, 196 provinces, 1,873 districts; CRS84 | Integrated as pinned, simplified web-reference assets |

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

## NASA LHASA route verification

The current operational route is NASA Earthdata GIS, not the previously tested NCCS address. The public ImageServers are `Landslides/LHASA_Hazard_Yesterday`, `LHASA_Hazard_Today`, and `LHASA_Hazard_Tomorrow`; the `Today` service is the canonical candidate for K1b. NASA declares WGS84 (`EPSG:4326`), 30 arcseconds (approximately 1 km), one raster band, coverage from 60°S to 60°N, and twice-daily updates. It exposes `Get Samples`, `Identify`, and `Export Image` operations. LHASA 2.x is a machine-learning situational-awareness product based on GPM rainfall, SMAP soil moisture and susceptibility factors; it is not a substitute for a local geotechnical study. The route is verified, but the connector stays pending until the numeric value semantics, nodata, timestamps, citation and point/area sampling are tested against the live service.

## COES generation labels (`in-coes`)

The connector uses the official [COES generation portal](https://www.coes.org.pe/Portal/portalinformacion/generacion) and its public `ExportarGeneracion` endpoint. It requests one closed month at a time with `indicador=1` (medidores), pauses between network requests, stores each original XLSX by SHA-256, and reads only the `PRODUCCIÓN DIARIA` sheet. The provider columns are `FECHA`, `EMPRESA`, `GRUPO/CENTRAL`, `TIPO GENERACIÓN`, and `TOTAL`. The portal labels production as **MWh**, so `TOTAL` is summed directly by exact central name and month; the connector does not integrate a 15-minute MW series.

Only rows whose exact normalized generation type is `SOLAR` are included. All provider plant names are retained, rather than replacing an absent requested plant with a similar facility. Missing plant-months are emitted with null generation and `PARTIAL` status. Raw files are not redistributed. The COES pages reviewed on 23-Oct-2026 did not publish specific data-reuse terms or an open license; the API therefore cites **COES-SINAC**, records that caveat, and awaits Christian's courtesy email.

Independent live verification of the September 2026 XLSX found 17 solar central names and 30 daily observations for each of the following priority facilities:

| Exact COES central | Sep-2026 MWh | Daily value on 01-Sep where checked |
|---|---:|---:|
| `CLEMESI` | 28,053.11 | 981.01 |
| `EXPANSIÓN INTIPAMPA` | 13,460.82 | — |
| `INTIPAMPA` | 9,650.78 | 333.28 |
| `MAJES` | 3,909.25 | — |
| `MOQUEGUA-SOLAR` | 3,717.63 | — |
| `PANAMERICANA-SOLAR` | 4,685.06 | — |
| `REPARTICION` | 3,871.90 | — |
| `RUBI` | 37,891.41 | — |

Coordinates and installed/effective capacity are requested from the official Osinergmin GISEM `MapaSEIN_Operacion` Solar layer (20), in WGS84. A capacity factor is calculated only when the normalized GISEM name is an exact, unique match and installed capacity is positive: `MWh / (MW × 24 × calendar days)`. The live GISEM query returned an ArcGIS 503 during QA on 23-Oct-2026; consequently the generation remains `REAL_DATA`, while unmatched capacity, coordinates and capacity factor are explicitly `DATA_UNAVAILABLE`. No fuzzy match or substitution is made. Curtailment, outages and maintenance still need a separate verified source before these labels can train the proposed calibrator.

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
