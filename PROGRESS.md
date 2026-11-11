# Estado del proyecto

Última actualización: 2026-11-10 (el estado vigente está en la última sección; lo anterior se conserva como historial)

## Versión operativa verificada

- Backend FastAPI con contratos Pydantic y documentación OpenAPI.
- Orquestador `POST /api/v1/projects/solar-screening` para ejecutar el caso solar de extremo a extremo.
- Consulta multiparámetro real a NASA POWER con caché de 24 horas, timeout y procedencia `REAL_DATA` / `CACHED_DATA`.
- Serie temporal anual real expuesta por la API y representada por sitio después de cada consulta.
- Mapa base contextual NASA EOSDIS GIBS Blue Marble, identificado como producto visual estático y no como evidencia analítica actual.
- Consulta pública a NASA CMR para localizar NASADEM HGT y SC por sitio, con procedencia, colección, resolución, CRS y vista previa oficial trazables.
- Pipeline visible de nueve pasos: selección, configuración, extracción, análisis, inteligencia territorial, evaluación, impacto económico, resultados y exportación.
- Medias anuales, Mann–Kendall, pendiente de Sen, p-value, intervalo de confianza y diagnóstico de autocorrelación lag-1.
- Corrección Benjamini–Hochberg para comparaciones de tendencias entre ubicaciones.
- Ordenamiento relativo por irradiancia media histórica con regla explícita, sin puntajes compuestos arbitrarios.
- Proyección de energía y VAN calculados solamente con supuestos editables del usuario.
- Interfaz Next.js 16 en español con mapa MapLibre, gráficos Recharts, comparativas, oportunidades, cautelas y brechas accionables.
- Exportación del reporte estructurado en JSON.
- Validación y métricas geodésicas WGS84 para geometrías GeoJSON de punto, corredor y polígono.
- Siete módulos del prompt representados con estados diferenciados y honestos.
- Docker Compose aislado de MyFix en los puertos 3100 y 8000.

## Evidencia de integración real

- Una ejecución NASA POWER 2019–2023 recuperó 1,826 observaciones diarias por variable y ubicación para Moquegua y Arequipa.
- El recorrido visual 2001–2024 representó 24 medias anuales reales por sitio en la gráfica temporal.
- El pipeline produjo nueve estados trazables: ocho completados y el paso de inteligencia territorial marcado como parcial.
- El resultado comparativo ubicó a Moquegua primero por irradiancia media histórica (6.5716 kWh/m²/día) y Arequipa segundo (6.5592 kWh/m²/día).
- Las cifras económicas resultaron negativas bajo los supuestos iniciales, demostrando que el sistema no fuerza una conclusión favorable.
- Consulta real CMR verificada para Moquegua (`s18w071`) y Arequipa (`s17w072`) en NASADEM HGT y SC; sin credencial, la respuesta declara `METADATA_ONLY` y `DATA_UNAVAILABLE` para las métricas raster.
- Suite backend: 16/16 pruebas aprobadas, incluidas la orquestación completa del screening, la selección de teselas NASADEM y la prohibición de sustituir un fallo NASA por datos ficticios.
- Compilación de producción Next.js y TypeScript aprobada.
- Auditoría npm: 0 vulnerabilidades conocidas.
- Recorrido funcional en navegador aprobado: interfaz y resultados en español, pipeline completo, mapa, gráficos, brechas y control de exportación sin errores de consola.
- Diseño adaptable verificado a 375 px de ancho sin desbordamiento horizontal.

## Sistema de calidad con Agent Skills

- Cuatro Skills oficiales de `openai/plugins`, plugin `build-web-apps` 0.1.2, instaladas globalmente y comparadas con la copia oficial auditada: `frontend-app-builder`, `frontend-testing-debugging`, `react-best-practices` y `shadcn-best-practices`.
- Cinco Skills especializadas, versionadas en `.agents/skills/`: `nasa-earth-data`, `geospatial-engineering`, `statistical-trend-analysis`, `infrastructure-investment` y `scientific-quality-assurance`.
- Las nueve Skills pasan `quick_validate.py`; las cuatro oficiales presentan cero diferencias de contenido después de normalizar finales de línea de Windows.
- `AGENTS.md` define estándares permanentes de arquitectura, procedencia, validación científica, seguridad, pruebas, navegador y reproducibilidad.
- El auditor científico del proyecto finaliza con `ok: true`, sin errores ni advertencias.
- Validadores especializados ejecutados con casos reales y controlados: respuesta NASA POWER, GeoJSON válido e inválido, tendencia Mann–Kendall/Sen, VAN y auditoría integral.
- Frontend verificado en navegador a 1440×900 y 390×844: edición de supuestos, pipeline completo, dos resultados, cinco brechas, cero overflow y cero errores de consola.
- Se corrigió el desplazamiento de resultados en móvil para que la cabecera fija no oculte el identificador reproducible.
- `supabase-best-practices` no se instaló porque el repositorio no utiliza Supabase.

