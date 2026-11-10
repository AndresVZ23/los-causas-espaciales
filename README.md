# Los Causas Espaciales

Plataforma de inteligencia territorial para convertir datos de observación de la Tierra en decisiones de inversión trazables. Tiene siete módulos: clima, energía (solar, eólica e hidroeléctrica), amenazas, ambiente, patrimonio, infraestructura vial e inversión inmobiliaria. Cada dato se contrasta con una segunda fuente independiente.

**¿Eres del equipo?** Empieza por [`docs/equipo/EMPEZAR_AQUI.md`](docs/equipo/EMPEZAR_AQUI.md), con la puesta en marcha, la forma de trabajo y las reglas. Lo hecho, lo que falta y las ideas para agregar están en la red del proyecto, `docs/equipo/pipeline.html`: ábrela con doble clic después de clonar.

## Qué puede hacer hoy

| Módulo | Qué hace | Segunda fuente que lo comprueba |
|---|---|---|
| 1 · Clima | Tendencias de temperatura, lluvia, viento y radiación desde 2001, extremos de lluvia ETCCDI y año en curso | ERA5; GPM IMERG y CHIRPS para la lluvia |
| 2 · Energía solar | Recurso, energía, VAN y puntaje de dos a cuatro sitios | ERA5 |
| 2 · Energía eólica | Viento horario llevado al buje, energía, VAN y puntaje | Global Wind Atlas; producción real del COES como validación |
| 2 · Energía hidroeléctrica | Central de pasada: caudal en la toma, salto hasta la casa de máquinas, curva de duración, energía y VAN | GEOGLOWS para el caudal y Copernicus para el salto; producción real del COES como validación |
| 3 · Amenazas | Lluvia extrema, relieve, riesgo y susceptibilidad de CENEPRED, puntos críticos de la ANA, volcanes de INGEMMET | Deslizamientos de NASA (susceptibilidad global, LHASA y reportes COOLR) |
| 4 · Ambiente | Insumos de línea base: vegetación MODIS con tendencia, agua, ecosistemas y áreas protegidas | ESA WorldCover |
| 5 · Territorio | Patrimonio arqueológico y consulta previa del Ministerio de Cultura | Sin segunda fuente; comunidades y conflictos siguen como brecha |
| 6 · Infraestructura | Corredor vial por tramos: lluvia, capas oficiales, VAN de mitigación y puntaje | Copernicus para el relieve |
| 7 · Inversión | Terrenos o territorios IGN: lluvia, relieve, capas oficiales, VAN y puntaje | Copernicus para el relieve |

En todos los módulos:

- Un pipeline visible de nueve etapas, de la selección a la exportación, con el tiempo y la procedencia de cada una.
- Mann–Kendall corregido por autocorrelación (Hamed–Rao), pendiente de Sen y ajuste Benjamini–Hochberg entre los sujetos comparados.
- Respuestas a las cinco preguntas del reto «Be An Earth System Trend Detective!».
- «Descubrimientos»: lo que aparece al cruzar fuentes (confirmaciones, contradicciones y artefactos probables).
- Supuestos financieros editables, escenarios base, adverso y favorable, tornado y puntos de equilibrio.
- Brechas declaradas: lo que falta para una decisión de factibilidad, nunca convertido en cero.
- Reporte ejecutivo en PDF con huella SHA-256, exportación JSON y un asistente que explica el resultado.

La descarga y lectura de celdas raster NASADEM requiere un `EARTHDATA_TOKEN`; sin él, el sistema se mantiene honestamente en `METADATA_ONLY` y usa Copernicus GLO-30 donde necesita una elevación. AppEEARS requiere `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD`: el token temporal permanece en memoria, se renueva al vencer y se revoca al terminar. Las fuentes activas y sus cautelas de licencia están en `docs/nasa-submission/DATA_SOURCES.md`. LHASA 2, ANA e INGEMMET volcánico ya están integrados; SINPAD, SERV_PERUALERTA, SENACE, Defensoría y comunidades continúan como brechas explícitas.

## Ejecución con Docker

El proyecto está aislado de MyFix. Usa `localhost:3100` para la web y `localhost:8000` para la API; no utiliza el puerto 3000.

```powershell
git clone https://github.com/ChristianVenegas7/los-causas-espaciales.git
cd los-causas-espaciales
Copy-Item .env.example .env
docker compose -p los-causas-espaciales up -d --build
```

- Aplicación: http://localhost:3100
- OpenAPI: http://localhost:8000/docs

Los documentos internos de seguimiento no forman parte de la aplicación; se abren como archivo local:

- DOP de desarrollo (dependencias, ruta crítica, backlog, evidencia y exportación JSON): `docs/interno/dop-neuronal.html`
- Plan operativo: `docs/interno/plan-operativo.html`
- Plan de trabajo Claude Code + Codex: `docs/coordination/PLAN_CLAUDE_CODEX.md`

## Ejecución local sin Docker

Desde la carpeta del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

En otra terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

## Documentación clave

- `docs/architecture/PRODUCT_PIPELINE.md`: flujo operativo de nueve pasos y capas del sistema.
- `docs/architecture/DECISION_LOG.md`: decisiones de producto y arquitectura.
- `docs/architecture/PROMPT_COVERAGE.md`: matriz honesta de cumplimiento del prompt maestro.
- `docs/interno/plan-operativo.html`: hoja de ruta interactiva, dependencias, puertas de calidad y DOP neuronal futuro (interno, fuera de la app).
- `PROGRESS.md`: evidencia verificada, límites y backlog priorizado.
- `docs/nasa-submission/`: materiales técnicos y de presentación para NASA Space Apps.
- `DESIGN.md`: sistema visual normativo para nuevas pantallas.
- `docs/design/VISUAL_REDESIGN.md`: auditoría antes/después, fidelity ledger y decisiones del workspace.
- `docs/design/CLAUDE_HANDOFF.md`: estado congelado, pruebas y backlog visual para continuar sin pisar la integración NASADEM.
- `docs/SKILLS_ACTIVE.md`: Skills instaladas, función y verificaciones realizadas.

NASA POWER puede limitar solicitudes o devolver errores temporales. La aplicación conserva caché y procedencia, expone el error real y nunca reemplaza observaciones faltantes con valores fabricados.
