# Estándares permanentes — Los Causas Espaciales

## Alcance

Aplicar estas reglas a todo el repositorio. Trabajar exclusivamente dentro de esta ruta. Mantener la experiencia y documentación de producto en español; conservar en inglés únicamente nombres propios, identificadores de API y términos técnicos que perderían precisión.

Puertos reservados:

- Web de Los Causas Espaciales: `3100`.
- API: `8000`.
- No usar `3000`; pertenece a MyFix.

## Skills obligatorias por dominio

- UI nueva o rediseño: `frontend-app-builder` y `react-best-practices`.
- QA visual o depuración de UI: `frontend-testing-debugging` y Browser.
- shadcn/ui: `shadcn-best-practices`; usarla solo si existe `components.json` o se adopta shadcn explícitamente.
- NASA/Earthdata: `.agents/skills/nasa-earth-data`.
- CRS, geometrías, mapas o rasters: `.agents/skills/geospatial-engineering`.
- Tendencias, incertidumbre o pruebas múltiples: `.agents/skills/statistical-trend-analysis`.
- VAN, energía, escenarios o riesgos: `.agents/skills/infrastructure-investment`.
- Cierre de funcionalidades: `.agents/skills/scientific-quality-assurance`.

No usar `supabase-best-practices` mientras el repositorio no use Supabase.

## Arquitectura y mantenibilidad

- Mantener límites claros: conectores externos, modelos/esquemas, estadística, geoespacial, sectores, API y presentación.
- Evitar archivos monolíticos. Extraer componentes, hooks, servicios y utilidades cuando mezclen responsabilidades o dificulten pruebas.
- Definir contratos Pydantic/TypeScript explícitos en las fronteras. No propagar diccionarios sin tipo entre capas.
- Mantener funciones científicas puras cuando sea posible; separar I/O, transformación y presentación.
- No duplicar fórmulas ni catálogos de variables. Mantener una fuente canónica y probarla.
- Preservar compatibilidad de API o documentar y versionar cambios incompatibles.

## React y Next.js

- Preferir Server Components; usar `"use client"` solo donde haya estado, efectos, mapas, gráficos o interacción necesaria.
- Dividir pantallas complejas en componentes semánticos y probables de probar.
- Evitar waterfalls, dependencias de efectos inestables, mutación de estado y renderizados innecesarios.
- Cargar dinámicamente bibliotecas pesadas cuando no sean necesarias para el primer render.
- Implementar estados de vacío, carga, éxito, parcial y error con texto accionable.
- Mantener accesibilidad: etiquetas, foco, contraste, nombres accesibles y controles por teclado.
- No añadir shadcn, Tailwind u otra biblioteca sin una decisión explícita y una necesidad concreta.

## Python y FastAPI

- Usar type hints, Pydantic para entrada/salida y excepciones de dominio traducidas a respuestas HTTP controladas.
- Definir timeout en toda llamada externa; limitar reintentos y no ocultar 4xx/5xx del proveedor.
- Separar router, servicio, conector y cálculo científico.
- No ejecutar I/O bloqueante dentro de rutas async sin aislamiento adecuado.
- Validar rangos, fechas, número de sitios, geometrías y supuestos antes de procesar.
- Mantener OpenAPI coherente con el comportamiento y ejemplos reales.

## Datos NASA y procedencia

- Verificar producto, versión, parámetro, unidad, resolución, período, estándar temporal, valores faltantes y QA contra documentación oficial.
- Conservar respuesta cruda/caché, fecha UTC de descarga, URL/DOI, coordenadas solicitadas, celda devuelta, transformaciones y clave de caché.
- Usar únicamente: `REAL_DATA`, `CACHED_DATA`, `MODEL_ESTIMATE`, `USER_ASSUMPTION`, `ILLUSTRATIVE_DEMO`, `DATA_UNAVAILABLE`.
- Nunca presentar datos ficticios, demos, supuestos o estimaciones como observaciones reales.
- Nunca convertir faltantes a cero ni rejuvenecer la fecha de una respuesta cacheada.
- Mostrar limitaciones de resolución y uso; NASA POWER no reemplaza medición in situ ni factibilidad.

## Estadística

- Declarar hipótesis, frecuencia, alpha, familia de pruebas, n válido y cobertura.
- Reportar efecto, pendiente, intervalo, p-value crudo/ajustado, autocorrelación y limitaciones.
- Diagnosticar empates, estacionalidad, faltantes y correlación serial.
- Contrastar cálculos sensibles con una implementación independiente y datasets controlados.
- Interpretar “no significativo” como evidencia insuficiente, no como ausencia probada de cambio.

## Geoespacial

- Declarar CRS de entrada, análisis y salida; confirmar orden de ejes y unidades.
- GeoJSON de intercambio usa WGS84 longitud-latitud conforme a RFC 7946.
- Usar geodesia para métricas sobre WGS84 o CRS proyectado apropiado para análisis local.
- Validar geometrías, nodata, cobertura, resolución, escala y licencia de capas.
- No afirmar ausencia de riesgo cuando una capa está ausente, incompleta o desactualizada.

## Inversión y finanzas

- Etiquetar cada entrada como dato, estimación o supuesto.
- Exponer fórmula, moneda, fecha base, periodicidad, horizonte y tasa.
- Probar VAN y cálculos técnicos con casos independientes.
- Incluir sensibilidad y escenarios adversos para variables materiales.
- Distinguir screening, prefactibilidad y factibilidad. No emitir recomendación más fuerte que la evidencia.

## Pruebas y definición de terminado

Antes de cerrar un cambio aplicable:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm.cmd run build
npm.cmd audit --audit-level=high
```

Además:

- Añadir pruebas nominales, límites, faltantes y errores externos.
- Ejecutar los validadores de las Skills de dominio relevantes.
- Verificar una integración NASA representativa contra una respuesta oficial real cuando cambie el conector.
- Probar componentes interactivos y el flujo principal mediante Browser.
- Revisar escritorio y un viewport móvil, consola, overlay, clipping, desbordamiento y estados de error.
- Corregir fallos antes de declarar completado; marcar como pendiente lo que no pudo verificarse.

## Seguridad

- No almacenar secretos en código, caché, fixtures, capturas o documentación.
- Mantener `.env` ignorado y `.env.example` sin credenciales.
- Auditar dependencias y revisar código/procedencia antes de instalar paquetes o ejecutar scripts externos.
- Validar entradas, nombres de archivo y URLs; limitar tamaño, tiempo y concurrencia de trabajos externos.
- No exponer trazas internas ni datos sensibles en respuestas de producción.

## Documentación y reproducibilidad

- Actualizar `README.md`, `PROGRESS.md`, OpenAPI y documentos de arquitectura cuando cambie alcance o comportamiento.
- Registrar decisiones relevantes en `docs/architecture/DECISION_LOG.md`.
- Conservar comandos, versiones, parámetros, fuentes, fechas y resultados de verificación.
- Cada análisis exportable debe incluir identificador, período, coordenadas, supuestos, procedencia, métodos, limitaciones y timestamp.
- Mantener estados honestos para los siete módulos y las brechas territoriales.

