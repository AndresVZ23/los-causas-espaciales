# DOP neuronal de desarrollo

El DOP neuronal representa el proceso necesario para determinar si un modelo neuronal puede aportar valor verificable. Es una arquitectura de trabajo; no afirma que exista un modelo entrenado.

## Cadena autorizada

1. Integrar fuentes NASA y territoriales con versión, unidades, QA, CRS, cobertura y procedencia.
2. Armonizar rasters y vectores sin ocultar reproyecciones, remuestreo o nodata.
3. Implementar muestreo de puntos, corredores y polígonos y persistir ejecuciones en PostGIS.
4. Construir un feature store versionado y etiquetas derivadas de resultados reales.
5. Congelar particiones temporales y espaciales sin fuga.
6. Entrenar y publicar baselines simples reproducibles.
7. Evaluar arquitecturas neuronales solo si la estructura de los datos lo justifica.
8. Validar mejora fuera de muestra, incertidumbre, calibración, explicabilidad y drift.
9. Someter cualquier candidato a revisión humana multidisciplinaria.
10. Desplegar únicamente como apoyo al screening, con monitoreo, abstención y rollback.

## Bloqueos actuales

- Acceso y producto final para GPM IMERG y AppEEARS.
- Selección y validación del DEM.
- Endpoints, licencias, fechas y cobertura de capas oficiales peruanas.
- Persistencia PostGIS y ejecución asíncrona.
- Corpus de resultados reales para construir etiquetas.

## Regla de adopción

Una red solo se adopta si supera al baseline fuera de muestra con una diferencia material, mantiene calibración aceptable en regiones y períodos no vistos, conserva trazabilidad completa y supera la puerta humana. Si no lo hace, se mantiene el método más simple.
