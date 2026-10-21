---
name: geospatial-engineering
description: Diseñar, implementar y verificar operaciones geoespaciales para puntos, corredores, polígonos, rasters y capas territoriales. Usar al trabajar con GeoJSON, MapLibre, PostGIS, pyproj, shapely, reproyección, distancias, áreas, buffers, intersecciones, muestreo raster, DEM, redes o capas oficiales peruanas; y al auditar CRS, orden de ejes, geometrías, resolución o unidades.
---

# Ingeniería geoespacial

Hacer explícito el modelo espacial antes de ejecutar cálculos. Una geometría visualmente correcta puede producir métricas incorrectas si CRS, eje o unidad son ambiguos.

## Flujo obligatorio

1. Definir la pregunta espacial y la magnitud de salida: coordenada, longitud, área, distancia, pendiente, intersección o muestra raster.
2. Identificar CRS de entrada, CRS de análisis y CRS de salida por código de autoridad o WKT2.
3. Validar geometría, rango de coordenadas, orden de ejes, dimensionalidad y antimeridiano.
4. Elegir operación:
   - visualización/intercambio GeoJSON: WGS84, longitud-latitud;
   - distancia sobre WGS84: geodesia elipsoidal;
   - área, buffer o topología local: CRS proyectado apropiado;
   - análisis raster: respetar CRS, tamaño de píxel, nodata, escala y remuestreo.
5. Transformar siempre con una librería CRS; nunca multiplicar grados por una constante para métricas de producción.
6. Registrar unidades de entrada y salida, transformación, resolución y tolerancias.
7. Probar geometrías límite: vacía, inválida, anillo abierto, coordenadas invertidas y multiparte.
8. Comparar una geometría conocida con una implementación independiente o referencia autoritativa.

Leer `references/standards.md` antes de introducir un formato o transformación nueva.

## Reglas de implementación

- Tratar GeoJSON RFC 7946 como longitud, latitud en WGS84; no insertar miembros `crs` heredados.
- Rechazar latitud fuera de [-90, 90] y longitud fuera de [-180, 180] cuando se espera WGS84.
- Usar `always_xy=True` en pyproj cuando la aplicación trabaja como x/y y documentar esa decisión.
- Corregir geometrías solo mediante una política explícita; no ocultar un `make_valid` silencioso.
- No combinar capas con CRS desconocido.
- No interpretar ausencia de intersección como ausencia de riesgo si la capa está incompleta o desactualizada.
- Conservar fuente, fecha, escala/resolución, licencia y cobertura de cada capa oficial.

## Validación ejecutable

Ejecutar `python scripts/validate_geojson.py archivo.geojson` para estructura, tipos, finitud, rangos WGS84, mínimos geométricos y cierre de anillos. Complementar con Shapely/PostGIS para topología y con pyproj/GeographicLib para métricas.

## Criterios de aceptación

- CRS y orden de ejes declarados en contrato y documentación.
- Geometría válida o error explicativo; nunca reparación oculta.
- Métricas acompañadas por unidad y método geodésico/proyectado.
- Nodata y cobertura espacial tratados explícitamente.
- Fuente, versión/fecha, licencia y resolución de cada capa registradas.
- Pruebas con geometrías nominales y casos límite.
- Comparación contra una segunda implementación dentro de tolerancia documentada.
- Mapa validado visualmente en escritorio y móvil si cambia la representación.

Bloquear cualquier resultado de área, distancia o riesgo si el CRS es desconocido.

