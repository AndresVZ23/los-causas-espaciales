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

La autocorrelación negativa venía de un año atípico: NASA POWER (MERRA-2) trae 314.5 mm entre el 12 y el 13 de septiembre de 2022 en Moquegua. La suma de los dos días es la misma con cualquier corte. El reparto entre días depende del estándar de tiempo. El conector pide `time-standard=UTC` (corte a las 00:00 UTC, las 19:00 del día anterior en Perú), y una consulta en hora solar local reparte la lluvia de otra forma. Codex verificó que pedir una o varias variables no cambia los valores; la primera lectura de Claude, que lo atribuía a eso, era errónea. Es un valor del proveedor, no un error de la corrección × 24 (ADR-017), pero no es verosímil para el clima del lugar. Cada índice ETCCDI marca los años con z robusto mayor que 10 (mediana y MAD × 1.4826) en `atypical_years`. No se excluyen: Mann–Kendall usa rangos y no cambia por su magnitud, pero la media anual sí, y quedan señalados para contrastarlos con estaciones SENAMHI o GPM IMERG.

La pregunta «¿Cuánto está cambiando?» elegía el mayor cambio comparando magnitudes en unidades distintas; ahora da el cambio de cada variable significativa por sitio. El pie del PDF ya no menciona supuestos del usuario cuando el sector no los usa.
## ADR-020 — Escenarios y sensibilidad del VAN en el sobre común

El sobre C2 agrega `financial_sensitivity` (aditivo; el contrato sigue en v1.0). Por cada sujeto incluye el VAN base, los escenarios base, adverso y favorable, el tornado y los puntos de equilibrio. El motor `backend/app/finance/sensitivity.py` es genérico: recibe la función de VAN del sector, así la fórmula vive en un solo lugar. El tornado mueve un factor a la vez y ordena por efecto. Los equilibrios se resuelven por bisección; el del precio se contrastó con la fórmula cerrada y el VAN con `verify_cashflow.py` de la skill de inversión. El verificador de conformidad exige escenario base y adverso, y un VAN base igual al de su escenario.

En el piloto solar, el rango del recurso no es un supuesto: sale de los percentiles 10 y 90 de las medias anuales observadas por NASA POWER (`MODEL_ESTIMATE`). Los rangos de precio, CAPEX, OPEX (±20 %), performance ratio (±0.05) y tasa (±2 puntos) son supuestos editables y quedan en `assumption_items`. Los escenarios combinados mueven recurso, precio, CAPEX y OPEX; el performance ratio y la tasa solo entran en el tornado. Con los supuestos por defecto, el recurso es el factor que menos mueve el VAN, y la irradiancia de equilibrio (7.7 kWh/m²/día) supera el mejor año observado. Para que el VAN sea positivo hace falta un precio cerca de 64 USD/MWh o un CAPEX cerca de USD 15 M, no más sol. Para K2 y K3: cada sector define sus `Driver` y su modelo, y el resto (tornado, escenarios, PDF y pantalla) se reutiliza.
## ADR-021 — GPM IMERG como contraste independiente de los extremos de lluvia

NASA POWER publica `IMERG_PRECTOT` (GPM IMERG, mm/día, UTC) en la misma API diaria; se verificó el 2026-10-23. El módulo climático lo pide junto con las demás variables y calcula los mismos seis índices ETCCDI con IMERG. La prueba de tendencia es la misma (Hamed–Rao + BH por índice entre sitios). Cada índice informa su `countercheck` con un acuerdo:
- **coincide:** ambas fuentes son significativas y van en la misma dirección.
- **contradice:** ambas son significativas, en direcciones opuestas.
- **sin respaldo:** solo MERRA-2 es significativa.
- **solo IMERG:** solo IMERG es significativa.
- **sin tendencia:** ninguna lo es.

Una tendencia de extremos se considera robusta solo si coincide. La pregunta de significancia lo dice y la de inversión agrega una salvedad cuando no hay respaldo. Si IMERG falla, el contraste se declara como brecha y el análisis sigue.

Resultado con datos reales (2001–2025):
- La única tendencia significativa de extremos, la lluvia máxima de 5 días en Arequipa (moderada), no se repite con IMERG (p BH 0.87): queda como indicio.
- IMERG no respalda los valores atípicos de MERRA-2 en Moquegua. El 12 y el 13 de septiembre de 2022 IMERG marca 0.0 mm frente a 314.5 mm del reanálisis, y el máximo diario de 2022 es de 12 mm en IMERG frente a 300 mm. IMERG sí registra lluvia en temporada húmeda (Arequipa, enero a marzo de 2023: 111.5 mm), así que el cero no es un relleno.
- El último dato válido de IMERG en POWER es del 2026-09-14.
- IMERG no mostró el defecto × 24, y ese día tampoco PRECTOTCORR al pedir hasta hoy; la guardia del ADR-017 se mantiene.
## ADR-022 — Puntaje multicriterio transparente, con estabilidad y empate práctico

El sobre C2 agrega `scorecard`, un campo aditivo. El motor `backend/app/scoring/multicriteria.py` es genérico: una suma ponderada de puntajes de 0 a 100.
- **Escalas:** cada criterio se normaliza con una escala de referencia declarada (peor valor = 0, mejor = 100, con recorte), no con mín–máx entre sujetos, que con dos sitios da siempre 0 y 100.
- **Datos faltantes:** el criterio sale del cálculo de ese sujeto, su peso se reparte entre los demás y se informa la cobertura.
- **Estabilidad:** 2 000 combinaciones de pesos Dirichlet centradas en los pesos elegidos (semilla fija); se informa en qué fracción queda primero cada sujeto.
- **Sensibilidad:** se lleva cada peso a la mitad y al 150 %, y se registra si cambia el primer lugar.
- **Empate práctico:** margen menor que 5 puntos o un líder que gana en menos del 75 % de las combinaciones. En ese caso la pantalla, el PDF y el pipeline dicen que el puntaje no separa los sitios.
- **Recálculo:** `POST /api/v1/scoring/scorecard` recalcula con otros pesos sin volver a consultar NASA, y la pantalla no duplica la fórmula.

Solar usa seis criterios: recurso, estabilidad interanual, deriva significativa, temperatura, pendiente NASADEM y VAN/CAPEX. Sus pesos por defecto son 30/10/10/10/15/25 y las escalas están declaradas en `SOLAR_CRITERIA`.

Con datos reales, Arequipa (67) y Moquegua (66) quedan en empate práctico: Arequipa es primera solo en el 59 % de las combinaciones, y el primer lugar cambia con el peso de la temperatura o de la pendiente. Es el resultado honesto, no un ganador fabricado.
## ADR-023 — Asistente en modo reglas, con Gemini solo a pedido y cifras verificadas

Decisión de Christian (2026-10-23): ningún gasto adicional. El asistente (C4, `POST /api/v1/assistant/ask`) responde **por defecto con reglas**: arma la respuesta con los textos y cifras del propio análisis, sin llamadas externas ni límite de uso. Cubre las 5 preguntas NASA, la tendencia y el año en curso por variable, los extremos de lluvia con su contraste IMERG, el puntaje, los escenarios del VAN, el relieve, las brechas y las fuentes, y filtra por el sitio que nombra la pregunta.

Gemini es **opcional y por pregunta**. El botón «Preguntar a Gemini» solo aparece si hay `GEMINI_API_KEY` y avisa que gasta la cuota gratuita. Se usa la API REST con `httpx`, sin SDK nuevo, y el alias estable `gemini-flash-latest` (verificado con ListModels, que no consume cuota). El contexto es solo el análisis, a temperatura 0.2, y la respuesta debe citar sus fuentes. El backend verifica que cada cifra de la respuesta salga del contexto, admitiendo redondeo, %, millones y por década. Si alguna no aparece, si Gemini falla o si se agota la cuota, se responde con reglas y se explica por qué. Las pruebas simulan Gemini sin red y afirman que una pregunta normal nunca lo llama.
## ADR-024 — Capas visuales NASA GIBS: fechas leídas de NASA y verificadas con una tesela

La consola ofrece ocho capas visuales de NASA GIBS (WMTS, EPSG:3857):
- color real del día;
- temperatura del mar y su anomalía (GHRSST MUR);
- viento sobre el mar (AMSR2);
- lluvia (IMERG);
- temperatura de la superficie (MODIS);
- vegetación (NDVI de 16 días);
- humedad del suelo (SMAP L4).

La lista curada vive en `backend/app/maplayers/catalog.py`. La fecha más reciente, el nivel máximo de zoom, el formato y la leyenda oficial se leen de las capacidades de GIBS y se guardan 6 h en caché, en `GET /api/v1/map/layers`.

La fecha `Default` de GIBS no siempre tiene teselas: AMSR2 declara el 01-09-2025, que da 404, mientras el 31-08-2025 sí existe. Por eso se pide una tesela z=2 sobre el Perú y se retrocede período a período hasta encontrar una publicada, y se avisa del ajuste. Una serie sin datos hace más de 30 días se marca como detenida. Si GIBS no responde, se sirve la lista sin fechas, con aviso.

Son capas **visuales**: la etiqueta y la leyenda dicen «no entra en el cálculo». Mientras hay una capa activa se quita el filtro de color del lienzo, para que los colores coincidan con la leyenda oficial.
## ADR-025 — Análisis por territorio: celdas descubiertas por el regional y pedidas como punto

El 2026-10-23 se verificó que el endpoint regional diario de NASA POWER rechaza períodos mayores de 366 días con un 422: «Please do not request a time period greater than 366 days». El conector K1 aceptaba 30 años y fallaba siempre con períodos de tendencia.

Para analizar un territorio, `backend/app/orchestration/territory.py` hace tres cosas:
1. Usa el regional **una sola vez, con el último año**, para descubrir qué celdas cubren el territorio y su peso por área de intersección (conector de Codex).
2. Pide cada celda **como punto**, que devuelve exactamente esa celda, con las 5 variables y todo el período en una consulta. Van en tandas de 4 para evitar 429 y cada celda pasa por la verificación de escala de precipitación del ADR-017.
3. Promedia con `aggregate_cells`, extraída sin cambios del conector de Codex para no duplicar la fórmula.

Moquegua con 9 celdas tarda unos 25 s la primera vez y luego queda en caché. Si un territorio supera 60 celdas, se pide uno menor. Un distrito menor que una celda se analiza como punto y se declara.

El módulo de Clima acepta de 1 a 4 sujetos entre sitios y territorios del IGN. Cada territorio informa nivel, ubigeo, área, celdas, cobertura y grilla. Las **tendencias por celda** (T2M y PRECTOTCORR) aplican Hamed–Rao y Benjamini–Hochberg entre las celdas y se dibujan como grilla con el par divergente validado; las celdas sin evidencia van atenuadas.

