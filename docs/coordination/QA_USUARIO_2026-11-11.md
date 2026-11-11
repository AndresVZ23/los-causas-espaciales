# QA de usuario y revisión cruzada · 11-nov-2026

## Alcance y entorno

- Rama: `codex/entrega-11nov`, creada desde `claude/pdf-linea-base` (`3517207`).
- Revisión de código: commits `d9330cc` y `3517207`.
- Ejecución aislada: API `127.0.0.1:8312`, web `127.0.0.1:3412`; no se usaron 3100 ni 8000.
- Navegador: Codex Browser, 1440 × 900 y 390 × 844.
- Recorrido: Clima, Energía, Amenazas, Ambiente, Territorio, Infraestructura, Inversión y Alertas en el mundo.
- Resultado base: los siete módulos cambian de contexto; las alertas devolvieron 25 eventos y 4 asociados a Perú; no hubo errores ni advertencias de consola y no se detectó desborde horizontal en 1440 o 390 px.
- CENEPRED sin datos en esta copia se considera esperado por ADR-044; no se interpretó como ausencia de riesgo.

## Hallazgos de revisión para Claude

### P1 · El diálogo de alertas no gestiona el foco

- Evidencia: `frontend/app/_components/world-alerts.tsx:48-56`.
- Reproducción: abrir «Alertas en el mundo» con teclado. El foco permanece en el botón disparador; no entra al diálogo, no queda contenido y no se restaura explícitamente al cerrar.
- Impacto: una persona que usa teclado o lector de pantalla puede no percibir el panel abierto ni recorrerlo como diálogo modal.
- Corrección sugerida: foco inicial en «Cerrar» o el título, ciclo/inert si es modal, Escape y restauración del foco al disparador.

### P1 · Las búsquedas antiguas pueden sobrescribir la consulta vigente

- Evidencia: `frontend/app/_components/world-alerts.tsx:119-130`.
- Reproducción: escribir dos consultas distintas con menos de 350 ms entre ellas y hacer que la primera respuesta sea más lenta. El temporizador se cancela, pero una petición ya iniciada no se aborta ni se valida contra la consulta actual.
- Impacto: se puede elegir un lugar que no corresponde al texto visible.
- Corrección sugerida: `AbortController` por efecto o identificador monotónico de petición antes de llamar `setPlaces`/`setError`.

### P2 · Preferencia de movimiento reducido incompleta

- Evidencia: `frontend/app/_components/geo-map.tsx:67` y `:227-267`.
- Reproducción: activar «reducir movimiento» y abrir alertas. El giro continuo se omite, pero `easeTo(... duration: 1100)` sigue animando; además, el cambio de preferencia durante la sesión no tiene listener.
- Corrección sugerida: duración 0 o `jumpTo` cuando la preferencia esté activa y listener `change` de `matchMedia`.

### P2 · Semántica ARIA inválida en resultados del geocodificador

- Evidencia: `frontend/app/_components/world-alerts.tsx:146-153`.
- El `ul` declara `role="listbox"`, pero sus descendientes son `li > button` sin `role="option"` ni patrón de selección. Usar lista normal de botones o implementar el patrón completo de combobox/listbox.

### P2 · Consulta formada solo por espacios llega vacía al proveedor

- Evidencia: `backend/app/api/world.py:19-25`.
- `min_length=2` valida antes de `strip()`: `q="  "` supera la longitud y luego el conector recibe una cadena vacía. Validar el valor normalizado y devolver 422 antes de llamar al proveedor.

### P2 · El despliegue temporal muestra puertos incorrectos

- Evidencia: `frontend/app/_components/workspace.tsx:774`.
- Reproducción: abrir la aplicación en 3412/8312 y bajar al pie. Sigue mostrando y enlazando «OpenAPI · 8000» y «Aplicación · 3100».
- Impacto: confunde al equipo en ramas paralelas y a cualquier despliegue que no use los puertos de Compose.
- Corrección sugerida: URL pública configurable y texto derivado de la configuración, sin asumir localhost.

### P2 · El fondo del globo incumple la regla visual sin degradados

