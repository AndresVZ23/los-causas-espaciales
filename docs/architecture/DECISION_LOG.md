# Registro de decisiones técnicas

## ADR-001 — Un motor compartido

Los siete módulos usan contratos, conectores, estadística, geoespacial y finanzas comunes. Motivo: evitar resultados incompatibles entre sectores y conservar trazabilidad.

## ADR-002 — Priorizar el piloto solar

Se implementa primero la comparación Moquegua–Arequipa porque NASA POWER ofrece acceso público verificable a irradiancia y variables meteorológicas. Carreteras y real estate requieren capas territoriales oficiales adicionales antes de producir evaluaciones útiles.

## ADR-003 — No crear scores sin evidencia

La comparación inicial muestra valores, tendencias, cobertura y posición relativa. Un score multicriterio aparecerá solo cuando cada criterio tenga fuente, normalización, ponderación, cobertura y sensibilidad documentadas.

## ADR-004 — Separar observación, modelo y supuesto

- NASA POWER: `REAL_DATA` o `CACHED_DATA`.
- Tendencias y energía calculada: `MODEL_ESTIMATE` con método identificado.
- CAPEX, precio, performance ratio y descuento: `USER_ASSUMPTION`.
- Capas aún no conectadas: `DATA_UNAVAILABLE`.

## ADR-005 — Estadística anual transparente

Se calculan medias anuales, Mann-Kendall, pendiente de Sen, intervalo, autocorrelación lag-1 y corrección Benjamini-Hochberg en comparaciones. No se infiere causalidad ni probabilidad de desastre.

## ADR-006 — Puerto y aislamiento local

La plataforma usa `localhost:3100` para no interferir con MyFix en `localhost:3000`. Docker Compose utiliza el proyecto `los-causas-espaciales` y servicios independientes.

## ADR-007 — Las redes neuronales requieren evidencia previa

El DOP neuronal es una arquitectura futura, no una funcionalidad operativa. Ningún modelo se entrena hasta contar con objetivo decisional, etiquetas confiables, dataset versionado, partición temporal/espacial sin fuga y un baseline simple reproducible. Una red sólo se adopta si mejora fuera de muestra, reporta incertidumbre y explicabilidad, y supera una puerta de revisión humana. Si no mejora al baseline, se conserva el método más simple.