Con datos reales, la temperatura sube con significancia en las 9 celdas de Moquegua (hasta +0.42 °C por década) y la lluvia no muestra tendencia en ninguna. Los índices de extremos de un promedio areal son más suaves que los de un punto, y así se declara en el método.

## ADR-026 — El piloto vial prioriza estudios, no declara carreteras seguras ni factibles

K2 usa una geometría pública Moquegua–Ilo calculada con OSRM sobre OpenStreetMap y dividida en cinco tramos. Se conserva la atribución ODbL y se declara que la línea simplificada no es un eje oficial del MTC, inventario de activos ni diseño vial. Los corredores que entregue el usuario deben ser LineString WGS84 válido y tampoco adquieren validez legal por ingresar a la plataforma.

La exposición combina, sin confundir sus significados: series puntuales NASA POWER para tendencia, muestreo K1 ponderado por área para precipitación reciente, NASADEM para relieve y consultas de intersección a capas oficiales peruanas. Una capa ausente o un servicio fallido crea una brecha `DATA_UNAVAILABLE`; una consulta con cero intersecciones sigue siendo neutral y no equivale a riesgo cero. Los criterios sin dato se omiten y el score informa la cobertura del peso restante.

El resultado económico modela una mitigación genérica: `VAN = −CAPEX + Σ[((días base × (1 − fracción residual)) × costo/día) − mantenimiento] / (1+r)^t`. Días y costo de interrupción, CAPEX, mantenimiento, fracción residual, tasa y horizonte son `USER_ASSUMPTION`. NASA no observa cierres, tráfico ni pérdidas. El score mayor significa prioridad preliminar de estudio/mitigación, no mejor carretera; el VAN no constituye presupuesto, ingeniería, prefactibilidad ni decisión de inversión. El piloto reutiliza sensibilidad y puntaje comunes para que la interfaz y el PDF puedan leer el contrato sin lógica sectorial nueva.

## ADR-027 — Pantalla del piloto vial sobre K2 y corrección del encolado del mapa

El módulo Infraestructura usa el backend K2 de Codex (`POST /api/v1/projects/road-screening`):
- **Corredor:** el piloto Moquegua–Ilo (OpenStreetMap, ODbL) o los corredores del usuario, dibujados o cargados en el panel de geometrías.
- **Supuestos:** viales editables.
- **Mapa:** tramos alternados en cian y blanco, con el nombre al pasar el mouse.
- **Lectura:** por tramo.
- **Tablas:** tramos y capas territoriales, con «No disponible» cuando la capa no respondió; cero no se presenta como ausencia de riesgo.
- **Reutilizados:** puntaje, escenarios, preguntas NASA, asistente y PDF, que leen el sobre C2 sin código propio del sector.

El gráfico anual, las fechas de datos y la procedencia leen sitios o tramos a través de `seriesSubjects()`.

**Error corregido en el mapa:** `whenReady` usaba `isStyleLoaded()`, que da falso mientras se descargan teselas. Si el evento `load` ya había pasado, la actualización esperaba para siempre, y el corredor no aparecía tras la consulta. Ahora el mapa se marca como listo al terminar su propio `load`.

## ADR-028 — K2 puntúa lluvia extrema con P99 y conserva RX1DAY como evidencia

El máximo diario espacial de K2 no es robusto ante un valor aislado del producto. En el tramo 2, una ejecución reproducible de 2022 encontró RX1DAY MERRA-2 de 286.58 mm el 13-sep frente a P99 de 15.2508 mm/día; ADR-021 ya mostró que IMERG no confirma el evento extremo relacionado del 12–13 sep. Eliminar el dato habría ocultado una discrepancia científica, pero puntuarlo como si fuera una amenaza confirmada distorsionaba la prioridad.

K2 conserva `rx1day_mm` y su fecha para trazabilidad, calcula `p99_precipitation_mm_day` con interpolación lineal sobre la serie diaria espacial reciente y usa P99 en el criterio `recent_p99_precip`. Si `RX1DAY - P99 ≥ 50 mm` y RX1DAY es al menos tres veces P99, añade una limitación que exige contraste IMERG o estaciones. No se corrige ni reemplaza el dato original, y P99 tampoco se interpreta como lluvia de diseño, período de retorno o suficiencia hidráulica. La prueba controlada con 361 valores de 1 mm y los valores 2, 3, 4 y 151 mm verifica que el máximo queda en 151 y P99 en 1.36, mientras el score usa únicamente P99.

## ADR-029 — K3 separa evidencia territorial de supuestos inmobiliarios

K3 acepta Polygon/MultiPolygon WGS84 del usuario o un territorio IGN identificado por nivel y ubigeo. La geometría se valida sin reparaciones ocultas, el punto de consulta se obtiene con `representative_point()` para garantizar que quede dentro del polígono y el área financiera se calcula directamente sobre el elipsoide WGS84 sin usar el valor redondeado de presentación. Los 12 territorios MultiPolygon de la versión fijada se aceptan y sus anillos se convierten explícitamente al formato ArcGIS para las consultas de intersección. Los límites IGN mantienen licencia CC BY-IGO, fecha 2015 y la advertencia de que no son catastro ni acreditan propiedad o zonificación.

El VAN carga suelo y mitigación en t=0 y reconoce ingreso, costo de construcción y costo comercial a medida que la absorción anual supuesta vende área. Fracción desarrollable, edificabilidad, precio, costos, absorción, tasa y horizonte son siempre `USER_ASSUMPTION`; no se infieren de NASA, IGN ni de las intersecciones. El modelo omite impuestos, financiamiento, permisos, cronograma de obra, inflación y valor residual, y lo declara. El score combina P99, pendiente, alertas devueltas, VAN/inversión y fracción desarrollable. Si falta una fuente necesaria el criterio queda sin dato y baja la cobertura; cero intersecciones no equivale a cero riesgo. Un recálculo separado de área y flujo descontado debe coincidir a USD 0.01 antes de aceptar la entrega.

## ADR-030 — Pantalla del piloto inmobiliario sobre K3 (registrada originalmente como ADR-028)

El módulo Inversión usa el backend K3 de Codex (`POST /api/v1/projects/real-estate-screening`) con tres fuentes de terrenos:
- **Áreas de ejemplo del contrato:** 3 cuadrados de unos 330 m, rotulados como ilustrativos («no son lotes reales»).
- **Polígonos propios:** dibujados o cargados en el panel de geometrías.
- **Territorios IGN:** se eligen con el mismo selector de Clima.

Incluye supuestos editables (precio, costos, fracción urbanizable, coeficiente de edificación, absorción, tasa y horizonte), lectura por terreno, tabla de terrenos y la tabla de capas territoriales, que ahora comparten ambos pilotos. Puntaje, escenarios, preguntas NASA, asistente y PDF se reutilizan del sobre C2.

Dos salvaguardas de interpretación, encontradas en el QA:
- **Escala:** un distrito usado como terreno daba un VAN de USD 2 236 M (Samegua, 64 km²), porque el modelo urbaniza una fracción fija de toda el área. Sobre 200 ha la lectura advierte que el VAN no describe un proyecto.
- **Un solo sujeto:** el puntaje dice que no compara, en vez de «lidera por 0 puntos». Aplica también al piloto vial.

## ADR-031 — K3 separa áreas territoriales de VAN de proyecto

K3 conserva los territorios IGN como entradas útiles para exposición climática, relieve y alertas territoriales, pero una geometría mayor de 2 km² (200 ha) deja de interpretarse como escala de proyecto. El backend no elimina el VAN ilustrativo ni cambia el contrato ya consumido por la consola: añade una cautela inequívoca en el resultado del sujeto y en la quinta pregunta NASA. La cautela explica que la fracción desarrollable y los demás supuestos se aplican a toda la geometría y exige un polígono predial para evaluar un proyecto.

Para una sola geometría, el scorecard conserva los puntajes de criterios pero declara `margin=None` y `tie=False`; una nota explica que esos valores no implican liderazgo frente a una alternativa. Una prueba controlada con el distrito IGN de Samegua reproduce la escala superior a 200 ha, verifica ambas cautelas y exige conformidad C2 sin convertir la ausencia de comparación en empate.

## ADR-032 — Línea base ambiental y patrimonial (módulos 4 y 5) como insumo de EIA

**Qué cubre.** Los módulos 4 (Ambiente) y 5 (Territorio: patrimonio y dimensión social) dejan de estar pendientes. Comparten un motor (`backend/app/sectors/baseline*.py`) que ordena la evidencia como la línea base de un EIA peruano:

| Medio | Módulo | Fuentes |
|---|---|---|
| Físico | 4 | ANA (cuerpos de agua con categoría ECA, unidades hidrográficas) y relieve NASADEM |
| Biológico | 4 | MODIS anual vía ORNL DAAC, MINAM (ecosistemas, cobertura vegetal 2015, lomas costeras, Ramsar) y SERNANP |
| Sociocultural | 5 | Ministerio de Cultura: bienes registrados y declarados, CIRA, DAS, Qhapaq Ñan, paisajes culturales, Patrimonio Mundial, consulta previa y reportes ciudadanos |

Responden con el sobre C2, en dos sectores nuevos: `environment` y `heritage` (cambio aditivo). Así heredan las preguntas NASA, la tubería, el asistente y el PDF.

**Áreas de estudio.** Se aceptan de 1 a 4 entre:
- sitios, convertidos en círculos geodésicos de radio elegido;
- territorios IGN;
- polígonos o corredores del usuario, ampliados con el mismo radio.

**Vegetación MODIS.** El servicio del ORNL entrega 10 fechas por consulta y tarda de 4 a 30 s por consulta (medido el 24-oct). Por eso se usan solo productos anuales:
- MOD44B: árboles, vegetación no arbórea y suelo sin vegetación.
- MOD17A3HGF: producción primaria neta.
- MCD12Q1: cobertura IGBP.

Cada año se promedia sobre los píxeles cuyo centro cae dentro del área (proyección sinusoidal, verificada contra el punto pedido) y entra solo si al menos la mitad de esos píxeles es válida. La tendencia es la misma que en clima: Hamed–Rao, Sen y Benjamini–Hochberg por indicador entre áreas. La producción primaria neta del desierto es relleno MODIS y no genera serie, en lugar de dar un cero. La ventana tiene un tope de ±10 km y se declara qué fracción del área cubre.