## Plan operativo y DOP neuronal (documentos internos, fuera de la app)

- Desde el 2026-10-22 el DOP y el plan operativo no se sirven en `localhost:3100`: son documentos internos de seguimiento y viven en `docs/interno/`. La vista React `/dop-neuronal` se retiró (queda en el historial de git); el tracker HTML conserva los 18 nodos, dependencias, bloqueos, salidas y puertas de aceptación.
- Tracker HTML en `docs/interno/dop-neuronal.html`, con vistas de dependencias, ruta crítica y backlog priorizado; persiste seguimiento en `localStorage`, exige evidencia para `VERIFICADO` y permite importar/exportar un JSON versionado.
- La siguiente acción se calcula a partir de predecesores verificados y prioriza la ruta crítica; los filtros combinan texto, estado, fase y trabajo ejecutable sin alterar los datos guardados.
- La ruta crítica conecta fuentes faltantes, armonización espacial, PostGIS/muestreo, etiquetas reales, splits sin fuga, baseline, candidatos neuronales y gate humano.
- El nodo NASADEM figura `EN_CURSO`: metadatos y preview están integrados; la validación de celdas HGT/SC queda bloqueada hasta configurar Earthdata Login.
- Hoja de ruta interactiva en `docs/interno/plan-operativo.html` (ya no enlazada desde la aplicación).
- Ocho fases con objetivo, insumos, tareas, resultado, dependencias y criterio de aceptación verificable.
- DOP neuronal con fuentes, procedencia/QA, ingeniería de características, baseline, modelos candidatos, incertidumbre, explicabilidad, revisión humana y exportación.
- Las redes neuronales se muestran como `FUTURO — NO IMPLEMENTADO`; requieren etiquetas confiables, dataset versionado y demostrar mejora fuera de muestra frente a baselines simples.
- Interacciones de fases y modelos verificadas mediante teclado y navegador; escritorio 1440×1000 y móvil 390×844 sin desbordamiento ni errores de consola.
- Tracker verificado en navegador a 1440, 768 y 390 px: 12 pasos críticos, 18 filas de backlog, cuatro nodos ejecutables iniciales, filtros combinados, puerta de evidencia y cero errores de consola.
- La referencia visual se conserva en `docs/design/plan-operativo-concept.png` y la decisión arquitectónica en `ADR-007`.

## Rediseño premium verificado

- La interfaz principal ahora es un Earth Intelligence Workspace operativo, no una landing page.
- Mapa central, procedencia, controles, pipeline, evidencia y decisión comparten una jerarquía técnica coherente.
- Public Sans e IBM Plex Mono se sirven con `next/font`; no dependen de fuentes del sistema del visitante.
- En móvil existe una barra persistente de cuatro destinos y acceso “Más” a los siete módulos.
- El drawer móvil gestiona `inert`, `aria-hidden`, foco inicial, retorno de foco y cierre con Escape.
- Cambiar a un módulo pendiente elimina el resultado solar previo para evitar atribución errónea.
- Recorrido funcional aprobado a 1440, 768 y 390 px. La auditoría visual automatizada más reciente conserva cuatro hallazgos de estilo preexistentes —microetiquetas, texto menor de 11 px, proximidad al borde y ausencia de `h1` en el workspace— como backlog explícito para la siguiente rama de diseño.
- Auditoría, prompt visual, capturas y fidelity ledger están en `docs/design/`.

## Pulido de consola (rama `claude/diseno-consola`)

