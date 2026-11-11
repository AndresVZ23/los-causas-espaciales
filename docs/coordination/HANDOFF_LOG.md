# Registro de traspaso Claude Code ↔ Codex

Solo se agregan entradas, de la más antigua a la más reciente. Formato: fecha · agente · rama · commit · entrega · evidencia · qué necesita del otro · bloqueos. El plan y el reparto están en `PLAN_CLAUDE_CODEX.md`.

---

## 2026-10-22 · Codex · master · 08be4ff

**Entrega:** integración NASADEM (CMR, preview, `METADATA_ONLY` sin token) y tracker del DOP.
**Evidencia:** 16 pruebas, build, npm 0 vulnerabilidades, auditor `ok: true`, CMR real s18w071 y s17w072.
**Para Claude:** backlog visual de 6 puntos en `docs/design/CLAUDE_HANDOFF.md`.

## 2026-10-22 · Claude · claude/diseno-consola · ver `git log -1 claude/diseno-consola`

**Entrega (3 commits sobre 08be4ff):**
1. Pulido de consola: los 6 puntos del backlog (ADR-010, ADR-011).
2. Pipeline v2: etapas con evidencia medida, `nasa_questions` y `trend_findings`, NASADEM dentro del orquestador (ADR-012); parseo de POWER sin bloquear el bucle (ADR-013).
3. DOP y plan operativo fuera de la app: movidos a `docs/interno/` y retirada la vista React `/dop-neuronal`, por decisión de Christian.

**Evidencia:** 20/20 pruebas backend, build aprobado, npm 0 vulnerabilidades, auditor `ok: true` sin advertencias, recorrido con Playwright a 1440/768/390 sin errores de consola ni desborde, ejecución real NASA POWER 2001–2024.

**Para Codex (X0), revisar en especial:**
- `backend/app/connectors/nasa/power.py` (es tuyo): lectura de caché con `asyncio.to_thread` y parseo con `date()` + `Observation.model_construct`. Medido: de 319 a 135 ms por sitio.
- `PipelineStatus.READY`: la exportación devuelve `LISTO` en lugar de `COMPLETADO` (cambio de semántica en la API).
- El frontend ya no llama a `/api/terrain`; usa `result.terrain`. La ruta sigue existiendo para la API.
- Si estás de acuerdo, fusiona en `master` y anota tu veredicto aquí. Luego arranca K1/K1b según el plan.

**Bloqueos:** ninguno para X0. Los pilotos dependen de las decisiones D1–D3 de Christian.

## 2026-10-22 · Claude · claude/mk-modificado · ver `git log -1 claude/mk-modificado`

**Entrega C1:** Mann–Kendall con corrección de Hamed y Rao (1998) como prueba de decisión y en el ajuste BH (ADR-014). `TrendResult` agrega `p_value_modified`, `variance_correction` y `autocorrelation_lag1_detrended` (cambio aditivo). Las preguntas NASA y la etapa 4 informan la corrección.
**Hallazgo con datos reales:** factor 1.000 en las 8 series. La autocorrelación bruta de la temperatura (0.48 y 0.42) era la propia tendencia; sin ella queda en 0.06 y 0.10. La temperatura se confirma (p corregido 0.0016 y 0.0141) y el pre-blanqueo libre de tendencia coincide. El viento de Moquegua queda al límite (p BH 0.048).
**Evidencia:** 24/24 pruebas, con referencias congeladas de `pymannkendall` 1.4.3 (no es dependencia; la suite pasa sin él), build, npm 0 vulnerabilidades, auditor `ok: true`, regresión en navegador sin errores.
**Para Codex:** esta rama nace de `claude/diseno-consola`; revisar ambas en X0. Toqué una línea de `api/routes.py` (`compare_sites` usa el p de decisión para BH). Revisar si estás de acuerdo.
**Siguiente de Claude:** C2, el contrato común `ScreeningEnvelope`, que desbloquea K2 y K3.

## 2026-10-22 · Claude · (sin rama: configuración local) · —

**D1 resuelta:** Christian creó su cuenta de Earthdata Login, generó el token y autorizó las aplicaciones (GES DISC y LP DAAC). El token está en `.env` (ignorado por git) y el contenedor `api` lo carga.
**Evidencia real NASADEM** (`POST /api/v1/terrain/points`): Moquegua `READY`, `REAL_DATA`, 1,420 m, pendiente 5.47°, orientación NO 315.1°, tesela s18w071. Arequipa `READY`, 2,316 m, 3.67°, SO 225.3°, tesela s17w072. El screening ya incluye las métricas: etapa 5 «2 de 2 sitios» y la brecha NASADEM desaparece.
**Para Codex (conector NASADEM, tuyo):** la primera descarga de las dos teselas tardó 350 s, pero el orquestador corta NASADEM a los 45 s (`TERRAIN_TIMEOUT_SECONDS` en `sectors/solar.py`). Al cancelarse, `_download` no captura `CancelledError`: el `.zip.part` queda huérfano y la siguiente consulta descarga desde cero. Para sitios nuevos de los pilotos, sugerencia: descarga en segundo plano o precarga, con reanudación (`Range`) o limpieza del `.part` ante cancelación. El orquestador seguirá declarando `DATA_UNAVAILABLE` mientras la tesela no esté lista. Pendiente también: validar IMERG con este token (K1b).
**Para Christian:** el token apareció completo en una captura dentro de la conversación con Claude; conviene revocarlo y generar otro en Earthdata, y pegarlo en la misma línea 6 de `.env`.

## 2026-10-22 · Claude · claude/contrato-sectores · ver `git log -1 claude/contrato-sectores`

**Token regenerado y verificado:** el contenedor `api` lo carga y Earthdata responde 206 a una lectura autenticada. Emitido el 22-oct a las 19:45 UTC, vence el 21-dic-2026.
**Entrega C2:** contrato `ScreeningEnvelope` v1.0 (ADR-015). Esquema, ejemplo real y guía en `docs/coordination/contracts/README.md`; piezas reutilizables en `backend/app/orchestration/` (`extraction`, `analysis`, `stages`, `conformance`); catálogo único de variables en `backend/app/core/variables.py`.
**Evidencia:** 29/29 pruebas (5 de conformidad), ejemplo real Moquegua–Arequipa con NASADEM `READY` y conformidad OK.
**Para Codex:**
- **Tu arreglo de descarga NASADEM:** `_extract_terrain` y `TERRAIN_TIMEOUT_SECONDS` se mudaron de `sectors/solar.py` a `backend/app/orchestration/extraction.py`. Cambia solo el conector; si necesitas otro límite o un modo «solo caché», pídelo aquí y lo ajusto. No edites `solar.py`.
- **Para K2/K3:** arma los pilotos con la guía del README del contrato y agrega su prueba de conformidad. El lente sectorial (`SectorLens`) va en tu módulo `sectors/road.py` o `sectors/real_estate.py`.
- Desde ahora trabajo en el worktree `Desktop\Codex\los-causas-claude`; la carpeta principal es tuya.
**Bloqueos:** ninguno. Siguiente de Claude: C3, el PDF ejecutivo sobre el sobre común.

## 2026-10-22 · Claude · claude/contrato-sectores · acuerdo de interfaz NASADEM asíncrona

Plan de Codex aprobado: descarga reanudable (`.part` + Range), renombrado atómico, bloqueo por tesela, precarga en segundo plano, reintentos y pruebas. Interfaz acordada para que el orquestador y la app no traten una descarga en curso como una falla:
1. `TerrainSiteResult.status` agrega `"PENDING"` (cambio aditivo en `schemas/terrain.py`, de Codex): tesela localizada en CMR con descarga en curso. `METADATA_ONLY` queda para «sin token o sin acceso».
2. `NasademConnector.points(sites)` responde rápido: `READY` si la tesela está en caché, `PENDING` si dispara o continúa la descarga en segundo plano. Nunca espera la descarga completa.
3. `NasademConnector.prefetch(points)` dispara la precarga sin esperar (para los pilotos K2/K3).
4. **Ya preparado por Claude** en esta rama: la etapa 5 cuenta las teselas `PENDING` («descargándose · vuelva a ejecutar»), la brecha NASADEM distingue «descarga en curso» de «sin token» y el panel de relieve muestra «Descargando tesela» en ámbar. Cuando el conector responda rápido, Claude reduce `TERRAIN_TIMEOUT_SECONDS` (en `orchestration/extraction.py`) a un tope solo para CMR.
5. El indicador del DOP es para seguimiento interno; el usuario lo ve en el panel de relieve de la app.
Codex: crea tu rama desde `claude/contrato-sectores` para tener `orchestration/extraction.py`, y toca solo `connectors/nasa/nasadem.py`, `schemas/terrain.py`, sus pruebas y el DOP.

## 2026-10-22 · Claude · claude/contrato-sectores · ver `git log -1 claude/contrato-sectores`

**Entrega C3:** PDF ejecutivo (ADR-016). `POST /api/v1/reports/executive-pdf` acepta cualquier `ScreeningEnvelope`, así que también servirá para K2 y K3 sin cambios. Botón «PDF ejecutivo» en la consola, vía `frontend/app/api/report-pdf/route.ts`.
**Cambio aditivo al contrato:** `TrendFinding.annual_series`, para graficar. `AnnualObservation` se mudó a `schemas/screening.py` (reexportada desde `schemas/pipeline.py`). Esquema y ejemplo regenerados.
**Dependencias nuevas** en `backend/requirements.txt`: `reportlab==4.2.5` y `pypdf==5.1.0` (solo pruebas), ambas BSD. **Al fusionar hay que reconstruir la imagen `api`** (`docker compose up -d --build api`); el Dockerfile no cambia.
**Evidencia:** 36/36 pruebas; PDF de 3 páginas con datos reales revisado visualmente; descarga en navegador a 1440 y 390 px con la etapa 9 en «Completado» y 0 errores de consola. Para no interrumpir tu stack, la prueba de navegador corrió en puertos temporales 8001/3101, ya apagados.
**Nota para tu revisión:** con caché caliente, la duración de la etapa 5 coincide con la de extracción porque el parseo de POWER (CPU) ocupa el bucle de eventos y NASADEM espera su turno. No afecta los resultados; tu conector asíncrono puede hacerlo más evidente o resolverlo.
**Siguiente de Claude:** C4, el asistente analítico (determinista por defecto). Necesita la decisión D4 de Christian para el modo con IA.

## 2026-10-22 · Claude · claude/contrato-sectores · aislamiento total del worktree

Por decisión de Christian, Claude trabaja solo en `Desktop\Codex\los-causas-claude`. Moví ahí todo lo que tenía afuera: scripts de QA (`scripts/qa/`, con Playwright propio en vez del de MyFix), evidencias (`.claude-qa/`, ignorada) y mis inspecciones de `.taste-skill/claude-*`, que ya no están en tu carpeta. El worktree tiene `.venv`, `node_modules`, `.env` y caché NASA propios; el build oficial con Turbopack ahora pasa allí.
**Para Codex:** en tu `.venv` quedan `reportlab` y `pypdf`, que instalé antes. No los quité porque `backend/requirements.txt` de mis ramas los requiere y puedes estar corriendo esas pruebas. Tu stack Docker y tu carpeta no tienen ningún otro cambio mío.

## 2026-10-22 · Christian (vía Claude) · cambio de roles

Claude es dueño del frontend, de lo visual y de lo que se sirve en `localhost:3100`; Codex pasa a soporte operativo. Detalle en `PLAN_CLAUDE_CODEX.md`, sección 2 («Roles vigentes») y sección 3 («Quién sirve el 3100 y el 8000»). Pendiente de Codex: apagar su stack sin borrar volúmenes y anotarlo aquí, para que Claude lo levante desde su carpeta.

## 2026-10-22 · Claude · claude/contrato-sectores · stack 3100/8000 servido desde la carpeta de Claude

Recibido el traspaso de Codex (`295c24b`, en `codex/nasadem-resumable`). Antes de levantar encontré el 3100 ocupado por un `next start` **mío**, que había quedado de una prueba anterior en la carpeta principal; lo apagué. Levanté `docker compose up -d --build` desde `Desktop\Codex\los-causas-claude`, con el mismo proyecto, los mismos puertos y el volumen `power-cache`. El token está cargado en la API (717 caracteres).
**Evidencia en el 3100 real:** pipeline con 8 etapas completadas, 1 parcial (territorial, con NASADEM 2 de 2 sitios) y exportación lista; enlaces etapa ↔ pregunta NASA; descarga del PDF ejecutivo a 1440 y 390 px; 0 errores de consola y 0 desborde.
**Para Codex:** cuando termines K0 en `codex/nasadem-resumable`, anótalo aquí; lo integro y redespliego. Verás el resultado en el 3100.

## 2026-10-22 · Claude · claude/contrato-sectores · DOP de la red neuronal v2

A pedido de Christian rediseñé el DOP interno (el HTML pasa a ser de Claude; `docs/architecture/NEURAL_DOP.md`):
- **Estado sincronizado con el repo:** ahora vive en `docs/interno/dop-datos.js` (esquema `los-causas-dop` v2). El HTML solo lo lee; se acabó el `localStorage` del tracker v1. Cada agente actualiza sus nodos y tareas con evidencia (`{ label, ref }`) y `updatedAt`/`updatedBy`.
- **Vistas:** DOP del proceso con simbología ASME, mapa de dependencias con trazado ortogonal y ruta crítica, definición de la red neuronal, plan y responsables, y backlog.
- **Red neuronal definida (propuesta, no implementada):** calibrador de rendimiento fotovoltaico. Predice el factor de planta mensual de centrales reales del sur del Perú desde NASA POWER, contra el baseline físico actual.
**Para Codex:**
- **K1b suma una verificación:** acceso, licencia y formato de la **generación mensual del COES por central fotovoltaica** (Moquegua, Arequipa, Tacna), con recortes e indisponibilidades. Son las etiquetas de la red; sin ellas el nodo `03B` sigue bloqueado.
- Mantén tus nodos en `dop-datos.js`: `01B` pasa a `VERIFICADO` cuando el contraste de celdas y K0 estén probados.
- `plan-operativo.html` sigue siendo tuyo.

## 2026-10-22 · Claude · claude/contrato-sectores · red de la plataforma y orquestación

El DOP ahora abre con la **red de la plataforma**: 16 entradas → capas A, B y C → 12 resultados, con 85 enlaces requeridos o enriquecedores (`platform` en `dop-datos.js`), y una vista de **orquestación** que calcula olas de trabajo por dependencias (`docs/architecture/NEURAL_DOP.md`).
**Para Codex:** mantén también el estado de tus unidades en `platform.units` (owner «Codex»), con la misma regla de evidencia. Para el demo del jurado, tus unidades de la ola 1 son: peligros geológicos e inundación, áreas protegidas, patrimonio, comunidades y conflictos, red vial, armonización espacial y catálogo de fuentes.
## 2026-10-22 · Codex · codex/nasadem-resumable · df128a0 · cambio de roles y traspaso operativo

**Recepción:** confirmado el cambio de roles decidido por Christian. Claude Code queda como único responsable de `frontend/**`, la experiencia visual y los servicios visibles en `localhost:3100` y `localhost:8000`. Codex queda como soporte operativo según las secciones 2 y 3 de `PLAN_CLAUDE_CODEX.md`.

**Operación:** ejecutado `docker compose down` desde la carpeta principal, sin `-v`. No quedaron contenedores activos ni puertos publicados por este stack. El volumen `los-causas-espaciales_power-cache` se conserva para reutilizar la caché NASA POWER y las teselas NASADEM.

**Compromiso operativo:** Codex no levantará servicios en los puertos 3100 ni 8000. Las verificaciones propias usarán `pytest`, `TestClient` o puertos temporales que se apagarán al terminar. Codex no editará el worktree `los-causas-claude` ni los archivos visuales reservados a Claude.

**Para Claude:** puede levantar el mismo proyecto Compose desde su worktree, con los mismos puertos y el volumen persistente compartido. La entrega K0 permanece en `codex/nasadem-resumable` (`df128a0`).

**Bloqueos:** ninguno para el traspaso.

## 2026-10-22 · Claude · claude/ola1-clima · datos hasta hoy y defecto de NASA POWER

**Integrado:** `master` local de Codex (`7a42125`, con K0) en `claude/ola1-clima`. 66/66 pruebas; NASADEM en caché 0.8 s y sitio nuevo (Ilo) `PENDING` en 2.4 s. El stack 3100/8000 corre con esto.
**Decisión de Christian:** datos **hasta hoy**, actualizados en cada consulta (ADR-017). Tendencias con años completos; año en curso comparado con la misma ventana. Última fecha publicada por variable: meteorología D-2, radiación CERES hasta el 31-jul-2026.
**Defecto de la API NASA POWER Daily v2.10.1:** si el rango incluye los días recientes, toda la serie `PRECTOTCORR` llega × 24 aunque declare mm/day (reproducible: 13-sep-2022 en Moquegua = 300.21 pidiendo hasta el 30-sep-2026 y 7205.04 hasta el 10-oct-2026). Lo controla `orchestration/extraction.py` con una ventana de referencia (corrige solo si la razón es 24 y lo registra en `SourceMetadata.quality_notes`). **No dupliques la corrección en el conector.**
**Para Codex:**
1. Sube `master` a GitHub (aprobado por Christian) y luego fusiona `claude/ola1-clima`.
2. En K2 y K3 usa fecha final = hoy y `extract_power` (ya incluye la verificación).
3. Operativo: precarga diaria de POWER y NASADEM para los sitios del demo (Moquegua, Arequipa, corredor y terrenos), para que el demo sea rápido y esté al día.
4. `DATA_SOURCES.md`: latencia por producto y el defecto ×24 con su evidencia. Prepara un borrador de reporte a NASA POWER; Christian decide si se envía.
## 2026-10-22 · Codex · master · 7a42125 · X0 y K0 integrados y verificados

**Entrega:** con aprobación explícita de Christian, `master` avanzó hasta `claude/contrato-sectores` (`7a43c10`, que contiene diseño, C1, C2 y C3) y luego fusionó `codex/nasadem-resumable` mediante `7a42125`. El único conflicto fue `docs/interno/dop-neuronal.html`; se conservó íntegramente la versión de Claude y el estado de K0 se registró en `docs/interno/dop-datos.js`.

**Puerta común sobre `master`:** 47/47 pruebas backend; 14/14 pruebas específicas NASADEM; build Next.js 16 aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; contraste estadístico independiente aprobado; GeoJSON WGS84 válido aceptado y latitud inválida rechazada.

**Evidencia NASA real:** consulta POWER Moquegua del 1 al 10 de enero de 2024 con 10 observaciones `REAL_DATA`; NASADEM Moquegua y Arequipa `READY`/`CACHED_DATA` en 470.6 ms. Una segunda implementación leyó directamente los ZIP, sin importar el backend: Moquegua 1,420 m, 5.47°, 315.12°; Arequipa 2,316 m, 3.67°, 225.3°.

**QA visual:** Browser cargó la consola temporal y ejecutó el análisis real, pero su captura y la interacción de descarga agotaron el tiempo interno; se usó el fallback Playwright versionado, reutilizando en modo lectura la dependencia instalada en el worktree de Claude. En 1440, 768 y 390 px: 0 px de desborde y 0 errores de consola. El PDF descargado en 1440 y 390 empieza con `%PDF`, pesa 59 KB y deja Exportación en `Completado`. Evidencia temporal: `C:\Users\USUARIO\AppData\Local\Temp\los-causas-master-qa-20261022-174509`.

**Operación:** las pruebas de navegador usaron únicamente 8001/3101 y ambos puertos quedaron apagados. No se tocó el stack de Claude en 3100/8000 ni se escribió en `los-causas-claude`.

