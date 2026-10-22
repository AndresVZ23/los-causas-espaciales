# Estado del proyecto

Última actualización: 2026-10-22

## Versión operativa verificada

- Backend FastAPI con contratos Pydantic y documentación OpenAPI.
- Orquestador `POST /api/v1/projects/solar-screening` para ejecutar el caso solar de extremo a extremo.
- Consulta multiparámetro real a NASA POWER con caché de 24 horas, timeout y procedencia `REAL_DATA` / `CACHED_DATA`.
- Serie temporal anual real expuesta por la API y representada por sitio después de cada consulta.
- Mapa base contextual NASA EOSDIS GIBS Blue Marble, identificado como producto visual estático y no como evidencia analítica actual.
- Consulta pública a NASA CMR para localizar NASADEM HGT y SC por sitio, con procedencia, colección, resolución, CRS y vista previa oficial trazables.
- Pipeline visible de nueve pasos: selección, configuración, extracción, análisis, inteligencia territorial, evaluación, impacto económico, resultados y exportación.
- Medias anuales, Mann–Kendall, pendiente de Sen, p-value, intervalo de confianza y diagnóstico de autocorrelación lag-1.
- Corrección Benjamini–Hochberg para comparaciones de tendencias entre ubicaciones.
- Ordenamiento relativo por irradiancia media histórica con regla explícita, sin puntajes compuestos arbitrarios.
- Proyección de energía y VAN calculados solamente con supuestos editables del usuario.
- Interfaz Next.js 16 en español con mapa MapLibre, gráficos Recharts, comparativas, oportunidades, cautelas y brechas accionables.
- Exportación del reporte estructurado en JSON.
- Validación y métricas geodésicas WGS84 para geometrías GeoJSON de punto, corredor y polígono.
- Siete módulos del prompt representados con estados diferenciados y honestos.
- Docker Compose aislado de MyFix en los puertos 3100 y 8000.

## Evidencia de integración real

- Una ejecución NASA POWER 2019–2023 recuperó 1,826 observaciones diarias por variable y ubicación para Moquegua y Arequipa.
- El recorrido visual 2001–2024 representó 24 medias anuales reales por sitio en la gráfica temporal.
- El pipeline produjo nueve estados trazables: ocho completados y el paso de inteligencia territorial marcado como parcial.
- El resultado comparativo ubicó a Moquegua primero por irradiancia media histórica (6.5716 kWh/m²/día) y Arequipa segundo (6.5592 kWh/m²/día).
- Las cifras económicas resultaron negativas bajo los supuestos iniciales, demostrando que el sistema no fuerza una conclusión favorable.
- Consulta real CMR verificada para Moquegua (`s18w071`) y Arequipa (`s17w072`) en NASADEM HGT y SC; sin credencial, la respuesta declara `METADATA_ONLY` y `DATA_UNAVAILABLE` para las métricas raster.
- Suite backend: 16/16 pruebas aprobadas, incluidas la orquestación completa del screening, la selección de teselas NASADEM y la prohibición de sustituir un fallo NASA por datos ficticios.
- Compilación de producción Next.js y TypeScript aprobada.
- Auditoría npm: 0 vulnerabilidades conocidas.
- Recorrido funcional en navegador aprobado: interfaz y resultados en español, pipeline completo, mapa, gráficos, brechas y control de exportación sin errores de consola.
- Diseño adaptable verificado a 375 px de ancho sin desbordamiento horizontal.

## Sistema de calidad con Agent Skills

- Cuatro Skills oficiales de `openai/plugins`, plugin `build-web-apps` 0.1.2, instaladas globalmente y comparadas con la copia oficial auditada: `frontend-app-builder`, `frontend-testing-debugging`, `react-best-practices` y `shadcn-best-practices`.
- Cinco Skills especializadas, versionadas en `.agents/skills/`: `nasa-earth-data`, `geospatial-engineering`, `statistical-trend-analysis`, `infrastructure-investment` y `scientific-quality-assurance`.
- Las nueve Skills pasan `quick_validate.py`; las cuatro oficiales presentan cero diferencias de contenido después de normalizar finales de línea de Windows.
- `AGENTS.md` define estándares permanentes de arquitectura, procedencia, validación científica, seguridad, pruebas, navegador y reproducibilidad.
- El auditor científico del proyecto finaliza con `ok: true`, sin errores ni advertencias.
- Validadores especializados ejecutados con casos reales y controlados: respuesta NASA POWER, GeoJSON válido e inválido, tendencia Mann–Kendall/Sen, VAN y auditoría integral.
- Frontend verificado en navegador a 1440×900 y 390×844: edición de supuestos, pipeline completo, dos resultados, cinco brechas, cero overflow y cero errores de consola.
- Se corrigió el desplazamiento de resultados en móvil para que la cabecera fija no oculte el identificador reproducible.
- `supabase-best-practices` no se instaló porque el repositorio no utiliza Supabase.