**Patrimonio.** El módulo 5 no mide cambios en el tiempo. Declara las cuatro preguntas de tendencia como evidencia insuficiente y responde la quinta con los registros, en palabras de la fuente: nombre, resolución y enlace al PDF del DAS. Quedan como brechas visibles:
- la Base de Datos de Pueblos Indígenas (sin servicio geográfico);
- las comunidades de MIDAGRI (TLS inválido);
- los conflictos de la Defensoría (solo PDF);
- los instrumentos aprobados de SENACE (TLS inválido).

**Cortesía con SIGDA.** El servidor corta la conexión TLS a la IP tras unas 20 consultas seguidas, aun de dos en dos (verificado dos veces el 24-oct). La línea base consulta una capa a la vez por servidor, espera 0.5 s entre consultas reales y reintenta una vez. Lo que sale de caché no espera. Si la fuente sigue caída, la capa queda `DATA_UNAVAILABLE` con su motivo.

**Resultados reales del 24-oct:**
- **Moquegua, radio 1 km.** El suelo sin vegetación sube (+3.8 puntos en 2000–2025, p BH 0.014) y la vegetación no arbórea baja: señal compatible con expansión urbana.
- **Distrito de Ilo.** La vegetación no arbórea sube +4.6 puntos y el pastizal MCD12Q1 pasa de 0.1 % a 9.2 % (2001–2024), donde MINAM registra lomas costeras. Cultura registra 7 bienes referenciales, 4 declarados (Icuy 2 y 3, Tancona 1) y 4 ámbitos de consulta previa.
## ADR-033 — El PDF ejecutivo lleva la línea base por área

**Problema.** El endpoint del PDF validaba el cuerpo como `ScreeningEnvelope` y descartaba los campos del sector. En Ambiente y Patrimonio eso borraba lo principal: áreas, capas, registros y vegetación. El reporte además citaba NASA POWER como fuente, aunque esos módulos no lo consultan.

**Cambio.** `POST /api/v1/reports/executive-pdf` elige el esquema por `sector`: `environment` y `heritage` se validan con `BaselineScreeningResponse` y los demás siguen con el sobre común. `reports/baseline_pdf.py` agrega, después de los sujetos de estudio, una sección por área con:
- indicadores MODIS: media, Sen, cambio, p BH y evidencia;
- cobertura IGBP del primer y el último año;
- notas;
- capas por medio con hasta seis registros en palabras de la fuente.

Los enlaces del DAS van como hipervínculos, y solo se aceptan direcciones `https`. Una capa caída se imprime «No disponible» con su motivo, nunca como cero. Las fuentes del pie son las consultadas (ORNL DAAC y los organismos de las capas). En Patrimonio, el pie dice que el reporte no sustituye el CIRA ni una opinión legal.

**Verificación:**
- Pruebas: dos de PDF sobre resultados sintéticos (registros, enlace `/URI` al PDF del DAS, «No disponible», sin NASA POWER).
- PDF real con Moquegua (radio 1 km) y el distrito de Ilo: Patrimonio en 4 páginas, Ambiente en 6, las 18 consultas respondieron.
- QA desde el botón en 1440 y 390.
## ADR-034 — Módulo 3: amenazas naturales sobre el motor de la línea base

**Qué cubre.** El módulo 3 deja de estar pendiente. Usa el mismo motor que los módulos 4 y 5: mismas áreas de estudio y sobre C2 (sector nuevo `hazards`, cambio aditivo), con un medio «amenazas». Por cada área reúne:
- lluvia anual y los seis índices ETCCDI desde 2001, en el punto representativo (NASA POWER con la guarda ×24), con contraste GPM IMERG y años atípicos marcados;
- relieve NASADEM;
- capas oficiales:
  - CENEPRED, escenarios de riesgo por inundación y movimientos en masa por distrito, con sus niveles de riesgo, susceptibilidad o peligro y vulnerabilidad;
  - ANA, puntos críticos por inundación 2022 y declaratoria de peligro inminente D.U. 015-2023;
  - INGEMMET, que sigue `DATA_UNAVAILABLE` por TLS.

**Reutilización.** Extracción, índices, ajuste BH, contraste IMERG y lente de lectura salen del módulo Clima. `countercheck_summary` pasó a recibir pares (etiqueta, extremos), y la tabla de extremos de la interfaz quedó como componente compartido.

**Lo que no se hizo:**
- No se agregaron las capas de susceptibilidad de CENEPRED (servicio FEN, capas 1 y 2): son ráster y responden 400 a una consulta por área.
- Los conteos de viviendas, escuelas y establecimientos de salud de CENEPRED no se muestran sin su definición oficial; solo se muestran los niveles.
- LHASA (NASA), el inventario de emergencias de INDECI y las estaciones SENAMHI quedan como brechas visibles.

**Resultado real del 25-oct (Moquegua con radio 1 km y distrito de Ilo):**
- Ningún índice de extremos tiene tendencia significativa.
- IMERG no respalda 6 años atípicos de 2022 (por ejemplo, PRCPTOT de Ilo: 387.6 mm en MERRA-2 frente a 10.5 mm en IMERG).
- CENEPRED marca riesgo alto por inundación en Moquegua y El Algarrobal, y riesgo alto por movimientos en masa en Ilo.
- La ANA registra un punto crítico en el río Ilo (valle de Ilo) y Moquegua dentro de la declaratoria de 2023.

**Verificación:** 177/177 pruebas (dos nuevas: amenazas con datos sintéticos y caída de NASA POWER declarada como brecha). QA `baseline_ui` en 1440, 768 y 390 sin errores; `release_ui` sin recortes ni problemas de teclado; `climate_ui` intacto tras el refactor.

## ADR-035 — Capas ráster y servicios sin consulta: muestreo por `identify`

**Problema.** Dos fuentes de amenaza no admiten una consulta por área:
- la susceptibilidad de CENEPRED (servicio FEN, capas 1 y 2) es ráster y responde 400;
- los mapas volcánicos de INGEMMET responden HTML 500 a `query`, y además el servidor omite el certificado intermedio.

**Decisión.** `connectors/peru/identify_layers.py` muestrea el área por puntos con `identify` de ArcGIS:
- **CENEPRED:** el píxel 1–5 se traduce a Muy bajo…Muy alto con la leyenda del servicio, validada en Bajo Piura (inundación 5) y Chosica (movimientos en masa 4). Se cuenta cuántos puntos caen en cada nivel y se declara «muestreo por puntos», no superficie.
- **INGEMMET:** las capas son Misti, Ticsani, Ubinas, Sabancaya y Tutupaca. Se consulta por POST con coordenadas a 5 decimales y se revisa la extensión (EPSG:32719 → WGS84) antes de preguntar.
- **TLS:** se incluye solo el intermedio Sectigo OV R36, que se carga junto a certifi. La raíz R46 ya está en certifi. La validación nunca se desactiva.
- **Cortesía:** una consulta a la vez por servidor, 0.5 s de pausa y un reintento.

**Lo que no se hizo.** El inventario nacional de peligros geológicos (SERV_PERUALERTA) no está publicado en el servidor de INGEMMET (verificado el 26-oct-2026); queda como brecha con esa razón.

## ADR-036 — Tres fuentes de lluvia y «descubrimientos» al cruzar fuentes

**Motivo.** MERRA-2, IMERG y CHIRPS miden la lluvia de forma distinta:
- MERRA-2 es un reanálisis (modelo, celda de ~55 × 65 km) y puede inventar tormentas;
- IMERG combina microondas e infrarrojo (~11 km) y pierde la garúa;
- CHIRPS combina infrarrojo, climatología y estaciones (~5 km), suaviza los extremos y da ceros en el desierto.

Ninguna basta sola. El principio desde ahora: cada dato nuevo se integra con al menos una fuente independiente, y lo que aparece al cruzarlas se publica como descubrimiento.

**CHIRPS (`connectors/nasa/climateserv.py`, `orchestration/rainfall_crosscheck.py`).**
- **Fuente:** CHIRPS v2.0 diario vía NASA SERVIR ClimateSERV, sobre el área (polígono simplificado) o sobre la celda de 0.05° del punto.
- **Descarga:** un trabajo por año, porque la serie completa de una vez no terminó en 5 minutos.
  - 6 trabajos en paralelo y 3 intentos ante 429/502/503/504; un 4xx no se reintenta.
  - Los años cerrados quedan en caché sin vencimiento.
  - Los valores −9999 o imposibles son faltantes, nunca ceros.
- **Espera:** 45 s. Si un área nueva no termina, el análisis sigue con MERRA-2 e IMERG y declara la brecha «descargándose», mientras la descarga sigue en segundo plano. Medido el 26-oct: un área nueva tarda de 3 a 6 minutos y la siguiente ejecución, ~5 s.
- **Cálculo:**
  - Un área sin días húmedos en CHIRPS sale sola, sin dejar sin contraste a las demás.
  - Las restantes se calculan juntas, para que Benjamini–Hochberg ajuste entre sitios igual que en MERRA-2.

**Contrato (aditivo).**
- `ExtremeIndexSummary.counterchecks`: un contraste por fuente.
- `AtypicalYear.countercheck_values`: el valor de cada fuente en el año atípico.
- `ScreeningEnvelope.discoveries`.
- `countercheck` sigue reservado a IMERG por compatibilidad: si IMERG falta, queda vacío en vez de mostrar CHIRPS con su nombre.

**Descubrimientos (`orchestration/discoveries.py`).** Reglas deterministas, sin consultas externas:
- **Artefacto probable:** el reanálisis supera al menos 5 veces a cada satélite en el mismo año; se agrupa por año, no por índice.
- **Tendencia significativa de MERRA-2:** se clasifica como confirmada, respaldada por n de m fuentes, sin respaldo o contradicha.
- **Cambio que solo ven los satélites:** «sin respaldo» si lo ve uno solo; «coincidencia» si lo ven los dos.
- **Coincidencia entre instituciones:**
  - riesgo alto de inundación de CENEPRED con un punto crítico de la ANA;
  - riesgo alto de movimientos en masa con pendiente NASADEM ≥ 15°;
  - más vegetación no arbórea en MOD44B con ganancia de pastizal o matorral en MCD12Q1.

Los descubrimientos entran a la etapa «Resultados» del pipeline, a un panel propio en todas las pantallas, al PDF ejecutivo y al asistente. La pregunta 4 del reto resume el contraste de ambos satélites.

**Resultado real del 26-oct-2026:**
- **Moquegua, 2022:**
  - RX1DAY: 300 mm en MERRA-2, 12 mm en IMERG y 21 mm en CHIRPS. Es un artefacto confirmado por las dos fuentes independientes.
  - CHIRPS ve aumentos significativos en 4 índices que MERRA-2 no ve. Se publican como pistas que hay que contrastar con estaciones, no como tendencias.
