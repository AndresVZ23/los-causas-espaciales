# Producto

<!-- impeccable:product-schema 1 -->

## Platform

web

## Usuarios

- Equipos de inversión, infraestructura y sostenibilidad que necesitan evaluar ubicaciones peruanas con evidencia terrestre verificable.
- Especialistas técnicos que revisan procedencia, calidad, estadística, unidades y limitaciones antes de aceptar una conclusión.
- Jurados y aliados del NASA Space Apps Challenge que deben comprender el mecanismo y la utilidad del producto en pocos minutos.

## Propósito del producto

Los Causas Espaciales convierte observaciones oficiales de la Tierra en evaluaciones territoriales e hipótesis de inversión trazables. El éxito consiste en que una persona pueda seleccionar ubicaciones, ejecutar un análisis reproducible, distinguir datos reales de supuestos y descargar evidencia sin confundir una brecha de datos con ausencia de riesgo.

## Posicionamiento

La plataforma une, en un mismo flujo auditable, datos NASA, control geoespacial, análisis estadístico y escenarios económicos basados exclusivamente en supuestos explícitos del usuario.

## Contexto operativo

El primer flujo funcional compara Moquegua y Arequipa para un screening solar. Consulta NASA POWER, calcula Mann–Kendall, pendiente de Sen, p-values ajustados, cobertura y variabilidad, y deriva un escenario VAN parametrizable. La interfaz se ejecuta en `localhost:3100`; la API FastAPI y OpenAPI, en `localhost:8000`. `localhost:3000` pertenece a MyFix y queda fuera de alcance.

## Capacidades y restricciones

- Frontend Next.js 16 con MapLibre y Recharts; backend FastAPI con OpenAPI.
- NASA POWER es la fuente operativa real. La procedencia debe conservar `REAL_DATA`, `CACHED_DATA`, `MODEL_ESTIMATE`, `USER_ASSUMPTION`, `ILLUSTRATIVE_DEMO` o `DATA_UNAVAILABLE`.
- Los siete módulos deben ser visibles, pero solo pueden declararse funcionales cuando exista integración y validación reproducible.
- IMERG, AppEEARS, PostGIS, polígonos, corredores y capas oficiales peruanas continúan pendientes hasta su integración verificada.
- No se instalará ni utilizará Supabase mientras el repositorio no lo requiera.
- No se presentarán datos ficticios, demostraciones o supuestos como observaciones reales.

## Compromisos de marca

- Nombre: Los Causas Espaciales.
- Idioma actual de producto y documentación: español.
- Carácter de la plataforma (`/plataforma`): científico, territorial, sobrio, preciso y comercialmente útil; sin estética infantil, gamificación ni afirmaciones grandilocuentes.
- Carácter del juego (portada, ADR-050): educativo para público general, cinematográfico y esperanzador. La gamificación es explícita y se declara (estado del planeta, regresos, decisiones simuladas); nunca reemplaza ni maquilla una cifra medida.
- La portada es el juego TERRA 2045; la consola de la plataforma debe seguir funcionando como un espacio de inteligencia terrestre, no como una landing page de marketing.

## Evidencia disponible

- Integración funcional con NASA POWER y caché local.
- Pruebas automatizadas del backend y compilación de producción del frontend.
- Respuesta real de NASA POWER para Moquegua ya verificada en el repositorio.
- Documentación oficial y registros de progreso en `README.md`, `PROGRESS.md` y `docs/`.
- No hay evidencia integrada todavía para IMERG, AppEEARS, PostGIS ni capas oficiales peruanas; esa ausencia debe permanecer visible.

## Principios de producto

1. La procedencia acompaña cada resultado.
2. Una brecha se muestra como brecha, nunca como riesgo cero.
3. La decisión nace de un flujo reproducible, no de una cifra aislada.
4. La interfaz prioriza operar, comparar y verificar por encima de persuadir.
5. Los cálculos económicos conservan sus supuestos y limitaciones.

## Accesibilidad e inclusión

La interfaz debe alcanzar WCAG 2.2 AA en contraste, navegación por teclado, foco visible, semántica y objetivos táctiles. Debe funcionar en escritorio, tableta y móvil, y respetar `prefers-reduced-motion`.

## Decisiones inferidas y abiertas

- **Inferencia aprobada por el encargo:** el usuario primario es un equipo técnico-comercial que evalúa inversiones territoriales; el repositorio y los prompts sostienen esta conclusión.
- **Abierto:** identidad gráfica definitiva y logotipo propietario. El rediseño puede establecer un sistema visual provisional documentado, sin inventar activos de marca.