- La lectura comparativa ordena los sitios (Arequipa 1.º con 6.616 y Moquegua 2.º con 6.602 kWh/m²/día; diferencia de 0.2 %) y muestra el VAN junto a los supuestos con que se calculó.
- La serie anual tiene leyenda por sitio y un eje vertical ajustado y declarado; las unidades se presentan en español.
- Masthead de 89 px con `h1`; el paso parcial del pipeline es visible; en móvil la lectura encabeza el banco tras ejecutar.
- Verificado con Playwright a 1440, 768 y 390 px: sin overflow, sin errores de consola, edición de supuestos y cambio de variable comprobados.

## Pipeline v2 y preguntas del reto NASA

- Las nueve etapas derivan su estado y su evidencia de la ejecución real (ADR-012); el inspector de la interfaz muestra resumen, evidencia, procedencia, tiempo y preguntas que sustenta cada etapa.
- La respuesta incluye `nasa_questions` y `trend_findings`. Con datos reales 2001–2024: la temperatura sube en Moquegua y Arequipa (+0.80 °C en Moquegua) y el viento baja en Moquegua; la irradiancia no muestra deriva. La significancia se marca con salvedades por autocorrelación lag-1 de 0.48 y 0.42.
- NASADEM se integra al orquestador; su fallo no bloquea el screening. El parseo de NASA POWER deja de bloquear el bucle (ADR-013).
- Backend: 20/20 pruebas, incluidas preguntas con y sin tendencia, caída de NASADEM y cobertura insuficiente.

## Datos hasta hoy y módulo climático (ola 1)

- Datos hasta hoy con la última fecha publicada por variable: meteorología hasta el 20-oct-2026 y radiación hasta el 31-jul-2026. Tendencias con años completos (2001–2025) y año en curso comparado aparte (ADR-017).
- Defecto de NASA POWER detectado y controlado: precipitación × 24 al incluir días recientes; se verifica y corrige en cada consulta, y queda registrado en la procedencia.
- Motor de extremos ETCCDI y endpoint `climate-screening` (ADR-018).
- Pantalla del Módulo 1 en 3100: lectura del año en curso por variable y sitio, pestañas de serie anual para RX1DAY, RX5DAY y CDD, tabla de los seis índices por sitio, método, preguntas NASA, PDF y JSON. QA Playwright (`scripts/qa/climate_ui.cjs`): 1440 y 390 px sin desborde ni errores de consola.
- Revisión científica de los resultados (ADR-019): la corrección de Hamed–Rao ya no reduce la varianza con autocorrelación negativa, y los años atípicos se marcan. Con datos reales hasta hoy quedan 5 de 20 pruebas significativas: temperatura sube en ambos sitios (fuerte), viento baja en ambos (moderada) y la lluvia máxima de 5 días sube en Arequipa (moderada). La «lluvia máxima de 1 día fuerte en Moquegua» que se informó antes dependía de la corrección y se retiró. NASA POWER trae 314 mm en dos días en Moquegua (12–13 sep 2022), marcado para contrastar con estaciones.
- En 2026, Moquegua va como el 3.er año más cálido y el de menos viento del registro, y Arequipa lleva 39 % más lluvia que el promedio del mismo período.
- Escenarios y sensibilidad del VAN (ADR-020): campo aditivo `financial_sensitivity` en el sobre C2 y motor genérico `finance/sensitivity.py`. En el piloto solar: escenarios base, adverso y favorable; tornado con seis factores, donde el recurso usa los percentiles 10–90 observados; equilibrios de precio, CAPEX e irradiancia. Rangos editables en «Supuestos financieros», panel en pantalla y sección en el PDF. Con los supuestos por defecto, el VAN es negativo en ambos sitios (−USD 3.0 M) y positivo solo en el escenario favorable. Para VAN positivo hace falta un precio de unos 64 USD/MWh o un CAPEX de unos USD 15 M; ningún año observado alcanza la irradiancia de equilibrio. QA `scripts/qa/sensitivity_ui.cjs`: 1440 y 390 px sin desborde ni errores.
- Backend: 77/77 pruebas, con contraste del VAN contra `verify_cashflow.py` y del precio de equilibrio contra la fórmula cerrada.
- Corredores y polígonos: dibujo y carga de GeoJSON en Infraestructura e Inversión, con validación y medición geodésica y exportación para K1. La longitud coincide con un Vincenty independiente (0.00003 %).
- GPM IMERG activo como contraste de los extremos (ADR-021): desmiente el atípico de 314 mm de Moquegua 2022 (IMERG: 0 mm) y no respalda la tendencia de RX5DAY en Arequipa. Ninguna tendencia de extremos de lluvia es robusta todavía. Backend: 85/85.
- Puntaje multicriterio (ADR-022, ola 2): escalas declaradas, pesos editables, estabilidad con 2 000 combinaciones de pesos y empate práctico. Arequipa 67 frente a Moquegua 66: empate, honesto. Backend: 92/92.
- Asistente C4 (ADR-023): reglas sin costo por defecto; Gemini solo a pedido y con verificación de cifras. Backend: 107/107.
- Pendientes de K1b (Codex): AppEEARS (falta usuario y contraseña de Earthdata en `.env`), capas Perú (CENEPRED, SERNANP y Osinergmin responden; INGEMMET, Cultura y SENAMHI por ubicar) y generación COES.