- **Arequipa:** la tendencia de RX5DAY (+1.1 mm/año, p BH 0.019), que IMERG no respaldaba, se repite en CHIRPS.

**Verificación:**
- 182/182 pruebas, cinco de ellas nuevas:
  - reintento ante 503 y no ante 400;
  - faltantes −9999;
  - un área desértica no arrastra a las demás;
  - descarga pendiente declarada;
  - descubrimientos: artefacto, sin respaldo, y cambio visto solo por satélites.
- Un `conftest.py` común aísla CHIRPS de la red.
- QA `baseline_ui`, `climate_ui` y `release_ui` en 1440, 768 y 390: 0 errores, 0 recortes, 0 desbordamientos y teclado sin problemas.
- Build de Next.js correcto; audit con 0 vulnerabilidades.

## ADR-037 — Deslizamientos: tres fuentes de NASA cruzadas con CENEPRED

**Motivo.** El principio de ADR-036 aplicado a los deslizamientos. CENEPRED publica la susceptibilidad a movimientos en masa del Perú; sin una segunda fuente, no hay forma de saber dónde ese mapa coincide con otro ni si lo ocurrido lo respalda. La carpeta `Landslides` de NASA Earthdata GIS trae tres fuentes independientes en un mismo servidor.

**Fuentes (`connectors/nasa/landslides.py`).** Verificadas en vivo el 27-oct-2026:
- **Susceptibilidad global** (`Global_Landslide_Susceptibility`, Stanley y Kirschbaum 2017, Natural Hazards 87:145–164):
  - ráster de 30″ (~1 km), clases 1–5 = Very Low … Very High (cortes difusos 0.11 / 0.49 / 0.67 / 0.75), nodata 127;
  - el servicio devuelve 0 en agua, océano y llano desértico (Titicaca, frente a Lima, desierto de Ica). El artículo no define el 0: se trata como «sin clase», nunca como susceptibilidad baja.
- **LHASA 2 del día** (`LHASA_Hazard_Today`): probabilidad 0–1 de un modelo de aprendizaje automático; nodata −9999.
  - NASA no publica umbrales ni la fecha del ráster en el servicio: se informa el orden de magnitud y la hora de consulta, sin clasificarlo como alerta.
  - `LHASA_Hazard_Tomorrow` devolvió valores idénticos a Hoy en cinco puntos: no se usa hasta entender esa diferencia.
- **COOLR** (`COOLR_Reports_Points`, Global Landslide Catalog y Landslide Reporter): deslizamientos ocurridos, con fecha, tipo, detonante, fallecidos, precisión de ubicación y enlace a la fuente.
  - En el Perú: 80 reportes de 1974 a 2020; precisión de 1 a 250 km. `COOLR_Events_Points` no tiene registros del Perú.

**Muestreo.** `sample_points` y el polígono ArcGIS pasan a `geospatial/sampling.py`: CENEPRED (`identify`) y NASA (`getSamples`) se leen en los mismos puntos, sin interpolar ninguna de las dos. Caché: 30 días para la susceptibilidad, 3 horas para LHASA y 7 días para COOLR; una consulta caída es `DATA_UNAVAILABLE` y activa el reintento de la línea base.

**Contrato.** Sin cambios: las tres fuentes entran como capas `nasa-landslide-susceptibility`, `nasa-coolr-reports` y `nasa-lhasa-nowcast` del medio «Amenazas y riesgo». La brecha estática de LHASA desaparece.

**Descubrimientos nuevos (`landslide_discoveries`).**
- **Mapa nacional frente a global:** en cada punto, CENEPRED y NASA coinciden si difieren a lo sumo en una clase de cinco. En el área, «coinciden» si lo hacen en al menos dos tercios de los puntos; si no, «discrepan», con cuántos puntos marca más alto cada fuente. Con la mitad no basta: en Moquegua, 4 de 7 puntos se leían como coincidencia aunque CENEPRED marcaba alto donde NASA marcaba baja.
- **Lo ocurrido frente a los mapas:** reportes COOLR en el área donde algún mapa marca alta o muy alta → «confirmado»; donde ninguno lo hace → «contradicción», con la precisión de ubicación del reporte.

**Resultado real del 27-oct-2026 (distritos IGN):**
- **Lurigancho-Chosica:** coinciden en 7 de 9 puntos; COOLR registra 6 deslizamientos entre 2009 y 2017 (Chosica, Huachipa) y ambos mapas marcan alta o muy alta: lo ocurrido respalda el mapa.
- **Ilo:** discrepan; solo 3 de 7 puntos coinciden y CENEPRED marca más alto en los otros 4. El mapa nacional tiene más detalle; la diferencia se resuelve en campo.
- LHASA del día: máximo 0.0027 en Lurigancho y 0.0025 en Ilo; puntos sin valor del servicio en ambos distritos, declarados y nunca leídos como cero.

**Verificación:**
- 189/189 pruebas; 7 nuevas en `test_landslides.py` (clases y 0 sin clase, nodata de LHASA, traducción de COOLR, servicio caído, coincidencia, discrepancia con la regla de dos tercios, confirmación por reportes). `conftest.py` aísla los deslizamientos de la red.
- API real en Docker: Amenazas para Lurigancho e Ilo en 47 s, con 6 de 6 consultas a NASA respondidas; el PDF lleva descubrimientos, nota de método y la cita de NASA en el pie.
- QA `baseline_ui` en 1440, 768 y 390: 0 errores y 0 desbordamientos; las tres capas de NASA y sus descubrimientos aparecen en pantalla. Build de Next.js correcto; audit con 0 vulnerabilidades.

## ADR-038 — Temperatura y radiación cruzadas con ERA5 (PVGIS)

**Motivo.** Clima y Energía leían la temperatura (MERRA-2) y la radiación (CERES) de una sola fuente, y la radiación mueve directamente la energía estimada y el VAN. ClimateSERV solo ofrece pronósticos CFSv2 de temperatura, no observaciones.

**Fuente (`connectors/jrc/pvgis.py`).** PVGIS 5.3 del JRC (`MRcalc`, público, sin clave):
- Sobre el Perú solo existe la base PVGIS-ERA5: SARAH-3 responde «fuera de cobertura» y NSRDB no se ofrece en la API 5.3 (verificado el 27-oct-2026).
- Devuelve por mes la irradiación global horizontal (kWh/m²/mes) y la temperatura media a 2 m, de 2005 a 2023.
- Se convierte a las unidades de NASA POWER: temperatura media ponderada por días y kWh/m²/día. Un año sin sus 12 meses se omite.
- Dos intentos ante 429/5xx; un 4xx no se reintenta. Es un archivo cerrado: la caché no vence.

**Contrato (aditivo).**
- `Agreement` y `ExtremeCountercheck` pasan a `schemas/pipeline.py`; `schemas/climate.py` los reexporta, así que las importaciones existentes siguen funcionando.
- `VariableSummary.counterchecks`.
- `ExtremeCountercheck.period` y `primary_slope_per_year`, opcionales.

**Comparación (`orchestration/era5_crosscheck.py`).**
- Las tendencias se comparan solo en los años comunes (2005–2023): la pendiente de NASA POWER se recalcula en esos años y Benjamini–Hochberg ajusta cada fuente entre sitios.
- Si una tendencia significativa del período completo deja de serlo en los años comunes, se declara.
- ERA5 se pide en el punto representativo; un territorio que en NASA POWER es promedio de celdas se compara con ese punto.

**Descubrimientos (`variable_discoveries`).**
- **Tendencia:** confirmada; de signo opuesto; «apunta igual pero sin significancia» (misma dirección, p BH ≥ 0.05); solo en ERA5; o no se sostiene en los años comunes.
- **Nivel del recurso solar:** coinciden con menos de 5 % de diferencia; desde 10 % la diferencia mueve el VAN y se marca como contradicción.
- **Nivel de temperatura:** desde 2 °C se marca. La celda de MERRA-2 (0.5° × 0.625°) mezcla altitudes andinas muy distintas.

**Resultado real del 27-oct-2026:**
- **Moquegua:**
  - la subida de temperatura se confirma (MERRA-2 +0.039, ERA5 +0.042 °C/año en 2005–2023);
  - el nivel difiere 10.6 °C (MERRA-2 7.4 °C, ERA5 18.0 °C);
  - el recurso solar coincide (+1.6 %).
- **Arequipa:**
  - ERA5 apunta igual (+0.039 °C/año) sin significancia (p BH 0.059);
  - el nivel difiere 3.4 °C;
  - el recurso solar coincide (−4.0 %).
- **Lectura:** las tendencias de temperatura de NASA POWER son sólidas, pero su nivel absoluto en los valles andinos no representa el sitio. El criterio de temperatura del puntaje solar hereda ese sesgo y queda visible como descubrimiento.

**Ajustes en el camino:**
- **Energía:** ahora publica descubrimientos y su PDF usa el esquema solar, con la cita de PVGIS en el pie.
- **CHIRPS:** si solo falla el año en curso (que nunca entra en los índices), la serie sigue con los años cerrados y lo anota. ClimateSERV devolvió 503 para 2026 durante la verificación.

**Verificación:**
- 196/196 pruebas: 5 nuevas en `test_era5.py`, 1 de integración en Clima y 1 de CHIRPS con el año en curso caído.
- API real: Clima y Energía con descubrimientos ERA5; el PDF solar lleva descubrimientos y la cita.
- QA `climate_ui` y `release_ui` (siete módulos) en 1440, 768 y 390: 0 errores, 0 recortes, 0 desbordamientos y teclado sin problemas. El gráfico anual dibuja ERA5 con raya y punto.
- Build de Next.js correcto.

**Ampliación del 27-oct: viento a 10 m.** Con esto, las cuatro variables de NASA POWER tienen contraste: la lluvia en los extremos (IMERG y CHIRPS) y las otras tres con ERA5.
- **Fuente:** PVGIS solo entrega el viento en la serie horaria `seriescalc` (`WS10m`, m/s).
  - La serie completa de una vez pesa 14 MB y tarda ~110 s.
  - Un año por consulta, seis a la vez con un tope global, tarda ~17 s por punto, con valores idénticos.
  - Cada año queda en caché sin vencimiento; un año con menos del 90 % de horas válidas se omite.
