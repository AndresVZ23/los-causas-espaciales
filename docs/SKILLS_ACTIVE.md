# Skills activas y función en el proyecto

## Oficiales de Build Web Apps

- `frontend-app-builder`: construcción y rediseño integral del frontend con validación visual.
- `frontend-testing-debugging`: pruebas en navegador, responsive, interacciones y regresiones.
- `react-best-practices`: patrones de rendimiento y arquitectura para React y Next.js.
- `shadcn-best-practices`: guía disponible para proyectos shadcn; este repositorio no depende hoy de shadcn/ui.

Estas Skills se instalaron desde el ecosistema oficial de `openai/plugins` y se compararon con su copia de procedencia. `supabase-best-practices` no se instaló porque el proyecto no usa Supabase.

## Especializadas del repositorio

Guardadas en `.agents/skills/` y validadas con `quick_validate.py`:

- `nasa-earth-data`: selección, consulta, validación y procedencia de productos NASA.
- `geospatial-engineering`: CRS, geometrías, unidades, validez topológica y métricas geodésicas.
- `statistical-trend-analysis`: Mann–Kendall, Sen, p-value, intervalos, autocorrelación y pruebas reproducibles.
- `infrastructure-investment`: energía, VAN, supuestos, sensibilidad y límites de interpretación.
- `scientific-quality-assurance`: auditoría transversal de evidencia, reproducibilidad, seguridad y criterios de aceptación.

## Sistema visual y de calidad

- `design-taste-frontend`: dirección visual `data-terminal`, lint e inspección multivista.
- `ui-ux-pro-max`: sistema de diseño persistido en `design-system/los-causas-espaciales/MASTER.md`.
- `impeccable`: contrato de superficie, revisión de cierre y documentación del sistema visual.
- Skills auxiliares instaladas junto al paquete UI/UX: `banner-design`, `brand`, `design`, `design-system`, `slides` y `ui-styling`.

Los scripts y manifiestos de terceros se revisaron antes de instalarlos. Los hooks externos quedaron desactivados y no existe `.codex/hooks.json`.

## Verificaciones ejecutadas

- Cinco Skills científicas: validación estructural aprobada.
- Backend: 13 pruebas aprobadas.
- Frontend: compilación de producción Next.js y TypeScript aprobada.
- Dependencias: `npm audit` con 0 vulnerabilidades conocidas.
- NASA: flujo real y respuesta de caché verificados mediante la API y el navegador.
- Responsive: inspección a 1440, 768 y 390 px con `0 FAIL / 0 WARN`.
- Interacción móvil: apertura/cierre de drawer, foco, Escape y aislamiento de resultados aprobados.
- Seguridad científica: sin sustitución de fallos NASA por datos ficticios.
