# Plan de trabajo conjunto — Claude Code + Codex

Fecha: 2026-10-22 · Dueño del producto: Christian · Documento vivo; cada agente actualiza solo su fila de estado.

## 0. Hitos de la sede Moquegua (mensaje de la Local Lead, 24-oct-2026)

| Fecha | Hito | Qué se entrega |
|---|---|---|
| **jue 29 oct** (límite de la sede: 30 oct) | Anteproyecto | Plantilla de una hoja de la sede: equipo, objetivos, idea principal y recursos. Sirve para asignar mentores y jueces. |
| 14 nov | Registro y equipos en la plataforma oficial | Equipo inscrito en NASA Space Apps |
| 14–15 nov | Hackathon internacional | Ajustes, demo y material de envío |
| **dom 15 nov, 23:59** | Entrega final en la plataforma oficial | Proyecto, demo (video ≤ 30 s o ≤ 7 láminas, según la guía vigente) y enlaces |

| Días | Claude | Codex |
|---|---|---|
| 24–28 oct | Anteproyecto (A1); K6 en pantalla cuando llegue | K6: escala ×24 en el muestreo regional, con prueba; manifiesto al 15-nov |
| 29 oct | Entrega del anteproyecto | — |
| 30 oct–13 nov | Material del demo (láminas y/o video), ensayo en voz alta, regresión 10 flujos × 1440/768/390 | Puerta final, push y etiqueta `v0.1.0` con aprobación de Christian |
| 14–15 nov | Hackathon: ensayo del día, precalentamiento y envío | Respaldo operativo |

Reglas: hasta el 15-nov no entran funcionalidades grandes. Si K6 no está verificado, el demo usa el acto 2B (solar) y el puntaje vial no se muestra.

### Calendario original (reemplazado el 24-oct)

Las olas salen de la vista «Orquestación» del DOP (`docs/interno/dop-neuronal.html`): cada una agrupa lo que puede avanzar en paralelo.

| Fechas | Ola | Claude | Codex | Se completa |
|---|---|---|---|---|
| 22–23 oct | 0 | Arrancar ola 1 | Fusionar y subir las ramas de Claude (X0); cerrar K0 | Base estable en `master` y GitHub |
| 23–28 oct | 1 | Extremos hidrometeorológicos; pantalla del módulo Clima; escenarios y sensibilidad financiera; dibujo y carga de corredores y polígonos | Peligros geológicos e inundación, áreas protegidas, patrimonio, comunidades, red vial; armonización espacial; catálogo de fuentes | Módulo 1 · Clima |
| 29 oct–1 nov | 2 | Puntajes multicriterio y asistente (C4, adelantados y listos el 23-oct); capas GIBS (C6); selector territorial y tendencias por celda (C7) | Límites IGN (K5); muestreo de corredores, polígonos y territorios por celdas POWER (K1); conector COES; exposición a amenazas; restricciones territoriales | Módulo 7 · Inversión; territorio y capas en la consola |
| 2–4 nov | 3 | Integración progresiva de los pilotos | Backend del piloto vial (K2) y del inmobiliario (K3), con el contrato C2 | — |
| 4–6 nov | 4 | Pantallas de los pilotos (C5) | QA cruzado, Docker y rendimiento | Módulo 6 · Vial y piloto inmobiliario |
| 6–7 nov | Cierre | `PITCH.md`, `DEMO_SCENARIOS.md` y ensayo del demo | `DATA_SOURCES.md`, `TECHNICAL_ARCHITECTURE.md`, congelamiento y etiqueta de versión | Entrega |

Reglas de calendario: si una unidad de la ola N se atrasa, lo de la ola N+1 que no depende de ella sigue adelante. Si al 4 de noviembre el piloto inmobiliario no llega, se presenta como avance sobre los mismos motores y el foco queda en el vial. El calibrador neuronal se presenta como hoja de ruta; antes de la entrega solo se verifica el acceso a los datos del COES.

## 1. Objetivo

Cerrar lo que más pesa para el jurado del NASA Space Apps Challenge sin pisarnos el trabajo:

1. Confirmar las tendencias autocorrelacionadas con Mann–Kendall modificado.
2. Reporte PDF ejecutivo.
3. Pilotos vial e inmobiliario, con el mismo motor del piloto solar.
4. Asistente analítico, determinista por defecto y con IA opcional.

Las reglas de `AGENTS.md` y `DESIGN.md` siguen vigentes. Nada se presenta como dato si no lo es, y cada brecha se declara como brecha.

## 2. Reparto: quién hace qué

### Roles vigentes desde el 2026-10-22 (decisión de Christian)