- **Espera:** igual que CHIRPS, la descarga corre en segundo plano y el análisis espera 45 s. Si no termina, se declara «ERA5 · viento horario» como descargándose, mientras temperatura y radiación siguen contrastadas.
- **Nivel:** el viento medio se marca desde 30 % de diferencia (dos reanálisis de celda gruesa difieren a menudo).
- **Resultado real:**
  - el viento medio difiere 55 % en Moquegua (MERRA-2 3.88, ERA5 1.76 m/s) y 41 % en Arequipa (3.13 frente a 1.83 m/s);
  - la bajada de viento que MERRA-2 marca como significativa en 2001–2025 no se sostiene en 2005–2023 en ninguna de las dos fuentes.
  - Primera ejecución con los dos puntos: 43 s; la siguiente, 11 s.
- **Verificación:** 199/199 pruebas (umbral de horas, un año por consulta con caché, viento pendiente declarado). QA `climate_ui` con la pestaña Viento, sin errores ni desbordamiento.

## ADR-039 — Relieve cruzado con Copernicus GLO-30

**Motivo.** La elevación y la pendiente venían solo de NASADEM, que es SRTM reprocesado. La pendiente alimenta el puntaje solar y la coincidencia «riesgo de movimientos en masa + pendiente ≥ 15°» con CENEPRED. Las teselas de terreno de AWS (Terrarium) no sirven como contraste: en el Perú también provienen de SRTM.

**Fuente (`connectors/copernicus/dem.py`).** Copernicus DEM GLO-30 (ESA · Airbus, TanDEM-X) en AWS Open Data, sin cuenta.
- **Formato:** cada tesela de 1° es un COG de 3600 × 3600 px en float32, con DEFLATE, predictor de punto flotante (TIFF 3) y bloques de 1024 × 1024 (verificado el 27-oct-2026).
- **Lectura sin GDAL:** no se agrega `rasterio`. Se lee el encabezado (64 KB) y solo el bloque del punto (~2.5 MB) por rango HTTP; `zlib` y `numpy` deshacen la compresión y el predictor.
- **Formato TIFF:** los arreglos que caben en 4 bytes van dentro de la propia entrada; la prueba con un COG sintético lo detectó y quedó corregido.
- **Pendiente:** método de Horn en la ventana 3 × 3. En el borde de una tesela, o junto a un vacío, queda sin pendiente (no se rellena).
- **Datum:** EGM2008, frente a EGM96 de NASADEM. La diferencia es submétrica a efectos de screening.
- **Caché:** encabezado y bloques sin vencimiento.

**Integración.**
- `extract_terrain` consulta NASADEM y Copernicus en paralelo para todos los módulos con relieve.
- `TerrainSiteResult.crosscheck` es aditivo. Si Copernicus falla, se anota en las limitaciones del sitio.
- El panel de relieve muestra la línea «Contraste Copernicus GLO-30», y el PDF cita la fuente.

**Descubrimientos (`terrain_discoveries`).**
- Coinciden si la elevación difiere menos de 50 m y la pendiente menos de 5°.
- Si no, difieren; y se marca aparte cuando la pendiente cruza el umbral de 15° según el modelo.
- La coincidencia CENEPRED + pendiente cita además la pendiente de Copernicus.

**Resultado real del 27-oct-2026:**
- **Moquegua:** 1,420 frente a 1,413 m y 5.5° frente a 6.0° → coinciden.
- **Arequipa:** 2,316 frente a 2,320 m y 3.7° frente a 3.3° → coinciden.
- **Ilo:** 509 m en ambos y 7.3° frente a 8.8° → coinciden.
- **Lurigancho-Chosica:** 32.2° frente a 23.0° → difieren. Ambos superan los 15°, así que la coincidencia con el riesgo de CENEPRED se mantiene; en la ladera, el valor exacto depende del modelo.

**Verificación:**
- 203/203 pruebas; 4 nuevas en `test_copernicus_dem.py`: decodificador inverso exacto, COG sintético completo con caché, borde y tesela inexistente, descubrimientos. `conftest.py` aísla Copernicus de la red.
- API real en Energía y Amenazas.
- QA `release_ui` en 1440, 768 y 390 limpio, y captura del panel de relieve en 1440 y 390.
- Build correcto.

## ADR-040 — Cobertura del suelo cruzada con ESA WorldCover

**Motivo.** La vegetación se cruzaba entre dos productos del mismo sensor (MOD44B y MCD12Q1). ESA WorldCover (Sentinel-1 y Sentinel-2, 10 m) es independiente de MODIS. Con esto, todos los datos satelitales que usa la plataforma tienen contraste.

**Lector común de COG (`connectors/cog.py`).** El encabezado TIFF, todos los niveles (resolución completa y overviews), los bloques DEFLATE con predictor 1, 2 o 3 y la caché sin vencimiento quedan en un solo módulo, sin GDAL. Copernicus DEM pasa a usarlo; su lectura real sigue en 1,413.3 m y 6.04° en Moquegua.

**Fuente (`connectors/esa/worldcover.py`).**
- **Formato:** teselas de 3° nombradas por su esquina suroeste. COG uint8 con DEFLATE sin predictor, bloques de 1024 y seis overviews (verificado el 28-oct-2026).
- **Lectura:** se usa el nivel más detallado que quepa en 16 bloques por tesela y se cuentan las clases en los centros de píxel dentro del área, con `shapely.contains_xy` y un muestreo regular de hasta 250,000 puntos. La clase 0 (sin dato) no se cuenta.
- **Tesela vecina:** un área cuyo borde norte o este cae justo en el límite de una tesela no pide la tesela vecina. La prueba con un COG sintético encontró ese conteo doble.
- **Años:** solo existen 2020 y 2021, así que se compara el nivel, no la tendencia.

**Comparación (`orchestration/cover_crosscheck.py`).**
- En la misma ventana del análisis MODIS (±km alrededor del punto) y en 2021.
- Grupos: árboles (10, 95) frente a `VCF_TREE`; vegetación no arbórea (20, 30, 40, 90, 100) frente a `VCF_NONTREE`; sin vegetación (50, 60, 70) frente a `VCF_BARE`. El agua (80) queda fuera en ambos.
- Coinciden si cada grupo difiere menos de 10 puntos; difieren desde 20. En la franja intermedia no hay descubrimiento, pero la tabla muestra los valores.
- La diferencia es esperable en vegetación rala, porque WorldCover da la clase dominante a 10 m y MOD44B la fracción a 250 m. Se declara.

**Contrato (aditivo).** `SubjectBaseline.land_cover_check` con clases, grupos, píxeles, resolución y procedencia. Si falla, queda una nota en `vegetation_notes`, nunca ceros.

**Pantalla y PDF.**
- Tabla «Contraste de cobertura 2021» en cada área de Ambiente.
- Las tablas de tres columnas (también la de IGBP) dejan de exigir 780 px y caben en 390.
- El PDF lleva la tabla y la cita (Zanaga et al. 2022, CC BY 4.0).

**Resultado real del 28-oct-2026:**
- **Ilo (ventana de ±10 km):** coinciden. Vegetación no arbórea 21.8 frente a 18.7 % y sin vegetación 77.6 frente a 81.3 %.
- **Moquegua (círculo de 1 km sobre la ciudad):** 13–15 puntos de diferencia, en la franja intermedia. A 10 m domina la ciudad; MOD44B atribuye a 250 m la fracción de jardines y árboles urbanos.

**Verificación:**
- 208/208 pruebas; 5 nuevas en `test_worldcover.py`: COG uint8 sintético con overview, nodata, caída al overview, tesela inexistente, grupos sin agua y descubrimientos. Más la integración ambiental.
- API real con PDF.
- QA `baseline_ui` y `release_ui` en 1440, 768 y 390 limpio, y capturas de la tabla.
- Build correcto; audit con 0 vulnerabilidades.

## ADR-041 — Piloto eólico: forma horaria de NASA POWER, nivel del Atlas Eólico Global

**Motivo.** El anteproyecto promete eólica e hidroeléctrica. La eólica entra como segunda tecnología del módulo Energía, con el mismo contrato C2 que la solar (`Sector.WIND`, aditivo).

**Fuentes.**
- **NASA POWER horario (`connectors/nasa/power_hourly.py`):** WS50M y WS10M de MERRA-2, los diez últimos años completos del período. Un año por consulta (~300 KB, ~3 s medido el 30-oct-2026), cuatro a la vez, caché sin vencimiento. Un año con menos de 90 % de horas válidas no entra; el −999 se descarta.
- **NASA POWER diario:** WS50M (nueva en el catálogo), WS10M, T2M y PRECTOTCORR para las tendencias, con ERA5 como contraste del viento a 10 m y de la temperatura (ADR-038).
- **Global Wind Atlas 4.0 (`connectors/gwa/wind_atlas.py`):** DTU con ESMAP del Banco Mundial, publicado en junio de 2025; velocidad media de largo plazo a 50 y 100 m con 250 m de resolución, CC BY 4.0. El archivo del Perú es BigTIFF en bloques de 512, ZSTD con predictor 3 y nodata NaN. El lector común `connectors/cog.py` ahora lee BigTIFF y ZSTD, con la dependencia `zstandard==0.23.0` (BSD).

**Energía (`sectors/wind_energy.py`, funciones puras).**
- **Altura del buje:** cada hora de 50 m se lleva al buje con la ley potencial. El exponente sale de las medias de 10 y 50 m de las mismas horas, acotado a [0, 0.5].
- **Densidad del aire:** atmósfera estándar a la elevación del sitio (NASADEM, o Copernicus si NASADEM no tiene métrica) y a la T2M media. Se aplica como velocidad equivalente (IEC 61400-12-1). Sin elevación se declara y la energía queda sobrestimada.
- **Curva de potencia genérica:** arranque 3, nominal 12 y parada 25 m/s, rampa cúbica. Es un supuesto editable; la curva del fabricante figura como brecha.
- **Energía y VAN:** energía = MW × 8,760 × factor de planta bruto × (1 − pérdidas), con VAN del motor común.

**Decisión: nivel del atlas en el caso base.** La celda de MERRA-2 (~55 km) subestima el viento donde el relieve o la costa lo aceleran. El caso base escala cada hora de NASA POWER por la razón entre medias al buje (atlas ÷ NASA POWER). Así conserva la forma horaria, la variación entre años y la tendencia de NASA, y toma el nivel del atlas. El nivel propio de NASA POWER queda como extremo adverso del recurso en el tornado («Nivel del recurso (Atlas Eólico ↔ NASA POWER)»). Si el atlas no responde, se usa el nivel de NASA POWER y se declara.

**Validación con producción real (30-oct-2026).** Con los XLSX oficiales de COES 2024, hoja PRODUCCIÓN DIARIA, tipo EÓLICA, y las potencias publicadas:

