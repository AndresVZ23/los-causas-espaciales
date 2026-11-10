# Los Causas Espaciales

Plataforma de inteligencia territorial para convertir datos de observación de la Tierra en decisiones de inversión trazables. Tiene siete módulos: clima, energía (solar y eólica), amenazas, ambiente, patrimonio, infraestructura vial e inversión inmobiliaria. Cada dato se contrasta con una segunda fuente independiente.

**¿Eres del equipo?** Empieza por [`docs/equipo/EMPEZAR_AQUI.md`](docs/equipo/EMPEZAR_AQUI.md), con la puesta en marcha, la forma de trabajo y las reglas. Lo hecho, lo que falta y las ideas para agregar están en [`docs/equipo/PIPELINE.md`](docs/equipo/PIPELINE.md).

## Qué puede hacer hoy

- Ejecutar un pipeline visible de nueve pasos, desde la selección del caso hasta la exportación.
- Consultar cuatro variables reales de NASA POWER para dos a cuatro ubicaciones.
- Graficar medias anuales reales por sitio y variable después de cada consulta.
- Usar NASA EOSDIS GIBS Blue Marble como mapa base contextual estático, separado de la evidencia analítica POWER.
- Consultar en NASA CMR los gránulos NASADEM HGT y SC para cada sitio, mostrar sus metadatos oficiales y superponer la vista previa pública disponible.
- Comparar irradiancia, temperatura, viento y precipitación sin inventar datos ausentes.
- Calcular Mann–Kendall, pendiente de Sen, p-value, intervalo de confianza y corrección Benjamini–Hochberg.
- Ordenar ubicaciones por irradiancia histórica mediante una regla explícita y reproducible, no mediante un puntaje opaco.
- Estimar energía anual y VAN utilizando únicamente supuestos editables del usuario.
- Mostrar oportunidades, cautelas, procedencia del dato y brechas que todavía impiden una decisión de factibilidad.
- Descargar el resultado completo en JSON.
- Crear tareas asíncronas AppEEARS para MOD13Q1.061 (NDVI/EVI + QA) y MOD44W.061 (agua + QA), consultar su estado, listar el bundle y descargar archivos con verificación SHA-256.
- Consultar intersecciones de punto, corredor o polígono en CENEPRED, SERNANP, Osinergmin y Cultura, conservando CRS, procedencia y límites de interpretación.
- Cruzar la susceptibilidad a deslizamientos de CENEPRED con la susceptibilidad global de NASA, el nowcast LHASA 2 y los reportes COOLR, sin convertir nodata ni ausencia de reportes en riesgo cero.
- Obtener generación mensual real de COES para Rubí, Intipampa, Moquegua FV, Majes, Repartición y Panamericana como etiquetas `in-coes`.

La descarga y lectura de celdas raster NASADEM requiere un `EARTHDATA_TOKEN`; sin él, el sistema se mantiene honestamente en `METADATA_ONLY`. AppEEARS requiere `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD`: el token temporal permanece en memoria, se renueva al vencer y se revoca al terminar. Las fuentes activas y sus cautelas de licencia están en `docs/nasa-submission/DATA_SOURCES.md`. LHASA 2, ANA e INGEMMET volcánico ya están integrados; SINPAD, SERV_PERUALERTA, SENACE, Defensoría y comunidades continúan como brechas explícitas.

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