**Para Claude:** integrar `master` o el merge `7a42125` en su rama de trabajo y redesplegar desde su carpeta. K0 ya expone `PENDING`, `prefetch`, reanudación HTTP Range, renombrado atómico, bloqueo/deduplicación por tesela y caché caliente subsegundo.

**Bloqueos:** ninguno para X0/K0. Siguiente frente de Codex: Ola 1, rama independiente para catálogo y conectores de fuentes territoriales.

## 2026-10-22 · Claude · claude/ola1-clima · Módulo 1 en pantalla y revisión científica (ADR-019)

**Entrega:** pantalla del módulo de Clima en 3100. Lectura del año en curso por variable y sitio, pestañas RX1DAY/RX5DAY/CDD en la serie anual, tabla de los seis índices ETCCDI por sitio, método, preguntas NASA, PDF y JSON. Proxy `frontend/app/api/climate-screening`. QA `scripts/qa/climate_ui.cjs`: 1440/390 px, 0 desborde, 0 errores, PDF 64 KB. El flujo solar sigue igual (`hoy_check.cjs`). 70/70 pruebas.
**Cambio estadístico (ADR-019):** Hamed–Rao con piso 1 en el factor n/n*. Con autocorrelación negativa ya no se infla la significancia. Retira la «lluvia máx. 1 día fuerte en Moquegua»: ahora quedan 5 de 20 pruebas significativas. Años atípicos marcados en `ExtremeIndexSummary.atypical_years` (z robusto > 10); no se excluyen.
**Hallazgo de datos:** NASA POWER (MERRA-2) trae 314.5 mm en Moquegua entre el 12 y el 13-sep-2022. Es valor del proveedor, no de nuestra corrección × 24. El corte del día cambia entre pedir una variable o varias (12-sep: 259.63 frente a 14.31 mm), pero la suma de los dos días es la misma.
**Para Codex:**
1. Fusiona `claude/ola1-clima` en `master` cuando Christian lo apruebe; corre la puerta común.
2. En la revisión, confirma con una implementación independiente que el piso de Hamed–Rao no altera las series con factor ≥ 1. Las pruebas congeladas de `pymannkendall` siguen pasando.
3. En `DATA_SOURCES.md` agrega el evento atípico del 12–13 sep 2022 y la diferencia de corte diario entre pedidos de una y varias variables. Averigua qué estándar de tiempo usa el conector.
4. Para K1 (fuentes territoriales): GPM IMERG es la contraprueba natural de los extremos. POWER la expone como precipitación diaria UTC con 3.5 meses de rezago en la versión Final.
## 2026-10-23 · Claude · claude/ola1-clima · escenarios y sensibilidad del VAN (ADR-020)

**Entrega:** el sobre C2 agrega `financial_sensitivity`; es aditivo, sigue en v1.0, y el esquema y el ejemplo se regeneraron con `export_contract.py` (conformidad OK). Motor genérico en `backend/app/finance/sensitivity.py` (`Driver`, `tornado`, `break_even`, `break_even_item`). Solar: rangos editables como supuestos y recurso desde los percentiles 10–90 observados. Panel con escenarios, tornado y equilibrios en 3100, y sección en el PDF. 77/77 pruebas. QA `sensitivity_ui.cjs`, `climate_ui.cjs` y `hoy_check.cjs` sin errores en 1440/390.
**Conformidad nueva:** si un sector llena `financial_sensitivity`, debe incluir los escenarios base y adverso, citar sujetos existentes y tener `base_npv` igual al escenario base.
**Para Codex:**
1. Fusiona con aprobación de Christian; corre la puerta común (`npm audit --omit=dev` ya da 0 vulnerabilidades en este worktree).
2. K2 y K3: definan sus `Driver` (vial: días de interrupción × costo diario, CAPEX de mitigación; inmobiliario: precio por m², absorción, costo de obra) y su función de VAN; `tornado` y `break_even_item` hacen el resto. Pantalla y PDF ya leen el campo.
3. Revisión independiente sugerida: rehacer el tornado solar con otra implementación a partir del ejemplo del contrato.

## 2026-10-22 · Codex · master · 13c1398 · Módulo 1 Clima fusionado y verificado

**Fusión aprobada:** `master` avanzó por fast-forward de `682eadd` a `claude/ola1-clima` (`13c1398`). La revisión cubrió el endpoint y contrato climático, los seis índices ETCCDI, la guarda de escala de precipitación y el cambio estadístico de ADR-019.

**Puerta común:** 70/70 pruebas backend aprobadas; build de producción Next.js 16.4.2 aprobado; `npm audit --omit=dev` con 0 vulnerabilidades. El auditor científico adicional terminó con `ok: true`, sin errores ni advertencias.

**Contraste Hamed–Rao independiente:** una implementación separada recalculó pendiente de Sen, rangos sin tendencia, ACF sesgada, rezagos significativos, S, varianza y p-valor para la serie congelada con factor mayor que uno. Resultado independiente y backend: factor `1.508421097`, p modificado `0.003042707546`; el piso no se activó. Se confirma que `n/n* ≥ 1` no altera esta clase de series.

**POWER Moquegua:** reproducción real contra Daily API v2.10.1 para `-17.193, -70.934`. En UTC: 14.31 mm (12-sep-2022) + 300.21 mm (13-sep-2022) = 314.52 mm. En LST/default: 259.63 + 54.88 = 314.51 mm. El conector fija `time-standard=UTC`, por lo que corta a las 00:00 UTC (19:00 del día anterior en Perú). Bajo coordenadas, fechas y estándar idénticos, una y varias variables devolvieron exactamente lo mismo: el efecto por cantidad de parámetros reportado antes no se reprodujo; la redistribución comprobada corresponde a UTC frente a LST. El defecto ×24 de rangos largos y recientes sí se reprodujo y queda cubierto por la guarda de extracción.

**Catálogo:** `DATA_SOURCES.md` registra el evento atípico, el resultado controlado sobre el corte, el defecto ×24 y GPM IMERG Final como contraprueba natural. Según la documentación oficial de POWER, la precipitación IMERG se ofrece diariamente en UTC y Final tiene aproximadamente 3.5 meses de latencia.

**DOP:** `o-climate` pasó de `LISTO_PARA_QA` a `VERIFICADO`, con evidencia de commit y puertas. `qa-core` registra el contraste independiente del piso Hamed–Rao.

**Operación:** pytest se ejecutó en un contenedor efímero sin red; no se reinició ni modificó el stack de Claude en 3100/8000. Bloqueo científico pendiente: contrastar el evento de 2022 con datos reales IMERG Final y, si están disponibles, estaciones SENAMHI dentro de K1b.

## 2026-10-23 · Claude · claude/ola1-clima · integración de master (8f7dbea) y corrección

**Integrado:** `master` de Codex (8f7dbea, Clima VERIFICADO) en `claude/ola1-clima`; el único conflicto fue la marca de actualización de `dop-datos.js`.
**Corrección:** Codex tiene razón. El reparto de la lluvia del 12–13 sep 2022 entre días depende de UTC frente a hora solar local, no de pedir una o varias variables. Mi consulta manual no fijaba `time-standard`. Corregido en ADR-019.
**Pendiente de fusión:** `4b1ac82` (escenarios y sensibilidad, ADR-020) y este merge.

## 2026-10-22 · Codex · master · 735a127 · ADR-020 fusionado y aprobado

**Fusión:** con aprobación de Christian, `master` avanzó por fast-forward desde `8f7dbea` hasta `claude/ola1-clima` (`735a127`), incluyendo escenarios y sensibilidad del VAN (`4b1ac82`) y la corrección de ADR-019.

**Revisión financiera independiente:** a partir de `screening-envelope-v1.0.example.json`, una implementación separada y sin imports del backend reconstruyó energía anual, flujo neto, descuento, VAN y cada perturbación univariada. Las doce barras de Moquegua y Arequipa coincidieron con el contrato dentro de USD 0.01; sus swings, dentro de USD 0.02; y el orden fue precio, CAPEX, tasa, performance ratio, OPEX y recurso. El precio cerrado de equilibrio fue 64.178680 USD/MWh en Moquegua frente a 64.1787 del contrato, y 64.038304 frente a 64.0383 en Arequipa.

**Puerta común:** 77/77 pruebas backend; build Next.js 16.4.2 aprobado; `npm audit --omit=dev` con 0 vulnerabilidades. El auditor científico terminó `ok: true`, sin errores ni advertencias.

**QA del 3100:** el navegador ejecutó el análisis solar real y cambió el tornado de Moquegua a Arequipa. Los escenarios, procedencias, equilibrio y barras respondieron; no hubo errores ni advertencias de consola. En el resultado vivo, el precio de equilibrio fue 64.40 USD/MWh en Moquegua y 64.28 en Arequipa; difiere levemente del ejemplo congelado porque la ejecución usa datos hasta hoy. En 1280 y 390 px no hubo desborde horizontal; se contrastó además la evidencia de Claude en 1440/390.

**Veredicto:** ADR-020 aprobado. `c-finance` pasa a `VERIFICADO`; el módulo de inversión general permanece `EN_CURSO` porque todavía falta la comparación multicriterio. K2 y K3 deben reutilizar `Driver`, `tornado` y `break_even_item` según el paso 5 del contrato.

**Operación:** no se inició, detuvo ni redesplegó el stack de Claude. Pytest se ejecutó en un contenedor efímero sin red. Con la autorización explícita de Christian y todas las puertas verdes, `master` queda aprobado para subir a GitHub.

## 2026-10-23 · Codex · codex/fuentes-amenazas · 994c670 · AppEEARS, capas Perú y etiquetas COES

**Entrega backend:** siete operaciones tipadas en OpenAPI: tareas AppEEARS de punto/área, estado, bundle y descarga; consulta territorial por punto/corredor/polígono; y generación mensual COES. AppEEARS conserva el token solo en memoria, renueva ante vencimiento/403, cierra sesión en `finally`, no reenvía el Bearer al CDN y verifica el SHA-256 oficial antes de guardar en caché. `.env.example` y Compose exponen las dos variables Earthdata sin valores. No se tocó `frontend/**`.

**Evidencia AppEEARS real:** tarea `975994a2-f686-4742-9805-714ad035c0c8` en `done`, bundle de siete archivos. MOD13Q1 CSV (1,775 bytes, SHA-256 `e6bb8c294237347f5ae0ace8351dc5a01034b320192107f63d01138bbf6a2040`) y MOD44W CSV (318 bytes, SHA-256 `c7466b67304c84f6e4bde6bb6e06e8b8788d4537854733e436f079e4d227b73b`) descargados y rehasheados. NDVI/EVI escalados y VI Quality decodificado; agua y QA presentes. El token no se registró ni se cacheó.

**Evidencia territorial real:** Moquegua punto, corredor Moquegua–Ilo y polígono Moquegua respondieron mediante CENEPRED, SERNANP, Osinergmin y Cultura. En corredor: CENEPRED inundación 5, Osinergmin 16, SERNANP 0, SIGDA 0; en polígono: 3, 3, 0 y 0 respectivamente, todos `READY/REAL_DATA`. Los ceros permanecen neutrales y no se interpretan como ausencia. INGEMMET queda `DATA_UNAVAILABLE` por TLS estricto y SENAMHI hasta seleccionar una capa WFS concreta.

**Evidencia COES real:** septiembre de 2026, 2,880/2,880 intervalos por serie. Rubí 37,891.383250 MWh; Intipampa 9,650.763435; Moquegua FV 3,717.629000; Majes 3,909.259913; Repartición 3,871.879248; Panamericana 4,685.059750. Una implementación independiente coincidió a 1e-6. Se conservaron los nombres exactos, sin sustituciones. El portal ofrece exportación pública, pero no publica una licencia abierta específica; `DATA_SOURCES.md` exige atribución y confirmación antes de redistribuir el archivo original.

**Puerta común:** 92/92 pruebas backend; build Next.js 16.4.2 aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; Compose válido; siete de siete rutas OpenAPI presentes; `git diff --check` limpio. Dos advertencias deprecadas de dependencias (ReportLab/Starlette), sin fallos.

**Operación y traspaso:** no se inició, detuvo ni utilizó 3100/8000 y no se escribió en `los-causas-claude`. Claude puede integrar `codex/fuentes-amenazas` y construir las pantallas. K1b permanece `EN_CURSO`: faltan IMERG, LHASA, ANA, SENACE, Defensoría, comunidades, red vial y resolver/seleccionar INGEMMET/SENAMHI. Rama sin fusionar ni subir; requiere revisión y aprobación de Christian.
## 2026-10-23 · Claude · claude/ola1-clima · dibujo y carga de corredores y polígonos

**Entrega:** módulos Infraestructura (corredores) e Inversión (terrenos) con panel «Geometrías de estudio».
- **Dibujo:** clic por vértice; termina con doble clic, Enter o «Terminar»; Escape cancela.
- **Carga de GeoJSON:** RFC 7946; rechaza `crs` no WGS84, coordenadas proyectadas, ejes latitud-longitud y anillos abiertos, sin reparar nada en silencio; separa las geometrías multiparte y lo declara.
- **Validación y medición:** `POST /api/v1/geospatial/inspect`, el endpoint de Codex, sin cambios en su backend.
- **Exportación:** FeatureCollection para K1.

**Verificación:** `scripts/qa/geometry_ui.cjs` en 1440/390 con 7 archivos límite. El GeoJSON exportado pasa `validate_geojson.py`. La longitud geodésica coincide con un Vincenty propio en 0.00003 %. El único error de consola es el 422 esperado del polígono autointersecado.
**Para Codex (K1):** el muestreo puede tomar el GeoJSON exportado (`properties.kind` = `segment`/`polygon`, `name`, `origin`, `length_km`, `area_km2`).
## 2026-10-23 · Claude · claude/ola1-clima · GPM IMERG activo y sondeo de las demás fuentes

**Activado (ADR-021):** GPM IMERG vía NASA POWER (`IMERG_PRECTOT`) como contraste de los extremos ETCCDI, con columna «Contraste GPM IMERG» en pantalla y valor IMERG junto a cada año atípico. IMERG desmiente el atípico de Moquegua 2022 y no respalda la única tendencia significativa de extremos (RX5DAY Arequipa). 85/85 pruebas.
**Sondeo de acceso del 2026-10-23, desde la máquina de Christian y solo lectura:**

| Fuente | Resultado |
|---|---|
| GES DISC (archivo IMERG diario V07) | 206 con el token: hay acceso directo, si se quiere 0.1° sin pasar por POWER |
| AppEEARS | Catálogo 200 (192 productos); `/api/task` con el token EDL da 403, porque exige `POST /api/login` con usuario y contraseña de Earthdata |
| CENEPRED SIGRID ArcGIS | 200 (carpetas sigrid, FEN, INDECI, VIVIENDA…) |
| SERNANP ArcGIS | 200 (gestion_de_anp, servicios_ogc) |
| Osinergmin GISEM | 200 (carpeta Electricidad) |
| COES portal | 200 |
| INGEMMET GEOCATMIN | Sin conexión |
| SENAMHI IDESEP | Timeout |
| Ministerio de Cultura (ruta probada) | 404 |
| NASA LHASA en NCCS | Sin conexión |

**Para Codex (K1b, con prioridad, pedido de Christian):**
1. AppEEARS: conector con `POST /api/login` (usuario y contraseña en `.env`, que Christian debe agregar) y tareas asíncronas de punto y área para NDVI/EVI (MOD13Q1.061) y agua superficial. Estado `PENDING` como NASADEM.
2. Capas Perú:
   - Primero las que responden: peligros de CENEPRED SIGRID, ANP de SERNANP y red eléctrica y subestaciones de Osinergmin GISEM, con consulta por punto, corredor y polígono.
   - Después, buscar los endpoints vigentes de INGEMMET (peligros geológicos), Ministerio de Cultura (SIGDA) y SENAMHI.
   - Registrar en `DATA_SOURCES.md` la licencia, la fecha, la escala y la cobertura de cada una.
3. COES: ubicar la descarga de generación por central (las centrales FV del sur), revisar los términos de uso y dejar series mensuales de etiquetas (`in-coes`) con su procedencia.
4. LHASA: confirmar la ruta vigente del servicio.
## 2026-10-23 · Claude · claude/ola1-clima · puntaje multicriterio (ADR-022, ola 2)

**Entrega:** `scorecard` en el sobre C2 (aditivo, con esquema y ejemplo regenerados y conformidad OK). Motor genérico `scoring/multicriteria.py` y endpoint `POST /api/v1/scoring/scorecard`. Panel con pesos editables, recálculo y aviso de empate práctico. Sección en el PDF. 92/92 pruebas. QA `scripts/qa/scorecard_ui.cjs` en 1440/390 sin errores.
**Para Codex (K2 y K3):** cada piloto define sus criterios (clave, dirección, peso, escala y fundamento) y llama a `build_scorecard`; la pantalla y el PDF ya lo leen. Vial: días de interrupción esperados, RX1DAY por tramo, pendiente, longitud expuesta. Inmobiliario: pendiente, extremos de lluvia, restricciones territoriales (sin dato no equivale a cero) y VAN.
## 2026-10-23 · Claude · claude/ola1-clima · asistente C4 (ADR-023, ola 2)

**Entrega:** panel «Pregunte al análisis» en Energía y Clima. Modo reglas sin costo por defecto; Gemini a pedido, con la clave de Christian solo en el `.env` de `los-causas-claude`. Endpoints `POST /api/v1/assistant/ask` y `GET /api/v1/assistant/status`. 107/107 pruebas. QA `scripts/qa/assistant_ui.cjs` en 1440/390 sin errores; nunca pulsa Gemini.
**Para Codex:** no hace falta `GEMINI_API_KEY` en tu carpeta. Si agregas preguntas tipo para K2 y K3, amplía `RULES` en `backend/app/assistant/context.py`. Cuando la puerta común corra el QA, que no use `use_gemini=true`.
## 2026-10-23 · Claude · claude/ola1-clima · DOP: territorio, capas visuales y COES verificado

**Decisión de Christian:** la consola deja de limitarse a Moquegua y Arequipa. Habrá un selector de departamento, provincia, distrito o zona propia, y capas visuales (temperatura del mar, viento, etc.). Ambas cosas entran al demo del jurado.
**DOP actualizado:**
- **Entradas:** `in-admin` (límites IGN) y `in-gibs` (capas GIBS).
- **Unidades:** `a-admin` (índice territorial), `b-celltrends` (tendencias por celda), `o-territory` (selector territorial) y `o-layers` (capas visuales).
- **Muestreo:** `a-sampling` ampliado a territorios.
- **Plan:** tareas K5, C6 y C7, también en `PLAN_CLAUDE_CODEX.md`.

**Verificado hoy:**
- **GIBS:** publica 1 353 capas. Para el Perú sirven `GHRSST_L4_MUR_Sea_Surface_Temperature` y `…_Anomalies`, `AMSRU2_Wind_Speed*`, `IMERG_Precipitation_Rate`, `MODIS_*_Land_Surface_Temp_*` y `MODIS_Terra_L3_NDVI_16Day`.
- **COD-AB Perú (IGN vía OCHA):** 25 departamentos, 196 provincias y 1 873 distritos, licencia CC BY-IGO, trazos de 2015 revisados en 2025. geoBoundaries no trae distritos.
- **POWER regional:** `/api/temporal/daily/regional` acepta un parámetro por pedido y devuelve grilla de 0.5°.

**COES (para K1b):**
- **Exportación pública:** `https://www.coes.org.pe/Portal/portalinformacion/ExportarGeneracion?fechaInicial=dd/mm/aaaa&fechaFinal=dd/mm/aaaa&indicador=1`. Con `indicador=1` usa medidores; con `0`, SCADA.
- **Formato:** devuelve un xlsx con la hoja «PRODUCCIÓN DIARIA» (FECHA, EMPRESA, GRUPO/CENTRAL, TIPO GENERACIÓN, TOTAL). El TOTAL es plausible en MWh/día: Clemesí 981, Intipampa 333; hay que confirmarlo.
- **Contenido:** trae las centrales solares del sur.
- **Términos:** el portal no publica términos de uso y no tiene `robots.txt`.
- **Mi prueba:** una sola descarga de un día, guardada en `.claude-qa/`.
## 2026-10-23 · Claude · claude/capas-territorio · capas visuales GIBS (C6, ADR-024)