## Plan operativo y DOP neuronal (documentos internos, fuera de la app)

- Desde el 2026-10-22 el DOP y el plan operativo no se sirven en `localhost:3100`: son documentos internos de seguimiento y viven en `docs/interno/`. La vista React `/dop-neuronal` se retiró (queda en el historial de git); el tracker HTML conserva los 18 nodos, dependencias, bloqueos, salidas y puertas de aceptación.
- Tracker HTML en `docs/interno/dop-neuronal.html`, con vistas de dependencias, ruta crítica y backlog priorizado; persiste seguimiento en `localStorage`, exige evidencia para `VERIFICADO` y permite importar/exportar un JSON versionado.
- La siguiente acción se calcula a partir de predecesores verificados y prioriza la ruta crítica; los filtros combinan texto, estado, fase y trabajo ejecutable sin alterar los datos guardados.
- La ruta crítica conecta fuentes faltantes, armonización espacial, PostGIS/muestreo, etiquetas reales, splits sin fuga, baseline, candidatos neuronales y gate humano.
- El nodo NASADEM figura `EN_CURSO`: metadatos y preview están integrados; la validación de celdas HGT/SC queda bloqueada hasta configurar Earthdata Login.
- Hoja de ruta interactiva en `docs/interno/plan-operativo.html` (ya no enlazada desde la aplicación).
- Ocho fases con objetivo, insumos, tareas, resultado, dependencias y criterio de aceptación verificable.
- DOP neuronal con fuentes, procedencia/QA, ingeniería de características, baseline, modelos candidatos, incertidumbre, explicabilidad, revisión humana y exportación.
- Las redes neuronales se muestran como `FUTURO — NO IMPLEMENTADO`; requieren etiquetas confiables, dataset versionado y demostrar mejora fuera de muestra frente a baselines simples.
- Interacciones de fases y modelos verificadas mediante teclado y navegador; escritorio 1440×1000 y móvil 390×844 sin desbordamiento ni errores de consola.
- Tracker verificado en navegador a 1440, 768 y 390 px: 12 pasos críticos, 18 filas de backlog, cuatro nodos ejecutables iniciales, filtros combinados, puerta de evidencia y cero errores de consola.
- La referencia visual se conserva en `docs/design/plan-operativo-concept.png` y la decisión arquitectónica en `ADR-007`.

## Rediseño premium verificado

- La interfaz principal ahora es un Earth Intelligence Workspace operativo, no una landing page.
- Mapa central, procedencia, controles, pipeline, evidencia y decisión comparten una jerarquía técnica coherente.
- Public Sans e IBM Plex Mono se sirven con `next/font`; no dependen de fuentes del sistema del visitante.
- En móvil existe una barra persistente de cuatro destinos y acceso “Más” a los siete módulos.
- El drawer móvil gestiona `inert`, `aria-hidden`, foco inicial, retorno de foco y cierre con Escape.
- Cambiar a un módulo pendiente elimina el resultado solar previo para evitar atribución errónea.
- Recorrido funcional aprobado a 1440, 768 y 390 px. La auditoría visual automatizada más reciente conserva cuatro hallazgos de estilo preexistentes —microetiquetas, texto menor de 11 px, proximidad al borde y ausencia de `h1` en el workspace— como backlog explícito para la siguiente rama de diseño.
- Auditoría, prompt visual, capturas y fidelity ledger están en `docs/design/`.

## Pulido de consola (rama `claude/diseno-consola`)

- La lectura comparativa ordena los sitios (Arequipa 1.º con 6.616 y Moquegua 2.º con 6.602 kWh/m²/día; diferencia de 0.2 %) y muestra el VAN junto a los supuestos con que se calculó.
- La serie anual tiene leyenda por sitio y un eje vertical ajustado y declarado; las unidades se presentan en español.
- Masthead de 89 px con `h1`; el paso parcial del pipeline es visible; en móvil la lectura encabeza el banco tras ejecutar.
- Verificado con Playwright a 1440, 768 y 390 px: sin overflow, sin errores de consola, edición de supuestos y cambio de variable comprobados.

## Pipeline v2 y preguntas del reto NASA