| Central | Producción 2024 | Potencia | Factor de planta real |
|---|---|---|---|
| Tres Hermanas | 481,842 MWh | 97.15 MW | 56.5 % |
| Marcona | 162,580 MWh | 32.1 MW | 57.7 % |
| San Juan | 614,927 MWh | 135.7 MW | 51.6 % |

En Marcona, el modelo da 46.7 % neto con el nivel del atlas y 14.0 % con el de MERRA-2. El nivel de NASA POWER solo habría descartado el mejor sitio eólico del país.

**Descubrimientos.** El viento al buje de NASA POWER frente al atlas: coinciden bajo 10 %; difieren desde 20 % (contradicción, con el factor de planta en ambos niveles). Se suman los de ERA5 y relieve ya existentes.

**Puntaje (pesos editables).**

| Criterio | Peso |
|---|---|
| Viento al buje | 0.25 |
| Estabilidad interanual del factor de planta | 0.10 |
| Deriva del viento a 50 m (solo si es significativa tras BH) | 0.10 |
| Confianza del recurso (\|Δ\| NASA–atlas) | 0.15 |
| Pendiente NASADEM | 0.10 |
| VAN / CAPEX | 0.30 |

**Brechas declaradas:**
- medición en sitio (torre o LiDAR, al menos un año);
- curva del fabricante;
- red eléctrica;
- restricciones ambientales y sociales, incluida la avifauna;
- elevación o atlas ausentes.

**Pantalla y PDF.**
- Selector «Tecnología» en Energía; Marcona y Moquegua son los sitios de ejemplo de eólica.
- Lectura con el viento al buje y el factor de planta.
- Pestañas Viento 50 m y 10 m.
- Tabla NASA POWER frente al atlas por sitio, puntaje, sensibilidad y método.
- El PDF cita NASA POWER Hourly y el Global Wind Atlas 4.0.

**Resultado real del 30-oct-2026 (Marcona frente a Moquegua, 2001 a hoy).**
- **Marcona:** 6.39 m/s al buje en NASA POWER y 9.74 m/s en el atlas (+52 %). Factor de planta 46.7 % neto, 204,355 MWh/año y VAN +USD 21.1 M con los supuestos por defecto (50 MW, USD 65 M, 55 USD/MWh, 10 %, 25 años). Precio de equilibrio 43.6 USD/MWh.
- **Moquegua:** 2.28 m/s en el atlas y factor de planta 0.3 %.
- **Puntaje:** 67 frente a 17.

**Verificación:**
- 16 pruebas nuevas en `test_wind.py`: curva, densidad, cizalladura, factor de planta, fórmula, años horarios, parseo horario, BigTIFF/ZSTD sintético ida y vuelta, atlas con nodata y fuera de archivo, sobre C2 con y sin atlas, PDF y descubrimientos.
- Conftest sin red para el horario y el atlas.
- QA `wind_shots` en 1440 y 390: 0 errores de consola, 0 desbordamiento, PDF de 6 páginas con las fuentes.

## ADR-042 — Piloto hidroeléctrico de pasada: caudal GloFAS con GEOGLOWS, salto NASADEM con Copernicus

**Motivo.** Es la tercera tecnología del módulo Energía y cierra lo que promete el anteproyecto. Usa el mismo contrato C2 (`Sector.HYDRO`, aditivo) y `POST /api/v1/projects/hydro-screening`. Cada sitio es una toma sobre el río y una casa de máquinas aguas abajo.

**Fuentes.**
- **Caudal (`connectors/copernicus/glofas.py`):** GloFAS v4 (Copernicus EMS, ECMWF; LISFLOOD forzado con ERA5, celdas de 0.05°) servido por la Flood API de Open-Meteo. Medido el 10-nov-2026: serie diaria válida desde 1997-01-01 (nula antes) hasta hoy, en m³/s.
- **Cuota de Open-Meteo:** cada consulta pesa días ÷ 14 ÷ 10 llamadas y el tope es 600 por minuto. La historia cerrada (1997 al año pasado, ~76 llamadas) se pide una vez por celda y queda en caché sin vencimiento; el año en curso, 24 h. El uso gratuito de esa API es solo no comercial: un producto comercial debe leer GloFAS del servicio de Copernicus o contratar el plan de pago.
- **Segunda opinión del caudal (`connectors/geoglows/streamflow.py`):** GEOGLOWS River Forecast System v2 (GEO con ECMWF, NASA, NOAA y BYU; CC BY 4.0), medias anuales desde 1940. También se fuerza con ERA5: cambia el modelo de tránsito (RAPID) y la red de ríos (TDX-Hydro). Es una segunda opinión de modelo, no una medición.
- **Salto:** elevación de la toma menos la de la casa de máquinas en NASADEM, contrastada con Copernicus GLO-30 (ADR-039). Sin token de Earthdata el salto sale de Copernicus y se declara.
- **Contexto:** precipitación y temperatura de NASA POWER en la toma, con Mann–Kendall corregido como en los demás sectores.

**Regla del cauce de GloFAS.** El cauce del modelo no siempre pasa por la celda del punto: el río Tambo en El Fiscal da 0.00 m³/s en su celda y 39.2 m³/s (1997–2025) en la vecina. Regla declarada, que no mira otra fuente:
1. Se lee el caudal medio del último año completo en el vecindario 3 × 3.
2. Si la celda del punto lleva al menos el 20 % del máximo vecino, se usa.
3. Si no, se usa la más cercana entre las que llevan al menos el 50 %, y se declara la distancia.
4. Si ninguna llega a 0.05 m³/s, no hay cauce modelado: error 422 con el motivo, nunca un cero.

**Regla de búsqueda de GEOGLOWS.** `getriverid` no devuelve el tramo cuya línea pasa por el punto. Con el punto exacto del cauce según OpenStreetMap:

| Punto | Tramo que devuelve en el punto | Cauce principal en la malla |
|---|---|---|
| Tambo, El Fiscal | 0.00 m³/s | 73.3 m³/s |
| Tambo alto (Moquegua) | 0.28 m³/s | 50.7–52.2 m³/s |
| Majes, Corire | 0.64 m³/s | 156.9 m³/s |

Por eso se consulta una malla de 5 × 5 puntos cada 0.02° (±4.4 km) y se toma el tramo de mayor caudal medio. El servicio corta las ráfagas (con seis conexiones cerró la sesión): se usan tres, con reintentos. Un punto nuevo tarda cerca de un minuto, así que la búsqueda corre en segundo plano con 40 s de espera; si no llega, el resultado lo declara «en consulta» y la siguiente ejecución lo trae de caché (30 días).

**Comparación de fuentes (constantes en `orchestration/discoveries.py`).**
- **Caudal:** coinciden bajo 25 % en la media de los años comunes; difieren desde 50 %. Si una fuente lleva más de diez veces el caudal de la otra, no se comparan: se registra que no ubican el mismo río y no entra al tornado.
- **Salto:** coinciden bajo 5 %; difieren desde 10 %.
- **Tendencia del caudal:** se contrasta en los años comunes con BH entre sitios (`orchestration/annual_crosscheck.py`, la misma pieza que ahora usa ERA5).

**Energía (`sectors/hydro_energy.py`, funciones puras).**
- Caudal ecológico: fracción declarada del caudal medio (10 % por defecto), que se deja siempre en el río.
- Caudal de diseño: el aprovechable excedido el 30 % del tiempo, o el que el usuario declare para el sitio.
- Cada día se turbina el caudal aprovechable con tope en el de diseño; bajo el mínimo técnico (20 % del de diseño) la central para.
- Potencia = ρ · g · Q · salto neto · eficiencia; la potencia instalada es un resultado, no un supuesto, y el CAPEX se declara por MW.
- Solo entran años con al menos el 90 % de sus días. Es una central sin embalse.

**Decisión: GloFAS en el caso base.** GEOGLOWS da entre 49 % y 64 % más caudal que GloFAS en los dos sitios de ejemplo, en los años comunes 2001–2024. La producción real respalda a GloFAS (ver validación), así que GEOGLOWS queda como el otro extremo del factor «Caudal (GloFAS ↔ GEOGLOWS)» en el tornado. Con el salto ocurre lo mismo: Copernicus es el otro extremo de «Salto (NASADEM ↔ Copernicus)».

**Validación con producción real (10-nov-2026).** Central Machupicchu, río Vilcanota: 192.45 MW y 61 m³/s de diseño. Represa y casa de máquinas tomadas de OpenStreetMap. El COES registra 1,252,221 MWh en 2024.

| | Factor de planta 2024 | Potencia |
|---|---|---|
| Central real (COES) | 74.1 % | 192.45 MW |
| Modelo, ecológico 10 % (por defecto) | 64.7 % | 163.2 MW |
| Modelo, ecológico 5 % | 71.8 % | 163.2 MW |
| Modelo, sin caudal ecológico | 77.1 % | 163.2 MW |

- El valor real cae dentro del rango que abre el supuesto de caudal ecológico: el régimen del río de GloFAS es consistente con la operación de la central. En estiaje GloFAS da unos 29 m³/s, por debajo de los 61 de diseño.
- La potencia queda 15 % por debajo porque el salto se lee sobre el terreno (330 m entre los dos puntos del mapa), no en el eje de la turbina.
- Con los supuestos por defecto, la energía de 2024 queda 26 % por debajo de la real: el modelo es prudente.
- La validación se reproduce con dos guiones fuera del producto: `scripts/qa/coes_production.py 2024 MACHUPICCHU` (producción real) y `scripts/qa/validate_hydro.py` (modelo). El primero también reproduce la validación eólica de ADR-041 con `--tipo EOL`.

**Puntaje (pesos editables).**

| Criterio | Peso |
|---|---|
| Factor de planta | 0.20 |
| Caudal firme en estiaje (Q95 ÷ diseño) | 0.10 |
| Deriva del caudal (solo si es significativa tras BH) | 0.10 |
| Confianza del caudal (\|Δ\| GloFAS–GEOGLOWS) | 0.15 |
| Confianza del salto (\|Δ\| NASADEM–Copernicus) | 0.10 |
| VAN / CAPEX | 0.35 |

**Brechas declaradas:** aforo en la toma; disponibilidad hídrica y caudal ecológico de la ANA; topografía, geología y sedimentos; red eléctrica; restricciones ambientales y sociales.

**Contrato y piezas comunes (aditivo).** `Sector.HYDRO`; `SectorLens.location_note`; `extraction_stage(..., provider=)`; unidad `m3/s` y variable `RIVER_DISCHARGE` en los catálogos.

**Pantalla y PDF.**
- Tercera opción en «Tecnología», con editor de toma y casa de máquinas por sitio y botón «Elegir en el mapa».
- Lectura con potencia, energía y VAN; pestaña Caudal con GloFAS continua y GEOGLOWS punteada.
- Por sitio: tabla caso base frente a segunda fuente y curva de duración con la línea de plena carga.
- El PDF cita GloFAS y GEOGLOWS.

