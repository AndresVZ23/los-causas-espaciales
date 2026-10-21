---
name: scientific-quality-assurance
description: Auditar y cerrar funcionalidades científicas de Los Causas Espaciales mediante evidencia trazable. Usar antes de declarar una tarea terminada, al revisar integraciones NASA, estadísticas, operaciones geoespaciales, cálculos financieros, seguridad, documentación, pruebas, exportaciones o UI; y al construir una matriz de cumplimiento y riesgos pendientes.
---

# Aseguramiento de calidad científica

Aplicar puertas de calidad basadas en evidencia. Un build aprobado no demuestra corrección científica, y una fórmula correcta no demuestra una experiencia funcional.

## Preparar la matriz de evidencia

Por cada requisito registrar: requisito, implementación, fuente primaria, prueba, resultado, artefacto verificable, limitación, responsable y estado (`VERIFICADO`, `PARCIAL`, `NO_DISPONIBLE`, `FALLÓ`). No usar porcentajes de avance sin criterios observables.

Leer `references/release-gates.md` y activar las Skills de dominio correspondientes.

## Puertas obligatorias

1. **Arquitectura:** contratos claros, módulos cohesivos, errores controlados y cambios sin duplicación innecesaria.
2. **Datos:** fuente primaria, versión, unidad, período, resolución, faltantes, caché y procedencia validados.
3. **Estadística:** hipótesis, n, cobertura, efecto, incertidumbre, autocorrelación y multiplicidad comprobados.
4. **Geoespacial:** CRS, ejes, geometría, nodata, unidades y tolerancias verificados.
5. **Inversión:** supuestos, moneda, fecha base, fórmula, sensibilidad, riesgos y disclaimer explícitos.
6. **Frontend:** build, carga, estados vacío/carga/error/éxito, interacción principal, consola, escritorio y móvil verificados en Browser.
7. **Backend:** pruebas unitarias, contrato OpenAPI, integración representativa y manejo de error externo.
8. **Seguridad:** secretos fuera del repositorio, dependencias auditadas, entradas validadas, timeouts y errores sin datos sensibles.
9. **Reproducibilidad:** comando, versiones, parámetros, identificador de análisis, exportación y documentación suficientes para repetir.

## Procedimiento de cierre

1. Ejecutar `python scripts/audit_project.py --root <repositorio>`.
2. Ejecutar pruebas backend y build/auditoría frontend desde `AGENTS.md`.
3. Ejecutar los validadores de dominio sobre una entrada válida y una inválida.
4. Probar el flujo principal en Browser: carga → acción → resultado esperado.
5. Repetir en viewport móvil y revisar errores/warnings relevantes de consola.
6. Comparar una respuesta NASA real y un cálculo estadístico/financiero con una segunda implementación.
7. Corregir fallos; no degradarlos a “limitación” si son defectos corregibles.
8. Marcar como pendiente cualquier puerta que no pudo ejecutarse y explicar el bloqueo concreto.

## Criterios de aceptación

- Cero puertas aplicables en estado `FALLÓ`.
- Toda afirmación científica o comercial importante enlaza evidencia y procedencia.
- Pruebas nominales, límites y errores aprobadas.
- Navegador sin overlay, errores relevantes, clipping ni desbordamiento.
- Dependencias sin vulnerabilidades conocidas de severidad acordada.
- Documentación y estados públicos coinciden con la implementación.
- El resumen final distingue verificado, parcial, no probado y pendiente.

No declarar completado por falta de tiempo. Entregar el estado honesto y conservar la evidencia.