- Las nueve etapas derivan su estado y su evidencia de la ejecución real (ADR-012); el inspector de la interfaz muestra resumen, evidencia, procedencia, tiempo y preguntas que sustenta cada etapa.
- La respuesta incluye `nasa_questions` y `trend_findings`. Con datos reales 2001–2024: la temperatura sube en Moquegua y Arequipa (+0.80 °C en Moquegua) y el viento baja en Moquegua; la irradiancia no muestra deriva. La significancia se marca con salvedades por autocorrelación lag-1 de 0.48 y 0.42.
- NASADEM se integra al orquestador; su fallo no bloquea el screening. El parseo de NASA POWER deja de bloquear el bucle (ADR-013).
- Backend: 20/20 pruebas, incluidas preguntas con y sin tendencia, caída de NASADEM y cobertura insuficiente.

## Contrato común entre sectores (C2)

- `ScreeningEnvelope` v1.0 con esquema y ejemplo real en `docs/coordination/contracts/` (ADR-015); la respuesta solar lo cumple y sigue siendo compatible con la interfaz.
- Orquestación reutilizable para los pilotos vial e inmobiliario: extracción POWER + NASADEM, análisis Hamed–Rao + BH, constructores de etapas, `SectorLens` para la quinta pregunta y verificación `envelope_violations`.
- Backend: 29/29 pruebas, incluidas 5 de conformidad.

## Reporte PDF ejecutivo (C3)

- Botón «PDF ejecutivo» en la consola y `POST /api/v1/reports/executive-pdf`, genérico para cualquier sector (ADR-016).
- PDF de 3 páginas con datos reales: las cinco preguntas NASA en la portada, tendencias con minigráfico y recta de Sen, relieve NASADEM, pipeline, supuestos, brechas, método, fuentes con DOI y huella SHA-256.
- Verificado: 36/36 pruebas backend (el texto del PDF se lee con pypdf) y descarga real en navegador a 1440 y 390 px, con la etapa 9 en «Completado» y sin errores de consola.

## Brechas prioritarias

0. ~~Confirmar las tendencias autocorrelacionadas con Mann–Kendall modificado~~ **Hecho (ADR-014):** Hamed–Rao como prueba de decisión; la tendencia de temperatura se confirma (p corregido 0.0016 en Moquegua y 0.0141 en Arequipa; factor 1.000) y el pre-blanqueo libre de tendencia coincide. El viento de Moquegua queda al límite (p BH 0.048).

1. Configurar un `EARTHDATA_TOKEN` y validar contra archivos oficiales las celdas de elevación, pendiente y orientación NASADEM ya conectadas por CMR.
2. Incorporar red eléctrica, subestaciones y distancia de conexión con fuente y fecha verificadas.
3. Añadir áreas protegidas, ecosistemas frágiles y restricciones ambientales oficiales.
4. Incorporar sensibilidad social, comunidades y patrimonio arqueológico con salvaguardas adecuadas.
5. Integrar GPM IMERG V07 y AppEEARS cuando exista acceso Earthdata configurado y verificable.
6. Implementar muestreo NASA a lo largo de corredores y polígonos; hoy esas geometrías solo se validan y miden.
7. Construir los pilotos vial y de desarrollo inmobiliario después de contar con las capas territoriales mínimas.
8. Añadir persistencia PostGIS, trabajos asíncronos y exportación PDF para análisis de mayor escala.

## Traspaso a Claude Code

- El incremento NASADEM y el mapa de desarrollo se cierran juntos para evitar que dos agentes editen simultáneamente `workspace.tsx`, `geo-map.tsx` y `styles.css`.
- El siguiente trabajo visual parte de `docs/design/CLAUDE_HANDOFF.md` y debe realizarse en una rama separada.
- La normalización de unidades, escala del gráfico, jerarquía del resultado, densidad de cabecera, etiqueta del paso 5 y orden móvil permanecen pendientes a propósito; no forman parte de la integración NASADEM.

## Riesgos y límites declarados

- NASA POWER utiliza estimaciones de grilla; no reemplaza mediciones in situ ni estudios de factibilidad.
- POWER puede aplicar límites de servicio; la caché reduce solicitudes repetidas, pero no elimina esa dependencia.
- NASADEM permite consultar metadatos y vistas previas mediante CMR público, pero los archivos analíticos HGT/SC permanecen protegidos por Earthdata Login.
- Mann–Kendall sin modificación puede verse afectado por correlación serial; cada resultado expone el diagnóstico lag-1 y la limitación.
- El orden relativo actual considera irradiancia histórica, no permisos, conexión, propiedad, CAPEX local ni impactos sociales.
- Ningún valor faltante se convierte en cero y ninguna capa pendiente se presenta como disponible.