- Evidencia: `frontend/app/styles.css:189` usa `radial-gradient(...)`.
- El inspector de diseño también detectó texto menor de 11 px en los tres anchos y, a 390 px, «Siete módulos, estados honestos» parcialmente cubierto en la tercera pantalla. Revisar ambos con la captura del inspector antes de cerrar el diseño.

### P2 · Controles del mapa menores al objetivo táctil recomendado

- Evidencia medida a 390 px: Zoom in, Zoom out y control de globo, 29 × 29 px.
- Impacto: objetivos difíciles de accionar con precisión en móvil. Ampliar el área interactiva a por lo menos 44 × 44 px sin sobredimensionar el icono.

## Defecto corregido por Codex fuera de los archivos reservados

- `backend/app/connectors/gdacs/events.py`: una respuesta compuesta se declaraba `REAL_DATA` si una consulta era real aunque la otra proviniera de caché. Ahora la procedencia conjunta es conservadora: `CACHED_DATA` si cualquiera de las dos partes es caché.
- Prueba agregada: `backend/tests/test_world.py::test_gdacs_combined_response_is_cached_when_either_query_is_cached`.

## Clon limpio y guía de arranque

Clon de prueba: `clean-clone-20261111-01`, obtenido desde el remoto oficial.

1. El remoto clonó `31455e2`, no `d9330cc`/`3517207`. Hasta publicar la rama integrada, una persona nueva no recibe el alcance global ni el globo.
2. `python --version` quedó bloqueado por el alias de Microsoft Store y `py -3.12` no estaba disponible. Se continuó con Python 3.12.14 del runtime de Codex. La guía ahora exige verificar 3.12 y explica el alias de Windows.
3. El entorno virtual y `backend/requirements.txt` se instalaron correctamente.
4. `npm install` instaló 91 paquetes y auditó 0 vulnerabilidades. NPM avisó que Recharts 2.15.4 está deprecado; no se cambió dependencia en esta entrega.
5. API en 8311 y web en 3411 respondieron 200. La guía ahora documenta `BACKEND_API_URL` y la detención con `Ctrl+C`.
6. Con red restringida falló la descarga de Public Sans e IBM Plex Mono desde Google Fonts y Next usó fuentes de respaldo. La guía ahora exige registrar el aviso y repetir el QA visual con acceso a las fuentes antes de aprobar.

## Resultado del inspector visual

El inspector local se ejecutó después del recorrido manual y terminó con 3 fallos y 1 advertencia:

- 10 microetiquetas en mayúsculas y con espaciado alto.
- 82 bloques de texto menores de 11 px.
- Texto «Siete módulos, estados honestos» cubierto parcialmente a 390 px.
- Cuatro iconos dentro de superficies teñidas; requiere defensa o ajuste de diseño.

Estos puntos pertenecen a los archivos visuales reservados por Claude; Codex no los modificó.

## Segunda revisión · «Entrar a la zona» y juego (`229e642`, `8854b53`)

### Alcance y entorno

- Rama: `codex/entrega-11nov-b`, creada desde `claude/pdf-linea-base` (`8854b53`).
- API temporal: `127.0.0.1:8313`; web temporal: `127.0.0.1:3413`. No se usaron 3100/8000, Docker ni el volumen `power-cache`.
- Rutas: `/zona/moquegua` y `/zona/taal`, en 1440 × 900 y 390 × 844.
- Codex Browser verificó estructura, lectura, anchos, teclas 1–6, N, P y F, rueda y ausencia de desborde. Su motor no concedió Pointer Lock (`document.pointerLockElement === null`), por lo que el flujo de mouse se repitió en Chrome local con el guion QA del repositorio, sin modificarlo, y con una prueba focalizada temporal.
- Resultado funcional: Pointer Lock activo en Chrome en los cuatro casos; rueda cambia la pieza; clic derecho coloca; clic izquierdo quita; «Deshacer» vuelve a cero; la lectura de elevación, pendiente y cobertura de la fuente permanece idéntica antes y después de editar. Las seis piezas, las balizas, la vista de pendientes y el modo vuelo/caminata respondieron. No hubo errores de consola ni desborde horizontal.
- El QA táctil adicional a 390 px mostró `Poner`, `Quitar`, `Subir/Bajar` y `Saltar`; colocar y quitar volvió de una edición a cero sin errores.

