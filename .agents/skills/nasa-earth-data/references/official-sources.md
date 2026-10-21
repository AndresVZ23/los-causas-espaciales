# Fuentes oficiales NASA

Consultar estas fuentes antes de añadir o modificar una integración. Registrar la fecha de consulta en la documentación del cambio.

## NASA POWER

- Documentación general: https://power.larc.nasa.gov/docs/
- Daily API: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- API Overview y códigos de error: https://power.larc.nasa.gov/docs/services/api/
- Diccionario de parámetros: https://power.larc.nasa.gov/parameters/
- Procesamiento temporal: https://power.larc.nasa.gov/docs/methodology/data/processing/

Controles clave: máximo de 20 parámetros por solicitud puntual, `time-standard` explícito, respuesta 429 posible, resolución distinta entre meteorología y radiación, y reemplazo posterior de datos cercanos a tiempo real por productos de calidad climática.

## Earthdata, GPM y AppEEARS

- NASA Earthdata: https://www.earthdata.nasa.gov/
- GPM IMERG: https://gpm.nasa.gov/data/imerg
- AppEEARS: https://appeears.earthdatacloud.nasa.gov/
- CMR Search API: https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
- Política de uso y cita: https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy
- Recomendaciones NASA de calidad: https://www.earthdata.nasa.gov/s3fs-public/imported/ESDS-RFC-034.pdf

No fijar una versión de IMERG, MODIS u otro producto solo por memoria. Resolverla desde CMR o la página oficial y conservar short name, versión y DOI.

