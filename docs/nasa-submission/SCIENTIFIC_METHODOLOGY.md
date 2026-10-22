# Scientific Methodology

## MVP variables

NASA POWER Daily Point: 2 m air temperature (`T2M`), corrected precipitation (`PRECTOTCORR`), all-sky surface shortwave irradiance (`ALLSKY_SFC_SW_DWN`), and 10 m wind speed (`WS10M`). Effective units are read from each service response.

## Workflow

1. Validate coordinates and require a minimum three-year period.
2. Retrieve daily observations in UTC and exclude fill values (`<= -900`).
3. Calculate valid annual means.
4. Apply the Mann-Kendall monotonic trend test with the Hamed and Rao (1998) variance correction: the series is detrended with the Sen slope, ranked, and only lags whose rank autocorrelation lies outside ±z(1−α/2)/√n inflate (or deflate) Var(S). If the corrected variance is not positive, the classical variance is kept and the limitation is reported.
5. Apply Theil-Sen for trend magnitude and a 95% confidence interval.
6. Report significance only when the corrected `p < 0.05` after Benjamini-Hochberg; otherwise display the required insufficient-evidence statement.

For multi-site comparison, the corrected p-values are adjusted with the Benjamini-Hochberg procedure to control the false discovery rate across compared locations. Each trend reports the classical p-value (Kendall tau), the corrected p-value, the variance factor n/n*, the raw lag-1 autocorrelation and the lag-1 autocorrelation of the detrended ranks. Raw autocorrelation alone is not used as a caution, because a monotonic trend induces it by itself.

The implementation is checked against frozen reference values from `pymannkendall` 1.4.3 (independent implementation): a detrended-autocorrelated series (factor 1.508421, p = 0.0030427), a series with ties, and an alternating series where `pymannkendall` returns NaN and this engine falls back to the classical variance.

## Answering the challenge questions

Every solar screening returns `nasa_questions`, built deterministically from the computed trends (`backend/app/orchestration/nasa_questions.py`); no language model is involved.

1. **What is changing?** Variables whose trend stays significant after Benjamini-Hochberg, out of all tests (variables × sites).
2. **Where is it changing?** Sites where each variable changes, with WGS84 coordinates, stated as POWER grid cells, not in-situ measurements.
3. **How much is it changing?** Sen slope per year with its 95% interval and the change over the period (slope × years). A percentage of the mean is reported only for ratio-scale variables; it is omitted for temperature in °C.
4. **Is the change statistically significant?** Counts before and after BH, the test family, α, and per series the classical, corrected and BH p-values with the variance factor. The answer is "partial" only for series shorter than 10 years.
5. **What do these changes mean for investment decisions?** Explicit sector rules per variable and trend direction, plus the NPV range under user assumptions. Always "partial" while territorial layers remain unavailable.

With no significant trend, questions 1–4 return the insufficient-evidence statement instead of a magnitude. Each answer lists its evidence, provenance and the pipeline stages that support it. Real-data run (Moquegua and Arequipa, 2001–2024): 2 m air temperature rises at both sites (+0.035 °C/year in Moquegua, 95% CI +0.014 to +0.061; about +0.80 °C over the period) and 10 m wind decreases in Moquegua; no irradiance drift is detected. The temperature series show raw lag-1 autocorrelation of 0.48 and 0.42, but after detrending the rank autocorrelation is 0.06 and 0.10, so the Hamed-Rao factor is 1.000 and the trends hold (corrected p = 0.0016 and 0.0141; BH p = 0.0033 and 0.0141). A trend-free pre-whitening cross-check (Yue et al., 2002) agrees (p = 0.0026 and 0.0151). The Moquegua wind decrease is borderline (BH p = 0.048) and should not be presented as a strong finding.

## Geospatial methods

GeoJSON Point, LineString, and Polygon inputs are validated with Shapely. Length, perimeter, and area are measured on the WGS84 ellipsoid using PROJ/Geod. These outputs describe geometry only; they do not establish exposure, vulnerability, ownership, permitting status, or legal restrictions.

## Limitations

POWER contains gridded estimates and does not replace ground stations or field campaigns. Serial correlation is corrected with Hamed-Rao; seasonality is not modelled because the test runs on annual means (a seasonal Mann-Kendall would be needed for monthly series). No causal inference is made. Benjamini-Hochberg correction is applied to multi-site comparisons, while broader raster-scale multiple testing remains pending.

## Reproducibility

Each analysis receives a SHA-256-derived identifier based on location, variable, and period. Results include source, unit, resolution, retrieval date, valid observation count, method, raw and adjusted p-values where applicable, slope, autocorrelation diagnostic, limitations, and provenance.
