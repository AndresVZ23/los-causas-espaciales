# Rediseño visual del Earth Intelligence Workspace

## Resultado

La portada genérica fue reemplazada por un espacio de trabajo técnico centrado en la decisión: mapa dominante, controles de análisis, lectura de procedencia, pipeline visible, evidencia estadística y escenario de inversión. La interfaz sigue en español y separa de forma explícita observación, caché, estimación, supuesto y dato no disponible.

## Dirección seleccionada

- Norte creativo: mesa nocturna de interpretación terrestre.
- Estilo: terminal de datos sobria, superficies minerales oscuras y una única línea cian de selección.
- Tipografías: Public Sans para lectura prolongada e IBM Plex Mono para identificadores, coordenadas y cifras tabulares.
- Materialidad: capas tonales y reglas de 1 px; sin gradientes, vidrio, brillo neón ni tarjetas decorativas.
- Firma: adquisición/pipeline como línea de progreso y mapa geoespacial como evidencia central.

El contrato de superficie está en `.impeccable/surfaces/frontend-app-page-tsx.md` y conserva la referencia obligatoria `seed:0d012c9d0aa09998` para reproducir la dirección.

## Proceso y auditoría

1. Captura de la interfaz anterior en escritorio y móvil.
2. Generación de un tablero conceptual con prompt y procedencia conservados.
3. Tres rondas de implementación y revisión visual.
4. Revisión independiente de cierre y correcciones de navegación móvil, foco, tipografía y aislamiento de resultados.
5. Reconstrucción estructural a partir de la referencia aprobada: masthead técnico, rail, mapa, configuración, serie anual y pipeline dentro del primer viewport.
6. Inspección final a 1440 y 390 px: detector Impeccable sin hallazgos, sin overflow y sin errores de consola.
7. Prueba funcional en navegador de consulta real, serie temporal anual, módulos pendientes y navegación accesible.

Las comparativas están en `docs/design/audit/before-desktop.png`, `before-mobile.png`, `after-desktop.png` y `after-mobile.png`.

## Fidelity ledger

| Punto del concepto | Implementación | Fidelidad / desviación consciente |
|---|---|---|
| Cabecera técnica de gran formato | Marca, verbos operativos, contexto, filtros y procedencia forman un masthead de 150 px | Alta; la paleta decorativa del tablero se reemplaza por controles y estado reales |
| Mapa nocturno como superficie principal | MapLibre usa NASA EOSDIS GIBS Blue Marble, con atribución visible, y conecta Moquegua–Arequipa | Alta; se identifica como mapa base estático y no como observación analítica de POWER |
| Grafito, blanco frío y cian mineral | Tokens globales en `styles.css` con un solo acento principal | Alta |
| Rail compacto y línea de selección | Rail de siete módulos en escritorio; bottom bar de cinco destinos en móvil | Alta; conserva estados reales sin copiar las categorías genéricas de la referencia |
| Etiquetas de procedencia | `REAL_DATA`, `CACHED_DATA`, `MODEL_ESTIMATE`, `USER_ASSUMPTION`, `DATA_UNAVAILABLE` visibles | Alta |
| Pipeline de adquisición | Nueve etapas y bitácora compacta ocupan la banda inferior del primer viewport | Alta |
| Gráfico temporal con escalas | Recharts grafica 24 medias anuales por sitio devueltas por la API | Alta; el estado previo conserva la cuadrícula pero declara que no representa observaciones |
| Adaptación móvil | Mapa, controles y resultados apilados; barra persistente 4 + “Más” | Alta; drawer con `inert`, `aria-hidden`, Escape y gestión de foco |
| Imaginería terrestre | NASA Blue Marble aporta el contexto visual del mapa con atribución y rótulo de mapa base estático | Alta en composición; desviación consciente respecto a una escena diaria para evitar nubes y falsa actualidad |

Las capturas de cierre están en `.impeccable/review/user-1440.png`, `.impeccable/review/user-390.png`, `.impeccable/review/desktop.png` y `.impeccable/review/mobile.png`.

## Diferencias de contenido

- Se eliminó el tono de landing page y se priorizó la pregunta operativa: configurar, ejecutar, comprobar procedencia y decidir.
- Los siete módulos mantienen nombres, alcance y estado verificable; las capacidades pendientes se expresan como brechas, no como promesas terminadas.
- El resultado económico se denomina escenario condicionado y nunca recomendación de inversión.
- La interfaz inicial no muestra métricas inventadas: los resultados solo aparecen después de una respuesta real o de caché del backend.

## Excepción documentada del inspector

El detector geométrico de Taste considera que cualquier barra inferior fija cubre texto durante un instante intermedio del desplazamiento. La dirección móvil exige una barra persistente y la captura completa confirma que ningún encabezado queda oculto en reposo. La comprobación final permitió exclusivamente `covered-text`; todos los demás criterios se evaluaron sin excepciones y el informe terminó sin hallazgos.
