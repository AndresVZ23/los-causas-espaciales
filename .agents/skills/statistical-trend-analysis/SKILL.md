---
name: statistical-trend-analysis
description: Implementar, revisar y contrastar análisis de tendencia temporal reproducibles. Usar con Mann-Kendall, Kendall tau, pendiente de Sen/Theil-Sen, p-values, intervalos de confianza, autocorrelación, agregación anual, datos faltantes, anomalías, comparaciones múltiples o interpretación estadística de series climáticas y geoespaciales.
---

# Análisis estadístico de tendencias

Separar siempre magnitud, incertidumbre y significancia. “No significativo” significa evidencia insuficiente bajo el diseño y período analizados, no ausencia demostrada de cambio.

## Flujo obligatorio

1. Definir hipótesis, unidad de análisis, período, frecuencia, alpha y familia de comparaciones antes de calcular.
2. Auditar fechas duplicadas, faltantes, sentinelas, finitud, cobertura y cambios de frecuencia.
3. Declarar la regla de agregación. No promediar promedios mensuales sin ponderación cuando se busca una media diaria/anual.
4. Exigir al menos cinco observaciones temporales agregadas para un resultado exploratorio; usar períodos más largos para inferencia climática y declarar la limitación.
5. Calcular estadístico de tendencia, p-value bilateral, pendiente robusta e intervalo de confianza.
6. Diagnosticar autocorrelación lag-1 y estacionalidad. Si son materiales, aplicar un método apropiado o limitar la interpretación; no afirmar independencia.
7. Definir la familia de hipótesis y aplicar corrección por comparaciones múltiples cuando corresponda.
8. Reportar n válido, cobertura, tau/S, pendiente por unidad de tiempo, IC, p crudo, p ajustado, alpha, método y limitaciones.
9. Contrastar una serie conocida mediante `scripts/crosscheck_trend.py` o una segunda implementación.

Leer `references/methods.md` antes de cambiar métodos, alpha o reglas de interpretación.

## Reglas de interpretación

- No decidir dirección solo por el signo de la pendiente cuando la evidencia no supera el umbral definido.
- No usar p-value como tamaño de efecto ni como probabilidad de que la hipótesis nula sea cierta.
- No ejecutar ajuste BH por separado para cada sitio si la familia declarada reúne sitios/variables.
- No mezclar observaciones diarias con medias anuales en una misma prueba.
- No imputar faltantes sin método, justificación y análisis de sensibilidad.
- Mostrar la pendiente incluso cuando no sea significativa, etiquetándola como estimación descriptiva.

## Validación reproducible

Ejecutar `python scripts/crosscheck_trend.py serie.csv`, con columnas `year,value`. Comparar S, p aproximado, pendiente de Sen y autocorrelación con el backend. Documentar tolerancias y diferencias de manejo de empates.

Casos mínimos de prueba:

- serie estrictamente creciente y decreciente;
- serie constante con empates;
- serie sin evidencia de tendencia;
- datos faltantes/no finitos;
- cinco y menos de cinco años;
- familia de p-values con BH y orden no clasificado.

## Criterios de aceptación

- Hipótesis, frecuencia, alpha y familia de pruebas explícitos.
- Observaciones válidas y cobertura reportadas.
- Pendiente con unidad temporal e intervalo de confianza.
- Autocorrelación diagnosticada y limitación visible.
- Corrección múltiple probada cuando aplica.
- Resultado contrastado por implementación independiente dentro de tolerancia.
- Interpretación distingue ausencia de evidencia de evidencia de ausencia.

