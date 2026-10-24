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
