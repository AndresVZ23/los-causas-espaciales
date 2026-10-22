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

## ADR-008 — Workspace operativo antes que landing promocional

La primera pantalla prioriza el trabajo real: mapa, configuración, lectura de procedencia, pipeline y evidencia. El sistema visual usa capas tonales oscuras, reglas de 1 px, cian limitado a selección/acción y numerales monoespaciados. Se prohíbe mostrar indicadores de ejemplo como si fueran resultados.

## ADR-009 — Navegación móvil persistente y estado aislado

En pantallas de hasta 820 px, cuatro destinos principales y “Más” forman una barra inferior persistente. El listado completo se abre como drawer accesible con foco controlado, `inert`, `aria-hidden` y Escape. Cada módulo posee su propio estado de resultado; seleccionar un módulo pendiente limpia la evidencia solar previa para impedir interpretaciones cruzadas.

## ADR-010 — Lectura comparativa ordenada y supuestos junto al VAN

La lectura principal deja de mostrar una cifra aislada del primer sitio ingresado. Presenta todos los sitios ordenados por `relative_solar_position`, con irradiancia, cobertura, tendencia y VAN condicionado, la diferencia absoluta y porcentual entre extremos y la advertencia de que el orden no es una recomendación. Los supuestos mostrados son `result.assumptions`, es decir, los usados en el cálculo; si el usuario los edita después, la lectura declara que el VAN debe recalcularse. En móvil la lectura se ubica antes del mapa y recibe el desplazamiento al terminar la ejecución.

## ADR-011 — Unidades de presentación y dominio legible de series

Las unidades de NASA POWER se traducen solo en la capa de presentación (`kWh/m²/día`, `°C`, `mm/día`); la procedencia y el JSON exportado conservan los códigos originales. La serie anual usa un dominio vertical de al menos 1.6 veces el rango observado y 12 % del nivel medio, sin bajar de cero para magnitudes no negativas, y el pie del gráfico declara que el eje está ajustado. Así una variación de 6.4 a 6.9 es legible sin amplificar ruido.

## ADR-012 — El pipeline informa lo que ocurrió, no lo que debía ocurrir

Las nueve etapas se construyen en `orchestration/stages.py` a partir de hechos medidos: cobertura (extracción parcial bajo 95 %), series con menos de cinco años, capas territoriales disponibles y tiempos de servidor. Cada etapa lleva evidencia (etiqueta, valor y procedencia) y las preguntas NASA que sustenta. Exportación queda `LISTO` hasta la descarga. NASADEM pasa al mismo orquestador, en paralelo con POWER y con un límite de 45 s; si falla, la etapa territorial lo declara y el análisis solar continúa. `orchestration/nasa_questions.py` responde de forma determinista las cuatro preguntas del reto y la quinta del producto, y cae en evidencia insuficiente cuando corresponde.

## ADR-013 — Parseo de NASA POWER fuera del camino crítico del bucle

Con la caché caliente, el conector leía y validaba unas 35 000 observaciones por sitio de forma síncrona y bloqueaba el bucle de eventos unos 800 ms. La lectura del archivo pasa a `asyncio.to_thread`. El parseo sigue en el hilo principal, porque en hilos competía por el GIL y se volvía 5 veces más lento, pero usa `date()` y `Observation.model_construct`: los valores ya se validan con `float()` y el constructor de fecha. Medido en local: de 319 a 135 ms por sitio.

## ADR-014 — Mann–Kendall con corrección de Hamed y Rao como prueba de decisión

La significancia se decide con el p-value de Mann–Kendall con varianza corregida por autocorrelación (Hamed y Rao, 1998), calculado sobre los rangos de la serie sin tendencia de Sen. El ajuste Benjamini–Hochberg usa ese p-value. El p-value clásico se conserva para trazabilidad. La autocorrelación bruta deja de usarse como alerta, porque una tendencia monótona la produce por sí sola; la alerta relevante es la autocorrelación de los rangos sin tendencia, que es la que corrige el método. Si la varianza corregida no es positiva (autocorrelación negativa extrema), se conserva la clásica y se declara. Se contrastó con valores congelados de `pymannkendall` 1.4.3, sin agregarlo como dependencia. Con datos reales 2001–2024, el factor es 1.000 en las ocho series y la tendencia de temperatura se mantiene.

## ADR-015 — Un solo sobre de respuesta para todos los sectores

Solar, vial e inmobiliario responden con `ScreeningEnvelope` (contrato C2, v1.0): sujetos de estudio con GeoJSON, pipeline de nueve etapas, preguntas NASA, tendencias, relieve, brechas, supuestos y aviso. Los campos propios de cada sector se agregan por herencia y no en un `sector_payload` anidado, para conservar la compatibilidad de la respuesta solar con el frontend existente. La extracción, el análisis con Hamed–Rao + BH, los constructores de etapas y la verificación de conformidad (`envelope_violations`) viven en `backend/app/orchestration/` y los reutilizan todos los pilotos. La quinta pregunta NASA recibe un `SectorLens` definido por cada sector, en lugar de reglas solares fijas. La verificación de conformidad detectó un defecto real en su primera ejecución: la respuesta «¿Dónde?» sin tendencias omitía la frase obligatoria de evidencia insuficiente.

## ADR-016 — PDF ejecutivo generado en el backend desde el sobre común

El reporte ejecutivo se genera en FastAPI con ReportLab (BSD, Python puro, compatible con `python:3.12-slim`) en `POST /api/v1/reports/executive-pdf`, a partir de cualquier `ScreeningEnvelope`. Así sirve para todos los sectores y no depende del navegador. No recalcula nada: presenta preguntas NASA, tendencias con minigráfico de la serie anual y la recta de Sen, relieve, pipeline, supuestos, brechas, método, fuentes con DOI y una huella SHA-256 del contenido recibido. Usa Public Sans e IBM Plex Mono (OFL), incluidas con sus licencias en `backend/app/reports/fonts/`; los glifos que no tienen (`α`, `→`) se escriben en texto. Para graficar sin datos del sector, `TrendFinding` agrega `annual_series` (cambio aditivo al contrato). `pypdf` se usa solo en pruebas para leer el texto del PDF.