**Entrega:** botón «Capas» sobre el mapa con las 8 capas GIBS, fecha, opacidad y leyenda oficial, en todos los módulos. Endpoint `GET /api/v1/map/layers`. 112/112 pruebas. QA `scripts/qa/layers_ui.cjs` en 1440/390: teselas reales 200, leyenda cargada, 0 errores de consola, sin desborde.
**Rama nueva** `claude/capas-territorio`, que parte de `2ec78b8`. La fusión de `claude/ola1-clima` sigue en pie; esta rama va después.

## 2026-10-23 · Codex · master · 63e0f36 · ola climática y capa de decisión fusionadas

**Fusión aprobada:** `master` integró `claude/ola1-clima` en `63e0f36`, cuyo extremo revisado es `2ec78b8`. Incluye ADR-020 (escenarios y sensibilidad), geometrías de corredores/polígonos, ADR-021 (contraste IMERG), ADR-022 (puntaje multicriterio), ADR-023 (asistente por reglas) y el DOP territorial. El único conflicto fue `docs/interno/dop-datos.js`; se conservaron el motor financiero previamente verificado y los nuevos estados de Claude.

**Puerta común sobre master:** 107/107 pruebas backend; build Next.js 16.4.2 aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias. Las dos advertencias de pytest pertenecen a deprecaciones de ReportLab y Starlette.

**Gemini y operación:** `GEMINI_API_KEY` está ausente en esta carpeta. Los dos casos `use_gemini=true` sustituyen `generate` por una función local y una clave ficticia; no hubo llamada externa ni consumo de cuota. No se iniciaron ni modificaron los servicios 3100/8000 y Codex no editó manualmente `frontend/**`.

**Veredicto:** incremento aprobado para `master` y para publicación. IMERG vía POWER, scorecard y C4 pasan a `VERIFICADO`; el acceso IMERG directo de 0.1° y el resto de K1b continúan como trabajo separado. Siguiente entrega Codex: reintegrar `codex/fuentes-amenazas` sobre este master, corregir COES al contrato XLSX `ExportarGeneracion` y confirmar LHASA antes de K5.

## 2026-10-23 · Codex · codex/fuentes-amenazas · 9cc815c · COES XLSX verificado y ruta LHASA confirmada

**Entrega backend K1b:** la rama fue actualizada con `master` y reemplaza el conector COES antiguo por el contrato oficial `ExportarGeneracion`: `indicador=1`, XLSX mensual secuencial con pausa, caché cruda SHA-256, límites de tamaño/descompresión, hoja `PRODUCCIÓN DIARIA`, filtro exacto `SOLAR` y suma de `TOTAL` por nombre de central. La unidad quedó confirmada como MWh en el portal oficial. El endpoint conserva todos los nombres COES; un plant-month ausente lleva generación nula, procedencia `DATA_UNAVAILABLE` y estado de serie `PARTIAL`, sin sustituciones.

**Evidencia real:** el parser se contrastó el 23-oct-2026 con el XLSX oficial de septiembre de 2026: 17 centrales solares, 30 días observados. Totales reproducidos: `CLEMESI` 28,053.11 MWh (981.01 el 01-sep), `RUBI` 37,891.41, `INTIPAMPA` 9,650.78, `MAJES` 3,909.25, `MOQUEGUA-SOLAR` 3,717.63, `PANAMERICANA-SOLAR` 4,685.06 y `REPARTICION` 3,871.90. La generación se etiqueta `REAL_DATA` y cita `COES-SINAC`.

**Cruce GISEM:** se agregó la capa oficial Solar de `MapaSEIN_Operacion` (20), WGS84, con potencia instalada/efectiva y coordenadas. Solo una coincidencia normalizada exacta habilita el factor de planta `MWh / (MW × 24 × días)`. El servicio devolvió ArcGIS 503 durante el QA real; por ello el contrato mantiene generación COES y marca capacidad/coordenadas/factor como `DATA_UNAVAILABLE`. No hubo coincidencias difusas. Los términos abiertos de COES siguen sin publicarse; el XLSX original no se redistribuye y queda pendiente el correo de cortesía de Christian.

**LHASA:** la ruta vigente quedó confirmada en NASA Earthdata GIS: `Landslides/LHASA_Hazard_Today/ImageServer`, con servicios Yesterday/Today/Tomorrow, EPSG:4326, 30 arcsec (~1 km), cobertura 60°S–60°N y actualización dos veces al día. Se documentó como ruta verificada, pero el conector permanece pendiente hasta validar significado de valores, nodata, timestamp y muestreo. No se presenta como estudio geotécnico local.

**Puerta:** 124/124 pruebas backend; 5/5 específicas COES (nominal, hoja inválida, caché/parámetros, error GISEM y central-mes faltante); build Next.js aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; DOP con sintaxis válida; ejecución real registrada. Sin secretos nuevos, sin llamadas Gemini, sin cambios en `frontend/**` y sin iniciar 3100/8000.

**Para Claude:** revisar e integrar `codex/fuentes-amenazas` cuando Christian lo apruebe. El contrato de `POST /api/v1/energy/coes/monthly-generation` ahora expone todas las centrales solares, `days_expected/days_observed`, `capacity_factor_percent` y `capacity_reference`; la interfaz debe aceptar `READY`, `PARTIAL` y `DATA_UNAVAILABLE`. K1b continúa por ANA/SENACE/Defensoría/comunidades y el conector LHASA; K5 queda como siguiente rama separada. Esta rama no fue fusionada ni subida.
## 2026-10-23 · Codex · codex/territorio · 2af9c55 · K5 índice territorial IGN/OCHA

**Entrega:** catálogo reproducible COD-AB Perú v01 con 25 departamentos, 196 provincias y 1,873 distritos; búsqueda por nombre o ubigeo, jerarquía departamento → provincia → distrito y geometría GeoJSON individual. Endpoints: `GET /api/v1/territories/search`, `GET /api/v1/territories/hierarchy` y `GET /api/v1/territories/{level}/{ubigeo}/geometry`. No se tocó `frontend/**`.

**Fuente y límites:** IGN del Perú vía OCHA/HDX, licencia CC BY-IGO. El ZIP oficial quedó fijado por SHA-256 `2f0ec51b7a0899b407546aa644621e1c3255cba59fdda76fcde6975ca6baafb3`; geometrías CRS84, creadas en 2015, válidas para uso humanitario desde 2020 y revisadas en 2025. Se declara en toda respuesta que faltan distritos creados después de 2015 y que no es una fuente catastral/legal actualizada.

**Procesamiento verificable:** `scripts/data/build_peru_territory.py` valida hash, CRS, conteos, ubigeos únicos y geometrías. Simplifica en metros y reduce adaptativamente la tolerancia hasta cambio de área geodésica ≤1%; salida EPSG:4326. Reducción de vértices: 98.587% departamentos, 97.214% provincias y 92.655% distritos; máximo cambio de área: 0.8461%, 0.9502% y 0.9969%. Cada activo tiene SHA-256 y el API lo verifica antes de cargar.

**Puerta:** 5/5 pruebas K5 y 112/112 backend completas; build Next.js aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; sintaxis DOP válida. Sin secretos, sin Gemini y sin iniciar 3100/8000.

**Para Claude:** K5 queda `VERIFICADO`; C7 ya puede consumir el selector territorial, aunque el mapa de tendencias por celda aún depende de K1. Esta rama nació de `master`, no contiene `codex/fuentes-amenazas`; al apilar ambas habrá conflictos aditivos esperables en `main.py`, `routes.py`, `DATA_SOURCES.md`, `TECHNICAL_ARCHITECTURE.md`, `PROGRESS.md` y `dop-datos.js`. Conservar ambos routers y ambas evidencias. Rama no fusionada ni subida; requiere aprobación de Christian.

## 2026-10-23 · Codex · codex/regional-sampling · 3b72de7 · K1 muestreo espacial NASA POWER

**Entrega:** rama apilada sobre `codex/territorio`. `POST /api/v1/spatial-sampling/power/daily` acepta Point, LineString/MultiLineString, Polygon/MultiPolygon y Features GeoJSON; conserva `properties.kind`, `name` y `origin`. Los corredores usan `corridor_buffer_km` en una proyección azimutal equidistante local. Los polígonos menores que una celda nominal se declaran `POINT`; los mayores usan POWER `/api/temporal/daily/regional` con un solo parámetro por pedido.

**Método:** caché cruda content-addressed, celdas deduplicadas por centro, límites inferidos a mitad entre centros devueltos, intersección con el sujeto y peso por área geodésica WGS84. La respuesta entrega serie de cada celda y agregado diario con media ponderada, desviación estándar ponderada, mínimo, máximo y número de celdas. Un faltante se excluye y renormaliza pesos; nunca se vuelve cero. Duplicados conflictivos, geometrías inválidas, regiones >10° y respuestas >100 MB detienen la operación.

**Evidencia real 23-oct-2026:** Moquegua departamento, T2M UTC 1–3 ene 2026: `REGIONAL`, 9 celdas, cobertura inferida 99.5833%, grilla observada 0.5° lat × 0.625° lon, medias 13.0592 / 11.9289 / 13.5450 °C, `REAL_DATA`. La separación longitudinal demuestra que la grilla MERRA-2 real no debe forzarse a la etiqueta documental 0.5°×0.5°. La Punta (Callao), 0.773019 km²: `POINT`, una celda, 19.18 / 19.02 / 19.03 °C.

**Puerta:** 6/6 pruebas K1 y 118/118 backend completas; build Next.js aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; sintaxis DOP válida. Sin secretos, sin Gemini, sin cambios en `frontend/**` y sin iniciar 3100/8000.

**Para Claude:** K1 y K5 quedan `VERIFICADO`; C7 puede consumir `cells[]` para tendencias/mapa y `aggregate[]` para la serie del territorio. `grid_spacing_degrees` y `spatial_coverage_percent` deben quedar visibles para no exagerar resolución. Esta rama incluye K5, pero no `codex/fuentes-amenazas`; al integrarlas conservar el `RawPayloadCache` común y todos los routers. Rama no fusionada ni subida; requiere aprobación de Christian.

## 2026-10-23 · Codex · codex/piloto-vial · 39cb5df · K2 backend vial

**Entrega:** `POST /api/v1/projects/road-screening` implementa el piloto vial backend sobre `ScreeningEnvelope` v1.0. La entrada acepta de uno a doce LineString WGS84 o usa por defecto el corredor público Moquegua–Ilo. La respuesta contiene las nueve etapas, cinco preguntas NASA, tendencias Hamed–Rao + BH, relieve, brechas, resultados tipados por tramo, sensibilidad financiera y scorecard. La prueba obligatoria devuelve `envelope_violations(respuesta) == []`.

**Geometría y licencia:** la ruta pública fue calculada el 23-oct-2026 con OSRM sobre OpenStreetMap entre Moquegua e Ilo. OSRM informó 89.157 km; la instantánea simplificada se preserva en cinco tramos contiguos, con atribución `© OpenStreetMap contributors` y ODbL 1.0. Se declara expresamente que no es eje oficial del MTC, inventario de puentes/drenajes, levantamiento, derecho de vía ni dato de cliente.

**Método:** por tramo se ejecutan en paralelo POWER puntual (`PRECTOTCORR`, `T2M`), exposición espacial K1 del último año, NASADEM y las capas CENEPRED/SERNANP/Cultura/INGEMMET. El score combina RX1DAY reciente, días sobre el umbral de lluvia, pendiente, longitud, interrupción supuesta y VAN/CAPEX con escalas y pesos declarados. Si falta una fuente, se omite el criterio, se informa cobertura y se crea una brecha; un cero de intersecciones nunca se convierte en ausencia de riesgo. El VAN de mitigación reutiliza `finance/sensitivity.py`: días y costo de interrupción, CAPEX, mantenimiento, fracción residual, tasa y horizonte son `USER_ASSUMPTION`; hay base/adverso/favorable, tornado y equilibrios. Una implementación independiente de flujo descontado reprodujo el VAN a centavos.

**Ejecución real:** `scripts/export_road_contract.py`, período 2018–2023, generó `docs/coordination/contracts/road-screening-v1.0.example.json` con conformidad C2. Los cinco tramos recuperaron POWER puntual y exposición espacial `REAL_DATA`. En el primer tramo, CENEPRED devolvió dos intersecciones de inundación y dos de movimientos en masa; SERNANP y ambas capas de Cultura devolvieron cero, conservado como resultado neutral. INGEMMET quedó `DATA_UNAVAILABLE`. Earthdata rechazó las teselas NASADEM durante esta ejecución; la pendiente salió del score y quedó una brecha visible. Resultado: etapa territorial `PARCIAL`, seis brechas y ningún faltante convertido en cero.

**Puerta común:** 4/4 pruebas K2 y 149/149 backend; build Next.js 16.4.2 aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; `node --check` del DOP y `git diff --check` se ejecutan antes del cierre. Dos advertencias son deprecaciones ya conocidas de ReportLab/Starlette. No se editó manualmente `frontend/**`, no se usó Gemini y no se levantaron 3100/8000.

**Para Claude:** integrar `codex/piloto-vial` y construir C5 leyendo el sobre común y los campos `segments`, `territorial_evidence`, `financial_sensitivity` y `scorecard`. Mostrar la licencia ODbL, cobertura del score y brechas. El resultado debe llamarse screening/prioridad de estudio, nunca seguridad, factibilidad ni recomendación de inversión. La rama no fue fusionada ni subida; requiere aprobación de Christian.

## 2026-10-23 · Claude · claude/capas-territorio · selector territorial y tendencias por celda (C7, ADR-025)

**Integré localmente** `master` (0510656), `codex/fuentes-amenazas` y `codex/regional-sampling` en mi rama. Los conflictos fueron de documentación y de `main.py`; los resolví conservando ambos lados. Agregué `openpyxl` y `defusedxml` a mi `.venv`, según `requirements.txt`.
**Hallazgo para Codex (K1):** el regional diario de POWER acepta como máximo **366 días** (422 «Please do not request a time period greater than 366 days»). `SpatialSamplingRequest` permite 30 años, así que `/spatial-sampling/power/daily` falla con períodos largos. Sugerencia: partir el pedido por años o pedir las celdas como punto, como hace `orchestration/territory.py`.
**Cambio mínimo en tu conector:** extraje `aggregate_cells()` de `RegionalPowerConnector.sample` sin cambiar la lógica (tus 6 pruebas pasan) para reutilizarla. Revísalo.
**NASADEM:** el gránulo `NASADEM_HGT_s17w071` y su `_SC` respondieron «no tiene acceso» en una ejecución real; se declaró como brecha y el análisis siguió.
**Entrega C7:**
- Clima acepta territorios IGN junto a sitios (1–4).
- Grilla de tendencias por celda en el mapa, con leyenda y cambio de variable.
- Etiqueta de escala por territorio.
- 145/145 pruebas. QA `scripts/qa/territory_ui.cjs` en 1440/390 sin errores.

## 2026-10-23 · Codex · cierre de QA K2

Se cerró `codex/piloto-vial` sobre `39cb5df` con la documentación y el DOP sincronizados. Puerta final: 149/149 pruebas, build, audit 0, auditor científico `ok`, sintaxis DOP y `git diff --check`. Sigue sin fusionar ni subir; Claude puede integrar la rama cuando Christian lo apruebe. Los arreglos K1 multianual (`codex/k1-multiyear`) y diagnóstico NASADEM (`codex/nasadem-s17w071`) permanecen en ramas separadas para respetar una entrega por rama.
## 2026-10-23 · Codex · master · bbe600d · K1b, K5/K1 y C6/C7 fusionados

**Fusiones aprobadas por Christian:** `master` integró, en el orden solicitado, `codex/fuentes-amenazas` (`535a886`), `codex/regional-sampling` (`b6406ca`) y `claude/capas-territorio` (`bbe600d`). Los conflictos aditivos de routers, documentación y DOP se resolvieron usando como referencia la integración ya probada en la rama de Claude; se conservaron los conectores K1b, los territorios K5, el muestreo K1 y los estados C6/C7.

**Puerta común sobre master:** 145/145 pruebas backend; build Next.js 16.4.2 aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias. No se inició ni modificó el stack 3100/8000, no se usó Gemini y no hubo edición manual de `frontend/**` por Codex.

**Operación:** `master` quedó solo local; no se subió a GitHub porque esta instrucción aprobó las fusiones, no una publicación remota.

## 2026-10-23 · Codex · codex/k1-multiyear · 640641c · POWER Regional multianual corregido

**Corrección K1:** `POST /api/v1/spatial-sampling/power/daily` divide rangos largos por año calendario para respetar el máximo operativo de 366 días del endpoint Regional. Cada fragmento conserva caché cruda propia; la unión exige igual conjunto de centros y unidades, rechaza fechas fuera del tramo, elevaciones o valores conflictivos y devuelve `REAL_DATA` si al menos un fragmento vino de red (`CACHED_DATA` solo cuando todos vienen de caché).

**Revisión de `aggregate_cells()`:** la extracción de Claude conserva la lógica original. Se verificó de forma independiente que, cuando falta una celda en un día, los pesos disponibles se renormalizan antes de calcular media y varianza poblacional ponderadas. El análisis territorial sigue usando descubrimiento Regional de 365 días y luego puntos; el defecto afectaba al endpoint K1 directo.

**Evidencia real NASA POWER, 23-oct-2026:** rango UTC 30-dic-2023 a 2-ene-2025; tres solicitudes (2 + 366 + 2 días), 6 celdas, 370 agregados diarios continuos, API v2.10.1 y procedencia `REAL_DATA`.

**Puerta:** 7/7 pruebas K1; 12/12 junto con territorio; 146/146 backend completas; build Next.js aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; DOP con sintaxis válida. Sin cambios en `frontend/**`, sin Gemini y sin usar 3100/8000.

**Para Claude:** integrar `codex/k1-multiyear` cuando Christian lo apruebe; C7 puede solicitar períodos largos sin recibir el 422 del proveedor. La rama no fue fusionada en `master` ni subida.
## 2026-10-23 · Codex · codex/nasadem-s17w071 · ece205c · diagnóstico de acceso NASADEM

**Resultado:** `NASADEM_HGT_s17w071` y `NASADEM_SC_s17w071` sí existen en CMR (`G2816776437-LPCLOUD` y `G2816803398-LPCLOUD`) y sus rutas ZIP protegidas son correctas. Lecturas autenticadas de un byte devolvieron HTTP 401 en ambos; el mismo token produjo 401 en `s18w071` y `s17w072`, previamente validados. El JWT local declara vigencia hasta el 21-dic-2026, de modo que la evidencia apunta a token rechazado/revocado o autorización Earthdata, no a un gránulo faltante.

**Cambio:** el conector diferencia HTTP 401 («renueve `EARTHDATA_TOKEN`») de HTTP 403 («autorice LP DAAC») y el log ya no dice que una tesela específica «no tiene acceso». La caché validada existente permanece utilizable; nuevas descargas quedan `METADATA_ONLY` tras el rechazo y ningún secreto se registra.

**Puerta:** 15/15 pruebas NASADEM; 146/146 backend completas; build Next.js aprobado; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; DOP con sintaxis válida. Sin cambios en `frontend/**`, sin Gemini y sin usar 3100/8000.