- **Claude Code es dueño del producto visible en `localhost:3100`:** todo el frontend, el diseño (`DESIGN.md`), la experiencia, el mapa y las pantallas de los pilotos, además de la capa de decisión (estadística de tendencias, contrato C2, PDF y asistente). **Claude sirve el 3100 y el 8000 desde su carpeta** (`Desktop\Codex\los-causas-claude`) y decide qué versión se ve.
- **Codex es soporte operativo:** conectores y datos NASA (NASADEM asíncrono, IMERG, LHASA, fuentes peruanas), muestreo geoespacial y backend de datos de los pilotos (K1, K1b, K2 y K3 sin interfaz), infraestructura (Docker, dependencias, rendimiento, seguridad), revisión de código y QA de las ramas de Claude, operaciones git (fusionar en `master` y subir a GitHub, siempre con la aprobación de Christian), el DOP interno y la documentación de fuentes y arquitectura técnica.
- Codex no edita `frontend/**`, `DESIGN.md` ni archivos visuales. Si detecta un problema visual o de experiencia, lo reporta en el registro con evidencia (captura, viewport, pasos) y Claude lo corrige.
- Codex no levanta servicios en 3100 ni 8000. Para sus pruebas usa `pytest`, `TestClient` o puertos temporales que apaga al terminar.

Regla general de datos y decisión: **Codex entrega datos verificados** (conectores, geoespacial, lógica sectorial). **Claude los convierte en experiencia y decisión** (lecturas, pipeline, preguntas NASA, PDF, asistente, pantalla).

| ID | Entrega | Dueño | Depende de | Rama |
|---|---|---|---|---|
| X0 | Revisar y fusionar `claude/diseno-consola` en `master` | **Codex** revisa · Christian aprueba | — | — |
| C1 | Mann–Kendall modificado (Hamed–Rao) y su uso en las preguntas NASA | **Claude** | X0 | `claude/mk-modificado` |
| C2 | Contrato común de screening por sector (`ScreeningEnvelope`) y preguntas NASA agnósticas al sector | **Claude** | X0 | `claude/contrato-sectores` |
| K1 | Muestreo NASA POWER sobre corredores y polígonos (geodésico, deduplicado por celda de grilla) | **Codex** | X0 | `codex/muestreo-geometrias` |
| K1b | Verificar acceso real a IMERG V07, LHASA, una capa oficial peruana de amenazas y **la generación mensual del COES por central fotovoltaica** (etiquetas de la red neuronal); registrar en `DATA_SOURCES.md` | **Codex** | — | `codex/fuentes-amenazas` |
| C3 | Reporte PDF ejecutivo (backend + botón) a partir del contrato C2 | **Claude** | C2 | `claude/reporte-pdf` |
| K0 | Descarga NASADEM asíncrona: reanudable, atómica, con bloqueo por tesela, precarga y estado `PENDING` (en curso) | **Codex** | C2 | `codex/nasadem-asincrono` |
| K2 | Piloto vial (backend): corredor, extremos de precipitación por tramo, relieve, amenazas disponibles y escenario de interrupción; responde con el sobre C2 | **Codex** | C2, K1 | `codex/piloto-vial` |
| C4 | Asistente analítico: reglas deterministas con citas al resultado + proveedor IA opcional por variables de entorno | **Claude** | C2 | `claude/asistente` |
| K3 | Piloto inmobiliario (backend): polígonos de terreno, relieve, precipitación, restricciones y comparación entre terrenos; responde con el sobre C2 | **Codex** | C2, K1 | `codex/piloto-inmobiliario` |
| C5 | Pantallas de los pilotos en la consola: selector, capas de línea y polígono en el mapa, lecturas, pipeline, preguntas y PDF | **Claude** | K2, K3 | `claude/integracion-pilotos` |
| K5 | Límites oficiales IGN (COD-AB Perú, CC BY-IGO): departamentos, provincias y distritos simplificados por nivel; búsqueda por nombre y ubigeo; geometría por territorio vía API. Declarar que los trazos son de 2015 | **Codex** | — | `codex/territorio` |
| C6 | Capas visuales NASA GIBS en el mapa: temperatura del mar y anomalía, viento sobre el mar, lluvia IMERG, temperatura de superficie, NDVI y humedad del suelo, con fecha, leyenda y etiqueta «visual, no entra en el cálculo» | **Claude** | — | `claude/capas-territorio` |
| C7 | Selector territorial (departamento → provincia → distrito, zona propia o clic; 2–4 territorios) y mapa de tendencias por celda | **Claude** | K5, K1 | `claude/capas-territorio` |
| O1 | Operación continua: revisar y fusionar ramas aprobadas, subir a GitHub con aprobación, mantener dependencias y Docker, y vigilar el vencimiento del token Earthdata (22-dic-2026) | **Codex** | — | — |
| Q1 | QA cruzado y materiales del jurado: Claude redacta `PITCH.md` y `DEMO_SCENARIOS.md`; Codex `DATA_SOURCES.md` y `TECHNICAL_ARCHITECTURE.md` | Ambos | todo lo anterior | — |