**Resultado real del 10-nov-2026 (2001 a hoy).**

| Sitio | Caudal medio | Salto | Potencia | Energía | Segunda opinión del caudal |
|---|---|---|---|---|---|
| Machupicchu (río Vilcanota) | 156 m³/s | 330 m | 163 MW | 970 GWh/año | +49 % (intermedia) |
| Tambo alto (Moquegua) | 32 m³/s | 146 m | 28 MW | 115 GWh/año | +64 % (difieren) |

- En el Tambo, el salto difiere 23 m entre NASADEM (146 m) y Copernicus (169 m).
- En Machupicchu, GloFAS muestra una tendencia creciente del caudal que GEOGLOWS no repite.

**Verificación:**
- 25 pruebas nuevas en `test_hydro.py` (250 en total): energía, regla del cauce, conectores con transporte simulado, búsqueda de GEOGLOWS, sobre C2 con y sin segunda fuente, fuente lenta, río no comparable, salto solo con Copernicus, puntos invertidos (422), un solo sitio, PDF.
- Conftest sin red para GloFAS y GEOGLOWS.
- Build con 20 rutas.
- QA `hydro_shots` en 1440 y 390: 0 errores de consola, 0 desbordamiento, PDF de 6 páginas.

## ADR-043 — El relieve cruzado llega a los pilotos vial e inmobiliario y al puntaje

**Motivo.** Los pilotos vial e inmobiliario ya recibían la pendiente de Copernicus GLO-30 junto a la de NASADEM (ADR-039), pero no la usaban: eran los dos únicos sectores sin descubrimientos. Además, cuatro puntajes (solar, eólico, vial e inmobiliario) puntúan la pendiente de NASADEM en un solo punto y no decían qué pasa si el otro modelo tiene razón.

**Decisión.**
- **Descubrimientos:** `terrain_discoveries` se aplica también a vial e inmobiliario y queda en la etapa «Resultados». Si ningún punto tiene contraste, la etapa dice «Sin contraste del relieve», no «ninguno»: una lista vacía ahí significa que no hubo con qué cruzar.
- **Puntaje (`orchestration/slope_check.py`):** se recalcula con la pendiente de Copernicus en lugar de la de NASADEM y una nota dice si el primer lugar cambia y con qué puntajes. La nota usa los pesos iniciales y lo declara, porque el usuario puede editarlos después.
- **Cuándo no se compara:** si a algún sujeto con pendiente le falta el contraste (no se mezclan modelos) o si hay menos de dos sujetos con puntaje.
- **Texto del método del puntaje:** ahora declara la regla de empate práctico (menos de 5 puntos o un primero que gana en menos del 75 % de las combinaciones). Un reemplazo de comas le había quitado la puntuación; quedó corregido.

**Resultado real del 10-nov-2026.**

| Sector | Primer lugar con NASADEM | Con la pendiente de Copernicus |
|---|---|---|
| Vial (corredor Moquegua–Ilo) | Tramo 5 (48.5) frente a Tramo 2 (38.7) | No cambia: Tramo 5 (44.4) frente a Tramo 4 (37.1) |
| Solar (Moquegua y Arequipa) | Arequipa, empate práctico | No cambia: Arequipa (66.9) frente a Moquegua (65.6) |
| Eólico (Marcona y Moquegua) | Marcona por 50 puntos | No cambia: Marcona (67.4) frente a Moquegua (16.3) |
| Inmobiliario (tres áreas de ejemplo) | Cerro Colorado, empate práctico | No cambia: Cerro Colorado (75.9) frente a Moquegua (72.4) |

La fila inmobiliaria usa las alertas de CENEPRED de su última copia válida (ADR-044). Con ese criterio fuera del puntaje, como estuvo unas horas el 10-nov, la nota daba 78.7 frente a 74.5.

- **El hallazgo del corredor:** el Tramo 5 lidera por su pendiente, 17.9° en NASADEM. Copernicus da 12.5° en el mismo punto: sigue siendo el más empinado (los demás tramos van de 1.2° a 4.2°), pero ya no supera el umbral de 15° de pendiente fuerte. El orden se sostiene; la magnitud debe confirmarse con topografía.
- En los cinco tramos NASADEM da entre 2.0° y 5.5° más de pendiente que Copernicus, con la elevación a 6 m o menos. En los puntos de solar, eólica e inmobiliario la diferencia es menor de 2° y va en ambos sentidos. La causa de ese sesgo sobre el corredor no se ha investigado.

**Verificación.** 10 pruebas nuevas (260 en total): seis en `test_slope_check.py` con puntajes calculados a mano y dos en cada piloto. Regresión en navegador de vial e inmobiliario en 1440/768/390 sin errores ni desbordes.

## ADR-044 — Última copia válida cuando una capa oficial deja de responder

**Motivo.** El 10-nov-2026 el servicio de CENEPRED (SIGRID, `FEN/ER_NINO2027_BD`) empezó a responder `499 Token Required` y su directorio público dejó de listar los servicios. Sus tres capas (riesgo por inundación, riesgo por movimientos en masa y susceptibilidad por puntos) quedaron como `DATA_UNAVAILABLE` en amenazas, vial e inmobiliario. La última respuesta válida que tenía la caché era del 24 al 28 de octubre. La misma regresión mostró el otro caso: SIGDA no contestó nueve capas del distrito de Ilo y una hora después sí.

**Decisión.** Si una capa oficial falla y existe una copia anterior de **la misma consulta**, se muestra esa copia y se declara.
- **Conectores:** `connectors/peru/territory.py` y `connectors/peru/identify_layers.py`. Primero se consulta al servicio; solo si falla se busca la copia (`RawPayloadCache.last_valid`).
- **Vigencia:** hasta 90 días (`STALE_MAX_AGE`). Más antigua, o sin copia, la capa queda como `DATA_UNAVAILABLE`, igual que antes.
- **Procedencia:** `CACHED_DATA` con la **fecha original** de la copia; nunca la de hoy. Si una fuente junta varias capas, se informa la fecha de la copia más antigua.
- **Dónde se declara:**
  - en la capa (`stale_note`, campo aditivo en `TerritorialSourceResult`, `BaselineLayer` y los resúmenes de vial e inmobiliario), con el motivo y la fecha;
  - en una brecha con procedencia `CACHED_DATA` y la acción siguiente;
  - en los descubrimientos que usan esa capa;
  - en la pantalla (etiqueta «copia del 25-oct-2026» junto al dato y nota al pie) y en el PDF.
- **Cortesía con el servidor:** en el muestreo por puntos, tras la primera falla no se vuelve a llamar por los demás puntos. Una falla por credenciales no se reintenta; un corte de conexión, una vez.

**Alcance.** Capas oficiales peruanas consultadas por área o con `identify` (CENEPRED, SERNANP, Cultura, ANA, MINAM y los mapas volcánicos de INGEMMET). No cambia NASA POWER ni las capas de NASA.

**Límites.**
- Solo cubre geometrías ya consultadas: un sitio nuevo no tendrá las capas de CENEPRED mientras el servicio exija token.
- Una copia no prueba que el dato siga vigente. Por eso entra como brecha y no como dato verificado hoy.
- Un producto comercial debe gestionar el acceso con CENEPRED; el equipo no crea cuentas en nombre de terceros.

**Resultado real del 10-nov-2026.**

| Caso | Sin la copia | Con la última copia válida |
|---|---|---|
| Corredor Moquegua–Ilo, riesgo de inundación y de movimientos en masa | «No disponible» en los cinco tramos | Entre 1 y 3 distritos por tramo, copia del 25-oct-2026 |
| Lurigancho (Chosica), tres capas de CENEPRED | Sin respuesta | 9, 9 y 18 registros, copia del 27-oct-2026 |
| Lurigancho, descubrimiento «CENEPRED y NASA coinciden en la susceptibilidad a deslizamientos» | No se podía calcular | Vuelve, con la advertencia de la copia |
| Inmobiliario, criterio de alertas de CENEPRED | Fuera del puntaje (cobertura 85 %) | Vuelve a puntuar |

**Verificación.** 6 pruebas nuevas (266 en total): copia servida con su fecha original, sin copia, copia demasiado antigua, muestreo por puntos que deja de insistir, y la declaración en capa, brecha, descubrimiento y PDF. QA en navegador a 1440 y 390 en amenazas y vial: sin recortes, desbordes ni errores de consola.

## ADR-045 — La validación con producción real se muestra junto al método

**Motivo.** Los modelos eólico e hidroeléctrico se validaron con la producción real del COES (ADR-041 y ADR-042), pero esa validación solo estaba en este registro y en dos guiones. En la pantalla y en el PDF nada la respaldaba.

**Decisión.** El sobre C2 agrega `method_validation` (lista de textos, aditiva, vacía por defecto). Eólica e hidroeléctrica la llenan con una frase cada una: qué central, qué año, qué dio la realidad, qué da el modelo, cuándo se midió y que es un solo caso. Se muestra como primera nota del panel «Método», marcada «real», y en la sección de método del PDF.

**Lo que no es.** No es un resultado del análisis en curso ni se recalcula con los sitios del usuario: es una constante del método, con fecha, que se reproduce con `scripts/qa/coes_production.py` y `scripts/qa/validate_hydro.py`. Traer la producción real de la central que el usuario elija sigue siendo una idea abierta del equipo (A1).

**Verificación.** Las pruebas de PDF de eólica e hidroeléctrica leen el texto del reporte y comprueban la frase, la cifra real y la advertencia de alcance.

## ADR-046 — Alcance global: cualquier lugar del mundo y alertas activas sobre el mapa

**Motivo.** Decisión de Christian (10-nov-2026): la plataforma debe funcionar en todo el mundo, con menos detalle que en el Perú, y mostrar con animaciones básicas los lugares que necesitan apoyo urgente, empezando por algunos del mundo y algunos del Perú.

**Qué ya era global y qué no.** Probado ese día en Nairobi, Sevilla y Chennai: Clima, solar, eólica, hidroeléctrica y los deslizamientos de NASA respondían fuera del Perú, porque NASA POWER, IMERG, CHIRPS, ERA5, NASADEM, Copernicus, MODIS, WorldCover, GloFAS y GEOGLOWS son globales. Estaban atados al Perú: el archivo del Atlas Eólico, las capas oficiales, la búsqueda de territorios y los títulos.