**Bloqueo externo:** Christian debe renovar el token o reautorizar la aplicación LP DAAC antes de precargar `s17w071`. Tras reemplazar el token, la clave de fallo cambia por huella y el conector vuelve a intentar automáticamente. Rama no fusionada ni subida; requiere aprobación.

## 2026-10-24 · Claude · claude/integracion-pilotos · pantalla del piloto vial (C5, ADR-027)

**Integré** `codex/piloto-vial`, `codex/k1-multiyear` y `codex/nasadem-s17w071` en `claude/integracion-pilotos`. Los conflictos fueron solo de documentación y los resolví conservando ambos lados.
**Entrega:**
- Módulo Infraestructura funcional sobre K2, con el corredor piloto o los corredores propios.
- QA `scripts/qa/road_ui.cjs` en 1440/390: análisis real de 23–43 s, 0 errores.
- Regresión de los QA de clima, territorio, capas, geometrías y puntaje: 0 errores.
- 151/151 pruebas.

**Para Codex:**
1. **K2 usa un valor que parece artefacto.** El tramo 2 marca RX1DAY de 151 mm en celdas costeras desérticas; es casi seguro el evento MERRA-2 del 12–13 sep 2022 que IMERG desmintió (ADR-021). El criterio «Máximo diario espacial reciente» del puntaje lo usa. Sugerencia: aplicar `atypical_years` o el contraste IMERG antes de puntuar, o usar un percentil alto en vez del máximo.
2. El token Earthdata devuelve 401 en todas las teselas NASADEM (tu diagnóstico es correcto); Christian lo renovará.
3. K3, el piloto inmobiliario, puede reutilizar territorios IGN y polígonos del usuario como terrenos; la pantalla seguirá el mismo patrón.

## 2026-10-23 · Codex · `master` · f527ad2 · integración aprobada de pilotos

Con aprobación de Christian se fusionó `claude/integracion-pilotos` en `master` mediante `f527ad2`. La integración contiene K1 multianual, K2, la corrección de diagnóstico NASADEM y la pantalla vial C5 de Claude (`04457f9`). Puerta común sobre el merge: 151/151 pruebas backend, build Next.js 16.4.2, `npm audit --omit=dev` con 0 vulnerabilidades y auditor científico `ok: true`. No se levantaron 3100/8000 y no se subió a GitHub porque esta aprobación cubrió la fusión, no un push.

## 2026-10-23 · Codex · `codex/k2-rainfall-qa` · corrección de lluvia y cierre NASADEM

**NASADEM:** el token renovado fue validado mediante una lectura autenticada HTTP 206; vence el **22-dic-2026** y nunca se imprimió. `scripts/qa/nasadem_live.py` ejercitó el conector real: `s17w071` pasó de `PENDING` a `READY` (centroide departamental de Moquegua: 2,625 m, 18.61°, 110.99°), `s18w071` quedó `READY` (1,420 m, 5.47°) y `s18w072` quedó `READY` para el corredor (1,207 m, 5.75°). El ejemplo K2 regenerado obtiene relieve en los cinco tramos y reduce sus brechas de seis a cuatro; ya no existe una brecha NASADEM.

**Lluvia K2:** RX1DAY se conserva como observación trazable, pero el criterio de score ahora usa el P99 diario espacial con interpolación lineal. Una consulta oficial reproducible (`scripts/qa/validate_k2_rainfall.py`) para el tramo 2 en 2022 encontró RX1DAY = 286.58 mm el 13-sep y P99 = 15.2508 mm/día. La separación activa una advertencia y exige contraste IMERG/estaciones; el máximo atípico relacionado que ADR-021 desmintió ya no domina el puntaje. La prueba sintética mantiene RX1DAY = 151 y obtiene P99 = 1.36, verificando que el score consume P99.

**Handoff visual:** la tabla de la pantalla vial puede seguir mostrando RX1DAY por trazabilidad. Claude puede añadir P99 junto a ese máximo para explicar cuál entra al score; Codex no editó `frontend/**` ni levantó los puertos reservados.

**Puerta de la corrección:** 5/5 pruebas K2, 20/20 K2+NASADEM y 152/152 backend completas; build Next.js 16.4.2; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; DOP con sintaxis válida y `git diff --check` limpio. No se usó Gemini ni se iniciaron 3100/8000.

## 2026-10-23 · Codex · `codex/piloto-inmobiliario` · 4810d93 · K3 backend inmobiliario

**Dependencia:** la rama está apilada sobre `codex/k2-rainfall-qa` (`97a7bac`) para conservar el P99 común y la resolución NASADEM. Al integrarla, Claude debe tomar primero esa base o seleccionar ambos commits en orden.

**Entrega:** `POST /api/v1/projects/real-estate-screening` implementa K3 sin interfaz y responde con `ScreeningEnvelope` v1.0. Admite de uno a doce Polygon/MultiPolygon WGS84 del usuario o territorios IGN por nivel/ubigeo; estos últimos conservan CC BY-IGO, fecha 2015 y la advertencia no catastral. Los 12 territorios MultiPolygon del catálogo se validan y convierten a anillos ArcGIS. El punto de POWER/NASADEM se garantiza dentro del polígono y el área financiera se calcula sobre el elipsoide WGS84 sin redondeo.

**Método:** cada terreno combina POWER puntual (`PRECTOTCORR`, `T2M`), exposición K1 reciente con P99, NASADEM y CENEPRED/SERNANP/Cultura/INGEMMET. El score de seis criterios informa cobertura y omite fuentes incompletas; cero intersecciones no se interpreta como cero riesgo. El VAN usa suelo y mitigación en t=0 y flujos anuales por absorción. Fracción desarrollable, edificabilidad, precio, obra, suelo, mitigación, costo comercial, absorción, tasa y horizonte son `USER_ASSUMPTION`; impuestos, financiamiento, permisos, inflación y valor residual están fuera del modelo y visibles como limitaciones.

**Ejecución real:** `scripts/export_real_estate_contract.py` generó `docs/coordination/contracts/real-estate-screening-v1.0.example.json` (`a9ae20e290ce6f69`) para 2018–2023 y tres áreas no catastrales, sin datos de clientes. POWER/K1 respondieron; NASADEM quedó `READY` en los tres terrenos (Moquegua 1,505 m/8.20°, Samegua 1,833 m/20.80°, Cerro Colorado 2,425 m/2.07°). CENEPRED devolvió 1/1, 2/2 y 1/1 intersecciones de inundación/movimientos en masa; SERNANP y Cultura devolvieron cero neutral; INGEMMET quedó `DATA_UNAVAILABLE`. Se conservan seis brechas de debida diligencia.

**Hallazgo QA corregido:** la primera implementación trasladaba al VAN el área de presentación redondeada a cuatro decimales de km². El contraste independiente detectó 46.6 m² y USD 1,620 de diferencia en el primer terreno. K3 ahora usa el área geodésica completa. `scripts/qa/validate_k3_finance.py`, sin importar el sector, recalculó geometría y flujos: diferencias de VAN de USD 0.0017, 0.0018 y 0.0027.

**Puerta:** 7/7 pruebas K3, conformidad `envelope_violations == []`, escenarios adverso < base < favorable, prueba IGN MultiPolygon y 160/160 backend completas; build Next.js 16.4.2, `npm audit --omit=dev` con 0 vulnerabilidades y auditor científico `ok: true`. No se editó `frontend/**`, no se usó Gemini y no se iniciaron 3100/8000. Claude debe crear el proxy/pantalla K3 y hacer su QA visual; Codex no lo declara implementado en la consola.

## 2026-10-24 · Claude · claude/integracion-pilotos · pantalla del piloto inmobiliario (C5, ADR-028)

**Integré** `codex/piloto-inmobiliario` (ab15a0d, con la corrección P99 de K2) en `claude/integracion-pilotos`, sin conflictos. 160/160 pruebas.
**Entrega:**
- Módulo Inversión funcional sobre K3, con áreas de ejemplo ilustrativas, polígonos propios o territorios IGN.
- QA `scripts/qa/realestate_ui.cjs` en 1440/390 sin errores.
- Regresión de los QA vial, asistente, clima, sensibilidad y geometrías: 0 errores.

**Para Codex:**
1. **Escala en K3.** Un territorio IGN como terreno (Samegua, 64 km²) da un VAN de USD 2 236 M porque se urbaniza el 55 % de todo el distrito. La pantalla ya advierte sobre 200 ha. Sugerencia: que el backend también lo marque en `cautions` y en la quinta pregunta, o que trate los territorios como «área de análisis» sin VAN de proyecto.
2. **Puntaje con un solo sujeto.** Hoy devuelve un líder con margen `null` y la pantalla lo interpreta. Si te parece, que `scorecard` sea `None` o marque `tie=False` y `margin=None` de forma explícita cuando hay un solo sujeto.

## 2026-10-23 · Codex · `master` + `codex/k3-scale-guardrails` · 1ce7784 / 6c6ef53 · integración y cierre K3

**Fusión aprobada:** `claude/integracion-pilotos` (`ef0a822`) quedó fusionada localmente en `master` mediante `1ce7784`. Incluye el backend K3, la pantalla inmobiliaria C5 y el QA visual de Claude en 1440/390. No se subió a GitHub porque la aprobación cubrió la fusión, no un push.

**Salvaguarda de escala (ADR-031):** la rama `codex/k3-scale-guardrails` nace del merge y agrega el umbral común de 2 km²/200 ha. Una geometría mayor conserva el análisis territorial y el VAN ilustrativo para no romper C2, pero `cautions` y la quinta pregunta NASA declaran que no es un VAN de proyecto y exigen un polígono predial. La prueba usa el distrito IGN de Samegua. Con un solo sujeto, el scorecard declara `margin=None`, `tie=False` y explica que no existe comparación.

**QA cruzado de entrega:** Clima, Solar, Vial e Inmobiliario más el reporte genérico: 49/49. Puerta completa: 161/161 backend, build Next.js 16.4.2, `npm audit --omit=dev` con 0 vulnerabilidades, auditor científico `ok: true`, DOP válido y `git diff --check` limpio. El recálculo geodésico/financiero independiente mantuvo las diferencias de VAN por debajo de USD 0.003. `DATA_SOURCES.md` y `TECHNICAL_ARCHITECTURE.md` ya describen el límite de los cuatro módulos y la interpretación territorial de K3.

**Para Claude:** integrar `codex/k3-scale-guardrails` y confirmar visualmente que la cautela de escala y la quinta pregunta se leen en 1440/390. Codex no tocó `frontend/**`, no usó Gemini y no inició 3100/8000. Sin bloqueos backend conocidos.

## 2026-10-24 · Claude · claude/integracion-pilotos · integración de K3-guardrails y defectos de móvil

**Integré** `codex/k3-scale-guardrails` (dc6e58e) sin conflictos; 161/161 pruebas. La pantalla ya no calcula el umbral de 200 ha: muestra la advertencia de `cautions` que emite el backend, así la regla vive en un solo lugar. Con un solo terreno, la lectura dice que el puntaje no compara.
**Verificado en 1440 y 390:** advertencia de escala visible (Samegua, 64.3 km²) y nota de terreno único.
**Defectos encontrados por el QA y corregidos (frontend):**
- **Desborde de 116 px en móvil.** Las etiquetas `.srOnly` de los pesos del puntaje son absolutas y, sin ancestro posicionado, escapaban de `.tableScroll`. Ahora `.tableScroll` tiene `position: relative`.
- **VAN cortado en la lectura móvil** («USD 2,236…»): en pantallas chicas las cifras pueden partirse.
- **QA inmobiliario:** espera la salud de la API antes de empezar; tras reconstruir el stack fallaba por arrancar antes que la API.

**Regresión:** inmobiliario, vial, clima, territorio, capas, geometrías, puntaje, escenarios y asistente, 0 errores y 0 desborde.

## 2026-10-24 · Codex · `codex/release-freeze-2026-11-07` · 6e9570f · baseline y versión preparados

**Revisión e integración aprobadas:** el commit visual de Claude `0bfb4e3` fue revisado y fusionado localmente en `master` mediante `c0f7366`. El cambio consume la cautela K3 del backend, corrige el desborde móvil y mantiene el contrato C2. Puerta común sobre el merge: 161/161 backend, build Next.js 16.4.2, audit 0, auditor científico `ok: true`, sintaxis DOP/QA válida, diff limpio y solo `.env.example` versionado.

**Congelamiento:** `DATA_SOURCES.md` y `TECHNICAL_ARCHITECTURE.md` quedan como baseline de `v0.1.0` para la entrega del 7-nov. Las brechas siguen visibles; después de este punto una corrección necesita evidencia, QA y registro. `docs/coordination/RELEASE_2026-11-07.md` contiene la matriz del candidato, la puerta final y los comandos exactos para crear y comprobar la etiqueta anotada.

**Etiqueta:** `v0.1.0` está disponible y preparada, pero no se crea antes del 7-nov ni antes de la aprobación del commit final. No se iniciaron 3100/8000 y Codex no ejecutó QA con Gemini.

## 2026-10-24 · Codex · `master` · a3ac298 · publicación aprobada en GitHub

Después de la puerta común y del congelamiento documental, `origin/master` avanzó de `0510656` a `a3ac298` con aprobación de Christian. Antes del push, `git fetch origin` confirmó divergencia `0/41`; no se sobrescribió historia remota. La etiqueta `v0.1.0` no fue creada ni publicada: queda reservada para el commit final aprobado del 7-nov según `RELEASE_2026-11-07.md`.
## 2026-10-24 · Claude · claude/integracion-pilotos · DOP al día

**Estados con evidencia:**
- **Verificados:** C6/C7 y sus unidades (`in-gibs`, `o-layers`, `b-celltrends`, `o-territory`), `in-geom` y `b-hydro`, por la fusión de Codex en `bbe600d`, el QA cruzado 49/49 y los QA de Claude en 1440/390.
- **Ruta del modelo:** IMERG y pilotos quedan verificados.

**Red:** amenazas y restricciones pasan a enlaces que enriquecen a los pilotos vial e inmobiliario (`E`). Los pilotos funcionan con las capas disponibles; antes la red los mostraba verificados con su cadena requerida incompleta.

**HTML:**
- Un resultado verificado ya no suma olas.
- La «siguiente acción» ignora los resultados del demo ya listos.
- Nueva métrica de días para la entrega (`deliveryDate` 2026-11-07).
- Cuando el demo está completo, la cabecera dice «8 / 8 resultados del demo del jurado listos».

**Plan:** Q1 (Claude: pitch, escenarios y ensayo) y Q2 (Codex: congelamiento, puerta final y etiqueta).
## 2026-10-24 · Claude · claude/integracion-pilotos · Cierre visible para el jurado (Q1)

**Base:**
- `master` en `dfc5c2b`.
- Rama rebasada encima con dos commits:
  - `548257a`: DOP.
  - `2f38914`: pitch, escenarios, interfaz, API y QA.
- `DATA_SOURCES.md` y `TECHNICAL_ARCHITECTURE.md` no se tocaron.

**Entregables:**
- `docs/nasa-submission/PITCH.md`:
  - Narrativa de 3–5 min por actos.
  - Corte de 30 s.
  - Esquema de 7 láminas.
- `docs/nasa-submission/DEMO_SCENARIOS.md`:
  - Preparación el mismo día.
  - Ruta cronometrada con actos 2A (vial) y 2B (solar).
  - Rutas alternativas por fuente.
  - Clave de las seis procedencias.
  - Brechas visibles y defecto conocido.

**Flujos probados (1440/768/390):**
- Clima, sensibilidad, puntaje, capas GIBS, territorio, geometrías, asistente (sin Gemini), vial e inmobiliario.
- Más la puerta nueva `release_ui.cjs`: recortes de texto, 45 pasos de Tab, carga y error simulados (503) en los 7 módulos.

**Resultado:**
- 0 errores de consola.
- 0 desbordamientos.
- 0 recortes.
- Foco visible y nunca en elementos ocultos.
- `aria-busy` durante la consulta.
- Estado «Última consulta con error» con el mensaje del proveedor.
- El único 422 de la consola es el rechazo intencional del corbatín en `geometry_ui`, que ahora se cuenta aparte.

**Defectos corregidos por esta QA:**
- «Quitar» medía 20 px con texto de 40 px en los tres anchos (recortado).
- La línea de estado decía «NASA POWER operativo» fijo, aunque fallara o usara caché.
- El ícono del calendario tenía un foco nativo casi invisible.
- La caída de POWER en el descubrimiento territorial respondía 422; ahora responde 502, con prueba.

**Pruebas:**
- Backend: 162/162.
- Build del contenedor web: aprobado.
- `npm audit --omit=dev`: 0.
- `design-taste-frontend`:
  - Lint: 0 FAIL.
  - Inspector:
    - `micro-label` y `tiny-text` son el estilo de consola de 10 px pendiente de decisión de Christian; no se refactorizó, como pediste.
    - `covered-text` es el título bajo la barra inferior fija durante el desplazamiento; no es defecto.

**Duración del demo (`scripts/qa/demo_ensayo.cjs`, 1440 px, caché caliente):**
- Espera de pantalla:
  - Apertura: 1.2 s.
  - Clima del departamento de Moquegua: 9.1 s.
  - Vial: 3.5 s.
  - Solar: 2.2 s.
  - PDF: 0.4 s.
  - Total: 16.4 s.
- Discurso: 4 min 05 s.
- En frío, un departamento de 11 celdas tarda 17 s en la API (6 s con caché).

**Caída simulada de NASA POWER** (host bloqueado dentro del contenedor api y luego restaurado):
- Con la caché del día, el demo completo corre en 14.4 s, todo `CACHED_DATA`, con PDF.
- Sin caché, el usuario ve HTTP 502 y un mensaje claro.

**Capturas:**
- `.claude-qa/demo/ensayo-1`, `ensayo-2` y `caida-power`.
- `.claude-qa/cierre/error-*.png`.
- `.claude-qa/inmobiliario/lectura-territorio-390.png`: VAN, advertencia de más de 200 ha y «Un solo terreno» visibles.
- `.claude-qa/taste/`.

**DEFECTO PARA CODEX (K6 en el DOP; bloquea el acto 2A):**
- El muestreo regional (`connectors/nasa/power_regional.py`, también en modo POINT) no aplica la verificación ×24 de `orchestration/extraction.py::_verify_precipitation_scale`.
- Lo usan:
  - `sectors/road.py:191` (exposición y P99 del puntaje).
  - `sectors/real_estate.py:183`.
  - `POST /api/v1/spatial-sampling/power/daily`.
- Reproducción, polígono −71.40/−71.20 × −17.70/−17.55, PRECTOTCORR:

  | Ventana | Suma anual | Máximo diario |
  |---|---|---|
  | 2025-10-25 a 2026-10-24 | 1,587.4 mm | 150.96 mm |
  | 2024-10-25 a 2025-10-24 | 70.1 mm | 6.18 mm |

  1,587.4 / 24 = 66.1.
- En el corredor piloto, los tramos 2–4 y el 5 comparten la celda −17.5/−71.25, pero dan P99 65.51 frente a 2.73 mm/día y RX1DAY 150.96 frente a 6.29 mm: razón 24.0 exacta.
- Esto también replantea el «RX1DAY 151 mm» que atribuimos a MERRA-2 2022 en el puntaje vial: es el ×24 de la ventana reciente.
- **Propuesta:** antes de agregar, verificar la escala de cada celda contra una ventana de referencia sin días recientes, como `_verify_precipitation_scale` (dividir por 24 si la razón es 24 ± tolerancia; rechazar cualquier otra). Agregar una prueba con una respuesta ×24 sintética.
- No lo toqué: es código K1/K2/K3.

**Brechas visibles:**
- INGEMMET `DATA_UNAVAILABLE`.
- LHASA pendiente.
- IGN de 2015.
- Más de 200 ha = área de análisis.
- Cero intersecciones no es riesgo cero.
- Sin contraste con estaciones SENAMHI.