## Contrato común entre sectores (C2)

- `ScreeningEnvelope` v1.0 con esquema y ejemplo real en `docs/coordination/contracts/` (ADR-015); la respuesta solar lo cumple y sigue siendo compatible con la interfaz.
- Orquestación reutilizable para los pilotos vial e inmobiliario: extracción POWER + NASADEM, análisis Hamed–Rao + BH, constructores de etapas, `SectorLens` para la quinta pregunta y verificación `envelope_violations`.
- Backend: 29/29 pruebas, incluidas 5 de conformidad.

## Reporte PDF ejecutivo (C3)

- Botón «PDF ejecutivo» en la consola y `POST /api/v1/reports/executive-pdf`, genérico para cualquier sector (ADR-016).
- PDF de 3 páginas con datos reales: las cinco preguntas NASA en la portada, tendencias con minigráfico y recta de Sen, relieve NASADEM, pipeline, supuestos, brechas, método, fuentes con DOI y huella SHA-256.
- Verificado: 36/36 pruebas backend (el texto del PDF se lee con pypdf) y descarga real en navegador a 1440 y 390 px, con la etapa 9 en «Completado» y sin errores de consola.

## Fuentes ambientales, territoriales y etiquetas COES (rama `codex/fuentes-amenazas`)

- AppEEARS opera con tareas asíncronas de punto y área para MOD13Q1.061 (NDVI/EVI y VI Quality) y MOD44W.061 (agua y QA). El token Earthdata solo vive en memoria, se renueva ante vencimiento/403 y se revoca al terminar cada operación.
- La tarea real `975994a2-f686-4742-9805-714ad035c0c8` llegó a READY. Sus dos CSV se descargaron mediante el conector, coincidieron con los SHA-256 oficiales y expusieron los valores escalados y campos QA esperados para Moquegua.
- El endpoint territorial consulta puntos, corredores y polígonos en CENEPRED, SERNANP, Osinergmin GISEM y Cultura SIGDA usando intersección en EPSG:4326. Un resultado de cero entidades permanece neutral y nunca se convierte en «no existe riesgo/restricción».
- El conector COES consume el XLSX oficial `ExportarGeneracion` con `indicador=1`, un mes por pedido, pausa entre solicitudes y caché SHA-256. Suma directamente la producción diaria `TOTAL` en MWh por nombre exacto de central solar; no integra ni sustituye series. La contraprueba real de septiembre de 2026 encontró 17 centrales y reprodujo, entre otros, Clemesí 28,053.11 MWh y Rubí 37,891.41 MWh.
- El cruce de potencia instalada y coordenadas usa la capa Solar vigente de Osinergmin GISEM y calcula factor de planta solo con coincidencia exacta. GISEM devolvió 503 durante el QA del 23-oct-2026, por lo que esos campos quedan `DATA_UNAVAILABLE` sin ocultar la generación COES.
- La ruta vigente de NASA LHASA fue confirmada en Earthdata GIS (`LHASA_Hazard_Today`, WGS84, 30 arcsec, dos actualizaciones diarias). El conector permanece pendiente hasta verificar valores, nodata y muestreo.
- Puerta de la rama: 124/124 pruebas backend, build Next.js aprobado, auditoría npm con 0 vulnerabilidades y auditor científico `ok: true`; no se inició 3100/8000 ni se modificó `frontend/**`.
- INGEMMET permanece `DATA_UNAVAILABLE` porque la cadena TLS oficial no pasa validación estricta; SENAMHI tiene catálogo WFS accesible, pero aún falta seleccionar una capa de amenaza concreta. ANA, SENACE, Defensoría y comunidades siguen pendientes.

