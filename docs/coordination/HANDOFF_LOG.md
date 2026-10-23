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