### Hallazgos para Claude en archivos reservados

#### P2 · La notificación tapa la ficha de una baliza en móvil

- Evidencia: `frontend/app/_components/zone/zone-explorer.css:48-60` y `:85-106`; ambos elementos son absolutos y no coordinan sus cajas en el corte móvil.
- Reproducción: 390 × 844, Moquegua, empezar, poner una pieza para mostrar la lectura de celda y abrir la segunda baliza antes de que pasen los 8 segundos de la notificación. El detector del propio flujo devuelve `.zoneToast × .zoneCard`.
- Impacto: la lectura de la pieza oculta parte de la evidencia científica y de la segunda fuente de la baliza.
- Corrección sugerida: reservar bandas que no se crucen, apilar una sobre otra o cerrar la notificación al abrir una ficha; agregar la combinación al QA móvil.

#### P2 · Clic derecho seguido de clic izquierdo no revierte la pieza de forma consistente en Moquegua

- Evidencia: `frontend/app/_components/zone/zone-explorer.tsx:114-126` usa `target.index` para quitar y `target.placeIndex` para poner; la distinción se origina en `frontend/app/_components/zone/zone-world.ts:10-31`.
- Reproducción: Moquegua, caminar hasta que `data-target=33100`, rueda a «Panel solar», clic derecho con el mouse capturado y luego clic izquierdo sin moverlo. En 1440 y 390, las ediciones quedan `1 → 1`; en Taal (`data-target=35500`) quedan `1 → 0`. Enter seguido de Supr sí vuelve a cero.
- Impacto: el mismo gesto y la misma mira se comportan distinto según la geometría; la persona puede quitar el bloque vecino o no recuperar la pieza recién puesta.
- Corrección sugerida: decidir y probar el contrato de la mira después de colocar (recalcular el objetivo de forma síncrona o quitar explícitamente la pieza que ocupa la cara apuntada) y agregar una prueba de terreno escalonado.

#### P2 · La ruta directa se anuncia como diálogo modal sin implementar el patrón modal

- Evidencia: `frontend/app/_components/zone/zone-explorer.tsx:255-262` declara `role="dialog" aria-modal="true"`, usa un `h2` como título principal y solo mueve el foco a «Salir al mapa» al montar; no hay ciclo de foco ni restauración en la ruta directa.
- Verificación independiente: el inspector no encontró ningún `h1` en 1440 ni 390.
- Impacto: lectores de pantalla reciben semántica de modal para una página completa, pero sin el comportamiento esperado; además la jerarquía de encabezados empieza en nivel 2.
- Corrección sugerida: en `/zona/{id}`, usar un contenedor de página con `h1`; reservar el patrón de diálogo para la variante realmente superpuesta y completar foco inicial, contención, Escape y restauración.

#### P2 · Atajos globales también actúan mientras el foco está en controles

- Evidencia: `frontend/app/_components/zone/zone-explorer.tsx:227-238` calcula `onControl`, pero solo lo aplica a Enter/Supr; P, N y 1–6 siguen actuando. `frontend/app/_components/zone/zone-controls.ts:49-61` protege Espacio, pero no F.
- Reproducción: enfocar un botón de la barra o una ficha y pulsar P, N, un dígito o F. El control conserva el foco y la escena cambia en segundo plano.
- Impacto: conflicto con navegación por teclado, tecnologías de asistencia y activación de botones mediante teclas.
- Corrección sugerida: ignorar todos los atajos del juego cuando el foco esté en un control, salvo que el mouse esté capturado o el canvas tenga un modo de juego enfocado explícitamente.

### Inspectores de diseño

- `design-taste-frontend` sobre los siete archivos de zona: 0 fallos y 7 advertencias por sombras. El inspector renderizado confirmó 0 desborde, 0 errores de consola y detectó la ausencia de `h1`; sus avisos de sombra corresponden a la estética de bloques aceptada en ADR-047 y deben resolverse o justificarse por Claude.
- `impeccable detect` sobre la ruta en 1440 y 390: 0 hallazgos primarios.
- No se modificó ningún archivo bajo `frontend/app/_components/zone/`, `scripts/zones/` o `backend/app/zones/`.
