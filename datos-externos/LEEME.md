# Datos externos que trae Christian

Aquí se dejan los archivos descargados a mano de fuentes oficiales que no tienen un servicio consultable. Los archivos de datos no se suben a git (ver `.gitignore`); este LEEME sí.

## senamhi/

Series diarias de 2 o 3 estaciones cercanas a Moquegua e Ilo.

1. Entrar a https://www.senamhi.gob.pe/?&p=descarga-datos-hidrometeorologicos y registrarse (el SENAMHI lo pide para descargar).
2. En el mapa, elegir las 2 o 3 estaciones más cercanas a Moquegua e Ilo que tengan **precipitación diaria** y la serie más larga.
3. Descargar cada una en el formato que ofrezca el portal (CSV, TXT o Excel) y dejar los archivos aquí, sin renombrarlos.
4. Copiar en `senamhi/fuente.txt` la URL de descarga, la fecha de hoy y cualquier condición de uso que muestre el portal.

Si el portal histórico solo llega a 2013–2014, en https://www.senamhi.gob.pe/?&p=estaciones están los datos recientes de la misma red.

## ingemmet/

Solo si el visor GEOCATMIN ofrece descarga de la capa **Peligros geológicos** (inventario de eventos):

1. Entrar a https://geocatmin.ingemmet.gob.pe, activar la capa de peligros geológicos y usar su opción de descarga por área (Moquegua y Tacna).
2. Dejar el archivo (shapefile en ZIP o KMZ) aquí y anotar en `ingemmet/fuente.txt` la URL y la fecha.

Si el visor no ofrece descarga, no hace falta: los mapas de peligro volcánico de INGEMMET se integran por su servicio en línea.
