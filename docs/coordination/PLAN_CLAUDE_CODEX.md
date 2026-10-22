# Plan de trabajo conjunto — Claude Code + Codex

Fecha: 2026-10-22 · Dueño del producto: Christian · Documento vivo; cada agente actualiza solo su fila de estado.

## 1. Objetivo

Cerrar lo que más pesa para el jurado del NASA Space Apps Challenge sin pisarnos el trabajo:

1. Confirmar las tendencias autocorrelacionadas con Mann–Kendall modificado.
2. Reporte PDF ejecutivo.
3. Pilotos vial e inmobiliario, con el mismo motor del piloto solar.
4. Asistente analítico, determinista por defecto y con IA opcional.

Las reglas de `AGENTS.md` y `DESIGN.md` siguen vigentes. Nada se presenta como dato si no lo es, y cada brecha se declara como brecha.

## 2. Reparto: quién hace qué

Regla general: **Codex es dueño de los datos** (conectores, geoespacial, sectores nuevos). **Claude es dueño de la capa de decisión y de la experiencia** (estadística de tendencias, contrato de respuestas, reporte, asistente, pantalla principal).

| ID | Entrega | Dueño | Depende de | Rama |
|---|---|---|---|---|
| X0 | Revisar y fusionar `claude/diseno-consola` en `master` | **Codex** revisa · Christian aprueba | — | — |
| C1 | Mann–Kendall modificado (Hamed–Rao) y su uso en las preguntas NASA | **Claude** | X0 | `claude/mk-modificado` |
| C2 | Contrato común de screening por sector (`ScreeningEnvelope`) y preguntas NASA agnósticas al sector | **Claude** | X0 | `claude/contrato-sectores` |
| K1 | Muestreo NASA POWER sobre corredores y polígonos (geodésico, deduplicado por celda de grilla) | **Codex** | X0 | `codex/muestreo-geometrias` |
| K1b | Verificar acceso real a IMERG V07, LHASA y una capa oficial peruana de amenazas; registrar en `DATA_SOURCES.md` | **Codex** | — | `codex/fuentes-amenazas` |
| C3 | Reporte PDF ejecutivo (backend + botón) a partir del contrato C2 | **Claude** | C2 | `claude/reporte-pdf` |
| K2 | Piloto vial: corredor, extremos de precipitación por tramo, relieve, amenazas disponibles y escenario de interrupción | **Codex** | C2, K1 | `codex/piloto-vial` |
| C4 | Asistente analítico: reglas deterministas con citas al resultado + proveedor IA opcional por variables de entorno | **Claude** | C2 | `claude/asistente` |
| K3 | Piloto inmobiliario: polígonos de terreno, relieve, precipitación, restricciones y comparación entre terrenos | **Codex** | C2, K1 | `codex/piloto-inmobiliario` |
| K4 | Capas de línea y polígono en el mapa (`geo-map.tsx`) | **Codex** | K1 | dentro de K2 |
| C5 | Integración de los pilotos en la consola (selector, lecturas, pipeline, preguntas, PDF) | **Claude** | K2, K3, K4 | `claude/integracion-pilotos` |
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
| `frontend/app/_components/geo-map.tsx`, `docs/interno/**` (DOP y plan operativo) | Codex |
| `backend/app/statistics/trends.py`, `backend/app/orchestration/**`, `backend/app/reports/**`, `backend/app/assistant/**`, `backend/app/schemas/screening.py` | Claude |
| `frontend/app/_components/workspace.tsx`, `styles.css`, `pipeline-panel.tsx`, `nasa-questions.tsx`, `site-verdict.tsx`, `temporal-chart.tsx` y los componentes nuevos de reporte y asistente | Claude |
| `backend/app/sectors/solar.py` | Claude (orquestación); Codex lo toca solo para cambios de conector |
| `README.md`, `PROGRESS.md`, `DECISION_LOG.md` | Ambos, solo agregando secciones propias; nunca reescribir la del otro |