## Selector territorial K5 (rama `codex/territorio`)

- COD-AB Perú v01 del IGN vía OCHA/HDX incorporado bajo CC BY-IGO: 25 departamentos, 196 provincias y 1,873 distritos.
- Búsqueda por nombre/ubigeo, jerarquía departamento → provincia → distrito y geometría GeoJSON por territorio mediante tres endpoints tipados.
- Activos simplificados reproducibles: 92.655–98.587% menos vértices, con geometrías válidas y cambio de área geodésica ≤1%; cada archivo se verifica por SHA-256 al cargarse.
- Los trazos se declaran como referencia de 2015, sin distritos posteriores y sin valor catastral; no se presentan como límites actuales exhaustivos.
- Pruebas K5 aisladas: 5/5 con conteos, acentos, ubigeo, jerarquía, geometría, errores y TestClient, sin levantar 8000.
- Puerta completa K5: 112/112 pruebas backend, build Next.js aprobado, auditoría npm con 0 vulnerabilidades y auditor científico `ok: true`; no se modificó `frontend/**` ni se inició 3100/8000.

## Muestreo espacial K1 (ramas `codex/regional-sampling` y `codex/k1-multiyear`)

- Endpoint tipado para puntos, corredores, polígonos y territorios; acepta los GeoJSON exportados por Claude con `properties.kind`, `name` y `origin`.
- Corredores amortiguados en proyección azimutal equidistante local; polígonos subcelda declarados como punto; áreas mayores consultadas en NASA POWER Regional con un parámetro por pedido.
- Celdas deduplicadas por centro, series por celda conservadas, promedio y desviación estándar diarios ponderados por área geodésica de intersección, y faltantes nunca convertidos en cero.
- Ejecución real Moquegua: 9 celdas, cobertura 99.5833%, grilla devuelta 0.5° lat × 0.625° lon, `REAL_DATA`. Ejecución real La Punta: 0.773019 km², modo `POINT`, una celda.
- El límite operativo confirmado del endpoint Regional (máximo 366 días por solicitud) se resuelve dividiendo períodos largos por año calendario. Cada fragmento conserva caché cruda propia; la unión exige las mismas celdas y unidades, rechaza fechas o valores conflictivos y propaga `REAL_DATA` si al menos un fragmento se descargó de la fuente.
- Ejecución real multianual del 30-dic-2023 al 2-ene-2025: tres solicitudes oficiales, incluida una de 366 días para 2024, 6 celdas y 370 observaciones diarias agregadas continuas (`REAL_DATA`, POWER v2.10.1).
- Pruebas K1 aisladas: 7/7 en `test_spatial_sampling.py` y 12/12 junto con el análisis territorial; incluyen caché completa/mixta, renormalización diaria, duplicados, valor faltante, corredor, geometría inválida, fallo externo y límite espacial; sin iniciar 8000.
- Puerta completa de `codex/k1-multiyear`: 146/146 pruebas backend, build Next.js aprobado, auditoría npm con 0 vulnerabilidades y auditor científico `ok: true`; sin cambios en `frontend/**`, sin Gemini y sin usar 3100/8000.

## Piloto vial K2 (rama `codex/piloto-vial`)