**Decisiones.**
- **País de un punto (`geospatial/countries.py`):** Natural Earth 1:110m, de dominio público, guardado en `backend/data/world/`. Con holgura de 0.5° para costas y fronteras simplificadas (Ilo y Marcona quedan fuera del polígono a esa escala). Un punto en mar abierto no tiene país: no se adivina.
- **Atlas Eólico Global:** se lee el archivo del país donde cae el punto. Sin país, no hay atlas y el modelo usa el nivel de NASA POWER, declarado.
- **Capas oficiales del Perú:** solo se consultan si el área toca el Perú. Fuera, no se llama a ningún servicio peruano (devolvería un cero que se leería como ausencia) y una sola brecha lo declara con el país. Las brechas fijas que nombran instituciones peruanas tampoco se muestran.
- **Búsqueda de lugares:** `GET /api/v1/world/places` con el geocodificador de Open-Meteo. Solo ubica el sitio.
- **Alertas del mundo (`orchestration/world_alerts.py`, `GET /api/v1/world/alerts`):**
  - «Apoyo urgente» no lo decide la plataforma: se usa el nivel de GDACS (ONU y Comisión Europea). Naranja y roja en el mundo; en el Perú también las verdes de inundación, sequía, incendio, ciclón y erupción, las ocho más recientes.
  - Segundo testigo: NASA EONET. Mismo tipo, a 150 km o menos (600 km en ciclones) y con fechas a 10 días o menos.
  - Los eventos abiertos de EONET sin pareja en GDACS se listan sin nivel. Sus incendios solo sirven para el cruce: eran 395 de 400.
  - Vigencia de una hora y última copia válida si una fuente falla (ADR-044). Si GDACS cae, no hay niveles: no se inventan.
- **Pantalla:** botón «Alertas en el mundo» sobre el mapa. Cada evento es un pulso con el color de su nivel; laten los vigentes y los de nivel naranja o rojo, y la animación se detiene con «reducir movimiento». El panel filtra Mundo o Perú y, por evento, ofrece «Analizar amenazas aquí» y «Analizar clima aquí». Sobre el editor de sitios, «Buscar un lugar del mundo».

**Lo que no es.** No es un sistema de alerta temprana. Analizar el punto de un evento muestra las tendencias y amenazas de fondo del lugar, no el estado del evento. Fuera del Perú no hay territorios oficiales (departamento, provincia, distrito), ni capas nacionales de riesgo, patrimonio o áreas protegidas, ni validación con producción real.

**Resultado real del 10-nov-2026.**
- 25 eventos: 4 alertas rojas (ciclones en la India, Filipinas y México), 14 naranjas (sequías en Europa, Centroamérica y África, sismos, erupciones e inundaciones), 3 tormentas abiertas de EONET y 4 alertas verdes del Perú (tres inundaciones y un incendio forestal). Ningún evento coincidió entre las dos fuentes ese día.
- Atlas Eólico fuera del Perú: Nairobi 3.61 m/s frente a 6.36 de NASA POWER; Sevilla 4.47 frente a 6.10. En esos dos puntos NASA POWER queda por encima del atlas, al revés que en Marcona.
- Amenazas en Chennai: tres capas de NASA y la brecha de capas nacionales, sin ninguna consulta a servicios peruanos.

**Ampliación del 11-nov: globo 3D y marcadores de bloques.** Pedido de Christian: vista 3D y una animación «tipo juego, que no sea pesada».
- **Globo:** al mostrar las alertas el mapa pasa a la proyección de globo de MapLibre 6.15 (sin dependencias nuevas), con atmósfera, empezando sobre Sudamérica. Gira despacio hasta que la persona toca el mapa, y nunca con «reducir movimiento». «Quitar del mapa» vuelve al plano. El botón de globo de MapLibre (arriba a la derecha) cambia la vista en cualquier momento.
- **Bloques:** cada evento es un cubo de píxeles con biselado que salta en pasos discretos, con su sombra y un marco cuadrado que se expande. Es CSS puro (transform y opacity), sin modelos 3D ni texturas. Es la estética genérica de los juegos de bloques, sin los gráficos de ningún juego concreto. «Pulsos» deja los anillos anteriores.
- Los marcadores del otro lado del planeta se ocultan: con el globo sobre Sudamérica se ven 8 o 9 de los 25 eventos.
- `world_ui.cjs` en 1440, 768 y 390: globo activo, 25 bloques (21 saltando), el bloque del Perú a la vista al elegirlo, sin recortes, desbordes ni errores de consola. En 390 px el panel abierto tapa casi todo el globo: se cierra con «Cerrar» y los bloques siguen.

**Verificación.** 10 pruebas nuevas (276 en total): país de un punto con costa y mar abierto, analizadores de GDACS y EONET, cruce y regla de pareja, última copia válida del GET común, fuente caída declarada, búsqueda de lugares y área fuera del Perú sin consultas peruanas. Build con 22 rutas. `scripts/qa/world_ui.cjs` en 1440, 768 y 390: 25 pulsos en su lugar, sin recortes, desbordes ni errores de consola.
## ADR-047 — «Entrar a la zona»: maqueta en bloques de un lugar real que se recorre a pie

**Fecha:** 2026-11-11. **Estado:** aceptado. **Pedido de Christian:** desde las alertas del globo, elegir un lugar, «entrar» y recorrerlo como en un juego de bloques para ver cómo apoyar su desarrollo. Alcance acordado para la entrega: dos zonas, Moquegua (Perú) y el volcán Taal (Filipinas).

**Decisión.**
- **Qué es:** una maqueta. Cada celda es una columna de bloques cuya altura sale de **Copernicus DEM GLO-30** y cuyo material sale de **ESA WorldCover 2021** (píxel más cercano al centro de la celda, sin interpolar). No reproduce edificios ni calles: los árboles y los volúmenes claros solo señalan celdas que WorldCover clasifica como arboladas o construidas.
- **Qué no es:** no es una vista del lugar ni una simulación del evento. Una persona de 1.7 bloques mide en la maqueta lo que 50 m en el terreno.
- **Relieve exagerado y declarado:** ×2 en Moquegua y ×3 en el Taal, para que se lea con celdas de 30 y 35 m. La pendiente se calcula **antes** de exagerar (Horn sobre las elevaciones reales) y la consola muestra la altitud real bajo los pies del jugador.
- **Agua plana:** cada celda de agua baja a la elevación de agua más baja de su vecindario de 5 × 5, que quita el ruido del modelo de elevación sobre lagos; el agua no tiene pendiente.
- **Sin dato no es terreno:** una celda sin elevación queda como «Sin dato» en la cobertura y no se presenta como medida.
- **Balizas:** cada una es un resultado real de la plataforma pedido a la API local al construir la zona (`scripts/zones/build_zones.py`): cifra, fuentes, qué dice la segunda fuente, qué mirar primero y por qué la baliza está en ese punto. Si un resultado no llega, la baliza no se crea. Varias balizas tienen ubicación ilustrativa porque su dato es de una celda de unos 55 km: la ficha lo dice.
- **Zonas construidas de antemano** (`backend/data/zones/*.json`, unos 215 KB cada una), servidas por `GET /api/v1/world/zones` y `/world/zones/{id}`. No se construyen zonas a pedido: una zona nueva se agrega al guion y se versiona.
- **Pantalla:** three.js 0.186.0 (única dependencia nueva), cargada solo al entrar. Una malla para el terreno con las caras a la vista, mallas instanciadas para árboles, volúmenes y vía, colores planos, sin texturas ni sombras. Teclado y mouse, arrastre con el dedo en pantallas táctiles, vuelo con F, vista «Pendientes» y teclas 1 a 6 para ir a cada baliza. La lista de hallazgos repite toda la información con botones, y es lo único que se muestra si el equipo no puede iniciar los gráficos 3D.
- **Estética:** genérica de juego de bloques; no usa gráficos, personajes ni nombre de ningún juego.

**Resultado real del 11-nov-2026.**
- **Moquegua** (6 × 6 km, 200 × 200 celdas de 30 m, 1,262 a 1,666 m s. n. m.): el 15 % de la maqueta supera los 15° y la celda más empinada tiene 43°. Seis balizas: laderas; el día de 300.2 mm de MERRA-2 en 2022 que IMERG (12.1 mm) y CHIRPS (17.4 mm) desmienten; calentamiento de 0.33 °C por década confirmado por ERA5; recurso solar de 6.58 kWh/m² por día con VAN de −3.08 millones de dólares con los supuestos por defecto; riesgo de inundación del distrito según CENEPRED (última copia válida, ADR-044); y el arranque del corredor Moquegua–Ilo (tramo de 21.6 km, 5.º de 5 en prioridad).
- **Volcán Taal** (7 × 7 km, celdas de 35 m, 3 a 296 m s. n. m., cuatro teselas del modelo de elevación): el 11 % supera los 15° y la celda más empinada tiene 69°, en la pared del cráter. Cinco balizas: laderas; la erupción con alerta naranja de GDACS del 8-oct-2026, sin pareja en NASA EONET; susceptibilidad a deslizamientos de NASA en 13 puntos a 3 km del cráter (5 baja, 2 moderada, 3 alta, 3 muy alta) sin reportes en COOLR; lluvia máxima diaria media de 114.6 mm sin tendencia; y la brecha: el mapa oficial de peligro volcánico de Filipinas no está conectado.

**Limitaciones.** GLO-30 es un modelo de superficie: en ciudad y bosque incluye techos y copas. WorldCover es de 2021 y asigna una clase dominante por píxel de 10 m, que aquí se muestrea cada 30 o 35 m. La maqueta no sirve para medir distancias de evacuación ni para ubicar obras. Las cifras de las balizas tienen la fecha de construcción de la zona, no la del día en que se recorre.

**Licencias.** Las zonas versionan un dato derivado de GLO-30 y de WorldCover: la pantalla muestra el aviso de dato adaptado de Copernicus y el crédito CC BY 4.0 de WorldCover en «Sobre esta maqueta», y el crédito de OpenStreetMap junto a la vía. Queda por confirmar, antes de publicar el repositorio, que la licencia completa de GLO-30 permite redistribuir la cuadrícula derivada (ver `DATA_SOURCES.md`).

**Verificación.** 8 pruebas nuevas sin red (284 en total): cuadrícula cuadrada en metros, pendiente de una rampa conocida, bloques sobre el punto más bajo, pendiente igual con y sin exageración, celda sin dato, agua plana, coherencia de las dos zonas con su cuadrícula y rutas de la API con identificadores inválidos. `scripts/qa/zone_ui.cjs` en 1440, 768 y 390: del globo a la zona, caminar, seis fichas, vista de pendientes, salida al globo y enlace directo `/zona/taal`, sin recortes, desbordes ni solapes.