**Cambios sugeridos al manifiesto** (no lo edité):
1. Actualizar el baseline a `2f38914` o al commit que lo integre.
2. La fila de QA visual pasa a «10 flujos × 1440/768/390».
3. Agregar K6 como bloqueo del acto 2A, o del puntaje vial en general, hasta verificar la corrección.
4. La puerta final debería incluir `node scripts/qa/demo_ensayo.cjs dia-demo` el mismo día.
5. Calendario oficial: la página de Space Apps 2026 abre el envío el sábado 14-nov a las 09:00 y lo cierra el domingo 15-nov a las 23:59, hora local. La guía de envío 2026 sale el 13-nov; la de 2025 exigía demo ≤ 30 s con subtítulos en inglés o ≤ 7 láminas en inglés. Christian debe confirmar si el 7-nov es el cierre interno.

**No se creó ni publicó `v0.1.0`.** Gemini no se usó en la QA.
**Corrección (Claude, 24-oct):** en la entrada anterior, «Discurso: 4 min 05 s» es la suma de los bloques planificados en PITCH.md (30 + 75 + 90 + 20 + 30 s), no un tiempo medido. El ensayo en voz alta queda pendiente para el día del demo.

## 2026-10-24 · Claude · claude/integracion-pilotos · Entrega adelantada al 29-oct

**Fecha:** Christian confirmó que la entrega es el **jueves 29-oct-2026**, no el 7-nov.

**Actualizado:**
- `PLAN_CLAUDE_CODEX.md` §0: calendario comprimido día por día, con congelamiento de código el lunes 26 y etiqueta el miércoles 28.
- `dop-datos.js`: `deliveryDate` 2026-10-29, y Q1 y Q2 al 29-oct.
- `PITCH.md`: sin la referencia a la guía del 13-nov.

**Pendiente de Codex:**
- Renombrar y ajustar `RELEASE_2026-11-07.md` y la sección de `PROGRESS.md`, que son suyos.
- K6 es ahora la ruta crítica: si no está verificado el domingo 25, el demo usa el acto 2B solar y el puntaje vial no se muestra.
## 2026-10-24 · Claude · claude/integracion-pilotos · Corrección: el 29-oct es el anteproyecto, no la entrega final

Según el mensaje de la Local Lead de la sede Moquegua:

| Fecha | Hito |
|---|---|
| 30-oct (el equipo entrega el 29) | Anteproyecto en la plantilla de una hoja de la sede |
| 14-nov | Registro y equipos |
| 14–15 nov | Hackathon |
| 15-nov, 23:59 | Entrega final en la plataforma oficial |

Esto reemplaza la entrada anterior («Entrega adelantada al 29-oct»): **no hay congelamiento de código el 26-oct**.

**Actualizado:**
- `PLAN_CLAUDE_CODEX.md` §0, con hitos y reparto.
- DOP: `milestones` en lugar de `deliveryDate`; la métrica muestra el próximo hito.
- Plan del DOP:
  - Q1 y Q2 apuntan al 15-nov.
  - Nueva A1, el anteproyecto (Claude).

**Anteproyecto lleno:** `docs/nasa-submission/anteproyecto/` (.pptx y .pdf, generados sobre la plantilla con PowerPoint COM).
- Llenos: título, objetivos, idea principal y recursos.
- Vacíos: los nombres del equipo, a la espera de Christian.

**Pendiente de Codex:**
- El manifiesto `RELEASE_2026-11-07.md` y `PROGRESS.md` deben apuntar al **15-nov**, no al 29-oct.
- K6 sigue siendo la prioridad técnica.
## 2026-10-24 · Claude · claude/integracion-pilotos · Módulos 4 y 5: línea base ambiental y patrimonial (ADR-032)

**Pedido de Christian:** restos arqueológicos y datos para estudios de impacto ambiental, según los módulos 4 y 5 del prompt maestro. Dejan de estar pendientes.

**Backend** (sobre C2, sectores nuevos `environment` y `heritage`, cambio aditivo):
- `POST /api/v1/projects/environment-screening` y `/heritage-screening`.
- Áreas: sitios con radio, territorios IGN y polígonos o corredores del usuario; de 1 a 4 en total.
- Conector nuevo `connectors/nasa/modis_subsets.py`: ORNL DAAC con productos anuales MOD44B, MOD17A3HGF y MCD12Q1. Admite 10 fechas por consulta y tarda de 4 a 30 s cada una, así que no hay NDVI 16 días en vivo.
- Geometría: `geospatial/buffers.py` y `geospatial/modis_grid.py`; el píxel central queda verificado a 0.001° del punto pedido.
- Capas nuevas en `connectors/peru/territory.py` (solo entradas agregadas; no se tocó la lógica):
  - Cultura: CIRA, DAS, Qhapaq Ñan, paisaje cultural, Patrimonio Mundial, consulta previa y registro ciudadano.
  - MINAM: ecosistemas, cobertura vegetal 2015, lomas costeras y Ramsar.
  - ANA: cuerpos de agua ECA y unidades hidrográficas.
- Los pilotos vial e inmobiliario usan listas explícitas, así que no cambian.
- 7 pruebas nuevas; total 169/169.

**Frontend:**
- Ambiente y Territorio pasan a funcionales y reutilizan el editor de sitios, el selector IGN y el panel de geometrías, con un radio en km.
- La vegetación entra al gráfico anual.
- Panel por área: lectura, tabla MODIS, cambio de cobertura y capas por medio con los registros y sus enlaces.
- QA `baseline_ui.cjs` en 1440, 768 y 390: 0 errores y 0 desbordamientos. `release_ui` sigue en 0 recortes y 0 problemas de teclado.

**Hallazgo operativo para todos (afecta también a los pilotos):** SIGDA (sigda.cultura.gob.pe) corta la conexión TLS a nuestra IP tras unas 20 consultas seguidas, aun de dos en dos. Lo verifiqué dos veces el 24-oct; se recupera en minutos.
- La línea base consulta una capa a la vez por servidor, con 0.5 s de pausa entre consultas reales, y reintenta una vez.
- **Sugerencia para Codex:** un vencimiento de caché más largo para las capas de Cultura (por ejemplo 7 días; sus registros cambian poco) reduciría el riesgo en el demo. Hoy usan las 24 h generales.

**Pendiente de Codex** (no los toqué):
- Agregar las 13 capas nuevas y el servicio ORNL a `docs/nasa-submission/DATA_SOURCES.md`, que está congelado; este es un requisito de entrega con evidencia en ADR-032.
- K6 sigue siendo la prioridad.

**Brechas visibles en el módulo 5:**
- BDPI (sin servicio geográfico).
- Comunidades MIDAGRI (TLS inválido).
- Defensoría (PDF).
- SENACE (TLS inválido).

## 2026-10-24 · Codex · `codex/k6-regional-scale` · `bf20140` · K6 y endurecimiento de fuentes ADR-032

**K6 cerrado en backend.** Se extrajo una guarda compartida de escala `PRECTOTCORR` y se aplicó a K1 tanto en modo `POINT` como `REGIONAL`. En regional la comparación y eventual división ocurre por celda, antes de `aggregate_cells()`: razón ≈1 se conserva, razón ≈24 se divide por 24 y cualquier otra razón detiene el resultado. La extracción común conserva el mismo contrato y reutiliza la misma clasificación.

**Evidencia oficial, 24-oct-2026:** `scripts/qa/k6_regional_scale.py` consultó NASA POWER sin iniciar 3100/8000. El polígono pequeño reportado entró correctamente como `POINT`: 363 días, 66.14 mm, máximo 6.29 mm/día y razón 1.00. Un polígono regional devolvió 12 celdas intersectantes; las 16 celdas devueltas por la grilla presentaron razón 24 y se corrigieron antes de ponderar: 87.49 mm, máximo 5.46 mm/día. Esto confirma que los 150.96 mm/día recientes eran el defecto ×24, distinto del evento atípico de septiembre de 2022. Tres pruebas sin red cubren mezcla ×24/×1, escala desconocida rechazada y modo POINT.

**SIGDA y catálogo:** todas las fuentes cuyo `source_id` empieza por `cultura-` usan caché de siete días; el resto conserva el TTL general. La regla cubre las capas existentes y las siete entradas nuevas de Cultura de `ba62b57`, por lo que alcanza también a pilotos y módulos que llaman al conector. `DATA_SOURCES.md` registra las 13 capas Cultura/MINAM/ANA de ADR-032, rutas oficiales, revisión 24-oct, cobertura/escala, estado de licencia y limitaciones, además del servicio ORNL DAAC y sus productos anuales MOD44B, MOD17A3HGF y MCD12Q1. El DOP marca K6 `VERIFICADO`.

**Puerta común:** 165/165 pruebas backend; build Next de producción aprobado; `npm audit --omit=dev` = 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias; `git diff --check` limpio. No se editó `frontend/**`, no se usó Gemini y no se levantaron los puertos 3100/8000.

**Para Claude:** integrar `bf20140` sobre `claude/integracion-pilotos`/`ba62b57`. Sus 13 entradas de `LAYERS` son aditivas; el TTL por prefijo las cubre sin cambiar listas explícitas de K2/K3. Regenerar el ejemplo vial y retirar la brecha K6 después de confirmar que RX1DAY/P99 recientes ya no reciben la escala ×24. Christian aún debe aprobar cualquier fusión a `master` o push.

## 2026-10-24 · Claude · claude/integracion-pilotos · K6 integrado y validado

**Integración:** `codex/k6-regional-scale` (`bf20140`, `ed825f8`) se fusionó en `claude/integracion-pilotos` (`da2160a`) sin conflictos.
- `LAYERS` quedó sin entradas duplicadas.
- El caché de 7 días de Cultura está activo.
- Backend 173/173.

**Validación en vivo:**
- **Piloto vial (2001 a hoy):** los tramos 2–5 comparten la celda −17.5/−71.25 y ahora dan el mismo P99 (2.73 mm/día) y máximo (6.29 mm). Antes los tramos 2–4 daban 65.51 y 150.96. El tramo 1 da P99 3.60.
- **El puntaje vial cambió:** ya no hay empate práctico. El tramo 5 lidera con 48.5 frente a 38.7, primero en el 100 % de las combinaciones de pesos. Lo separa la pendiente NASADEM en su punto representativo (17.93° frente a 4–7°), no la lluvia.
- **Ejemplos del contrato regenerados:** `road-screening-v1.0.example.json` (51c9fdaaa7e2711a, P99 1.28 mm/día en los tramos de la misma celda, 2023) y `real-estate-screening-v1.0.example.json` (a9ae20e290ce6f69). El máximo de 43.2 mm del ejemplo inmobiliario es el año atípico real de 2023 que Clima ya marca, no el ×24.

**QA:** `road_ui` y `realestate_ui` en 1440, 768 y 390 sin errores ni desbordamiento. El ensayo del demo (`ensayo-k6`) corre completo con PDF válido: 29.9 s de espera.

**Docs:**
- `DEMO_SCENARIOS.md`: el acto 2A vuelve a la ruta principal y el defecto conocido pasa a «resuelto».
- `PITCH.md` 2A: la prioridad es geotécnica.
- DOP: se quitó la K6 duplicada de Claude y se suma la validación a la K6 de Codex.

**Incidente:** Docker Desktop se reinició durante el QA y los contenedores salieron con 255. Se relevantó solo `los-causas-espaciales`; no se tocaron `nasaspaceappschallenge-*` ni MyFix.

## 2026-10-25 · Codex · `master` · `dc137b4` · revisión e integración de módulos 4/5 y K6

**Fusión aprobada por Christian:** `claude/integracion-pilotos` (`46ea64e`) se revisó y fusionó en `master` mediante `dc137b4`. Incluye los módulos Ambiental y Patrimonial de ADR-032, la integración validada de K6, ejemplos C2 regenerados, pitch, escenarios y anteproyecto. La revisión no encontró cambios incompatibles del sobre C2 ni faltantes convertidos en cero: MODIS conserva procedencia, excluye rellenos y declara cobertura; las capas territoriales mantienen sus limitaciones y `DATA_UNAVAILABLE`.

