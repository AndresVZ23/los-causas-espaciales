# DOP de la red neuronal

El DOP tiene dos niveles. El primero es la **red de la plataforma**: cómo muchas entradas, a través de las capas A, B y C del prompt maestro, producen muchos resultados, y en qué orden se completa lo que falta. El segundo es el detalle de una de sus neuronas, el **calibrador FV**: el proceso para determinar si una red neuronal aporta valor verificable. Es una arquitectura de trabajo: no afirma que exista un modelo entrenado.

## Red de la plataforma

- **Unidades** (`platform.units` en `dop-datos.js`): 16 entradas (NASA, territorio peruano, usuario y resultados reales), 6 unidades de la capa A, 7 de la capa B, 8 de la capa C y 12 resultados (los 7 módulos, los pilotos y los entregables).
- **Enlaces** (`platform.links`): `[origen, destino]` es **requerido** (sin él el destino no funciona); `[origen, destino, "E"]` solo **enriquece**. Por ejemplo, el muestreo de corredores amplía el motor de tendencias, que ya funciona con puntos.
- **Cobertura de un resultado:** unidades activas de su cadena requerida sobre el total. **Ola** de una unidad pendiente: 1 + la mayor ola de sus requisitos pendientes. Las unidades activas valen 0. Un resultado queda completo en la mayor ola de su cadena. Una ola no es una semana: es un escalón de dependencias, y lo de una misma ola avanza en paralelo.
- **Siguiente acción de mayor impacto:** la unidad de la ola 1 que habilita más resultados del demo del jurado (`platform.juryTargets`).
- Con el estado del 2026-10-22, el demo necesita 4 olas: clima en la 1, inversión en la 2, lentes vial e inmobiliario en la 3 y sus pantallas en la 4.

## Dónde vive y cómo se lee

- `docs/interno/dop-neuronal.html`: documento interno, fuera de la aplicación. Se abre con doble clic, sin servidor.
- `docs/interno/dop-datos.js`: **única fuente del estado** (esquema `los-causas-dop`, versión 2), versionada en git. El HTML solo la lee; ya no guarda estados en el navegador (eso reemplaza al tracker v1 con `localStorage` y JSON importable).

Vistas: **Red de la plataforma** (entradas, capas y resultados con sus conexiones), **Orquestación** (olas de trabajo para los resultados objetivo que se elijan), **ASME del modelo** (simbología ASME del calibrador FV), **Ruta del modelo** (sus 18 etapas por fase, con ruta crítica), **Calibrador FV** (definición de la propuesta), **Plan y responsables** y **Backlog**.

## Cómo se actualiza

1. Editar `dop-datos.js` en la rama de trabajo: el estado del nodo, su evidencia (`{ label, ref }` con commit, prueba o archivo) y la tarea del plan si cambia.
2. Un nodo pasa a `VERIFICADO` solo con evidencia que cumpla su puerta de aceptación; `LISTO_PARA_QA` si está implementado y falta una puerta.
3. Actualizar `updatedAt` y `updatedBy`.
4. Dueños: Claude mantiene el HTML y los nodos y tareas a su cargo; Codex, los suyos (`owner` en cada nodo). La puerta humana (`05A`) la decide el equipo.

## Red neuronal propuesta: calibrador de rendimiento fotovoltaico

**Estado: propuesta, no implementada; bloqueada hasta verificar las etiquetas.**

- **Decisión que mejora:** reemplazar el performance ratio fijo que hoy entra como supuesto al VAN y cuantificar las pérdidas térmicas, que la tendencia significativa de temperatura vuelve materiales.
- **Objetivo:** factor de planta mensual de centrales fotovoltaicas reales del sur del Perú.
- **Etiquetas:** generación mensual publicada por el COES; acceso, licencia, recortes e indisponibilidades por verificar (Codex, tarea K1b).
- **Variables:** NASA POWER mensual en la celda de cada central (irradiancia, temperatura, viento, precipitación), relieve NASADEM, mes y edad de la planta.
- **Baselines:** el cálculo físico actual del piloto, con PR fijo, y una regresión estadística (lineal y gradient boosting).
- **Candidata:** perceptrón multicapa pequeño o red temporal convolucional sobre 12 a 24 meses, elegida por la estructura de los datos.
- **Validación:** dejar una central fuera en cada vuelta y reservar el último año; error absoluto medio, calibración e intervalos conformales.
- **Adopción:** solo con mejora material, pre-registrada, fuera de muestra; calibración aceptable y gate humano. Si no, se queda el baseline.
- **Riesgos:** muestra pequeña (cientos de planta-mes), resolución gruesa de POWER, recortes de despacho que no son clima, y correlación sin causalidad.

## Cadena autorizada

1. Integrar fuentes NASA y territoriales con versión, unidades, QA, CRS, cobertura y procedencia.
2. Armonizar rasters y vectores sin ocultar reproyecciones, remuestreo ni nodata.
3. Muestrear puntos, corredores y polígonos y persistir ejecuciones.
4. Construir features versionadas y etiquetas derivadas de resultados reales.
5. Congelar particiones por central y por tiempo, sin fuga.
6. Entrenar y publicar baselines simples reproducibles.
7. Evaluar la red solo si la estructura de los datos lo justifica.
8. Validar mejora fuera de muestra, incertidumbre, calibración, explicabilidad y drift.
9. Someter cualquier candidato a revisión humana multidisciplinaria.
10. Desplegar únicamente como apoyo al screening, con monitoreo, abstención y rollback.

## Regla de adopción

Una red solo se adopta si supera al baseline fuera de muestra con una diferencia material, mantiene calibración en centrales y períodos no vistos, conserva trazabilidad completa y supera la puerta humana. Si no lo hace, se mantiene el método más simple.