- Endpoint tipado `POST /api/v1/projects/road-screening`, backend-only, compatible con `ScreeningEnvelope` v1.0 y sus nueve etapas.
- Corredor público Moquegua–Ilo calculado con OSRM sobre OpenStreetMap, ODbL 1.0, 89.157 km de ruta y cinco tramos contiguos; se declara que no es eje ni inventario oficial del MTC.
- Por tramo: NASA POWER diario para precipitación y temperatura, exposición espacial K1 del último año, NASADEM cuando está disponible e intersecciones de CENEPRED, SERNANP, Cultura e INGEMMET. Un cero de intersecciones no se presenta como ausencia de riesgo o restricción.
- Puntaje de prioridad con escalas y pesos explícitos, cobertura por faltantes y estabilidad. El extremo espacial que entra al score es el percentil 99 diario; RX1DAY se conserva para trazabilidad y se marca para contraste IMERG/estaciones cuando se separa de forma extrema del P99. El VAN de mitigación usa días y costo de interrupción, CAPEX, mantenimiento, fracción residual, tasa y horizonte etiquetados `USER_ASSUMPTION`.
- Sensibilidad con escenarios base/adverso/favorable, tornado y puntos de equilibrio mediante el motor común. El VAN fue contrastado con una suma descontada independiente.
- Ejecución real 2018–2023 conforme a C2: cinco series y exposiciones POWER disponibles; CENEPRED con intersecciones reales, SERNANP/Cultura con ceros neutrales, INGEMMET como brecha visible y las cinco lecturas NASADEM `READY`. El ejemplo reproducible está en `docs/coordination/contracts/road-screening-v1.0.example.json` y conserva cuatro brechas explícitas.
- QA real del tramo 2 en 2022: RX1DAY MERRA-2 = 286.58 mm/día (13-sep), P99 = 15.2508 mm/día. El score usa P99 y no deja que el máximo atípico ya refutado por IMERG en ADR-021 domine la prioridad.
- Pruebas K2 aisladas: 5/5, incluidas conformidad `envelope_violations == []`, VAN independiente, degradación honesta por faltantes, validación HTTP de geometría y protección frente al máximo atípico.

## Brechas prioritarias

0. ~~Confirmar las tendencias autocorrelacionadas con Mann–Kendall modificado~~ **Hecho (ADR-014):** Hamed–Rao como prueba de decisión; la tendencia de temperatura se confirma (p corregido 0.0016 en Moquegua y 0.0141 en Arequipa; factor 1.000) y el pre-blanqueo libre de tendencia coincide. El viento de Moquegua queda al límite (p BH 0.048).

1. ~~Renovar `EARTHDATA_TOKEN` y reautorizar LP DAAC~~ **Resuelto:** credencial renovada y validada por HTTP 206; vence el **22-dic-2026**. `s17w071`, `s18w071` y `s18w072` quedaron `READY` y en caché. Debe vigilarse la caducidad, sin exponer el token.
2. ~~Incorporar red eléctrica y subestaciones~~ **Fuente activa:** Osinergmin GISEM; falta calcular distancia y verificar capacidad de conexión.
3. ~~Añadir áreas protegidas~~ **Fuente activa:** SERNANP; faltan ecosistemas frágiles y el análisis normativo de restricciones.
4. Incorporar sensibilidad social y comunidades; Cultura SIGDA ya aporta la alerta arqueológica inicial, sin reemplazar CIRA ni debida diligencia.

5. Integrar GPM IMERG V07 y LHASA. AppEEARS MOD13Q1/MOD44W ya está verificado con descarga y QA reales.
6. ~~Implementar muestreo NASA a lo largo de corredores y polígonos~~ **K1 listo:** celdas regionales ponderadas por área, división multianual y series por celda.
7. ~~Construir los backends vial e inmobiliario~~ **K2 integrado y K3 listo** en `codex/piloto-inmobiliario`; la pantalla inmobiliaria corresponde a Claude/C5.
8. Añadir persistencia PostGIS, trabajos asíncronos y exportación PDF para análisis de mayor escala.

## Diagnóstico NASADEM `s17w071` (rama `codex/nasadem-s17w071`)

- CMR confirmó `NASADEM_HGT_s17w071` (`G2816776437-LPCLOUD`) y `NASADEM_SC_s17w071` (`G2816803398-LPCLOUD`) con nombres y rutas LP DAAC correctos; la tesela no está ausente ni mal identificada.
- El incidente del token anterior devolvió HTTP 401 en ambos gránulos y también en teselas previamente accesibles, lo que descartó un problema específico de `s17w071`.
- El conector ahora distingue 401 («renueve el token») de 403 («autorice LP DAAC») y el log ya no atribuye el rechazo a un gránulo específico. El secreto nunca se imprime ni se cachea.
- La credencial renovada vence el 22-dic-2026. La validación autenticada devolvió HTTP 206 y descargó `s17w071`, `s18w071` y `s18w072`; Moquegua departamental quedó `READY` con 2,625 m, 18.61° y 110.99°. El piloto vial ya obtiene relieve `READY` en sus cinco tramos.
- Puerta del diagnóstico: 15/15 pruebas NASADEM y 146/146 backend; la nueva validación real usa `scripts/qa/nasadem_live.py`, sin levantar 3100/8000.