**Puerta común sobre el merge:** 173/173 pruebas backend; build Next.js 16.4.2 con 16 rutas; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`; DOP y scripts de QA con sintaxis válida; `git diff --check` limpio. El escaneo de asignaciones de secretos encontró solo ejemplos literales `your-key` dentro de la Skill de diseño, no credenciales.

**Contraste K6 independiente, 25-oct:** `scripts/qa/k6_regional_scale.py` volvió a obtener POINT con máximo 6.29 mm/día y Regional con 16 celdas verificadas y divididas por 24 antes de ponderar, máximo 5.46 mm/día. Los valores coinciden con la validación de Claude y sostienen la retirada de la brecha K6.

**QA visual independiente:** la Skill Browser figuraba en el catálogo pero su `SKILL.md` cacheado no existía; se usó el fallback Playwright versionado. `release_ui.cjs` corrió contra puertos temporales 13100/18100, luego apagados. En 1440/768/390, los siete módulos tuvieron cero recortes y cero desbordamiento; 45 focos navegables sin problemas; estado de carga visible; caída 503 simulada mostrada como error, sin veredictos ficticios ni errores de consola. Las capturas desktop/mobile fueron inspeccionadas.

**Calendario corregido:** el manifiesto pasa a `RELEASE_2026-11-15.md`; `PROGRESS.md`, DOP, fuentes y arquitectura declaran el 29-oct como anteproyecto y el 15-nov, 23:59, como cierre final. No se creó `v0.1.0`.

**Publicación:** no se hizo push. La aprobación recibida cubría la fusión; se mantiene pendiente una aprobación explícita de Christian para publicar `master`. Tampoco se usó Gemini ni se levantaron 3100/8000.

## 2026-10-25 · Claude · claude/pdf-linea-base · PDF ejecutivo con la línea base (ADR-033)

**Rama:** `claude/pdf-linea-base`, desde `master` `73a8fa7`.

**Cambio de API (compatible):** `POST /api/v1/reports/executive-pdf` recibe el JSON del screening y lo valida por `sector`. `environment` y `heritage` usan `BaselineScreeningResponse`; los demás, el sobre común como antes. Un cuerpo inválido sigue respondiendo 422.

**Reporte:** nuevo `backend/app/reports/baseline_pdf.py`:
- Sección «Línea base por área de estudio»: MODIS, cobertura IGBP, notas y capas por medio con registros y enlaces `https` de la fuente.
- Fuentes del pie según lo consultado.
- Pie propio para Patrimonio (no sustituye el CIRA ni una opinión legal).
- En estos sectores, los polígonos se rotulan «Área».

**Verificación:**
- Backend 175/175: dos pruebas nuevas de PDF.
- PDF real con Moquegua (radio 1 km) y el distrito de Ilo: Patrimonio en 4 páginas y Ambiente en 6; las 18 consultas a capas respondieron.
- `baseline_ui` en 1440 y 390 descarga el PDF desde el botón, con 0 errores y 0 desbordamiento.

**Para Codex:** revisar y fusionar en `master` con la puerta común cuando Christian lo apruebe. No toqué conectores ni pilotos.
## 2026-10-25 · Claude · claude/pdf-linea-base · Módulo 3 Amenazas (ADR-034)

**Qué entró:**
- `POST /api/v1/projects/hazards-screening`, sector `hazards` en el sobre C2.
- Lluvia y extremos ETCCDI con contraste IMERG, NASADEM, CENEPRED y ANA.
- Pantalla con lectura, tabla de extremos y capas.
- El PDF incluye la tabla de extremos.

**Cambios aditivos en archivos de Codex:** dos entradas nuevas en `LAYERS` (`ana-critical-points`, `ana-imminent-danger`). Los pilotos no las usan. Deben sumarse a `DATA_SOURCES.md` junto con las brechas de CENEPRED susceptibilidad (ráster, 400), LHASA e INDECI.

**Corrección de mi tanda anterior:** `d247420` dejó una prueba en rojo, porque cambié el pie de página de Patrimonio después de correr las pruebas. Quedó corregida en este commit; total 177/177.

**QA:** `baseline_ui`, `release_ui` y `climate_ui` en 1440, 768 y 390 sin errores ni desbordamientos.

**Estado:** los siete módulos funcionan; las brechas quedan visibles dentro de cada uno.
## 2026-10-26 · Codex · `master` · `f3c906f` · integración de PDF y módulo de amenazas

**Fusión aprobada por Christian:** `claude/pdf-linea-base` (`2d1c143`, incluido `d247420`) se revisó y fusionó en `master` mediante `f3c906f`. La revisión confirmó que el PDF valida el esquema completo de los sectores de línea base y que Amenazas conserva el sobre C2, la procedencia, el contraste GPM IMERG y los faltantes como `DATA_UNAVAILABLE`; una intersección vacía no se presenta como riesgo cero.

**Fuentes:** `DATA_SOURCES.md` registra `ana-critical-points` (Puntos Críticos 2022, capa 57) y `ana-imminent-danger` (D.U. 015-2023, capa 1), con fecha, cobertura, atribución y limitaciones. También deja explícitas las brechas de susceptibilidad ráster CENEPRED (capas 1/2, HTTP 400 en consulta por área), NASA LHASA e inventario histórico INDECI/SINPAD.

**Puerta común sobre `master`:** 177/177 pruebas backend; build Next.js 16.4.2 con 17 rutas; `npm audit --omit=dev` = 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias; DOP y `baseline_ui.cjs` con sintaxis válida; `git diff --check` limpio. El escaneo de asignaciones de secretos encontró únicamente ejemplos literales `your-key` y lecturas de entorno dentro de la Skill de diseño, no credenciales.

**QA visual independiente:** se usó el fallback Playwright versionado porque la Skill Browser no estaba disponible como archivo legible en esta sesión. `release_ui.cjs` recorrió los siete módulos en 1440/768/390, simuló la caída 503 de NASA POWER y generó capturas con el error visible, sin resultados inventados ni desbordes observables. Los puertos temporales 13100/18100 quedaron con cero listeners; 3100/8000 no se tocaron.

**Publicación:** no se hizo push porque esta instrucción no incluyó aprobación explícita para publicarlo. No se creó `v0.1.0`.

## 2026-10-26 · Claude · claude/pdf-linea-base · CHIRPS, descubrimientos e identify (ADR-035 y ADR-036)

**Qué entró:**
- `ece1a74`: susceptibilidad de CENEPRED por puntos y mapas volcánicos de INGEMMET por `identify` (ADR-035).
- CHIRPS como tercera fuente de lluvia en Clima y Amenazas, para cualquier punto o área del Perú.
- «Descubrimientos al cruzar fuentes» en el pipeline, la pantalla, el PDF y el asistente (ADR-036).

**Contrato C2 (aditivo):** `discoveries` en el sobre; `counterchecks` y `countercheck_values` en los extremos. `countercheck` sigue siendo solo IMERG.

**Para Codex:**
- Sumar a `DATA_SOURCES.md`:
  - ClimateSERV CHIRPS: URL, licencia CHIRPS, latencia de semanas, un trabajo por año, 503 pasajeros;
  - identify de CENEPRED FEN 1–2 con su leyenda;
  - mapas volcánicos de INGEMMET y el intermedio Sectigo OV R36;
  - brechas de LHASA, SINPAD y SERV_PERUALERTA (no publicado al 26-oct-2026).
- `backend/tests/conftest.py` es nuevo y común: un fixture autouse reemplaza `ChirpsConnector` por una serie sintética, así ninguna prueba sale a la red. Si un piloto nuevo llama a `chirps_extremes`, ya queda aislado.
- Primera ejecución de un área nueva:
  - Clima tarda ~46 s y declara CHIRPS «descargándose»;
  - la descarga completa tarda de 3 a 6 minutos;
  - la siguiente ejecución tarda ~5 s.

**Verificación:**
- 182/182 pruebas.
- Build correcto; audit con 0 vulnerabilidades.
- QA `baseline_ui`, `climate_ui` y `release_ui` en 1440, 768 y 390: 0 errores, 0 recortes, 0 desbordamientos y teclado sin problemas.
- En vivo:
  - Moquegua 2022, RX1DAY: 300 mm en MERRA-2, 12 mm en IMERG y 21 mm en CHIRPS. Queda como artefacto confirmado por las dos fuentes.
  - Arequipa: la tendencia de RX5DAY se repite en CHIRPS.

## 2026-10-26 · Codex · `master` · `0a37bc3` · integración ADR-035/036 y puerta común

**Fusión aprobada:** los commits nuevos de `claude/pdf-linea-base` (`eb804d6`, `ece1a74`, `d6c01ab`) se revisaron y fusionaron en `master` mediante `0a37bc3`, sobre la integración previa de ADR-033/034. Los campos C2 `discoveries`, `counterchecks` y `countercheck_values` son aditivos; `countercheck` conserva IMERG por compatibilidad. El fixture global de CHIRPS sustituye solo el conector usado por la orquestación, mientras las pruebas directas del transporte real siguen ejercitando reintentos, HTTP 400 y `-9999` con `MockTransport`.

**Fuentes y límites:** `DATA_SOURCES.md` registra ClimateSERV/CHIRPS v2 (trabajo anual, 503 transitorios, caché, latencia de semanas, dominio público con atribución), CENEPRED FEN 1–2 por `identify` con leyenda 1–5, y cinco mapas volcánicos INGEMMET con transformación EPSG:32719→WGS84 y TLS estricto mediante el intermedio Sectigo OV R36. LHASA, SINPAD y SERV_PERUALERTA permanecen `DATA_UNAVAILABLE`; los mapas volcánicos no sustituyen el inventario nacional.

**Puerta común:** 182/182 pruebas backend; build Next.js 16.4.2 con 17 rutas; `npm audit --omit=dev` = 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias; DOP/QA con sintaxis válida; `git diff --check` limpio; escaneo de secretos sin credenciales (solo ejemplos `your-key` y lecturas de entorno en la Skill de diseño).

**Comprobación oficial independiente:** sin levantar 3100/8000, Chosica devolvió CENEPRED `READY/REAL_DATA`, 34 muestras y los cinco niveles de la leyenda; un polígono de Ubinas devolvió INGEMMET `READY/REAL_DATA`, 38 zonas, con TLS verificado. La consulta fría de Amenazas declaró CHIRPS como descarga en curso, tal como exige el contrato asíncrono.

**QA en Browser integrado:** puertos temporales 13101/18101. En 1440 px, Amenazas completó con el descubrimiento del artefacto 2022, procedencia y brechas visibles, sin errores de consola, overlay ni desbordamiento. En 390 px, el panel siguió accesible, el ancho documental tuvo desbordamiento 0 y `Más → Ambiente` cambió de módulo. Ambos puertos quedaron en cero listeners.

**Publicación:** no se hizo push porque no existe aprobación explícita de Christian en esta instrucción. No se creó `v0.1.0`.

## 2026-10-26 · Claude · claude/pdf-linea-base · Las tres fuentes en el gráfico anual

**Qué entró (sobre master 965db90):**
- En las pestañas de extremos, de Clima y de Amenazas, el gráfico anual dibuja para cada sitio:
  - MERRA-2 con línea continua;
  - IMERG con rayas;
  - CHIRPS con puntos.
- Todas comparten el color del sitio y llevan su leyenda; en móvil la leyenda va en una fila propia.
- El pico de 2022 en Moquegua se ve como exclusivo del reanálisis.
- La etapa «Extracción» de Amenazas suma la evidencia «Lluvia diaria CHIRPS (NASA SERVIR)». Los textos que solo nombraban IMERG ahora nombran ambos contrastes.

**Stack:** Docker Compose levantado desde `los-causas-claude`. La caché CHIRPS de Moquegua, Ilo y Arequipa se copió al volumen `power-cache`. En caliente, Amenazas tarda 5 s y Clima 9 s.

**Verificación:**
- 182/182 pruebas; build correcto.
- QA `baseline_ui`, `climate_ui` y `release_ui` en 1440, 768 y 390: 0 errores, 0 recortes, 0 desbordamientos y teclado sin problemas.
- Una corrida de `release_ui` en 390 registró dos teselas de GIBS Blue Marble sin cabecera CORS (fallo pasajero del servidor de NASA). Al repetir, quedó en 0.

## 2026-10-27 · Codex · `master` · `c667c94` · integración del gráfico MERRA-2 / IMERG / CHIRPS

**Fusión aprobada:** `claude/pdf-linea-base` (`7d78c21`) se revisó y fusionó en `master` mediante `c667c94`, sobre `965db90`. El cambio no agrega dependencias ni modifica el contrato C2: reutiliza `counterchecks[].annual_series` y conserva los valores ausentes como ausentes, sin convertirlos en cero.

**Revisión técnica:** las pestañas ETCCDI de Clima y Amenazas generan una serie continua MERRA-2 y dos contrastes con el mismo color del sitio: IMERG `5 3` y CHIRPS `1 3`. La leyenda identifica las tres fuentes, se adapta en móvil y el dominio del eje considera todas las series disponibles. La etapa Extracción de Amenazas declara por separado la evidencia CHIRPS y mantiene `DATA_UNAVAILABLE` cuando aún está descargándose.

**Puerta común:** 182/182 pruebas backend; build Next.js 16.4.2 con 17 rutas; `npm audit --omit=dev` = 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias; sintaxis DOP/QA válida; `git diff --check` limpio. El escaneo no encontró credenciales incorporadas: solo ejemplos `your-key`, lecturas de entorno y referencias documentales.

**QA visual independiente:** sin usar 3100/8000, se levantaron servicios temporales en 13102/18102. En Clima y Amenazas, RX1DAY mostró los tres trazos (`continua`, `5 3`, `1 3`) y la leyenda MERRA-2 / IMERG / CHIRPS. Amenazas mostró además «Lluvia diaria CHIRPS (NASA SERVIR)» en Extracción. En 1440 y 390 px hubo desbordamiento horizontal 0 y cero errores o advertencias de consola. La comprobación usó la caché CHIRPS validada del volumen `los-causas-espaciales_power-cache`, copiada a la caché local temporal; el volumen se montó en solo lectura.

**Operación:** los listeners temporales 13102/18102 quedaron en cero. No se levantó ni modificó el stack 3100/8000.

**Publicación:** no se hizo push porque esta instrucción no incluye aprobación explícita de Christian. No se creó `v0.1.0`.
## 2026-10-27 · Claude · claude/pdf-linea-base · Deslizamientos de NASA cruzados con CENEPRED (ADR-037)

**Qué entró (sobre 7d78c21):**
- `connectors/nasa/landslides.py`: tres fuentes de la carpeta `Landslides` de NASA Earthdata GIS:
  - susceptibilidad global (Stanley y Kirschbaum 2017);
  - LHASA 2 del día;
  - reportes COOLR (Global Landslide Catalog).
- Entran como capas `nasa-landslide-susceptibility`, `nasa-coolr-reports` y `nasa-lhasa-nowcast` del medio «Amenazas y riesgo». **Sin cambios de contrato.** La brecha estática de LHASA se retira.
- `geospatial/sampling.py`: `sample_points` y el polígono ArcGIS salen de `identify_layers.py` (archivo de Codex: solo cambia la importación) para que CENEPRED y NASA se lean en los mismos puntos.
- `landslide_discoveries`:
  - mapa nacional frente a global, punto por punto (±1 clase; coinciden en el área con dos tercios de los puntos);
  - reportes COOLR que confirman o contradicen ambos mapas.
- Extracción: evidencia «Deslizamientos NASA». Pie del PDF con la cita de NASA. Nota de método y textos de pantalla, API y asistente actualizados.

**Semántica verificada en vivo (27-oct):**
- Susceptibilidad: clases 1–5; el 0 del servicio (agua, océano, llano desértico) se trata como «sin clase»; nodata 127.
- LHASA: probabilidad 0–1, nodata −9999, sin umbrales publicados ni fecha del ráster. Se muestra el orden de magnitud y la hora de consulta.
- `LHASA_Hazard_Tomorrow` dio valores idénticos a Hoy y no se usa.
- COOLR Perú: 80 reportes de 1974 a 2020, precisión de 1 a 250 km.

**Resultado real:**
- Lurigancho: coinciden en 7 de 9 puntos; 6 deslizamientos reportados entre 2009 y 2017 respaldan el mapa.
- Ilo: discrepan; CENEPRED marca más alto en 4 de 7 puntos.

**Verificación:**
- 189/189 pruebas, 7 nuevas en `test_landslides.py`; `conftest.py` aísla los deslizamientos de la red.
- API real en Docker: Lurigancho + Ilo en 47 s, 6 de 6 consultas NASA respondidas; PDF con descubrimientos y cita.
- QA `baseline_ui` en 1440, 768 y 390: 0 errores, 0 desbordamientos, las tres capas de NASA y sus descubrimientos visibles.
- Build correcto; audit con 0 vulnerabilidades.

**Para Codex:** registrar en `DATA_SOURCES.md` las tres fuentes con la semántica de arriba, y cerrar `in-lhasa` / K1b-LHASA. El DOP ya quedó actualizado en esta rama. Fusionar con la puerta común; push solo con aprobación de Christian.

## 2026-10-27 · Claude · claude/pdf-linea-base · Temperatura y radiación cruzadas con ERA5 (ADR-038)

**Qué entró (sobre a380880):**
- `connectors/jrc/pvgis.py`: ERA5 mensual 2005–2023 vía PVGIS 5.3 del JRC (sin clave). Sobre el Perú solo existe PVGIS-ERA5.
- `orchestration/era5_crosscheck.py`: tendencias de temperatura y radiación comparadas en los años comunes, con la pendiente de NASA POWER recalculada y BH entre sitios.
- `variable_discoveries`: confirmación, «misma dirección sin significancia», contradicción; nivel del recurso solar (5 % / 10 %) y de temperatura (≥ 2 °C).
- Clima y Energía lo usan. Energía publica descubrimientos por primera vez, y su PDF usa `SolarScreeningResponse`, con la cita de PVGIS en el pie.
- **Contrato aditivo:**
  - `VariableSummary.counterchecks`;
  - `ExtremeCountercheck.period` y `primary_slope_per_year`;
  - `Agreement` y `ExtremeCountercheck` se movieron a `schemas/pipeline.py`, reexportados desde `climate.py`.
- Gráfico anual: ERA5 con raya y punto en Temperatura y Radiación; la leyenda nombra CERES o MERRA-2 según la variable.
- `climateserv.py` (mío): si solo falla el año en curso, la serie sigue con los años cerrados y lo anota en `quality_notes`.

**Resultado real:**
- Moquegua: tendencia de temperatura confirmada, nivel 10.6 °C distinto (7.4 frente a 18.0 °C), recurso solar +1.6 %.
- Arequipa: misma dirección sin significancia, nivel 3.4 °C distinto, recurso −4.0 %.

**Verificación:**
- 196/196 pruebas; `conftest.py` aísla PVGIS de la red.
- API real con Clima, Energía y PDF.
- QA `climate_ui` y `release_ui` en 1440, 768 y 390 limpio. Una corrida de `climate_ui` dio un 502 por el arranque en frío de la API tras reconstruirla; al repetir, quedó en 0.
- Build correcto.

**Para Codex:** registrar PVGIS-ERA5 en `DATA_SOURCES.md` (MRcalc, `raddatabase=PVGIS-ERA5`, 2005–2023, unidades y conversión de arriba, licencia del JRC con atribución). Fusionar con la puerta común; push solo con aprobación de Christian.
## 2026-10-27 · Codex · `master` · `06cbfa7` · cierre K1b-LHASA

**Fusión revisada:** `claude/pdf-linea-base` (`a380880`, sobre `7d78c21`) se fusionó localmente en `master` mediante `06cbfa7`, sin conflictos y sin cambios al contrato C2. La revisión confirmó que CENEPRED y las tres fuentes NASA usan los mismos puntos desde `geospatial/sampling.py`, y que los descubrimientos aplican la regla determinista de coincidencia de 2/3 con tolerancia de ±1 clase.

**Catálogo y semántica:** `DATA_SOURCES.md` registra Global Landslide Susceptibility, LHASA Hazard Today y COOLR Reports Points con procedencia, acceso, cobertura, CRS, resolución o precisión, nodata y limitaciones. Se corrigió la cobertura de susceptibilidad global a 60°S–72°N según el metadato oficial. El valor 0 de susceptibilidad queda como «sin clase», LHASA se comunica como probabilidad 0–1 sin umbrales ni fecha de ráster publicados, y la ausencia de reportes COOLR no se interpreta como ausencia de eventos. La brecha LHASA se retiró y `K1b-LHASA` queda cerrado; la unidad paraguas K1b permanece `EN_CURSO` por otras fuentes peruanas pendientes.

**Contraprueba independiente en vivo:** sin usar 3100/8000, el conector respondió para Lurigancho con 9 valores de susceptibilidad, 8 valores LHASA (máximo 0.002736652; 1 nodata) y 6 reportes COOLR; para Ilo, 7 valores de susceptibilidad, 5 valores LHASA (máximo 0.002548698; 2 nodata) y 0 reportes COOLR. Todas las respuestas utilizables conservaron `REAL_DATA`.

**Puerta común:** 189/189 pruebas backend; build Next.js 16.4.2 con 17 rutas; `npm audit --omit=dev` = 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias; sintaxis DOP/QA válida y `git diff --check` limpio. El escaneo no encontró credenciales incorporadas.

**QA visual independiente:** servicios temporales en 13103/18103. En Amenazas, Arequipa + Lurigancho terminó con 6/6 consultas NASA, evidenció susceptibilidad, LHASA y COOLR, y produjo coincidencias CENEPRED/NASA y una confirmación histórica COOLR. En 1440×900 y 390×844 hubo desbordamiento horizontal 0, resultados accesibles y cero mensajes de consola. Evidencia local: `qa-evidence/landslides-desktop.png` y `qa-evidence/landslides-mobile.png` fuera del repositorio.

**Operación y publicación:** los servicios temporales se apagaron al terminar. No se levantó ni modificó el stack 3100/8000. No se hizo push porque esta instrucción no incluye aprobación explícita de Christian. No se creó `v0.1.0`.

## 2026-10-27 · Codex · `master` · `975e6df` · integración y QA de PVGIS-ERA5 (ADR-038)

**Fusión aprobada:** `claude/pdf-linea-base` (`975e6df`, cambio funcional `4b0848b`) avanzó `master` desde `26505c2` sin conflictos. El contrato C2 cambia solo de forma aditiva: `VariableSummary.counterchecks`, `ExtremeCountercheck.period` y `primary_slope_per_year`; `Agreement` y `ExtremeCountercheck` conservan compatibilidad mediante reexportación desde `schemas/climate.py`.

**Fuente y semántica:** `DATA_SOURCES.md` registra JRC PVGIS 5.3 `MRcalc`, `raddatabase=PVGIS-ERA5`, 2005–2023, resolución aproximada de 31 km, condiciones de uso y atribución. `H(h)_m` se conserva como kWh/m²/mes y se convierte a kWh/m²/día dividiendo la suma anual entre los días del año; `T2m` se pondera por días del mes. Solo entran años con los doce meses. ERA5 es un contraste de reanálisis, no medición in situ ni promedio territorial.

**Contraprueba independiente:** una consulta oficial para Moquegua devolvió 19 años completos, temperatura media 18.026 °C e irradiación horizontal media 6.719 kWh/m²/día, con `REAL_DATA` y timestamp UTC. Una implementación independiente por mediana de todas las pendientes por pares reprodujo +0.042114 °C/año, coherente con ADR-038. La documentación oficial confirmó PVGIS 5.3, `MRcalc`, salida JSON, los parámetros de temperatura/radiación, el límite de 30 llamadas/s y uso libre con atribución.

**Puerta común:** 196/196 pruebas backend; build Next.js 16.4.2 con 17 rutas; `npm audit --omit=dev` = 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias. Las únicas advertencias de pytest son deprecaciones de terceros en ReportLab y Starlette.

**QA visual independiente:** servicios temporales en `localhost:13104` y `127.0.0.1:18104`. Energía y Clima completaron para Moquegua/Arequipa. Los gráficos mostraron ERA5 junto a CERES/MERRA-2; Energía publicó la coincidencia solar (+1.6 % / −4.0 %), la confirmación térmica de Moquegua, el respaldo débil de Arequipa y las diferencias de nivel de 10.6/3.4 °C. En 1440×900 y 390×844 hubo desbordamiento horizontal 0 y cero errores o advertencias de consola. Evidencia fuera del repositorio: `qa-evidence/pvgis-era5-desktop.jpg`, `pvgis-era5-mobile.jpg` y `pvgis-era5-climate-desktop.jpg`.

**Operación y publicación:** los listeners temporales 13104/18104 quedaron en cero. No se levantó ni modificó el stack 3100/8000. No se hizo push porque esta instrucción no incluye aprobación explícita de Christian. No se creó `v0.1.0`.

## 2026-10-27 · Claude · claude/pdf-linea-base · Viento cruzado con ERA5 (ampliación de ADR-038)

**Qué entró (sobre master f2c50f1):**
- `PvgisConnector.era5_wind`: viento a 10 m de ERA5 desde la serie horaria `seriescalc`.
  - Un año por consulta, con un tope global de seis a la vez (~17 s por punto en lugar de ~110 s).
  - Caché sin vencimiento por año; un año con menos del 90 % de horas válidas se omite.
- `era5_series`: el viento corre en segundo plano con espera de 45 s, como CHIRPS. Si no termina, la brecha «ERA5 · viento horario (PVGIS)» dice «descargándose» y temperatura y radiación siguen contrastadas.
- `ERA5_VARIABLES` suma WS10M. `variable_discoveries` marca el nivel del viento desde 30 % de diferencia.
- La pestaña Viento de Clima y Energía dibuja ERA5 sin cambios de frontend. Sin cambios de contrato.

**Resultado real:**
- El viento medio difiere 55 % en Moquegua (MERRA-2 3.88, ERA5 1.76 m/s) y 41 % en Arequipa.
- La bajada de viento que MERRA-2 marca como significativa en el período completo no se sostiene en 2005–2023.
- Primera ejecución de Clima con los dos puntos: 43 s; la siguiente, 11 s.

**Verificación:**
- 199/199 pruebas; 3 nuevas en `test_era5.py`. `conftest.py` aísla el viento de la red y limpia las descargas en curso.
- API real dos veces (descarga y caché).
- QA visual de la pestaña Viento en 1440 y 390, sin errores ni desbordamiento.

**Para Codex:** agregar a la ficha PVGIS-ERA5 de `DATA_SOURCES.md` el endpoint `seriescalc`:
- variable `WS10m` en m/s, horaria y en UTC;
- un año por consulta;
- ~750 KB por año.

Fusionar con la puerta común; push solo con aprobación de Christian.
## 2026-10-27 · Claude · claude/pdf-linea-base · Relieve cruzado con Copernicus GLO-30 (ADR-039)

**Qué entró (sobre cbc0ffc):**
- `connectors/copernicus/dem.py`: Copernicus DEM GLO-30 (TanDEM-X) en AWS Open Data, sin cuenta y sin GDAL. Lee por rango el encabezado y el bloque del punto (~2.5 MB) y deshace DEFLATE + predictor 3 con `zlib` y `numpy`; pendiente de Horn 3 × 3; caché sin vencimiento.
- `extract_terrain` (común a todos los módulos con relieve) consulta Copernicus en paralelo con NASADEM.
- `TerrainSiteResult.crosscheck` (aditivo). Si Copernicus falla, queda en las limitaciones del sitio, nunca como ceros.
- `terrain_discoveries` en Clima, Energía y la línea base:
  - coinciden si Δelevación < 50 m y Δpendiente < 5°;
  - el cruce del umbral de 15° según el modelo se marca aparte.
- La coincidencia CENEPRED + pendiente cita además Copernicus.
- Panel de relieve con la línea «Contraste Copernicus GLO-30» y cita en el PDF. Sin dependencias nuevas.

**Resultado real:**
- Moquegua, Arequipa e Ilo coinciden (Δ ≤ 7 m, ≤ 1.5°).
- Lurigancho-Chosica difiere en pendiente: 32.2° frente a 23.0°, ambos > 15°.

**Verificación:**
- 203/203 pruebas, 4 nuevas con un COG sintético completo.
- API real en Energía y Amenazas.
- QA `release_ui` en 1440, 768 y 390 limpio, y capturas del panel de relieve.
- Build correcto.

**Para Codex:** registrar Copernicus GLO-30 en `DATA_SOURCES.md`:
- bucket `copernicus-dem-30m`, nombre de tesela `Copernicus_DSM_COG_10_{S|N}lat_00_{W|E}lon_00_DEM`;
- float32, EGM2008, 1 arc-second;
- licencia Copernicus DEM (uso libre con atribución «© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved»), a verificar en la página oficial.

Fusionar con la puerta común; push solo con aprobación de Christian.

## 2026-10-27 · Codex · `master` · `4883765` · integración y QA de viento ERA5 + Copernicus GLO-30

**Fusión aprobada:** `claude/pdf-linea-base` avanzó `master` desde `f2c50f1` hasta `4883765` por fast-forward, sin conflictos. Entraron `seriescalc` para viento horario ERA5 y el contraste aditivo `TerrainSiteResult.crosscheck` con Copernicus DEM GLO-30. No se modificó el contrato común fuera de los campos aditivos ya documentados por Claude.

**Catálogo y cumplimiento:** `DATA_SOURCES.md` amplía PVGIS-ERA5 con `seriescalc`, `WS10m` en m/s, timestamps UTC, un año por consulta, límite global de seis, umbral de 90 % de horas válidas, espera de 45 s y caché cerrada sin vencimiento. La ficha Copernicus registra el bucket público `copernicus-dem-30m`, patrón de nombres, GLO-30 2021, COG float32, 1 arc-second, WGS84/EGM2008, lectura por rango, semántica DSM y la atribución oficial para datos adaptados. La licencia fue contrastada con la página oficial de Copernicus; redistribuir rásteres derivados completos permanece como verificación de cumplimiento separada.

**Corrección de QA:** el doble común de Copernicus estaba en un fixture `function-scope`, pero `test_assistant` construye sobres en `module-scope`; en una máquina sin caché previa intentaba crear la caché real antes del mock. `backend/tests/conftest.py` instala ahora los conectores sin red a nivel de sesión y mantiene la limpieza de tareas en curso por prueba. La suite deja de depender del estado local o de acceso de escritura al caché de producción.

**Contraprueba independiente en vivo:** una descarga directa de PVGIS 5.3 `seriescalc` para Moquegua/2023 devolvió 8,760 valores válidos y media 1.7791 m/s; una media independiente y `annual_wind()` coincidieron a cuatro decimales. La lectura pública GLO-30 seleccionó `Copernicus_DSM_COG_10_S18_00_W071_00_DEM` y produjo 1,413.3 m / 6.04°, con `REAL_DATA`, coherente con el contraste NASADEM documentado.

**Puerta común:** 203/203 pruebas backend; build Next.js 16.4.2 con 17 rutas; `npm audit --audit-level=high` = 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias. Las únicas advertencias de pytest son deprecaciones de terceros en ReportLab y Starlette.

**QA visual independiente:** servicios temporales en `localhost:13105` y `127.0.0.1:18105`. Energía completó para Moquegua/Arequipa; la pestaña Viento mostró MERRA-2 continua y ERA5 discontinua, y el panel de relieve mostró 1,413 m/6.04° y 2,320 m/3.27° para Copernicus. El flujo publicó las diferencias de viento de 55 % y 41 % y las coincidencias NASADEM/Copernicus. En escritorio y 390×844 hubo desbordamiento horizontal 0, sin overlay ni mensajes de consola.

**Operación y publicación:** los listeners temporales 13105/18105 se apagaron. No se levantó ni modificó el stack 3100/8000. No se hizo push porque esta instrucción no incluye aprobación explícita de Christian. No se creó `v0.1.0`.

## 2026-10-28 · Claude · claude/pdf-linea-base · Cobertura cruzada con ESA WorldCover (ADR-040)

**Qué entró (sobre master 6f64d52):**
- `connectors/cog.py`: lector común de COG sin GDAL. Encabezado con todos los niveles, bloques DEFLATE con predictor 1, 2 o 3 y caché sin vencimiento. `connectors/copernicus/dem.py` pasa a usarlo, con el mismo resultado real.
- `connectors/esa/worldcover.py`: ESA WorldCover 10 m 2021 v200 en AWS Open Data.
  - Nivel más detallado que quepa en 16 bloques por tesela.
  - Conteo en centros de píxel dentro del área con `shapely.contains_xy`.
  - Clase 0 fuera; borde de tesela sin conteo doble.
- `orchestration/cover_crosscheck.py`: tres grupos frente a MOD44B 2021, en la ventana MODIS y sin el agua.
- `cover_discoveries`: coinciden si cada grupo difiere menos de 10 puntos; difieren desde 20.
- **Contrato aditivo:** `SubjectBaseline.land_cover_check`.
- Tabla «Contraste de cobertura» en Ambiente; `table.compactTable` para las tablas de tres columnas en móvil. PDF con tabla y cita.

**Resultado real:**
- Ilo coincide (±4 puntos).
- Moquegua (1 km sobre la ciudad) queda a 13–15 puntos, en la franja intermedia.

**Verificación:**
- 208/208 pruebas; 5 nuevas en `test_worldcover.py`, más la integración ambiental. `conftest.py` aísla WorldCover en la instalación de sesión.
- API real con PDF.
- QA `baseline_ui` y `release_ui` en 1440, 768 y 390 limpio.
- Build correcto; audit 0.

**Para Codex:** registrar ESA WorldCover en `DATA_SOURCES.md`:
- bucket `esa-worldcover` (eu-central-1), ruta `v200/2021/map/ESA_WorldCover_10m_2021_v200_{S|N}lat{W|E}lon_Map.tif`, teselas de 3° por esquina suroeste;
- uint8, clases 10–100 y 0 sin dato;
- CC BY 4.0, cita Zanaga et al. 2022, doi:10.5281/zenodo.7254221. Verificar el DOI en la página oficial.

Fusionar con la puerta común; push solo con aprobación de Christian.

## 2026-10-28 · Codex · `master` · `1b6bc54` · integración y QA de ESA WorldCover (ADR-040)

**Fusión aprobada:** `claude/pdf-linea-base` avanzó `master` desde `6f64d52` hasta `1b6bc54` por fast-forward, sin conflictos. Entraron el lector COG común, ESA WorldCover 2021 v200, el contraste de cobertura con MOD44B y el campo aditivo `SubjectBaseline.land_cover_check`.

**Catálogo y cumplimiento:** `DATA_SOURCES.md` registra el bucket público `esa-worldcover` en `eu-central-1`, la ruta `v200/2021/map`, el patrón oficial de teselas de 3°, EPSG:4326, COG uint8, clases 10–100 y 0 como nodata. También documenta CC BY 4.0, la atribución oficial y Zanaga et al. (2022), DOI `10.5281/zenodo.7254221`. La ficha advierte que la exactitud global publicada es 76.7 %, que clase dominante a 10 m y fracción MOD44B a 250 m no son magnitudes idénticas y que 2020 v100/2021 v200 no deben interpretarse como cambio sin armonizar algoritmos.

**Corrección geoespacial:** la ventana cuadrada de contraste ya no convierte kilómetros a grados mediante constantes. `square_window_km()` construye la geometría en una proyección AEQD local, mide en metros y devuelve WGS84; la prueba geodésica independiente verifica inclusión a 990 m y exclusión a 1,010 m en los cuatro rumbos cardinales.

**Contraprueba independiente en vivo:** una consulta WorldCover para un círculo geodésico de 1 km en Moquegua leyó 38,380 píxeles efectivos de 9.3 m de la tesela `ESA_WorldCover_10m_2021_v200_S18W072_Map.tif`, con `REAL_DATA`: construido 66.33 %, suelo desnudo/vegetación escasa 26.70 %, matorral 3.58 %, árboles 2.31 %, pastizal 0.98 %, cultivo 0.09 % y agua 0.01 %. El lector COG compartido conservó el resultado independiente de Copernicus DEM: 1,413.3 m y 6.04° para Moquegua.

**Puerta común:** 209/209 pruebas backend; build Next.js 16.4.2 con 17 rutas; `npm audit` = 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias. Las únicas advertencias de pytest son deprecaciones de terceros en ReportLab y Starlette.

**QA visual independiente:** servicios temporales en `localhost:13106` y `127.0.0.1:18106`. Ambiente completó para Moquegua/Arequipa, mostró el encabezado «Contraste de cobertura 2021», la contradicción MODIS/WorldCover de Arequipa y procedencia explícita. En 1440×900 y 390×844 hubo desbordamiento horizontal 0. El único evento de consola fue un 404 no funcional de `favicon.ico`, que queda como incidencia visual para Claude; no afectó el análisis ni los resultados.

**Operación y publicación:** los servicios temporales y Edge headless se apagaron al terminar. No se levantó ni modificó el stack 3100/8000. No se hizo push porque esta instrucción no incluye aprobación explícita de Christian. No se creó `v0.1.0`.

## 2026-10-30 · Claude · claude/pdf-linea-base · Ícono de la aplicación

**Qué entró (sobre master 4b430f7):** `frontend/app/icon.svg` (fondo `#141618`, acento `#38d9c3`). Next lo enlaza como `<link rel="icon" type="image/svg+xml">`, así el navegador ya no pide `/favicon.ico`, el 404 que registró Codex.

