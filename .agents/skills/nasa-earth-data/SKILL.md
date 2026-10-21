---
name: nasa-earth-data
description: Integrar, revisar y validar datos NASA de observación de la Tierra con procedencia verificable. Usar al trabajar con NASA POWER, GPM IMERG, AppEEARS, Earthdata, CMR, productos raster o series temporales NASA; al añadir conectores, parámetros, caché o metadatos; y al comprobar que una respuesta oficial respalda un resultado mostrado por Los Causas Espaciales.
---

# NASA Earth Data

Aplicar un flujo de evidencia desde el producto oficial hasta el resultado de la aplicación. No tratar una respuesta HTTP exitosa como validación científica suficiente.

## Flujo obligatorio

1. Definir variable, uso decisional, cobertura espacial, período, resolución y latencia aceptable.
2. Leer `references/official-sources.md` y confirmar producto, versión, proveedor, documentación y condiciones de acceso.
3. Registrar el parámetro oficial, unidad, temporalidad, resolución, time standard, valores faltantes y banderas de calidad.
4. Construir la solicitud mínima. Respetar límites, usar timeout, reintentos acotados, caché y un identificador de usuario cuando la API lo requiera.
5. Conservar la respuesta cruda o su caché inmutable antes de transformar datos.
6. Validar estructura, parámetros, fechas, coordenadas, unidades, completitud, sentinelas, finitud y consistencia temporal.
7. Transformar con funciones puras; registrar agregaciones, conversiones, filtros y exclusiones.
8. Propagar procedencia y limitaciones hasta API, interfaz y exportación.
9. Contrastar al menos una consulta representativa con la documentación o interfaz oficial antes de declarar integración operativa.

## Contrato mínimo de procedencia

Conservar: proveedor, dataset/producto, versión, endpoint o DOI, parámetros/bandas, coordenadas solicitadas, celda devuelta cuando esté disponible, CRS, resolución, período, estándar temporal, unidades, fecha UTC de descarga, URL/canonical id, clave de caché y transformaciones aplicadas.

Clasificar cada valor:

- `REAL_DATA`: observación o estimación oficial recuperada y validada.
- `CACHED_DATA`: copia íntegra de una respuesta previamente validada, con fecha original.
- `MODEL_ESTIMATE`: resultado derivado por una fórmula o modelo declarado.
- `USER_ASSUMPTION`: entrada explícita del usuario.
- `ILLUSTRATIVE_DEMO`: valor sintético visible como demostración.
- `DATA_UNAVAILABLE`: dato necesario no recuperado o no verificado.

Nunca convertir un faltante en cero, mezclar versiones silenciosamente ni presentar un valor derivado como observación NASA.

## Validación por producto

### NASA POWER

- Confirmar comunidad, parámetro, rango temporal, formato y `time-standard`.
- Respetar el máximo documentado de parámetros y evitar repetir solicitudes para la misma celda.
- Interpretar `-999` u otro sentinela documentado como faltante.
- Verificar las unidades devueltas; no inferirlas únicamente por el nombre del parámetro.
- Ejecutar `python scripts/validate_power_response.py respuesta.json --parameters ALLSKY_SFC_SW_DWN,T2M` sobre una respuesta cruda representativa.

### GPM IMERG y AppEEARS

- Verificar short name, colección/versión, DOI, resolución, calidad y autenticación Earthdata.
- Aplicar las QA flags del producto antes de resumir valores.
- Registrar reproyección, remuestreo, escala, offset y estrategia de agregación.
- Mantener `DATA_UNAVAILABLE` mientras credenciales, producto o validación no estén completos.

## Criterios de aceptación

- Fuente primaria oficial accesible y citada.
- Respuesta cruda verificable y esquema validado.
- Unidades, fechas, CRS/resolución y faltantes explícitos.
- Procedencia visible en backend, frontend y exportación.
- Caché no altera ni rejuvenece artificialmente la fecha de descarga.
- Prueba automatizada para respuesta válida, faltantes y error del proveedor.
- Consulta real de integración registrada sin secretos.
- Limitaciones científicas mostradas junto al resultado.

Bloquear la finalización si falta cualquiera de los cuatro primeros criterios.