## Piloto inmobiliario K3 (rama `codex/piloto-inmobiliario`)

- Endpoint tipado `POST /api/v1/projects/real-estate-screening`, backend-only y conforme a `ScreeningEnvelope` v1.0. Acepta de uno a doce Polygon/MultiPolygon WGS84 del usuario o referencias oficiales IGN por nivel/ubigeo; cada entrada resuelve un punto interior, área geodésica sin redondeo y procedencia. Los 12 territorios MultiPolygon del catálogo están cubiertos.
- Por terreno: NASA POWER diario (`PRECTOTCORR`, `T2M`), P99 espacial K1 del último año, NASADEM, CENEPRED, SERNANP, Cultura e INGEMMET. Los faltantes quedan `DATA_UNAVAILABLE`; cero intersecciones no se traduce a cero riesgo.
- VAN condicionado con fracción desarrollable, edificabilidad, precio, obra, suelo, mitigación, costo comercial, absorción, tasa y horizonte etiquetados `USER_ASSUMPTION`. Incluye base/adverso/favorable, tornado y equilibrios mediante el motor común.
- Scorecard de seis criterios con cobertura: P99, pendiente, alertas de amenaza, alertas de restricción, VAN/inversión inicial y fracción desarrollable. Las fuentes incompletas eliminan el criterio relacionado en vez de imputar cero.
- Ejecución real 2018–2023 para tres áreas de análisis no catastrales cerca de Moquegua, Samegua y Cerro Colorado: POWER/K1 disponibles, tres NASADEM `READY`, CENEPRED/SERNANP/Cultura consultados e INGEMMET visible como brecha. Contrato reproducible en `docs/coordination/contracts/real-estate-screening-v1.0.example.json`.
- Recalculo independiente de área WGS84 y flujos descontados: diferencia de VAN menor a USD 0.003 en los tres terrenos.
- Salvaguarda de escala: sobre 2 km² (200 ha), el terreno se declara área de análisis y el VAN no se presenta como VAN de proyecto; la cautela aparece en el sujeto y en la quinta pregunta NASA. Un solo sujeto devuelve `margin=None`, `tie=False` y una nota de no comparación.
- Pruebas K3: 8/8; matriz cruzada Clima/Solar/Vial/Inmobiliario + PDF: 49/49; suite backend completa: 161/161. Build Next.js 16.4.2, auditoría npm (0 vulnerabilidades), auditor científico (`ok: true`), DOP y diff aprobados.

## Traspaso a Claude Code

- El incremento NASADEM y el mapa de desarrollo se cierran juntos para evitar que dos agentes editen simultáneamente `workspace.tsx`, `geo-map.tsx` y `styles.css`.
- El siguiente trabajo visual parte de `docs/design/CLAUDE_HANDOFF.md` y debe realizarse en una rama separada.
- La normalización de unidades, escala del gráfico, jerarquía del resultado, densidad de cabecera, etiqueta del paso 5 y orden móvil permanecen pendientes a propósito; no forman parte de la integración NASADEM.

## Riesgos y límites declarados

- NASA POWER utiliza estimaciones de grilla; no reemplaza mediciones in situ ni estudios de factibilidad.
- POWER puede aplicar límites de servicio; la caché reduce solicitudes repetidas, pero no elimina esa dependencia.
- NASADEM permite consultar metadatos y vistas previas mediante CMR público, pero los archivos analíticos HGT/SC permanecen protegidos por Earthdata Login.
- Mann–Kendall sin modificación puede verse afectado por correlación serial; cada resultado expone el diagnóstico lag-1 y la limitación.
- El orden relativo actual considera irradiancia histórica, no permisos, conexión, propiedad, CAPEX local ni impactos sociales.
- Ningún valor faltante se convierte en cero y ninguna capa pendiente se presenta como disponible.

## Baseline de entrega · cierre final 15 de noviembre de 2026