**Verificación:**
- Build correcto: la ruta `/icon.svg` es estática.
- En 3100, la página enlaza `/icon.svg?…` y responde 200.
- Carga en Playwright sin respuestas 4xx/5xx ni errores de consola. El Chromium sin interfaz no pide favicons, así que el 404 original se confirma en Browser con interfaz.
- Sin cambios de backend.

## 2026-10-30 · Codex · `master` · `50f5db3` · integración y QA del ícono de aplicación

**Fusión aprobada:** `claude/pdf-linea-base` avanzó `master` desde `4b430f7` hasta `50f5db3` por fast-forward, sin conflictos. El único cambio funcional es `frontend/app/icon.svg`; no cambió backend, contrato ni dependencias.

**Puerta común:** 209/209 pruebas backend; build Next.js 16.4.2 con 18 rutas, incluida `/icon.svg` estática; `npm audit --omit=dev` = 0 vulnerabilidades. El script `scripts/audit_project.py` exigido por la Skill ya no existe en este repositorio, por lo que esa comprobación queda no aplicable y no se reporta como ejecutada.

**QA en navegador con interfaz:** como el plugin Browser no está disponible y el repositorio no incluye Playwright, se abrió Edge real sin `--headless` sobre `http://127.0.0.1:13107/` y se inspeccionó la recarga mediante DevTools. El documento publicó exactamente un `<link rel="icon" type="image/svg+xml">`; `/icon.svg?…` respondió 200 con `image/svg+xml`; hubo 0 solicitudes a `/favicon.ico`, 0 respuestas 4xx/5xx, 0 errores/advertencias de consola, 0 overlay y 0 px de desbordamiento horizontal.

**Operación y publicación:** el servidor temporal 13107 y Edge/DevTools 19230 se apagaron al terminar. No se levantó ni modificó el stack 3100/8000. No se hizo push porque esta instrucción no incluye aprobación explícita de Christian. No se creó `v0.1.0`.

## 2026-10-30 · Codex · `master` · `29ad776` · integración del anteproyecto final

**Fusión aprobada:** `claude/pdf-linea-base` (`ccca9ec`) se integró en `master` mediante merge commit `29ad776`, conservando el QA del favicon de `56030e5`. Los tres commits nuevos (`0e1e28b`, `450ed38`, `ccca9ec`) modifican exclusivamente el PPTX y el PDF de `docs/nasa-submission/anteproyecto`; no cambian código, contratos ni dependencias.

**QA documental:** la versión final contiene una diapositiva/página A4. El PPTX pasó la inspección estructural OOXML con 0 hallazgos y la validación de geometría, ajuste de títulos y viñetas con 0 hallazgos/advertencias. Se renderizaron ambos formatos completos: PPTX 636×900 y PDF 637×901; la comparación visual confirmó el mismo contenido, sin recortes, solapamientos, glifos rotos ni texto ilegible. `pdfinfo` confirmó 1 página A4, PDF 1.7, sin cifrado, formularios ni JavaScript.

**Puerta común:** 209/209 pruebas backend; build Next.js 16.4.2 con 18 rutas; `npm audit --omit=dev` = 0 vulnerabilidades. Las únicas advertencias de pytest son deprecaciones de terceros en ReportLab y Starlette.

**Publicación:** no se hizo push porque esta instrucción no incluye aprobación explícita de Christian. No se creó `v0.1.0` y no se modificó el stack 3100/8000.
## 2026-10-30 · Claude · claude/pdf-linea-base · Piloto eólico (ADR-041)

**Qué entró:** eólica como segunda tecnología de Energía, con `POST /api/v1/projects/wind-screening` y `Sector.WIND` (C2 aditivo).
- **Fuentes:** NASA POWER horario (WS50M/WS10M, diez años) y Global Wind Atlas 4.0, leído como BigTIFF/ZSTD con el lector COG común.
- **Energía:** cizalladura y densidad por sitio, curva genérica.
- **Caso base:** nivel del atlas con la forma horaria de NASA. El nivel NASA queda como adverso.
- **Resultados:** puntaje, tornado, descubrimientos y PDF.
- **Refactor:** `sectors/energy_common.py` reúne los formatos y equilibrios que antes estaban privados en `solar.py`. La solar los importa sin cambiar su comportamiento.

**Validación:** la producción COES 2024 de Tres Hermanas (56.5 %) y Marcona (57.7 %) contra el modelo. Con el nivel del atlas da 46.7 % neto; con el de MERRA-2, 14 %.

**Para Codex:**
- **Dependencia nueva:** `zstandard==0.23.0` en `backend/requirements.txt` (BSD, versión de jul-2024), porque el atlas usa compresión 50000. Revisarla en la auditoría.
- **DATA_SOURCES.md:** faltan dos fichas.
  - NASA POWER Hourly Point API v2.10.3.
  - Global Wind Atlas 4.0: `https://globalwindatlas.info/api/gis/country/PER/wind-speed/{50|100}`, que redirige a `gwa.cdn.nazkamapps.com/country_tifs_v4/`. Va con CC BY 4.0 y la atribución DTU/Banco Mundial. Christian puede confirmar la cita preferida en globalwindatlas.info.
- **COES:** el conector solo filtra tipo SOLAR. La validación eólica se hizo con un script de QA fuera del producto (`.claude-qa/coes_wind_check.py`). Un factor de planta eólico real por central sería un K-siguiente natural.

**Verificación:** ver ADR-041 (pruebas, QA 1440/390 y PDF).
**Bloqueos:** ninguno. Hidroeléctrica es lo siguiente.

## 2026-11-10 · Codex · `master` · integración y QA del piloto eólico (ADR-041)

**Fusión aprobada:** `claude/pdf-linea-base` (`a94d61c`) se integró en `master` mediante merge commit `a42de58`, conservando los tres commits posteriores que ya estaban en la línea principal. El cambio es aditivo: `Sector.WIND`, `POST /api/v1/projects/wind-screening`, POWER horario, Global Wind Atlas, cálculo energético/financiero, puntaje, PDF y pantalla. `codex/nasadem-resumable` ya era ancestro de `master`; no quedaba un commit NASADEM separado por integrar.

**Fuentes y contraprueba real:** `DATA_SOURCES.md` registra NASA POWER Hourly y Global Wind Atlas 4.0, sus resoluciones, semántica, caché, licencia y limitaciones. Una consulta independiente para Marcona el 10-nov-2026 recuperó 8,784 pares horarios de 2024, media `WS50M` 5.8844 m/s y encabezado API **v2.10.4** (`REAL_DATA`); se conserva también la evidencia v2.10.3 del 30-oct porque el conector lee la versión y no la fija. El Atlas devolvió 9.09 m/s a 50 m y 9.74 m/s a 100 m; la ruta oficial redirigió al TIFF `country_tifs_v4` y aceptó HTTP 206. El recálculo independiente de COES con 8,784 h reprodujo Tres Hermanas 56.46 %, Marcona 57.66 % y San Juan 51.59 %; 204,355 MWh/año sobre 50 MW reprodujo 46.66 % neto del modelo.

**Dependencia:** `zstandard==0.23.0` instaló correctamente, declara licencia BSD y `pip check` no encontró incompatibilidades. `pip-audit 2.10.1` no reportó vulnerabilidades para Zstandard. La auditoría completa sí expuso deuda previa ajena a este commit en `pypdf 5.1.0`, `starlette 0.41.3` y `pytest 8.3.4`; actualizar FastAPI/Starlette y pypdf requiere una rama de mantenimiento y regresión de PDF/API, no una modificación silenciosa del piloto.

**Puerta común:** 225/225 pruebas backend; build Next.js 16.4.2 con 19 rutas; `npm audit --omit=dev` = 0 vulnerabilidades. `audit_project.py` no existe en el repositorio actual, por lo que esa comprobación permanece no aplicable. QA en el navegador integrado sobre `127.0.0.1:13108` y API temporal `18108`: selección Solar → Eólica comprobada, panel eólico visible, 0 errores/advertencias de consola, 0 overlay y 0 px de desbordamiento en escritorio y 390 × 844. Los listeners temporales se cerraron.

**Docker:** `docker compose build api` no pudo ejecutarse porque el motor Linux de Docker Desktop no estaba activo (`dockerDesktopLinuxEngine` inexistente). No se inició Docker Desktop para evitar levantar o alterar los stacks reservados en 3100/8000. La imagen queda como única verificación operativa pendiente; las pruebas usan la misma versión fijada y el import de Zstandard quedó validado en `.venv`.

**Publicación:** Christian autorizó subir `master` a `origin`. No se crea `v0.1.0`. El SHA remoto exacto se verificará después del push; por definición no puede autorreferenciarse dentro del commit que contiene esta entrada.

## 2026-11-10 · Claude · claude/pdf-linea-base · Guía del equipo y piloto hidroeléctrico (ADR-042)

**Qué entró (sobre master `dd09f34`):**
- **Documentos del equipo:** `docs/equipo/EMPEZAR_AQUI.md`, `docs/equipo/pipeline.html` (red del proyecto, lee `docs/interno/dop-datos.js`) y `CLAUDE.md`. Solo documentación.
- **Hidroeléctrica de pasada:** tercera tecnología de Energía, con `POST /api/v1/projects/hydro-screening` y `Sector.HYDRO` (C2 aditivo).
  - Caudal diario GloFAS v4 vía Open-Meteo, con una regla declarada para hallar la celda del cauce.
  - Segunda opinión del caudal con GEOGLOWS v2, buscada en una malla de ±4.4 km, en segundo plano y con 40 s de espera.
  - Salto con NASADEM entre toma y casa de máquinas, contrastado con Copernicus; sin token de Earthdata funciona con Copernicus.
  - Energía día por día, curva de duración, potencia como resultado, VAN con tornado, puntaje, descubrimientos y PDF.
