---
name: infrastructure-investment
description: Diseñar y auditar evaluaciones preliminares de inversión en energía, carreteras, inmuebles e infraestructura usando evidencia territorial, supuestos explícitos y modelos financieros reproducibles. Usar al calcular VAN/NPV, energía o ingresos, estructurar escenarios, sensibilidad, riesgos, mitigaciones, ranking de sitios o recomendaciones comerciales.
---

# Inversión en infraestructura

Mantener separados recurso observado, estimación técnica, supuesto comercial y conclusión de inversión. Un screening prioriza estudios; no equivale a factibilidad ni recomendación financiera.

## Flujo obligatorio

1. Definir etapa de decisión: exploración, screening, prefactibilidad, factibilidad o debida diligencia.
2. Formular la decisión y alternativa base: invertir, descartar, priorizar estudio o comparar ubicaciones.
3. Crear registro de supuestos con nombre, valor, unidad, moneda, fecha base, fuente, propietario y rango de sensibilidad.
4. Vincular cada entrada con `REAL_DATA`, `CACHED_DATA`, `MODEL_ESTIMATE`, `USER_ASSUMPTION` o `DATA_UNAVAILABLE`.
5. Implementar fórmulas dimensionalmente consistentes y exponerlas en API/documentación.
6. Construir flujos de caja por período. Distinguir CAPEX, OPEX, ingresos, reposiciones, impuestos, valor residual y mitigación; si no están modelados, declararlos como exclusiones.
7. Mantener consistencia nominal/real, tasa/flujo, moneda y periodicidad.
8. Calcular escenario base y sensibilidades sobre variables materiales; no ocultar escenarios adversos.
9. Construir registro de riesgos con probabilidad, impacto, evidencia, responsable, mitigación, costo y riesgo residual.
10. Emitir una conclusión condicionada a brechas y próximos estudios.

Leer `references/decision-framework.md` antes de añadir un puntaje, una recomendación o un tipo de financiamiento.

## Reglas de modelado

- Calcular `VAN = Σ CF_t / (1+r)^t`, incluyendo inversión inicial en t=0.
- No descontar flujos reales con tasa nominal ni mezclar monedas sin tipo de cambio y fecha.
- No derivar CAPEX, precio o tarifa desde NASA; son supuestos o fuentes comerciales separadas.
- No asignar cero a permisos, conexión, predios, impactos sociales o arqueología cuando faltan datos.
- No crear score compuesto sin variables, normalización, pesos, dirección, tratamiento de faltantes y sensibilidad visibles.
- Preferir comparación transparente por indicador antes que un score opaco.
- Expresar energía solar como estimación de modelo dependiente de irradiancia y performance ratio, no como producción garantizada.

## Validación ejecutable

Ejecutar `python scripts/verify_cashflow.py escenario.json`. El archivo debe incluir `discount_rate` y `cashflows`, donde el primer flujo corresponde a t=0. Comparar el VAN independiente con el backend a tolerancia de moneda definida.

Casos mínimos: tasa cero, VAN positivo/negativo, horizonte de un año, flujo inicial, mitigación adicional y entrada inválida.

## Criterios de aceptación

- Etapa de decisión y disclaimer visibles.
- Supuestos editables con unidad, moneda y procedencia.
- Fórmulas y periodicidad documentadas.
- Prueba independiente del VAN y cálculos técnicos.
- Sensibilidad de variables materiales y al menos un escenario adverso.
- Brechas territoriales no tratadas como riesgo cero.
- Resultado reproducible mediante identificador y exportación estructurada.
- Ninguna recomendación supera la evidencia disponible.

