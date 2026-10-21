# Métodos y fuentes primarias

- SciPy `kendalltau`: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kendalltau.html
- SciPy `theilslopes`: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html
- statsmodels `multipletests`: https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html
- Mann (1945), prueba no paramétrica: https://doi.org/10.2307/1907187
- Sen (1968), estimador de pendiente: https://doi.org/10.1080/01621459.1968.10480934
- Benjamini y Hochberg (1995), FDR: https://doi.org/10.1111/j.2517-6161.1995.tb02031.x

SciPy `kendalltau` prueba asociación entre orden temporal y valores y maneja empates con tau-b. Registrar esta elección; no denominar automáticamente a cualquier correlación Kendall como una implementación estacional o modificada de Mann-Kendall.