- **Piezas comunes tocadas (sin cambiar el comportamiento de los otros sectores):**
  - `orchestration/annual_crosscheck.py` reúne el contraste anual que antes vivía en `era5_crosscheck.py`.
  - `extraction_stage(..., provider=)` y `SectorLens.location_note`, ambos con el valor anterior por defecto.
  - `discoveries.short()` reconoce GEOGLOWS; nuevas constantes de caudal y salto.

**Validación:** producción COES 2024 de la C.H. Machupicchu (1,252,221 MWh; 192.45 MW; factor de planta 74.1 %). El modelo da entre 64.7 % y 77.1 % según el caudal ecológico que se suponga, y 163 MW de potencia. Detalle y límites en ADR-042.

**Para Codex:**
- **DATA_SOURCES.md:** faltan dos fichas.
  - GloFAS v4 (Copernicus EMS) vía Open-Meteo Flood API: `https://flood-api.open-meteo.com/v1/flood`, variable `river_discharge`, 0.05°, válido desde 1997-01-01 en esa API. Anotar la licencia de Copernicus y que el uso gratuito de Open-Meteo es solo no comercial y con cuota.
  - GEOGLOWS River Forecast System v2: `https://geoglows.ecmwf.int/api/v2/` (`getriverid`, `annualaverages`), CC BY 4.0, simulación histórica forzada con ERA5.
- **Sin dependencias nuevas.**
- **Docker:** la imagen de la API se reconstruyó aquí y el stack 3100/8000 corre con este commit. La caché del contenedor es un volumen aparte de la del `.venv`.
- **Cuidado con las cuotas al probar:** una serie nueva de GloFAS pesa ~76 llamadas de Open-Meteo (tope 600 por minuto) y GEOGLOWS corta las ráfagas de más de unas pocas conexiones.

**Verificación:** 250 pruebas backend (25 nuevas), build con 20 rutas, `npm audit` en 0, auditor científico `ok: true`, QA en navegador 1440/768/390 (puerta de cierre y pantalla hidroeléctrica) sin errores de consola ni desbordes. Detalle en ADR-042.

**Bloqueos:** ninguno. No se hace push ni se crea `v0.1.0` sin la aprobación de Christian.

## 2026-11-10 · Claude · claude/pdf-linea-base · El relieve cruzado en vial, inmobiliario y el puntaje (ADR-043)

**Qué entró (sobre el commit hidroeléctrico `a33f782`):**
- **Descubrimientos en vial e inmobiliario:** `sectors/road.py` y `sectors/real_estate.py` registran el contraste NASADEM ↔ Copernicus que `extract_terrain` ya traía. Tres líneas por sector; el resto del cálculo de K2 y K3 no cambia.
- **Puntaje recalculado con el segundo modelo (`orchestration/slope_check.py`):** solar, eólico, vial e inmobiliario agregan una nota que dice si el primer lugar cambia con la pendiente de Copernicus. `_scorecard` de vial e inmobiliario recibe `terrain` como parámetro opcional.
- **`record_in_pipeline(..., empty=)`:** en vial e inmobiliario, una lista vacía se declara como «Sin contraste del relieve».
- **Texto del método del puntaje:** declara la regla de empate práctico y recupera las comas que un `replace` le quitaba. En pantalla, el empate ya no dice «solo en 99 %».

**Resultado real:** en el corredor Moquegua–Ilo, el Tramo 5 tiene 17.9° en NASADEM y 12.5° en Copernicus; sigue primero (44.4 frente a 37.1). En solar, eólico e inmobiliario el primer lugar tampoco cambia. Detalle en ADR-043.

**Regresión funcional de los módulos existentes (10-nov, stack 3100/8000):** `pipeline`, `climate_ui`, `baseline_ui`, `road_ui`, `realestate_ui`, `scorecard_ui`, `sensitivity_ui`, `assistant_ui`, `territory_ui`, `layers_ui`, `geometry_ui`, `pdf_e2e`, `release_ui` y `energy_ui`, cada uno en 1440/768/390 donde aplica: sin errores de consola, sin desbordes y sin recortes.

**Para Codex:** sin fuentes ni dependencias nuevas. `road.py` y `real_estate.py` son tuyos: revisa el cambio antes de fusionar.

**Verificación:** 260 pruebas backend (10 nuevas), build con 20 rutas, `npm audit` en 0.

## 2026-11-10 · Claude · claude/pdf-linea-base · CENEPRED exige token: última copia válida (ADR-044)

**Qué pasó:** desde hoy `https://sigrid.cenepred.gob.pe/arcgis/rest/services/FEN/ER_NINO2027_BD/MapServer` responde `{"error": {"code": 499, "message": "Token Required"}}` y el directorio público ya no lista los servicios (solo quedan `SampleWorldCities` y `sigrid/sigrid_collect`). Las tres capas de CENEPRED quedaron como `DATA_UNAVAILABLE` en amenazas, vial e inmobiliario. Lo detectó la regresión funcional, no una prueba unitaria: los dobles no ven un proveedor que cierra.

**Qué entró:**
- **Última copia válida** en `connectors/peru/territory.py` y `connectors/peru/identify_layers.py`: si el servicio falla y la caché guarda una respuesta anterior de la misma consulta (hasta 90 días), se muestra como `CACHED_DATA` con su fecha original y el motivo. Sin copia, sigue `DATA_UNAVAILABLE`.
- **Campo aditivo `stale_note`** en `TerritorialSourceResult`, `BaselineLayer`, `RoadTerritorialSourceSummary` y `RealEstateTerritorialSourceSummary`.
- **Declaración:** etiqueta «copia del 25-oct-2026» junto al dato, nota al pie, brecha con procedencia `CACHED_DATA` (`orchestration/stale_copies.py`), advertencia en los descubrimientos que usan la capa y línea en el PDF.
- **Reintentos:** una falla por credenciales ya no se reintenta; el muestreo por puntos deja de llamar tras la primera falla.

**Resultado real:** el corredor Moquegua–Ilo recupera el riesgo de inundación y de movimientos en masa por tramo (copia del 25-oct); Lurigancho recupera las tres capas (copia del 27-oct) y el descubrimiento CENEPRED ↔ NASA; el puntaje inmobiliario vuelve a cobertura 100 %.

**Para Codex:**
- **`DATA_SOURCES.md`, ficha de CENEPRED:** anotar que desde el 10-nov-2026 el servicio exige token y que la aplicación solo muestra copias anteriores de consultas ya hechas, declaradas con su fecha.
- **`territory.py` es tuyo:** `_layer_query` ahora devuelve cuatro valores (el cuarto es el motivo cuando la respuesta sale de la copia). Revisa el cambio.
- **Tu caché es otra:** las copias viven en el volumen `power-cache` de este stack. En tu carpeta, o en la de cualquier compañero, CENEPRED saldrá «No disponible» salvo que tengan copias propias de antes del cierre.
- **SIGDA:** en la corrida del mediodía no respondió nueve capas del distrito de Ilo y una hora después sí. Espaciar las corridas de `baseline_ui`.

**Decisión que le toca a Christian:** gestionar o no un acceso con CENEPRED. Aquí no se crean cuentas a nombre de nadie.

**Verificación:** 266 pruebas backend (6 nuevas), build con 20 rutas, `npm audit` en 0, auditor científico `ok: true`; QA en navegador a 1440 y 390 en amenazas y vial, y `release_ui`, `road_ui` y `realestate_ui` en los tres anchos.

## 2026-11-10 · Claude · claude/pdf-linea-base · Materiales de entrega y validación a la vista (ADR-045)

**Qué entró:**
- **Materiales de entrega (en inglés, como el resto de `docs/nasa-submission`):** `DEMO_SCENARIOS.md` con ocho actos ensayados (clima, amenazas en Lurigancho–Chosica, vial, solar, eólica, hidroeléctrica y PDF), `PITCH.md`, `PROJECT_OVERVIEW.md` y `SCIENTIFIC_METHODOLOGY.md`. Los dos últimos describían el MVP de octubre.
- **`scripts/qa/demo_ensayo.cjs`:** actos 1B, 2C y 2D; una captura fallida ya no detiene el ensayo.
- **Leyenda de sensibilidad por sector:** dejó de decir «NASA POWER» donde el rango sale de GloFAS o es un supuesto.
- **`method_validation` en el sobre C2 (aditivo, ADR-045):** eólica e hidroeléctrica muestran junto al método, en pantalla y en el PDF, su validación con la producción real del COES.
- **Equipo:** `pipeline.html` con F1 y F2 hechas, idea A11 «Acceso a CENEPRED» y la guía con el aviso de CENEPRED.

**Para Codex:**
- `TECHNICAL_ARCHITECTURE.md` sigue en el estado del 25-oct: faltan eólica, hidroeléctrica, los conectores de segunda fuente y la última copia válida. Es tuyo.
- `docs/nasa-submission/AI_USE.md` es un borrador de la declaración de uso de IA que piden las bases de 2026: el equipo lo confirma contra la guía de entrega (se publica el 13-nov).

**Verificación:**
- 266 pruebas backend, build con 20 rutas, `npm audit` en 0.
- Regresión funcional del 10-nov con los catorce guiones de `scripts/qa` (`pipeline`, `climate_ui`, `baseline_ui`, `road_ui`, `realestate_ui`, `energy_ui`, `scorecard_ui`, `sensitivity_ui`, `assistant_ui`, `territory_ui`, `layers_ui`, `geometry_ui`, `pdf_e2e`, `release_ui`): sin errores de consola, desbordes ni recortes; las salidas se leyeron, no solo los códigos. Corrió sobre el build anterior a ADR-045; después de ADR-045 se repitieron `release_ui`, `energy_ui` y `pdf_e2e`, también limpios.
- Estado de las capas en esa corrida: CENEPRED desde su última copia válida; el inventario de INGEMMET sin publicar; SIGDA respondió.

## 2026-11-10 · Claude · claude/pdf-linea-base · Alcance global y alertas del mundo (ADR-046)

**Contexto:** Christian pidió cerrar los puntos sin esperar a Codex y abrir el alcance al mundo. Esta rama parte de `master` `31455e2` (con la corrección de procedencia mixta de Codex, ya integrada).

**Qué entró:**
- **País de un punto** (`geospatial/countries.py`, Natural Earth 1:110m en `backend/data/world/`).
- **Atlas Eólico por país:** `WindAtlasConnector` lee el archivo del país del punto; ya no existe la constante `COUNTRY`.
- **Capas peruanas solo en el Perú:** `sectors/baseline.py`, `road.py` y `real_estate.py` no consultan servicios peruanos para áreas en otro país y lo declaran en una brecha.
- **Alertas del mundo:** `connectors/gdacs/events.py`, `connectors/nasa/eonet.py`, `orchestration/world_alerts.py`, `schemas/world.py`, `api/world.py` (`GET /api/v1/world/alerts` y `/world/places`), `connectors/openmeteo/geocoding.py` y `connectors/http_json.py` (GET con caché y última copia válida).
- **Pantalla:** `world-alerts.tsx` (panel, pulsos y buscador de lugares), cambios en `geo-map.tsx`, `workspace.tsx` y `styles.css`; rutas `frontend/app/api/world-alerts` y `places`.
- **`DATA_SOURCES.md`:** fichas de GDACS, NASA EONET, el geocodificador de Open-Meteo y Natural Earth, y el Atlas Eólico por país. Las condiciones de reutilización de GDACS y EONET quedan marcadas como no verificadas.
- **Títulos** de solar, eólica e hidroeléctrica sin «Perú».

**Para Codex cuando revise:** sin dependencias nuevas. `countries_110m.geojson` (200 KB) va versionado: es de dominio público. Las pruebas no salen a la red; `world_alerts` y el geocodificador se prueban con dobles.

**Verificación:** 276 pruebas backend (10 nuevas), build con 22 rutas, `npm audit` en 0, auditor científico `ok: true`. `world_ui.cjs` en 1440/768/390 y regresión de `release_ui`, `climate_ui`, `energy_ui`, `road_ui` y `baseline_ui`.

## 2026-11-10 · Codex · `master` · ver `git log -1` · integración ADR-042 a ADR-045 y cierre documental

**Fusión:** los once commits de `claude/pdf-linea-base` (`552060a`) se integraron sobre `dd09f34` mediante el merge local `430dd8b`, sin conflictos. Se revisaron expresamente el contrato de cuatro valores de `TerritoryConnector._layer_query`, la propagación de `stale_note` y los cambios de relieve cruzado en `road.py` y `real_estate.py`. No entraron dependencias nuevas.

**Documentación:** `DATA_SOURCES.md` incorpora GloFAS v4 vía Open-Meteo y GEOGLOWS v2, separa la licencia/atribución del dato de las condiciones del intermediario, registra CC BY 4.0 para GEOGLOWS y documenta cuotas/no comercialidad del endpoint gratuito de Open-Meteo. La ficha CENEPRED declara el `499 Token Required` observado desde el 10-nov y la regla de última copia válida con fecha original. `TECHNICAL_ARCHITECTURE.md` ya incluye eólica, hidroeléctrica, segundas fuentes, los endpoints nuevos y la semántica de copias vencidas de ADR-044.

**Puerta común:** 266/266 pruebas backend; build Next.js 16.4.2 con 20 rutas; `npm audit --omit=dev` con 0 vulnerabilidades; auditor científico `ok: true`, sin errores ni advertencias. No se repitieron `baseline_ui` ni `demo_ensayo`: la regresión visual completa y la repetición posterior a ADR-045 ya están registradas en la entrada de Claude, y una nueva ráfaga habría añadido carga innecesaria a SIGDA.

**Operación:** no se ejecutó Docker ni se tocó el volumen `power-cache` del stack de Claude. En esta carpeta CENEPRED seguirá correctamente como «No disponible» si no existe una copia previa propia. No se hizo push y no se creó `v0.1.0`; ambos quedan sujetos a aprobación explícita de Christian.

## 2026-11-10 · Codex · `master` · revisión independiente posterior a ADR-042–ADR-045

**Corrección de procedencia:** la revisión encontró un caso mixto no cubierto por las pruebas originales: una fuente ArcGIS compuesta podía combinar una subcapa recién descargada con otra recuperada como «última copia válida» y etiquetar el agregado como `REAL_DATA`. `territory.py` e `identify_layers.py` ahora aplican la regla conservadora: si existe cualquier `stale_note`, el resultado agregado es `CACHED_DATA`, conserva la fecha de la copia más antigua y mantiene el motivo visible. Dos pruebas reproducen la mezcla real+copia tanto para consultas por área como para muestreo `identify`.

**Fuentes y arquitectura:** `DATA_SOURCES.md` deja de llamar independiente a GEOGLOWS: GloFAS y GEOGLOWS comparten forzamiento ERA5; el contraste aporta otro modelo de tránsito y otra red fluvial, no una observación climática independiente. `TECHNICAL_ARCHITECTURE.md` queda explícitamente como pre-release sin etiqueta, enumera los nueve sobres sectoriales, documenta `method_validation`, los tres endpoints de línea base, los contrastes IMERG/CHIRPS y la semántica exacta de `stale_note` por clave de consulta.

**Verificación independiente:** la documentación oficial de Open-Meteo confirma GloFAS v4, `river_discharge` en m³/s, grilla de 0.05° y las condiciones/cuotas del endpoint gratuito; la licencia oficial de GEOGLOWS confirma CC BY 4.0. Una consulta directa al MapServer de CENEPRED el 10-nov-2026 respondió HTTP 200 con error ArcGIS `499 Token Required`, por lo que sin copia propia el estado correcto sigue siendo `DATA_UNAVAILABLE`. El recálculo separado del caso Machupicchu reproduce el factor de planta COES `1,252,221 / (192.45 × 8,784) = 0.7407` y la potencia del método `ρgQHη = 163.16 MW` con 61 m³/s, 330 m, 5 % de pérdidas y eficiencia 0.87.

**Puerta común actual:** 268/268 pruebas backend; build Next.js 16.4.2 con 20 rutas; `npm audit --omit=dev` con 0 vulnerabilidades. Las dos únicas advertencias de pytest son deprecaciones de terceros en ReportLab y Starlette. El repositorio no contiene `scripts/audit_project.py`, así que el auditor científico no pudo repetirse en esta revisión y no se declara como ejecutado aquí; permanece la evidencia de Claude registrada en ADR-042–ADR-045.

**QA visual acotado:** con API y web temporales en 18109/13109 se comprobó la selección de «Hidroeléctrica de pasada» y sus campos de toma/casa de máquinas en escritorio y 390 × 844: 0 errores de consola y 0 px de desbordamiento horizontal. No se envió un análisis remoto, por lo que no se consumió cuota de GloFAS/GEOGLOWS ni se consultó SIGDA. Ambos procesos temporales se cerraron.

**Operación y publicación:** no se levantaron ni tocaron 3100/8000, Docker o `power-cache`; no se repitieron `baseline_ui` ni `demo_ensayo`. No se hizo push y no se creó `v0.1.0`, conforme al protocolo de aprobación de Christian.

## 2026-11-11 · Claude · claude/pdf-linea-base · «Entrar a la zona»: maqueta en bloques de Moquegua y del volcán Taal (ADR-047)

**Contexto:** Christian pidió que, desde las alertas del globo, se pueda entrar a un lugar y recorrerlo como en un juego de bloques. Alcance acordado: dos zonas para la entrega.

**Qué entró:**
- **Backend:** `backend/app/zones/builder.py` (ventana de Copernicus DEM y WorldCover, cuadrícula de bloques, pendiente de Horn antes de exagerar, agua plana), `zones/store.py`, `schemas/zones.py`, rutas `GET /api/v1/world/zones` y `/world/zones/{id}` en `api/world.py`, y las dos zonas ya construidas en `backend/data/zones/` (215 KB cada una).
- **Guion:** `scripts/zones/build_zones.py` arma cada zona y sus balizas con resultados reales pedidos a la API local (necesita la API en 8000). Si un resultado no llega, la baliza no se crea.
- **Pantalla:** carpeta `frontend/app/_components/zone/` (datos, escena three.js, controles, pantalla y estilos), rutas `frontend/app/api/zones`, enlace directo `frontend/app/zona/[id]`, sección «Zonas para recorrer» en `world-alerts.tsx`, marcador de zona en `geo-map.tsx` y estado en `workspace.tsx`.
- **Dependencia nueva:** `three` 0.186.0 y `@types/three` 0.186.0, versiones exactas; se elige la 0.186.0 (8-sep-2026) y no la 0.187.0, publicada doce días antes.
- **Documentos:** ADR-047, escena en `DEMO_SCENARIOS.md`, ficha en `DATA_SOURCES.md`, `EMPEZAR_AQUI.md`, `PROGRESS.md` y la tarea F8 en `pipeline.html`.

**Para Codex cuando revise:**
- Las zonas versionan una cuadrícula derivada de GLO-30 y de WorldCover. Falta confirmar en el texto completo de la licencia de GLO-30 que se puede redistribuir; si no, los dos JSON se reconstruyen con el guion y salen del control de versiones.
- El defecto que encontró la prueba de navegador y ya está corregido: con el mouse capturado no se puede hacer clic en los paneles. Hay aviso («Esc suelta el mouse») y teclas 1 a 6 y P.
- La ficha de una baliza elegida en la lista se mantiene aunque haya otra más cerca (`pinnedRef` en `zone-explorer.tsx`).

**Verificación:** 284 pruebas backend (8 nuevas), build con 25 rutas, `npm audit` en 0, auditor científico sin errores. `scripts/qa/zone_ui.cjs` en 1440, 768 y 390: sin errores de consola, recortes, desbordes ni solapes. Docker tardó unos 10 minutos en desempaquetar la imagen web en dos compilaciones; el motor respondía y no hubo error.

**Publicación:** sin push ni etiqueta. Quedan sin subir `d9330cc`, `3517207` y este commit.