Los pilotos de Codex entregan su interfaz como componentes en `frontend/app/_components/pilots/` (por ejemplo `road-reading.tsx`), sin tocar `workspace.tsx`. Claude los conecta en C5.

## 4. Contrato compartido (C2)

Todos los sectores responden con el mismo sobre, para que el pipeline, las preguntas NASA, el PDF y el asistente funcionen igual en solar, vial e inmobiliario:

```text
ScreeningEnvelope
  analysis_id, generated_at, sector, title, period
  geometries: puntos | corredor | polígonos (WGS84, RFC 7946)
  pipeline: list[PipelineStage]          # 9 etapas, evidencia y estados derivados (ADR-012)
  nasa_questions: list[NasaQuestionAnswer]
  trend_findings: list[TrendFinding]
  data_gaps: list[DataGap]
  assumptions: dict + procedencia USER_ASSUMPTION
  disclaimer
  sector_payload: modelo propio del sector (SolarPayload, RoadPayload, RealEstatePayload)
```

- Las preguntas 1–4 se calculan igual para todos los sectores. La quinta usa un registro de lecturas por sector (`SECTOR_READINGS[sector][(variable, dirección)]`), y Codex agrega las de vial e inmobiliario en su rama.
- Los cambios al contrato son solo aditivos. Un cambio incompatible requiere un ADR y el acuerdo de ambos.
- Claude publica el contrato con un ejemplo JSON real en `docs/coordination/contracts/` al cerrar C2.

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

- Cada rama nace del `master` vigente y trata un solo tema. Antes de pedir revisión, se actualiza con `master`.
- Al terminar, el agente agrega una entrada a `docs/coordination/HANDOFF_LOG.md` (solo agregar, nunca editar entradas ajenas):
  `fecha · agente · rama · commit · qué entrega · evidencia de la puerta · qué necesita del otro · bloqueos`.
- El otro agente revisa: lee el diff, corre la puerta y deja su veredicto en el mismo registro. Christian aprueba la fusión. Nadie sube a GitHub sin su instrucción.
- El DOP interno (`docs/interno/dop-neuronal.html`) refleja estas entregas con el responsable de cada nodo. Lo mantiene Codex.
- Christian transmite los mensajes entre agentes. Para ahorrarle trabajo, cada mensaje apunta a la entrada del registro en lugar de repetir su contenido.

## 7. Decisiones que necesitamos de Christian

| # | Decisión | Por qué importa | Propuesta |
|---|---|---|---|
| D1 | **Crear la cuenta Earthdata Login y el token** (`EARTHDATA_TOKEN` en `.env`, nunca en git) | Desbloquea las métricas de NASADEM, IMERG y AppEEARS; sin token, los pilotos vial e inmobiliario quedan casi sin relieve ni lluvia satelital | Hacerlo primero; es gratuito |
| D2 | Corredor del piloto vial | Define la geometría y las amenazas a evaluar | Un tramo cercano a Moquegua, por relevancia local, con geometría pública de OpenStreetMap (ODbL, con atribución) |
| D3 | Terrenos del piloto inmobiliario | Deben ser coordenadas públicas, nunca datos de clientes (`AGENTS.md`, sección 21 del prompt) | Dos o tres polígonos en zonas de expansión de Arequipa o Moquegua elegidos por el equipo |
| D4 | Proveedor de IA del asistente | La plataforma funciona sin IA, con reglas; la IA solo redacta sobre el resultado calculado | Empezar determinista; agregar el proveedor por variable de entorno cuando haya clave |

## 8. Estado

| ID | Estado | Última entrada |
|---|---|---|
| X0 | Pendiente de revisión de Codex | `claude/diseno-consola` @ ver registro |
| C1 | **Hecho**, pendiente de revisión de Codex | `claude/mk-modificado` (ver registro) |
| C2 | Siguiente para Claude | — |
| K1 | Pendiente de X0 | — |
| K1b | Disponible para Codex | — |