### Orden

```
X0 ──► C1 ─────────────────────────────┐
   ├─► C2 ──► C3 (PDF) ──► C4 (asistente) ├─► C5 ──► Q1
   └─► K1 ──► K2 (vial) ──► K3 (inmob.) ──┘
K1b en paralelo, sin dependencias
```

C2 es el cuello de botella: Claude lo entrega antes que nada para que K2 y K3 no inventen su propio formato de respuesta.

## 3. Archivos: dueño único

Solo el dueño edita su archivo. Si el otro necesita un cambio, lo pide en el registro de traspaso (sección 6) en lugar de editarlo.

| Archivos | Dueño |
|---|---|
| `backend/app/connectors/**`, `backend/app/geospatial/**`, `backend/app/sectors/road.py`, `backend/app/sectors/real_estate.py`, `backend/app/schemas/terrain.py` y los esquemas de geometría | Codex |
| `docs/interno/plan-operativo.html`, `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `docs/nasa-submission/DATA_SOURCES.md`, `docs/nasa-submission/TECHNICAL_ARCHITECTURE.md` | Codex |
| **Todo `frontend/**`** (incluido `geo-map.tsx`), `DESIGN.md`, `PRODUCT.md`, `docs/design/**`, `.taste-skill/`, `.impeccable/`, `docs/interno/dop-neuronal.html` | Claude |
| `docs/interno/dop-datos.js` (estado del DOP): cada agente actualiza sus nodos y tareas, con evidencia | Ambos |
| `backend/app/statistics/trends.py`, `backend/app/orchestration/**`, `backend/app/reports/**`, `backend/app/assistant/**`, `backend/app/schemas/screening.py` | Claude |
| `frontend/app/_components/workspace.tsx`, `styles.css`, `pipeline-panel.tsx`, `nasa-questions.tsx`, `site-verdict.tsx`, `temporal-chart.tsx` y los componentes nuevos de reporte y asistente | Claude |
| `backend/app/sectors/solar.py` | Claude (orquestación); Codex lo toca solo para cambios de conector |
| `README.md`, `PROGRESS.md`, `DECISION_LOG.md` | Ambos, solo agregando secciones propias; nunca reescribir la del otro |

Los pilotos de Codex entregan solo backend: un endpoint por sector que responde con el sobre C2 y su prueba de conformidad, más un ejemplo JSON real en `docs/coordination/contracts/`. Claude diseña y construye sus pantallas en C5.

### Quién sirve el 3100 y el 8000

1. Codex apaga su stack (`docker compose down`, sin `-v`, para conservar el volumen de caché `power-cache`) y lo anota en el registro.
2. Claude levanta `docker compose up -d --build` desde `Desktop\Codex\los-causas-claude`. Mismo proyecto Compose, mismos puertos y mismo volumen de caché.
3. Para que su trabajo se vea en el 3100, Codex lo entrega en una rama y Claude la integra en la suya antes de redesplegar. `master` sigue siendo la línea estable: Codex fusiona allí lo aprobado por Christian.

## 4. Contrato compartido (C2) — entregado

Ver `docs/coordination/contracts/README.md`: esquema, ejemplo real y guía paso a paso para armar un piloto. En resumen:

- `ScreeningEnvelope` (`backend/app/schemas/screening.py`) lleva sujetos de estudio (`point`, `segment` o `polygon` con GeoJSON), pipeline de nueve etapas, preguntas NASA, tendencias, relieve, brechas, supuestos y aviso.
- Los campos del sector se agregan **heredando** el sobre, en lugar de un `sector_payload` anidado. Así la respuesta solar sigue siendo compatible con el frontend actual (ADR-015).
- Las preguntas 1–4 son comunes. La quinta recibe un `SectorLens` que define cada sector en su propio módulo; no hay registro central que editar.
- Piezas reutilizables en `backend/app/orchestration/`: `extraction`, `analysis`, `stages` y `conformance`. Cada piloto prueba `envelope_violations(...) == []`.
- Los cambios al contrato son solo aditivos. Uno incompatible requiere un ADR y el acuerdo de ambos.

## 5. Puerta de calidad común (definición de terminado)

Cada rama, antes de pedir revisión:

1. `.\.venv\Scripts\python.exe -m pytest backend\tests -q` en verde, con pruebas nominales, de límites, de faltantes y de error externo.
2. `npm.cmd run build` y `npm.cmd audit --omit=dev` sin vulnerabilidades.
3. Auditor científico `audit_project.py --root .` con `ok: true`.
4. Si toca la interfaz: lint e inspector de `design-taste-frontend` en 1440/768/390, recorrido en navegador sin errores de consola ni desborde.
5. Si toca un conector: una ejecución real contra la fuente oficial, registrada con fecha y resultado.
6. Documentación al día (`PROGRESS.md`, ADR si cambia una decisión, `DATA_SOURCES.md` si cambia una fuente).
7. Sin secretos versionados; Next en modo dev genera `frontend/AGENTS.md` y toca `next-env.d.ts`: no confirmarlos.

## 6. Protocolo de traspaso

- Claude trabaja en una copia de trabajo hermana (`git worktree`, carpeta `Desktop\Codex\los-causas-claude`); la carpeta principal queda para Codex. Así nadie cambia la rama activa del otro ni pisa archivos sin confirmar. **Por decisión de Christian, Claude trabaja exclusivamente en esa carpeta**: tiene su propio `.venv`, sus `frontend/node_modules`, su `.env` (ignorado por git), su caché NASA en `backend/data/cache` y su Playwright en `scripts/qa/` (ver `scripts/qa/README.md`). Las evidencias de QA quedan en `.claude-qa/`, ignorada por git. Claude no escribe en la carpeta principal ni usa el stack Docker de Codex; para pruebas en navegador levanta su versión en puertos temporales y los apaga al terminar.
- `docs/coordination/HANDOFF_LOG.md` se fusiona con `merge=union` (`.gitattributes`): las entradas de ambos se unen sin conflicto.
- Cada rama nace del `master` vigente y trata un solo tema. Antes de pedir revisión, se actualiza con `master`.
- Al terminar, el agente agrega una entrada a `docs/coordination/HANDOFF_LOG.md` (solo agregar, nunca editar entradas ajenas):
  `fecha · agente · rama · commit · qué entrega · evidencia de la puerta · qué necesita del otro · bloqueos`.
- El otro agente revisa: lee el diff, corre la puerta y deja su veredicto en el mismo registro. Christian aprueba la fusión. Nadie sube a GitHub sin su instrucción.
- El DOP interno (`docs/interno/dop-neuronal.html`) refleja estas entregas con el responsable de cada nodo. Lo mantiene Codex.
- Christian transmite los mensajes entre agentes. Para ahorrarle trabajo, cada mensaje apunta a la entrada del registro en lugar de repetir su contenido.

## 7. Decisiones que necesitamos de Christian

| # | Decisión | Por qué importa | Propuesta |
|---|---|---|---|
| D1 | ✅ **Resuelta el 2026-10-22**: cuenta, token y aplicaciones autorizadas; NASADEM verificado con datos reales (ver registro). El token vence a los 60 días. | Desbloquea las métricas de NASADEM, IMERG y AppEEARS; sin token, los pilotos vial e inmobiliario quedan casi sin relieve ni lluvia satelital | Hacerlo primero; es gratuito |
| D2 | Corredor del piloto vial | Define la geometría y las amenazas a evaluar | Un tramo cercano a Moquegua, por relevancia local, con geometría pública de OpenStreetMap (ODbL, con atribución) |
| D3 | Terrenos del piloto inmobiliario | Deben ser coordenadas públicas, nunca datos de clientes (`AGENTS.md`, sección 21 del prompt) | Dos o tres polígonos en zonas de expansión de Arequipa o Moquegua elegidos por el equipo |
| D4 | Proveedor de IA del asistente | La plataforma funciona sin IA, con reglas; la IA solo redacta sobre el resultado calculado | Empezar determinista; agregar el proveedor por variable de entorno cuando haya clave |

## 8. Estado

| ID | Estado | Última entrada |
|---|---|---|
| X0 | Pendiente de revisión de Codex | `claude/diseno-consola` @ ver registro |
| C1 | **Hecho**, pendiente de revisión de Codex | `claude/mk-modificado` (ver registro) |
| C2 | **Hecho**, pendiente de revisión de Codex | `claude/contrato-sectores` (ver registro) |
| C3 | **Hecho**, pendiente de revisión de Codex | `claude/contrato-sectores` (ver registro) |
| K1 | Pendiente de X0 | — |
| K1b | Disponible para Codex | — |
