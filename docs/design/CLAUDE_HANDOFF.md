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
