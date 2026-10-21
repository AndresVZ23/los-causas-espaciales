# Los Causas Espaciales

Plataforma de inteligencia territorial para convertir datos de observación de la Tierra en decisiones de inversión trazables. Esta primera versión operativa implementa un screening solar comparativo para Moquegua y Arequipa con datos reales de NASA POWER.

## Qué puede hacer hoy

- Ejecutar un pipeline visible de nueve pasos, desde la selección del caso hasta la exportación.
- Consultar cuatro variables reales de NASA POWER para dos a cuatro ubicaciones.
- Comparar irradiancia, temperatura, viento y precipitación sin inventar datos ausentes.
- Calcular Mann–Kendall, pendiente de Sen, p-value, intervalo de confianza y corrección Benjamini–Hochberg.
- Ordenar ubicaciones por irradiancia histórica mediante una regla explícita y reproducible, no mediante un puntaje opaco.
- Estimar energía anual y VAN utilizando únicamente supuestos editables del usuario.
- Mostrar oportunidades, cautelas, procedencia del dato y brechas que todavía impiden una decisión de factibilidad.
- Descargar el resultado completo en JSON.

Las capas de pendiente, red eléctrica, restricciones ambientales, sensibilidad social y arqueológica, GPM IMERG y fuentes oficiales peruanas todavía no están integradas. La interfaz las muestra como brechas, nunca como resultados terminados.

## Ejecución con Docker

El proyecto está aislado de MyFix. Usa `localhost:3100` para la web y `localhost:8000` para la API; no utiliza el puerto 3000.

```powershell
cd "C:\Users\USUARIO\Desktop\Codex\Nasa Space Apps Challenge"
Copy-Item .env.example .env
docker compose -p los-causas-espaciales up -d --build
```

- Aplicación: http://localhost:3100
- Plan operativo y DOP neuronal: http://localhost:3100/plan-operativo.html
- OpenAPI: http://localhost:8000/docs

## Ejecución local sin Docker

```powershell
cd "C:\Users\USUARIO\Desktop\Codex\Nasa Space Apps Challenge"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

En otra terminal:

```powershell
cd "C:\Users\USUARIO\Desktop\Codex\Nasa Space Apps Challenge\frontend"
npm.cmd install
npm.cmd run dev
```

## Documentación clave

- `docs/architecture/PRODUCT_PIPELINE.md`: flujo operativo de nueve pasos y capas del sistema.
- `docs/architecture/DECISION_LOG.md`: decisiones de producto y arquitectura.
- `docs/architecture/PROMPT_COVERAGE.md`: matriz honesta de cumplimiento del prompt maestro.
- `frontend/public/plan-operativo.html`: hoja de ruta interactiva, dependencias, puertas de calidad y DOP neuronal futuro.
- `PROGRESS.md`: evidencia verificada, límites y backlog priorizado.
- `docs/nasa-submission/`: materiales técnicos y de presentación para NASA Space Apps.
- `DESIGN.md`: sistema visual normativo para nuevas pantallas.
- `docs/design/VISUAL_REDESIGN.md`: auditoría antes/después, fidelity ledger y decisiones del workspace.
- `docs/SKILLS_ACTIVE.md`: Skills instaladas, función y verificaciones realizadas.

NASA POWER puede limitar solicitudes o devolver errores temporales. La aplicación conserva caché y procedencia, expone el error real y nunca reemplaza observaciones faltantes con valores fabricados.
