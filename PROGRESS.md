# Estado del proyecto

Última actualización: 2026-10-21

## Versión operativa verificada

- Backend FastAPI con contratos Pydantic y documentación OpenAPI.
- Orquestador `POST /api/v1/projects/solar-screening` para ejecutar el caso solar de extremo a extremo.
- Consulta multiparámetro real a NASA POWER con caché de 24 horas, timeout y procedencia `REAL_DATA` / `CACHED_DATA`.
- Serie temporal anual real expuesta por la API y representada por sitio después de cada consulta.
- Mapa base contextual NASA EOSDIS GIBS Blue Marble, identificado como producto visual estático y no como evidencia analítica actual.
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
- Suite backend: 13/13 pruebas aprobadas, incluidas la orquestación completa del screening y la prohibición de sustituir un fallo NASA por datos ficticios.
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

## Plan operativo y DOP neuronal

- DOP neuronal interactivo disponible en `http://localhost:3100/dop-neuronal`, con 18 nodos, dependencias ascendentes/descendentes, bloqueos, salidas y puertas de aceptación.
- La ruta crítica conecta fuentes faltantes, armonización espacial, PostGIS/muestreo, etiquetas reales, splits sin fuga, baseline, candidatos neuronales y gate humano.
- Hoja de ruta interactiva disponible en `http://localhost:3100/plan-operativo.html` y enlazada desde la navegación principal.
- Ocho fases con objetivo, insumos, tareas, resultado, dependencias y criterio de aceptación verificable.
- DOP neuronal con fuentes, procedencia/QA, ingeniería de características, baseline, modelos candidatos, incertidumbre, explicabilidad, revisión humana y exportación.
- Las redes neuronales se muestran como `FUTURO — NO IMPLEMENTADO`; requieren etiquetas confiables, dataset versionado y demostrar mejora fuera de muestra frente a baselines simples.
- Interacciones de fases y modelos verificadas mediante teclado y navegador; escritorio 1440×1000 y móvil 390×844 sin desbordamiento ni errores de consola.
- La referencia visual se conserva en `docs/design/plan-operativo-concept.png` y la decisión arquitectónica en `ADR-007`.

## Rediseño premium verificado

- La interfaz principal ahora es un Earth Intelligence Workspace operativo, no una landing page.
- Mapa central, procedencia, controles, pipeline, evidencia y decisión comparten una jerarquía técnica coherente.
- Public Sans e IBM Plex Mono se sirven con `next/font`; no dependen de fuentes del sistema del visitante.
- En móvil existe una barra persistente de cuatro destinos y acceso “Más” a los siete módulos.
- El drawer móvil gestiona `inert`, `aria-hidden`, foco inicial, retorno de foco y cierre con Escape.
- Cambiar a un módulo pendiente elimina el resultado solar previo para evitar atribución errónea.
- Inspección visual final a 1440, 768 y 390 px: 0 errores y 0 advertencias.
- Auditoría, prompt visual, capturas y fidelity ledger están en `docs/design/`.

## Brechas prioritarias

1. Integrar un modelo digital de elevación para pendiente y orientación del terreno.
2. Incorporar red eléctrica, subestaciones y distancia de conexión con fuente y fecha verificadas.
3. Añadir áreas protegidas, ecosistemas frágiles y restricciones ambientales oficiales.
4. Incorporar sensibilidad social, comunidades y patrimonio arqueológico con salvaguardas adecuadas.
5. Integrar GPM IMERG V07 y AppEEARS cuando exista acceso Earthdata configurado y verificable.
6. Implementar muestreo NASA a lo largo de corredores y polígonos; hoy esas geometrías solo se validan y miden.
7. Construir los pilotos vial y de desarrollo inmobiliario después de contar con las capas territoriales mínimas.
8. Añadir persistencia PostGIS, trabajos asíncronos y exportación PDF para análisis de mayor escala.

## Riesgos y límites declarados

- NASA POWER utiliza estimaciones de grilla; no reemplaza mediciones in situ ni estudios de factibilidad.
- POWER puede aplicar límites de servicio; la caché reduce solicitudes repetidas, pero no elimina esa dependencia.
- Mann–Kendall sin modificación puede verse afectado por correlación serial; cada resultado expone el diagnóstico lag-1 y la limitación.
- El orden relativo actual considera irradiancia histórica, no permisos, conexión, propiedad, CAPEX local ni impactos sociales.
- Ningún valor faltante se convierte en cero y ninguna capa pendiente se presenta como disponible.
