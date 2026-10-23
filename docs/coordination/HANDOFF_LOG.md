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
