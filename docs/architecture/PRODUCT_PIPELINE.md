# Pipeline del producto

Este documento define el flujo operativo único exigido por el prompt maestro. Los siete módulos sectoriales reutilizan este pipeline; no son aplicaciones independientes.

## Flujo de nueve pasos

| Paso | Entrada | Proceso | Salida verificable | Estado MVP |
|---|---|---|---|---|
| 1. Selección | Punto, polígono o corredor | Validación WGS84 | Geometría válida y referencia espacial | Punto funcional; geometrías validadas |
| 2. Configuración | Sector, variables, período y supuestos | Reglas por sector | Solicitud reproducible | Solar funcional |
| 3. Extracción | Solicitud validada | Conector oficial y caché | Observaciones con metadatos y procedencia | NASA POWER funcional |
| 4. Análisis | Series temporales | Agregación anual, Mann-Kendall, Sen, autocorrelación y BH | Magnitud, p-value, intervalo y limitaciones | Funcional |
| 5. Inteligencia territorial | Geometría y capas oficiales | Cruces espaciales | Restricciones y exposición documentada | Parcial; capas oficiales pendientes |
| 6. Evaluación | Evidencia científica y territorial | Comparación transparente | Oportunidades, cautelas y brechas | Piloto solar funcional sin score arbitrario |
| 7. Impacto económico | Supuestos del usuario | Energía y VAN condicionados | Flujos y sensibilidad | Escenario solar base funcional |
| 8. Resultados | Productos anteriores | Síntesis trazable | Panel integrado y recomendaciones de estudios | Funcional para piloto solar |
| 9. Exportación | Resultado estructurado | Serialización | Reporte JSON reproducible | Funcional |

## Separación de las tres capas

1. **Earth Observation & Data Intelligence:** conectores, caché, metadatos, calidad y geometrías.
2. **Geospatial & Risk Intelligence:** tendencias, significancia, comparación y futuras superposiciones territoriales.
3. **Investment & Decision Intelligence:** escenario financiero, lectura comparativa y próximos estudios.

## Primer caso completo

El piloto de energía solar del sur peruano compara Moquegua y Arequipa con `ALLSKY_SFC_SW_DWN`, `T2M`, `WS10M` y `PRECTOTCORR`. NASA POWER se consulta una vez por sitio con varios parámetros. La producción anual y el VAN son estimaciones condicionadas a supuestos explícitos, no observaciones NASA ni una factibilidad definitiva.

## Regla de honestidad

Un paso puede ser `COMPLETADO`, `PARCIAL`, `NO DISPONIBLE` o `ERROR`. Ninguna ausencia de datos se transforma en riesgo cero y ninguna interfaz vacía se presenta como módulo terminado.
