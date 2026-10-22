# Scientific Methodology

## MVP variables

NASA POWER Daily Point: 2 m air temperature (`T2M`), corrected precipitation (`PRECTOTCORR`), all-sky surface shortwave irradiance (`ALLSKY_SFC_SW_DWN`), and 10 m wind speed (`WS10M`). Effective units are read from each service response.

## Workflow

1. Validate coordinates and require a minimum three-year period.
2. Retrieve daily observations in UTC and exclude fill values (`<= -900`).
3. Calculate valid annual means.
4. Apply Kendall tau as the Mann-Kendall monotonic trend test.
5. Apply Theil-Sen for trend magnitude and a 95% confidence interval.
6. Report significance only when `p < 0.05`; otherwise display the required insufficient-evidence statement.

For multi-site comparison, p-values are adjusted with the Benjamini-Hochberg procedure to control the false discovery rate across compared locations. The API also reports lag-1 autocorrelation for annual values and adds a caution when its absolute value is at least 0.3. The trend test remains unmodified; the diagnostic does not silently change the underlying method.

## Answering the challenge questions

Every solar screening returns `nasa_questions`, built deterministically from the computed trends (`backend/app/orchestration/nasa_questions.py`); no language model is involved.

1. **What is changing?** Variables whose trend stays significant after Benjamini-Hochberg, out of all tests (variables × sites).
2. **Where is it changing?** Sites where each variable changes, with WGS84 coordinates, stated as POWER grid cells, not in-situ measurements.
3. **How much is it changing?** Sen slope per year with its 95% interval and the change over the period (slope × years). A percentage of the mean is reported only for ratio-scale variables; it is omitted for temperature in °C.
4. **Is the change statistically significant?** Raw and BH-adjusted counts, the test family and α. When lag-1 autocorrelation is ≥ 0.3 in a significant series, the answer is downgraded to "answered with caveats", because unmodified Mann-Kendall can overstate significance.
5. **What do these changes mean for investment decisions?** Explicit sector rules per variable and trend direction, plus the NPV range under user assumptions. Always "partial" while territorial layers remain unavailable.

With no significant trend, questions 1–4 return the insufficient-evidence statement instead of a magnitude. Each answer lists its evidence, provenance and the pipeline stages that support it. Real-data run (Moquegua and Arequipa, 2001–2024): 2 m air temperature rises at both sites (+0.035 °C/year in Moquegua, 95% CI +0.014 to +0.061; about +0.80 °C over the period) and 10 m wind decreases in Moquegua; no irradiance drift is detected. The temperature series have lag-1 autocorrelation of 0.48 and 0.42, so a corrected variant (for example Hamed–Rao) is the recommended next step.

## Geospatial methods

GeoJSON Point, LineString, and Polygon inputs are validated with Shapely. Length, perimeter, and area are measured on the WGS84 ellipsoid using PROJ/Geod. These outputs describe geometry only; they do not establish exposure, vulnerability, ownership, permitting status, or legal restrictions.

## Limitations

POWER contains gridded estimates and does not replace ground stations or field campaigns. The initial version diagnoses but does not correct serial correlation; this assumption must be assessed before decision-grade use. No causal inference is made. Benjamini-Hochberg correction is applied to multi-site comparisons, while broader raster-scale multiple testing remains pending.

## Reproducibility

Each analysis receives a SHA-256-derived identifier based on location, variable, and period. Results include source, unit, resolution, retrieval date, valid observation count, method, raw and adjusted p-values where applicable, slope, autocorrelation diagnostic, limitations, and provenance.