- `DATA_SOURCES.md` y `TECHNICAL_ARCHITECTURE.md` quedaron fijados el 24-oct-2026 como baseline de fuentes y arquitectura para `v0.1.0`.
- El manifiesto `docs/coordination/RELEASE_2026-11-15.md` define la evidencia, las brechas aceptadas, la puerta final y los comandos exactos de etiquetado.
- El 29-oct corresponde al anteproyecto de la sede. La entrega final cierra el 15-nov a las 23:59; la etiqueta anotada `v0.1.0` se crea únicamente entonces sobre el commit final aprobado.

## Estado vigente al 10 de noviembre de 2026

Los siete módulos funcionan sobre el contrato común C2, y cada dato satelital tiene una segunda fuente que lo comprueba. Lo que aparece al cruzarlas se registra como «descubrimientos» en la pantalla, el PDF y el asistente.

| Módulo | Estado | Contraste | Decisión |
|---|---|---|---|
| 1 · Clima | Funcional | ERA5 para temperatura, radiación y viento; GPM IMERG y CHIRPS para los extremos de lluvia | ADR-018, 019, 021, 036 y 038 |
| 2 · Energía solar | Funcional | ERA5 | ADR-038 |
| 2 · Energía eólica | Funcional | Global Wind Atlas; validada con la producción COES 2024 de Marcona | ADR-041 |
| 2 · Energía hidroeléctrica | Funcional | GEOGLOWS para el caudal y Copernicus para el salto; validada con la producción COES 2024 de Machupicchu | ADR-042 |
| 3 · Amenazas | Funcional | Deslizamientos de NASA frente a CENEPRED; IMERG y CHIRPS | ADR-034 a ADR-037 |
| 4 · Ambiente | Funcional | ESA WorldCover frente a MODIS | ADR-032, ADR-040 |
| 5 · Territorio | Patrimonio funcional | Sin segunda fuente; comunidades y conflictos siguen como brecha | ADR-032 |
| 6 · Infraestructura | Piloto vial funcional | Copernicus para el relieve, en los descubrimientos y en el puntaje | K2, ADR-043 |
| 7 · Inversión | Piloto inmobiliario funcional | Copernicus para el relieve, en los descubrimientos y en el puntaje | K3, ADR-043 |

- **Puerta al 10-nov:** 276 pruebas backend, build de Next.js con 22 rutas, `npm audit` en 0 y QA en navegador a 1440, 768 y 390 px.
- **Alcance global (ADR-046):** cualquier lugar del mundo en Clima, Energía, Amenazas y Ambiente; buscador de lugares; Atlas Eólico por país; capas oficiales solo en el Perú, declaradas fuera de él; «Alertas en el mundo» con los niveles de GDACS, NASA EONET como segundo testigo y pulsos animados en el mapa.
- **«Entrar a la zona» (ADR-047, 11-nov):** desde el panel de alertas, «Zonas para recorrer» abre una maqueta en bloques de Moquegua o del volcán Taal que se recorre a pie o volando. El relieve es de Copernicus DEM GLO-30 y el material de ESA WorldCover; las balizas muestran resultados reales de la plataforma con su segunda fuente. Es una maqueta con el relieve exagerado y declarado, sin edificios ni calles reales. Puerta al 11-nov: 284 pruebas backend, build con 25 rutas, `npm audit` en 0 y `zone_ui.cjs` a 1440, 768 y 390 px.
- **La validación con producción real se ve junto al método** de eólica e hidroeléctrica, en pantalla y en el PDF (ADR-045).
- **El puntaje dice si depende del modelo de elevación:** solar, eólica, vial e inmobiliario lo recalculan con la pendiente de Copernicus y declaran si cambia el primer lugar (ADR-043).
- **CENEPRED exige token desde el 10-nov:** sus capas se muestran desde la última copia válida, con la fecha de la copia y el motivo a la vista, solo donde ya se había consultado antes. En un sitio nuevo figuran como no disponibles (ADR-044).
- **Lo que falta para la entrega del 15-nov:** escenarios de demo, video, pitch y textos, QA de usuario y la puerta final con la etiqueta `v0.1.0`. El detalle y las ideas para sumar están en `docs/equipo/pipeline.html`.
- **Brechas que siguen declaradas:** aforos y mediciones en sitio, comunidades y conflictos, emergencias viales reales, distancia a la red eléctrica, persistencia de ejecuciones.
