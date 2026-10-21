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

## Geospatial methods

GeoJSON Point, LineString, and Polygon inputs are validated with Shapely. Length, perimeter, and area are measured on the WGS84 ellipsoid using PROJ/Geod. These outputs describe geometry only; they do not establish exposure, vulnerability, ownership, permitting status, or legal restrictions.

## Limitations

POWER contains gridded estimates and does not replace ground stations or field campaigns. The initial version diagnoses but does not correct serial correlation; this assumption must be assessed before decision-grade use. No causal inference is made. Benjamini-Hochberg correction is applied to multi-site comparisons, while broader raster-scale multiple testing remains pending.

## Reproducibility

Each analysis receives a SHA-256-derived identifier based on location, variable, and period. Results include source, unit, resolution, retrieval date, valid observation count, method, raw and adjusted p-values where applicable, slope, autocorrelation diagnostic, limitations, and provenance.
