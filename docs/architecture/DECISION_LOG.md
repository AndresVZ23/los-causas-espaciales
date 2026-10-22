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

## ADR-017 — Datos hasta hoy, años completos en la tendencia y verificación de escala de NASA POWER

Por decisión de Christian (2026-10-22), la plataforma pide datos **hasta hoy** y se actualiza en cada consulta (la caché dura 24 h). Cada producto se publica con su propia latencia, medida ese día: temperatura, precipitación y viento hasta dos días antes; radiación CERES SYN1deg hasta fin de julio. Por eso se informa la **última fecha publicada por variable**, nunca un «hasta hoy» genérico. Las tendencias usan solo **años completos** (al menos 90 % de días válidos); el año en curso queda fuera, porque su media depende de las estaciones que cubre. Se informa aparte, comparado con la misma ventana del calendario en los años completos, con anomalía y puesto.

Al pedir hasta hoy apareció un **defecto de la API NASA POWER Daily v2.10.1**: si el rango incluye los días más recientes, toda la serie `PRECTOTCORR` de la respuesta llega multiplicada por 24, aunque declara mm/day. Reproducido el 2026-10-22: el 13-sep-2022 en Moquegua vale 300.21 al pedir hasta el 30-sep-2026 y 7205.04 al pedir hasta el 10-oct-2026. Temperatura, viento y radiación no se alteran. `orchestration/extraction.py` compara cada respuesta reciente con una ventana de referencia anterior a los últimos 60 días: si la razón es 1, la deja; si es 24, la corrige y lo registra en `SourceMetadata.quality_notes`; si es otra, se detiene con error. Sin esta verificación, el módulo climático habría reportado una lluvia máxima de 542 mm en un día en Moquegua.

## ADR-018 — Extremos de precipitación con índices ETCCDI

El módulo de inteligencia climática (`POST /api/v1/projects/climate-screening`, sector `climate` del contrato C2) agrega seis índices del ETCCDI sobre la precipitación diaria: RX1DAY, RX5DAY, R95P, PRCPTOT, R10MM y CDD. Cada índice pasa por la misma prueba de tendencia (Hamed–Rao + BH por índice entre sitios). Adaptaciones declaradas: percentil 95 sobre el período analizado, rachas y ventanas dentro del año calendario, y años con menos de 90 % de días excluidos. Las preguntas NASA distinguen evidencia fuerte (p BH < 0.01) de moderada.

## ADR-019 — Hamed–Rao solo ensancha la varianza y los años atípicos se marcan

Al revisar la pantalla del módulo climático con datos reales, la «lluvia máxima de 1 día» en Moquegua aparecía con evidencia fuerte (p BH 0.003), aunque el intervalo de Sen cruzaba el cero (−0.09 a +0.75 mm/año). La causa: la serie sin tendencia tenía autocorrelación negativa (−0.48) y el factor n/n* de Hamed y Rao (0.15) encogía la varianza; el p pasaba de 0.22 a 0.001. Desde ahora el factor tiene piso 1: la corrección puede volver la prueba más exigente, nunca más permisiva que la clásica, y cuando se aplica el piso se declara en las limitaciones. Sustituye la regla de ADR-014 para varianzas no positivas, que queda incluida. Con datos reales, 5 de 20 pruebas siguen siendo significativas, antes 7.

La autocorrelación negativa venía de un año atípico: NASA POWER (MERRA-2) trae 314.5 mm entre el 12 y el 13 de septiembre de 2022 en Moquegua. La suma coincide con cualquiera de los dos cortes de día; el reparto entre días cambia según se pidan una o varias variables, porque la hora de corte difiere. Es un valor del proveedor, no un error de la corrección × 24 (ADR-017), pero no es verosímil para el clima del lugar. Cada índice ETCCDI marca los años con z robusto mayor que 10 (mediana y MAD × 1.4826) en `atypical_years`. No se excluyen: Mann–Kendall usa rangos y no cambia por su magnitud, pero la media anual sí, y quedan señalados para contrastarlos con estaciones SENAMHI o GPM IMERG.

La pregunta «¿Cuánto está cambiando?» elegía el mayor cambio comparando magnitudes en unidades distintas; ahora da el cambio de cada variable significativa por sitio. El pie del PDF ya no menciona supuestos del usuario cuando el sector no los usa.