# Traspaso a Claude Code

Fecha de corte: 2026-10-22

## Base segura para continuar

- Aplicación web: `http://localhost:3100`.
- API y OpenAPI: `http://localhost:8000` y `http://localhost:8000/docs`.
- MyFix y `localhost:3000` están fuera de alcance.
- El sistema visual normativo vive en `DESIGN.md`; las reglas permanentes de desarrollo viven en `AGENTS.md`.
- No hay credenciales versionadas. `.env` permanece ignorado y `EARTHDATA_TOKEN` solo aparece vacío en `.env.example`.

## Incremento cerrado

- NASA CMR localiza los gránulos NASADEM HGT/SC para cada sitio.
- La vista previa pública puede superponerse al mapa y ocultarse mediante un control accesible.
- La API declara `METADATA_ONLY` y `DATA_UNAVAILABLE` cuando no existe credencial Earthdata; no inventa elevación, pendiente ni orientación.
- El DOP autónomo registra NASADEM como `EN_CURSO`, con evidencia, bloqueo y puerta de aceptación actualizados.
- El tracker conserva 18 nodos, ruta crítica, backlog, filtros, persistencia local e importación/exportación JSON.

## Evidencia del corte

- Backend: 16 pruebas aprobadas.
- Next.js: build de producción aprobado.
- npm: 0 vulnerabilidades conocidas.
- Auditor científico: `ok: true`, sin errores ni advertencias.
- CMR real: Moquegua `s18w071`; Arequipa `s17w072` para HGT y SC.
- Preview NASADEM: HTTP 200, `image/jpeg`.
- Navegador: ejecución solar, metadatos NASADEM, toggle de capa y vista de ruta crítica comprobados.
- Detector Impeccable sobre los archivos UI modificados: sin hallazgos.

## Backlog visual acordado

Estos cambios deben vivir en una rama separada para no mezclar el rediseño con el conector NASADEM:

1. Ajustar el dominio Y de la serie temporal para que la variación entre 6.4 y 6.9 sea legible sin exagerarla ni ocultarla.
2. Normalizar unidades de presentación (`kWh/m²/día`, `°C`, `mm/día`) sin cambiar los códigos/unidades originales conservados en la procedencia.
3. Identificar claramente el sitio del valor principal, sustituir `Posición 2/2` por lenguaje comprensible y acercar los supuestos al VAN condicionado.
4. Compactar la cabecera para devolver espacio al mapa y a los resultados.
5. Evitar el truncamiento del paso 5, “Inteligencia territorial”.
6. Reordenar móvil para que un resultado resumido aparezca antes del mapa o inmediatamente después de ejecutar.

La auditoría visual automatizada también señala microetiquetas, texto menor de 11 px, proximidad de texto a bordes y ausencia de un `h1` semántico en el workspace. Son coherentes con la deuda de densidad descrita arriba; deben resolverse sin abandonar el carácter de consola científica.

### Resultado en la rama `claude/diseno-consola` (2026-10-22)

1. **Hecho.** Dominio Y legible en `temporal-chart.tsx` (`readableDomain`): irradiancia 6.2–7.2, temperatura 4–14 y precipitación desde 0. Ticks en mono de 10 px y leyenda por sitio en la cabecera de la serie.
2. **Hecho.** `format.ts` traduce unidades solo para presentación; procedencia y JSON exportado intactos. También se aplica a los hallazgos comparativos que redacta el backend.
3. **Hecho.** Nuevo `site-verdict.tsx`: sitios ordenados, diferencia entre extremos (0.014 kWh/m²/día, 0.2 %), VAN junto a los supuestos realmente usados y aviso cuando se editan después de ejecutar. Ver ADR-010.
4. **Hecho.** Masthead de 150 a 89 px, con `h1`; el banco gana 65 px (fila superior de 355 a 420 px).
5. **Hecho.** Los nombres del pipeline ocupan dos líneas; el paso parcial tiene anillo ámbar y la palabra «Parcial».
6. **Hecho.** En móvil la lectura encabeza el banco tras ejecutar y recibe el desplazamiento.

Además: los tipos pasaron a `types.ts` y ningún texto baja de 10 px. Verificación: pytest 16/16, build aprobado, npm 0 vulnerabilidades, lint taste-skill 0 FAIL, Playwright a 1440/768/390 sin overflow ni errores de consola.

**Abierto, pendiente de decisión:** el inspector taste-skill aún marca microetiquetas en mayúsculas espaciadas y texto de 10 px (pide ≥ 11 px). Ambos son rasgos deliberados de la consola en este `DESIGN.md`. Subirlos a 11 px exige volver a medir el primer viewport de escritorio.

### Pipeline v2 (misma rama, 2026-10-22)

- Backend: nuevos `orchestration/stages.py`, `orchestration/nasa_questions.py` y `core/units.py`; `sectors/solar.py` orquesta POWER + NASADEM y mide tiempos; `schemas/pipeline.py` agrega `StageEvidence`, `NasaQuestionAnswer`, `TrendFinding`, `PipelineStatus.READY` y `display_unit`. Todo es aditivo, salvo que la exportación ahora devuelve `LISTO` en lugar de `COMPLETADO`.
- Conector POWER: lectura de caché en hilo y parseo con `model_construct` (ADR-013). Conviene revisarlo, porque es código de Codex.
- Frontend: `pipeline-panel.tsx` (pasos seleccionables + inspector) y `nasa-questions.tsx`; el relieve ya no se pide por separado a `/api/terrain`, viene en `result.terrain`. La ruta sigue existiendo.
- Siguiente paso científico sugerido: Mann–Kendall modificado para series con autocorrelación lag-1 ≥ 0.3.

## Archivos con mayor probabilidad de conflicto

- `frontend/app/_components/workspace.tsx`
- `frontend/app/_components/geo-map.tsx`
- `frontend/app/styles.css`
- `frontend/public/dop-neuronal.html`

Antes de editarlos, crear una rama desde el commit de este corte. Mantener el conector y los contratos backend separados de los cambios puramente visuales cuando sea posible.

## Comandos de verificación

```powershell
docker compose up -d --build
docker compose run --rm api python -m pytest -q
cd frontend
npm.cmd audit --audit-level=high
```

Para cerrar la sesión sin eliminar cachés ni afectar MyFix:

```powershell
docker compose down
```
