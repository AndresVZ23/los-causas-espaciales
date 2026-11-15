"""Construye las misiones del «modo jugador» y las guarda en backend/data/missions/missions.json.

Cada misión es un lugar del mundo con su análisis climático real, pedido a la API local en el momento de construir
(NASA POWER desde 2001, con ERA5 como segunda fuente de la temperatura). Los años atípicos de lluvia extrema se guardan
con el valor del mismo año en los productos de contraste que devuelva la API: en el archivo actual las 26 marcas traen
uno solo, GPM IMERG, y ninguna trae CHIRPS (revisado el 13-nov-2026). El texto de «contexto» lo escribe el equipo y no
sale de la plataforma; puede llevar años y sus fuentes externas van en CONTEXT_SOURCES. Si el análisis de un lugar no
llega, la misión no se crea y el guion lo dice.

    python3 scripts/missions/build_missions.py              # todas
    python3 scripts/missions/build_missions.py nazca taal   # algunas
    python3 scripts/missions/build_missions.py --textos     # sin red: reaplica los textos del guion al archivo que ya existe

Construir requiere la API en http://localhost:8000 (variable MISSIONS_API para otra dirección). Un sitio por consulta,
para que la familia de Benjamini–Hochberg sea siempre la de las variables de ese sitio y no dependa de con quién se agrupe.

«built_at» es la última vez que este guion escribió el archivo con análisis nuevos, no la fecha de cada análisis: al
construir solo algunos lugares, los demás se conservan tal cual y su fecha sigue en «analysis.generated_at». El modo
--textos no consulta nada y por eso no toca «built_at» ni «analysis».
"""

import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = os.environ.get("MISSIONS_API", "http://localhost:8000") + "/api/v1"
OUT = ROOT / "backend" / "data" / "missions" / "missions.json"
START = "2001-01-01"
END = (date.today() - timedelta(days=2)).isoformat()
WORKERS = 3

# (id, continente, país, lugar, lat, lon, contexto cualitativo, lo que la plataforma no mide aquí)
PLACES = [
    ("nazca", "Sudamérica", "Perú", "Líneas de Nazca", -14.74, -75.13,
     "Geoglifos del desierto costero, Patrimonio Mundial de la UNESCO. Las lluvias, raras en este desierto, y la erosión que provocan están entre sus principales amenazas físicas, junto con la actividad humana.",
     "El estado de los geoglifos ni la erosión del suelo."),
    ("poopo", "Sudamérica", "Bolivia", "Lago Poopó", -18.78, -67.08,
     "Fue el segundo lago más grande de Bolivia y quedó prácticamente seco a fines de 2015, entre sequía, El Niño y el uso del agua de los ríos que lo alimentan.",
     "La superficie del lago ni el caudal de sus ríos."),
    ("manaos", "Sudamérica", "Brasil", "Amazonía, Manaos", -3.12, -60.02,
     "Puerta de la Amazonía. En 2023 el río Negro bajó en Manaos a su nivel más bajo registrado.",
     "El nivel del río ni la pérdida de bosque."),
    ("santiago", "Sudamérica", "Chile", "Chile central, Santiago", -33.45, -70.67,
     "Chile central vive desde 2010 una sequía prolongada que los científicos chilenos llaman «megasequía».",
     "La nieve de la cordillera ni el agua de los embalses."),
    ("perito-moreno", "Sudamérica", "Argentina", "Glaciar Perito Moreno", -50.47, -73.03,
     "Uno de los glaciares más visitados de la Patagonia; los campos de hielo patagónicos, en conjunto, pierden hielo.",
     "El espesor ni el avance o retroceso del glaciar."),
    ("guayaquil", "Sudamérica", "Ecuador", "Guayaquil", -2.19, -79.89,
     "El puerto más grande de Ecuador, golpeado por inundaciones en los años de El Niño fuerte, como 1997-1998.",
     "El nivel del río Guayas ni las mareas."),
    ("mocoa", "Sudamérica", "Colombia", "Mocoa", 1.15, -76.65,
     "En 2017 una avenida torrencial de lodo y piedras arrasó barrios enteros tras una noche de lluvias intensas.",
     "La inestabilidad de las laderas ni el caudal de los ríos."),
    ("porto-alegre", "Sudamérica", "Brasil", "Porto Alegre", -30.03, -51.23,
     "En 2024 Rio Grande do Sul sufrió las peores inundaciones de su historia; buena parte de Porto Alegre quedó bajo el agua.",
     "El nivel del lago Guaíba ni de los ríos."),
    ("lago-mead", "Norteamérica", "Estados Unidos", "Lago Mead, río Colorado", 36.15, -114.45,
     "El mayor embalse de Estados Unidos. En 2022 llegó a su nivel más bajo desde que se llenó, tras años de sequía en el río Colorado.",
     "El nivel del embalse ni el caudal del río."),
    ("cdmx", "Norteamérica", "México", "Ciudad de México", 19.43, -99.13,
     "Una metrópoli de más de veinte millones de personas construida sobre un antiguo lago; enfrenta escasez de agua y hundimiento del suelo.",
     "El agua subterránea ni el hundimiento."),
    ("yellowknife", "Norteamérica", "Canadá", "Yellowknife", 62.45, -114.37,
     "En agosto de 2023 toda la ciudad fue evacuada por incendios forestales.",
     "Los incendios ni el área quemada."),
    ("ilulissat", "Norteamérica", "Groenlandia (Dinamarca)", "Fiordo helado de Ilulissat", 69.22, -51.10,
     "Patrimonio Mundial donde desemboca uno de los glaciares más rápidos de Groenlandia.",
     "El hielo del glaciar ni el nivel del mar."),
    ("choluteca", "Norteamérica", "Honduras", "Corredor Seco, Choluteca", 13.30, -87.19,
     "En el Corredor Seco centroamericano, donde las sequías repetidas afectan las cosechas de maíz y frijol.",
     "Las cosechas ni la humedad del suelo."),
    ("nueva-orleans", "Norteamérica", "Estados Unidos", "Nueva Orleans", 29.95, -90.07,
     "En 2005 el huracán Katrina rompió los diques y la mayor parte de la ciudad se inundó.",
     "Los huracanes ni la marea de tormenta."),
    ("san-juan", "Norteamérica", "Puerto Rico (EE. UU.)", "San Juan", 18.47, -66.11,
     "En 2017 el huracán María dejó a toda la isla sin electricidad, en muchos lugares durante meses.",
     "Los huracanes ni la marea de tormenta."),
    ("puerto-principe", "Norteamérica", "Haití", "Puerto Príncipe", 18.54, -72.34,
     "Una de las ciudades más expuestas del Caribe: el terremoto de 2010 y huracanes frecuentes.",
     "Los terremotos ni los huracanes."),
    ("sevilla", "Europa", "España", "Andalucía, Sevilla", 37.39, -5.98,
     "Andalucía atravesó entre 2022 y 2024 una sequía severa, con embalses muy bajos.",
     "El agua de los embalses."),
    ("venecia", "Europa", "Italia", "Venecia", 45.44, 12.33,
     "Una ciudad sobre una laguna; desde 2020 la protegen compuertas móviles (MOSE) frente al «agua alta».",
     "El nivel del mar ni las mareas."),
    ("aletsch", "Europa", "Suiza", "Glaciar Aletsch", 46.44, 8.08,
     "El glaciar más grande de los Alpes; los glaciares suizos pierden hielo año tras año.",
     "El hielo del glaciar."),
    ("svalbard", "Europa", "Noruega", "Svalbard", 78.22, 15.65,
     "Archipiélago del Ártico, una de las regiones del planeta que más rápido se calientan.",
     "El hielo marino ni el permafrost."),
    ("rotterdam", "Europa", "Países Bajos", "Rotterdam", 51.92, 4.48,
     "Buena parte del país está bajo el nivel del mar; la protegen diques y barreras móviles como Maeslant.",
     "El nivel del mar."),
    ("atenas", "Europa", "Grecia", "Atenas", 37.98, 23.73,
     "Grecia vive incendios forestales cada verano; en 2023 hubo evacuaciones masivas en Rodas y en los alrededores de Atenas.",
     "Los incendios ni el área quemada."),
    ("ahr", "Europa", "Alemania", "Valle del Ahr", 50.54, 7.11,
     "En julio de 2021 lluvias extremas desbordaron el río Ahr en una de las peores inundaciones de Alemania en décadas.",
     "El caudal del río."),
    ("valencia", "Europa", "España", "Valencia", 39.47, -0.38,
     "En octubre de 2024 una DANA (gota fría) descargó lluvias torrenciales y causó inundaciones devastadoras al sur de la ciudad.",
     "El caudal de los barrancos."),
    ("delhi", "Asia", "India", "Nueva Delhi", 28.61, 77.21,
     "Una de las ciudades más pobladas del mundo, con olas de calor y un aire muy contaminado.",
     "La contaminación del aire."),
    ("taal", "Asia", "Filipinas", "Volcán Taal", 14.00, 120.99,
     "Volcán activo dentro de un lago; su erupción de enero de 2020 obligó a evacuar a miles de personas.",
     "La actividad del volcán."),
    ("aral", "Asia", "Kazajistán", "Mar de Aral", 46.00, 60.50,
     "Fue uno de los lagos más grandes del mundo; se redujo drásticamente desde los años sesenta, cuando se desviaron sus ríos para regar algodón.",
     "La superficie del agua ni el polvo salino."),
    ("daca", "Asia", "Bangladés", "Daca", 23.81, 90.41,
     "Capital de un país en el delta más grande del mundo, expuesto a inundaciones y ciclones.",
     "Las inundaciones de los ríos ni el nivel del mar."),
    ("jacobabad", "Asia", "Pakistán", "Jacobabad", 28.28, 68.44,
     "Una de las ciudades más calurosas del planeta. En 2022 Pakistán sufrió inundaciones históricas.",
     "La humedad combinada con el calor ni las inundaciones."),
    ("sendai", "Asia", "Japón", "Sendai", 38.27, 140.87,
     "En 2011 un terremoto y un tsunami golpearon esta costa y provocaron el accidente nuclear de Fukushima.",
     "Los terremotos ni los tsunamis."),
    ("yakarta", "Asia", "Indonesia", "Yakarta", -6.21, 106.85,
     "Una de las ciudades que más rápido se hunden en el mundo; Indonesia construye una nueva capital.",
     "El hundimiento del suelo ni el nivel del mar."),
    ("zhengzhou", "Asia", "China", "Zhengzhou", 34.75, 113.63,
     "En julio de 2021 lluvias récord inundaron la ciudad, incluido su metro.",
     "El caudal de los ríos."),
    ("turkana", "África", "Kenia", "Turkana, Lodwar", 3.12, 35.60,
     "En el Cuerno de África, que entre 2020 y 2023 vivió varias temporadas de lluvia fallidas seguidas.",
     "Las cosechas ni el ganado."),
    ("alejandria", "África", "Egipto", "Delta del Nilo, Alejandría", 31.20, 29.92,
     "Una costa baja en el delta del Nilo, expuesta a la subida del mar y a la entrada de agua salada.",
     "El nivel del mar ni la salinidad."),
    ("mbandaka", "África", "República Democrática del Congo", "Selva del Congo, Mbandaka", 0.05, 18.26,
     "En el corazón de la selva del Congo, la segunda gran selva tropical del planeta.",
     "La pérdida de bosque."),
    ("ambovombe", "África", "Madagascar", "Sur de Madagascar, Ambovombe", -25.17, 46.08,
     "El sur de Madagascar sufrió en 2021 una sequía que provocó una grave crisis de hambre.",
     "Las cosechas ni la humedad del suelo."),
    ("niamey", "África", "Níger", "Sahel, Niamey", 13.51, 2.11,
     "En el Sahel, la franja entre el Sahara y la sabana, donde la lluvia cambia mucho de un año a otro.",
     "El avance del desierto ni las inundaciones del río Níger."),
    ("derna", "África", "Libia", "Derna", 32.77, 22.64,
     "En septiembre de 2023 la tormenta Daniel rompió dos presas y la riada arrasó parte de la ciudad.",
     "El estado de las presas."),
    ("beira", "África", "Mozambique", "Beira", -19.84, 34.84,
     "En 2019 el ciclón Idai golpeó la ciudad y provocó grandes inundaciones en Mozambique.",
     "Los ciclones ni la marea de tormenta."),
    ("mogadiscio", "África", "Somalia", "Mogadiscio", 2.05, 45.32,
     "Somalia sufrió entre 2020 y 2023 la peor sequía en décadas del Cuerno de África.",
     "Las cosechas ni el agua de los pozos."),
    ("cairns", "Oceanía", "Australia", "Gran Barrera de Coral, Cairns", -16.92, 145.77,
     "Puerta de la Gran Barrera de Coral, que ha sufrido varios blanqueamientos masivos de coral en los últimos años.",
     "La temperatura del mar ni el estado del coral."),
    ("funafuti", "Oceanía", "Tuvalu", "Funafuti", -8.52, 179.20,
     "Capital de Tuvalu, un atolón de pocos metros de altura frente a la subida del nivel del mar.",
     "El nivel del mar."),
    ("lismore", "Oceanía", "Australia", "Lismore", -28.81, 153.28,
     "En 2022 la ciudad sufrió la mayor inundación de su historia registrada.",
     "El caudal del río Wilsons."),
    ("lahaina", "Oceanía", "Estados Unidos (Hawái)", "Lahaina, Maui", 20.88, -156.68,
     "En agosto de 2023 un incendio impulsado por el viento destruyó casi todo el pueblo histórico de Lahaina.",
     "Los incendios ni la sequedad de la vegetación."),
    ("thwaites", "Antártida", "Antártida", "Glaciar Thwaites", -75.50, -106.75,
     "Llamado «el glaciar del fin del mundo»: si se deshace, el nivel del mar subiría en todo el planeta. Los científicos lo vigilan de cerca.",
     "El hielo del glaciar ni el nivel del mar."),
    ("rey-jorge", "Antártida", "Antártida (estación peruana)", "Isla Rey Jorge, estación Machu Picchu", -62.09, -58.47,
     "Junto a la estación científica del Perú en la Antártida, frente a la península Antártica, una de las zonas que más se han calentado en el último medio siglo.",
     "El hielo marino ni los glaciares."),
    ("chosica", "Sudamérica", "Perú", "Chosica, Lurigancho", -11.94, -76.70,
     "En la temporada de lluvias de la sierra, los huaicos suelen bajar por las quebradas que cruzan Chosica.",
     "La inestabilidad de las laderas ni el caudal de las quebradas."),
    ("piura", "Sudamérica", "Perú", "Piura", -5.19, -80.63,
     "En 2017 el Niño Costero desbordó el río Piura e inundó buena parte de la ciudad.",
     "El caudal del río ni la temperatura del mar."),
    ("lima", "Sudamérica", "Perú", "Lima Metropolitana", -12.05, -77.04,
     "En septiembre de 2025 el SENAMHI alertó niveles insalubres de partículas finas en el aire de varios distritos de Lima; más de la mitad de esas emisiones viene de los vehículos.",
     "El aire que se respira en la calle (PM2.5 de las estaciones del SENAMHI): aquí solo se ven los aerosoles de toda la columna de aire sobre una celda grande."),
    ("huascaran", "Sudamérica", "Perú", "Huascarán y Yungay", -9.12, -77.60,
     "En 1970 un terremoto desprendió hielo y roca del Huascarán y el aluvión sepultó la ciudad de Yungay.",
     "El hielo del nevado ni las lagunas glaciares."),
    ("villarrica", "Sudamérica", "Chile", "Volcán Villarrica", -39.42, -71.93,
     "Uno de los volcanes más activos de Chile, con un lago de lava en su cráter.",
     "La actividad del volcán."),
    ("popocatepetl", "Norteamérica", "México", "Volcán Popocatépetl", 19.02, -98.62,
     "Volcán activo muy cerca de Ciudad de México; sus emisiones de ceniza son vigiladas a diario.",
     "La actividad del volcán ni la ceniza."),
    ("phoenix", "Norteamérica", "Estados Unidos", "Phoenix", 33.45, -112.07,
     "Una de las ciudades más calurosas de Estados Unidos; en 2023 sufrió una ola de calor récord.",
     "El calor de las calles ni la sombra urbana."),
    ("etna", "Europa", "Italia", "Volcán Etna", 37.75, 14.99,
     "El volcán activo más alto de Europa; entra en erupción con frecuencia.",
     "La actividad del volcán."),
    ("chamonix", "Europa", "Francia", "Chamonix, Mont Blanc", 45.92, 6.87,
     "Valle al pie del Mont Blanc, famoso por el montañismo y vigilado por el riesgo de avalanchas.",
     "La nieve acumulada ni el riesgo de avalanchas."),
    ("merapi", "Asia", "Indonesia", "Volcán Merapi", -7.54, 110.45,
     "Uno de los volcanes más activos de Indonesia; en 2010 una gran erupción obligó a evacuar a cientos de miles de personas.",
     "La actividad del volcán."),
    ("kilauea", "Oceanía", "Estados Unidos (Hawái)", "Volcán Kīlauea", 19.41, -155.28,
     "Uno de los volcanes más activos del planeta; en 2018 la lava destruyó cientos de casas.",
     "La actividad del volcán ni la lava."),

]

# Lugares que se recorren como paisaje (lago, glaciar, desierto): la cámara no baja a nivel de calle.
LANDSCAPES = {"nazca", "poopo", "perito-moreno", "lago-mead", "ilulissat", "aletsch", "aral", "turkana", "ambovombe", "thwaites", "rey-jorge",
              "huascaran", "villarrica", "popocatepetl", "etna", "chamonix", "merapi", "kilauea"}
# Peligro principal del juego en cada lugar (evento simulado inspirado en su riesgo real); el resto se elige por los datos.
HAZARDS = {
    # Sudamérica
    "nazca": "huaico", "poopo": "calor", "manaos": "inundacion", "santiago": "calor", "perito-moreno": "avalancha", "guayaquil": "inundacion",
    "mocoa": "huaico", "porto-alegre": "inundacion", "chosica": "huaico", "piura": "inundacion", "lima": "aire", "huascaran": "avalancha", "villarrica": "erupcion",
    # Norteamérica
    "lago-mead": "calor", "cdmx": "inundacion", "yellowknife": "calor", "ilulissat": None, "choluteca": "calor", "nueva-orleans": "inundacion",
    "san-juan": "inundacion", "puerto-principe": "huaico", "popocatepetl": "erupcion", "phoenix": "calor",
    # Europa
    "sevilla": "calor", "venecia": "inundacion", "aletsch": "avalancha", "svalbard": "avalancha", "rotterdam": "inundacion", "atenas": "calor",
    "ahr": "inundacion", "valencia": "inundacion", "etna": "erupcion", "chamonix": "avalancha",
    # Asia
    "delhi": "calor", "taal": "erupcion", "aral": "calor", "daca": "inundacion", "jacobabad": "calor", "sendai": "inundacion", "yakarta": "inundacion",
    "zhengzhou": "inundacion", "merapi": "erupcion",
    # África
    "turkana": "calor", "alejandria": "inundacion", "mbandaka": "inundacion", "ambovombe": "calor", "niamey": "inundacion", "derna": "inundacion",
    "beira": "inundacion", "mogadiscio": "calor",
    # Oceanía y Antártida
    "cairns": "inundacion", "funafuti": "inundacion", "lismore": "inundacion", "lahaina": "calor", "kilauea": "erupcion", "thwaites": None, "rey-jorge": None,
}

# Fuentes externas del texto de contexto de cada lugar: {id: [{"title": ..., "url": ...}]}. Solo fuentes verificadas
# (la página dice lo que dice el contexto); un lugar sin entrada queda con la lista vacía y el juego lo trata como
# texto del equipo sin fuente enlazada. Después de editarlo: python3 scripts/missions/build_missions.py --textos
CONTEXT_SOURCES: dict[str, list[dict[str, str]]] = {
    "lima": [
        {"title": "Alerta: Lima registra niveles insalubres de contaminación en el aire (Actualidad Ambiental, 22-sep-2025)", "url": "https://www.actualidadambiental.pe/lima-registra-niveles-insalubres-en-el-aire/"},
        {"title": "SENAMHI alerta que aire en Lima alcanzó niveles insalubres (América Noticias, 19-sep-2025)", "url": "https://www.americatv.com.pe/noticias/actualidad/senamhi-alerta-que-aire-lima-alcanzo-niveles-insalubres-n511103"},
    ],
    "nazca": [
        {"title": "Climatic & Anthropogenic Hazards to the Nasca World Heritage: Application of Remote Sensing, AI, and Flood Modelling (arXiv 2405.11814, IGARSS 2024)", "url": "https://arxiv.org/html/2405.11814v1"},
        {"title": "Rare heavy rains damage Peru's Nazca lines (NBC News)", "url": "https://www.nbcnews.com/news/amp/wbna28739302"},
    ],
    "poopo": [
        {"title": "Lake Poopó: why Bolivia's second largest lake disappeared – and how to bring it back (Smart Water Magazine, republicación de The Conversation)", "url": "https://smartwatermagazine.com/blogs/juan-torres-batllo/lake-poopo-why-bolivias-second-largest-lake-disappeared-and-how-bring-it"},
        {"title": "Lake Poopó, Bolivia (NASA/JPL, PIA21546)", "url": "https://www.jpl.nasa.gov/images/pia21546-lake-poopo-bolivia/"},
    ],
    "manaos": [
        {"title": "Drought on the Rio Negro (NASA Earth Observatory)", "url": "https://science.nasa.gov/earth/earth-observatory/drought-on-the-rio-negro-151961"},
        {"title": "Drought parches central Amazon in October 2023 (NOAA Climate.gov)", "url": "https://content-drupal.climate.gov/news-features/event-tracker/drought-parches-central-amazon-october-2023"},
    ],
    "santiago": [
        {"title": "Informe a la Nación: La megasequía en Chile | Centro de Ciencia del Clima y la Resiliencia - CR2", "url": "https://www.cr2.cl/megasequia/"},
    ],
    "perito-moreno": [
        {"title": "Melting Beauty: The Patagonian Icefields (NASA Sea Level Change)", "url": "https://sealevel.nasa.gov/news/133/melting-beauty-the-patagonian-icefields"},
        {"title": "Día Nacional de los Glaciares: cuáles son los más importantes de la Argentina (La Nación)", "url": "https://www.lanacion.com.ar/sociedad/dia-nacional-de-los-glaciares-cuales-son-los-mas-importantes-de-la-argentina-nid15022025/"},
    ],
    "guayaquil": [
        {"title": "GUAYAQUIL Port - Ports Directory (MarineLink)", "url": "https://ports.marinelink.com/ports/port/guayaquil"},
        {"title": "Climate Change, El Niño, and the State of Emergency in Ecuador (Pacific Standard)", "url": "https://psmag.com/?p=24298"},
    ],
    "mocoa": [
        {"title": "The Mocoa Event on March 31 (2017) (repositorio TU Delft)", "url": "https://repository.tudelft.nl/record/uuid:cb3c34d3-2c10-4382-9989-d716f48bd4d6"},
        {"title": "Sube a 320 el número de muertos por avalancha de Mocoa (El Heraldo, Colombia)", "url": "https://www.elheraldo.co/colombia/2017/04/13/sube-a-320-el-numero-de-muertos-por-avalancha-de-mocoa-347907/"},
    ],
    "porto-alegre": [
        {"title": "Climate change made devastating Brazil floods twice as likely, scientists say (Reuters, en The Star)", "url": "https://thestar.com.my/news/world/2024/06/04/climate-change-made-devastating-brazil-floods-twice-as-likely-scientists-say"},
        {"title": "Floods Engulf Porto Alegre (NASA Earth Observatory)", "url": "https://science.nasa.gov/earth/earth-observatory/floods-engulf-porto-alegre-152795/"},
    ],
    "lago-mead": [
        {"title": "Lake Mead Keeps Dropping (NASA Earth Observatory, 22 de julio de 2022)", "url": "https://science.nasa.gov/earth/earth-observatory/lake-mead-keeps-dropping-150111"},
    ],
    "cdmx": [
        {"title": "Mexico City is sinking so quickly, it can be seen from space (AP, en WTOP)", "url": "https://wtop.com/funny-weird-news/2026/05/mexico-city-is-sinking-so-quickly-it-can-be-seen-from-space/"},
        {"title": "NASA-ISRO satellite maps Mexico City's rapid sinking as water crisis deepens (Smart Water Magazine)", "url": "https://smartwatermagazine.com/news/smart-water-magazine/nasa-isro-satellite-maps-mexico-citys-rapid-sinking-water-crisis-deepens"},
    ],
    "yellowknife": [
        {"title": "City of Yellowknife ordered to evacuate due to nearby N.W.T. wildfires (Global News, 16 de agosto de 2023)", "url": "https://globalnews.ca/news/9901527/yellowknife-evacuation-order-wildfires"},
        {"title": "Wildfires force entire capital city of Canada's Northwest Territories to evacuate (CBS News, 17 de agosto de 2023)", "url": "https://www.cbsnews.com/miami/news/wildfires-force-entire-capital-city-of-canadas-northwest-territories-to-evacuate/"},
    ],
    "ilulissat": [
        {"title": "Ilulissat Icefjord (IUCN World Heritage Outlook)", "url": "https://worldheritageoutlook.iucn.org/node/1134"},
        {"title": "Ilulissat Icefjord - A world heritage site (GEUS, Servicio Geológico de Dinamarca y Groenlandia)", "url": "https://eng.geus.dk/products-services-facilities/publications/popular-geology/books/ilulissat-icefjord"},
    ],
    "choluteca": [
        {"title": "Orocuina se declara en emergencia por sequía (El Heraldo, Honduras, 31 de julio de 2018)", "url": "https://www.elheraldo.hn/honduras/orocuina-se-declara-en-emergencia-por-sequia-KXEH1202954"},
        {"title": "Honduras, segunda afectada en Centroamérica por sequía en el corredor seco (El Heraldo, Honduras, 2 de junio de 2023)", "url": "https://www.elheraldo.hn/honduras/honduras-segunda-afectada-centroamerica-por-sequia-corredor-seco-crisis-alimento-DA13750704"},
    ],
    "nueva-orleans": [
        {"title": "Hurricane Katrina - August 2005 (National Weather Service, NOAA)", "url": "https://weather.gov/mob/katrina"},
    ],
    "san-juan": [
        {"title": "Hurricane Maria leaves entire island of Puerto Rico without power - ABC13 Houston", "url": "https://abc13.com/post/maria-leaves-entire-island-of-puerto-rico-without-power/2435282/"},
        {"title": "Puerto Rico officials say all of island now has power again - ABC13 Houston", "url": "https://abc13.com/post/puerto-rico-officials-say-all-of-island-now-has-power-again/3965934/"},
    ],
    "puerto-principe": [
        {"title": "Haiti | World Bank Group", "url": "https://www.worldbank.org/en/country/haiti/overview"},
        {"title": "On Shaky Ground (NASA Earthdata)", "url": "https://www.earthdata.nasa.gov/news/feature-articles/shaky-ground"},
    ],
    "sevilla": [
        {"title": "La sequía pone a prueba el modelo económico de Andalucía (Público, 03/02/2024)", "url": "https://www.publico.es/politica/sequia-pone-prueba-modelo-economico-andalucia.html"},
        {"title": "Sequía en Andalucía: haciendo frente a una crisis hídrica en escalada (iAgua, 06/02/2024)", "url": "https://www.iagua.es/noticias/redaccion-iagua/sequia-andalucia-haciendo-frente-crisis-hidrica-escalada"},
    ],
    "venecia": [
        {"title": "Venice, for the first time MoSE is raised against high water and succeeds in blocking the tide (Campaign for a Living Venice, 05/10/2020)", "url": "https://campaignforalivingvenice.org/2020/10/05/venice-for-the-first-time-mose-is-raised-against-high-water-and-succeeds-in-blocking-the-tide/"},
    ],
    "aletsch": [
        {"title": "Record-low snow accumulation on biggest Alpine glacier: study (Phys.org/AFP, 16/10/2020)", "url": "https://www.phys.org/news/2020-10-record-low-accumulation-biggest-alpine-glacier.html"},
        {"title": "And Swiss glaciers continue to melt (Swiss Academy of Sciences, SCNAT, 01/10/2025)", "url": "https://scnat.ch/en/id/wLLYv"},
    ],
    "svalbard": [
        {"title": "Norwegian Arctic archipelago feels the heat of climate change (AFP vía The Local, 22/06/2022)", "url": "https://www.thelocal.no/20220622/norwegian-arctic-archipelago-feeling-the-heat-of-climate-change"},
        {"title": "Svalbard: The race to save the fastest-warming place on Earth (RNZ, 27/10/2022)", "url": "https://www.rnz.co.nz/news/world/477514/svalbard-the-race-to-save-the-fastest-warming-place-on-earth"},
    ],
    "rotterdam": [
        {"title": "Maeslant Barrier (Rijkswaterstaat)", "url": "https://www.rijkswaterstaat.nl/en/projects/iconic-structures/maeslant-barrier"},
        {"title": "Resilient to sea level rise: more sand, more safety (Rijkswaterstaat)", "url": "https://www.rijkswaterstaat.nl/en/news/archive/2025/12/resilient-to-sea-level-rise-more-sand-more-safety"},
    ],
    "atenas": [
        {"title": "Greece conducts country's largest wildfire evacuation as island of Rhodes burns (PBS News/AP, 23/07/2023)", "url": "https://www.pbs.org/newshour/world/greece-conducts-countrys-largest-wildfire-evacuation-as-island-of-rhodes-burns"},
        {"title": "Photos: Greece wildfires force thousands to flee seaside resorts (Al Jazeera, 18/07/2023)", "url": "https://www.aljazeera.com/gallery/2023/7/18/photos-greece-wildfires-force-thousands-to-flee-seaside-resorts"},
    ],
    "ahr": [
        {"title": "Heavy rainfall which led to severe flooding in Western Europe made more likely by climate change (World Weather Attribution)", "url": "https://www.worldweatherattribution.org/heavy-rainfall-which-led-to-severe-flooding-in-western-europe-made-more-likely-by-climate-change/"},
    ],
    "valencia": [
        {"title": "Devastating rainfall hits Spain in yet another flood-related disaster (OMM/WMO, 31/10/2024)", "url": "https://wmo.int/media/news/devastating-rainfall-hits-spain-yet-another-flood-related-disaster"},
        {"title": "621 mm de agua en seis horas en Turís: AEMET ha publicado un informe en el que analiza la DANA de octubre (Xataka)", "url": "https://www.xataka.com/ecologia-y-naturaleza/621-mm-agua-seis-horas-turis-aemet-ha-publicado-informe-que-analiza-dana-octubre"},
    ],
    "delhi": [
        {"title": "68% of the world population projected to live in urban areas by 2050, says UN | UN DESA", "url": "https://www.un.org/development/desa/en/news/population/2018-revision-of-world-urbanization-prospects.html"},
        {"title": "India had 13 of 20 most polluted world cities in 2024: Study (Scroll.in, 11/03/2025)", "url": "https://scroll.in/latest/1080178/india-had-13-of-20-most-polluted-cities-in-2024-study"},
    ],
    "taal": [
        {"title": "Sulfur Spews from Taal (NASA Earth Observatory)", "url": "https://science.nasa.gov/earth/earth-observatory/sulfur-spews-from-taal-146142/"},
        {"title": "Taal Volcano remains on Level 4 alert, but what does that mean? (NASA Science)", "url": "https://science.nasa.gov/?p=1068206"},
    ],
    "aral": [
        {"title": "World of Change: Shrinking Aral Sea (NASA Earth Observatory)", "url": "https://science.nasa.gov/earth/earth-observatory/world-of-change/aral-sea"},
    ],
    "daca": [
        {"title": "Ganges River Delta | NASA Jet Propulsion Laboratory (JPL)", "url": "https://www.jpl.nasa.gov/images/ganges-river-delta"},
        {"title": "Earth from Space: Ganges' dazzling delta (ESA)", "url": "https://www.esa.int/Applications/Observing_the_Earth/Earth_from_Space_Ganges_dazzling_delta"},
    ],
    "jacobabad": [
        {"title": "In Jacobabad, One of the Hottest Cities on the Planet, a Heat Wave Is Pushing the Limits of Human Livability (Inside Climate News)", "url": "https://insideclimatenews.org/news/20062022/jacobabad-pakistan-heat-health/"},
        {"title": "Eight million may still be exposed to Pakistan floodwaters: UN (Al Jazeera)", "url": "https://www.aljazeera.com/news/2022/12/7/8-million-still-potentially-exposed-to-pakistan-floodwaters-un"},
    ],
    "sendai": [
        {"title": "On This Day: 2011 Tohoku Earthquake and Tsunami (NOAA NCEI)", "url": "https://www.ncei.noaa.gov/news/day-2011-japan-earthquake-and-tsunami"},
        {"title": "Earthquake and Tsunami near Sendai, Japan (NASA Earth Observatory)", "url": "https://science.nasa.gov/earth/earth-observatory/earthquake-and-tsunami-near-sendai-japan-49621"},
    ],
    "yakarta": [
        {"title": "Why Indonesia is moving its capital from Jakarta to Borneo (PBS News)", "url": "https://www.pbs.org/newshour/world/why-indonesia-is-moving-its-capital-from-jakarta-to-borneo"},
        {"title": "From Jakarta to Nusantara: Land subsidence and other pressing water challenges in a sinking mega city (Space4Water, UNOOSA)", "url": "https://www.space4water.org/news/jakarta-nusantara-land-subsidence-and-other-pressing-water-challenges-sinking-mega-city"},
    ],
    "zhengzhou": [
        {"title": "State of Climate in 2021: Extreme events and major impacts (OMM)", "url": "https://wmo.int/news/media-centre/state-of-climate-2021-extreme-events-and-major-impacts"},
        {"title": "Cover Story: How Historic Rainfall Overwhelmed Zhengzhou (Caixin Global)", "url": "https://www.caixinglobal.com/2021-07-27/cover-story-how-historic-rainfall-overwhelmed-zhengzhou-101745293.html"},
    ],
    "turkana": [
        {"title": "Vulnerable children in the Horn of Africa have been living through insecurity for years (UNICEF Eastern and Southern Africa)", "url": "https://www.unicef.org/esa/stories/crisis-horn-of-africa"},
        {"title": "Meteorological and humanitarian agencies sound alert on East Africa (OMM, 30 de mayo de 2022)", "url": "https://wmo.int/node/15001"},
    ],
    "alejandria": [
        {"title": "Coastal case study: West Nile Delta, Egypt (Climatic Research Unit, University of East Anglia, proyecto CIRCE)", "url": "https://crudata.uea.ac.uk/projects/circe/WestNileDelta.html"},
    ],
    "mbandaka": [
        {"title": "OFAC - Forest Ecosystem (Observatoire des Forêts d'Afrique Centrale, COMIFAC)", "url": "https://www.observatoire-comifac.net/africa/forest_ecosystems?lang=en"},
    ],
    "ambovombe": [
        {"title": "Madagascar edges toward famine, UN food agency appeals for assistance (UN News, 29 de abril de 2021)", "url": "https://news.un.org/en/story/2021/04/1090922"},
    ],
    "niamey": [
        {"title": "Bioclimatic Regions Map (USGS EROS, West Africa: Land Use and Land Cover Dynamics)", "url": "https://www.usgs.gov/centers/eros/science/bioclimatic-regions-map"},
    ],
    "derna": [
        {"title": "Storm Daniel leads to extreme rain and floods in Mediterranean, heavy loss of life in Libya (OMM)", "url": "https://wmo.int/media/news/storm-daniel-leads-extreme-rain-and-floods-mediterranean-heavy-loss-of-life-libya"},
        {"title": "UN launches flash appeal to aid 250,000 Libyans hit by devastating floods (UN News)", "url": "https://news.un.org/en/story/2023/09/1140767"},
    ],
    "beira": [
        {"title": "WHO sending urgent health assistance after Cyclone Idai displaces thousands of people in Southern Africa (OMS África)", "url": "https://www.afro.who.int/news/who-sending-urgent-health-assistance-after-cyclone-idai-displaces-thousands-people-southern"},
        {"title": "Tropical Cyclone Idai affects 1.5 million across Mozambique and Malawi, as UN ramps up response (UN News, 15 de marzo de 2019)", "url": "https://news.un.org/en/node/1034741"},
    ],
    "mogadiscio": [
        {"title": "Meteorological and humanitarian agencies sound alert on East Africa (OMM, 30 de mayo de 2022)", "url": "https://wmo.int/node/15001"},
        {"title": "Somalia in need of humanitarian aid as it faces worst drought in decades (PBS News, 11 de abril de 2023)", "url": "https://www.pbs.org/newshour/show/somalia-in-need-of-humanitarian-aid-as-it-faces-worst-drought-in-decades"},
    ],
    "cairns": [
        {"title": "Aerial Surveys Reveal Mass Coral Bleaching Event Unfolding on Great Barrier Reef (ECO Magazine, comunicado de AIMS y la Reef Authority)", "url": "https://ecomagazine.com/news/coastal/aerial-surveys-reveal-mass-coral-bleaching-event-unfolding-on-great-barrier-reef/"},
        {"title": "Travel Guide to Cairns, Queensland - Tourism Australia", "url": "https://www.australia.com/en/places/cairns.html"},
    ],
    "funafuti": [
        {"title": "Funafuti, Tuvalu - City Scan (City Resilience Program, Banco Mundial, mayo de 2025)", "url": "https://wbcrp.quarto.pub/tuvalu-funafuti/"},
        {"title": "Funafuti Atoll, Tuvalu (NASA Earth Observatory)", "url": "https://science.nasa.gov/earth/earth-observatory/funafuti-atoll-tuvalu-153047"},
    ],
    "lismore": [
        {"title": "Flood history - Lismore City Council", "url": "https://www.lismore.nsw.gov.au/Community/Natural-hazards-and-emergency-information/Flood-information-for-Lismore1/Flood-history"},
        {"title": "New South Wales, 22 February onwards (flood 2022) - Australian Institute for Disaster Resilience", "url": "https://knowledge.aidr.org.au/resources/flood-flooding-new-south-wales-2022/"},
    ],
    "lahaina": [
        {"title": "Wildfire blazes through Maui, killing at least 53 people and destroying historic Hawaiian town - PBS NewsHour / Associated Press (10-ago-2023)", "url": "https://www.pbs.org/newshour/nation/wildfire-blazes-through-hawaii-killing-at-least-36-people-on-maui-and-destroying-historic-town"},
        {"title": "Lahaina, Hawaii Fire Timeline Report - U.S. Fire Administration (FEMA)", "url": "https://www.usfa.fema.gov/blog/lahaina-hawaii-fire-timeline-report/"},
    ],
    "thwaites": [
        {"title": "Grim outlook for Antarctica's Thwaites Glacier - International Thwaites Glacier Collaboration", "url": "https://thwaitesglacier.org/node/834"},
        {"title": "Antarctica's \"Doomsday Glacier\" is set to retreat \"further and faster,\" scientists warn - CBS News", "url": "https://www.cbsnews.com/news/antarcticas-doomsday-glacier-thwaites"},
    ],
    "rey-jorge": [
        {"title": "¿Sabías que Perú tiene otro Machu Picchu en la Antártida? Conoce su ubicación e importancia para el país - Infobae", "url": "https://www.infobae.com/peru/2024/09/03/sabias-que-peru-tiene-otro-machu-picchu-en-la-antartida-conoce-su-ubicacion-e-importancia-para-el-pais/"},
        {"title": "New climate history adds to understanding of recent Antarctic Peninsula warming - British Antarctic Survey (vía EurekAlert!)", "url": "https://www.eurekalert.org/news-releases/481699"},
    ],
    "chosica": [
        {"title": "Ministra del Ambiente inspecciona quebradas en Lurigancho ante lluvias - Caretas (27-feb-2026)", "url": "https://caretas.pe/politica/ministra-del-ambiente-inspecciona-quebradas-en-lurigancho-ante-lluvias/"},
        {"title": "Alerta por huaicos en Chosica: Senamhi advierte posible activación de quebradas por lluvias - La República (12-feb-2025)", "url": "https://larepublica.pe/sociedad/2025/02/12/senamhi-emite-alerta-por-huaicos-en-chosica-posible-activacion-de-quebradas-por-lluvias-al-este-de-lima-949608"},
    ],
    "piura": [
        {"title": "A tres años del desborde del río Piura - Universidad de Piura", "url": "https://www.udep.edu.pe/hoy/2020/03/a-tres-anos-del-desborde-del-rio-piura/"},
        {"title": "Desborde de río Piura llegó hasta a Plaza de Armas y el Amazonas se encuentra en alerta roja - Actualidad Ambiental (SPDA), 27-mar-2017", "url": "https://www.actualidadambiental.pe/desborde-de-rio-piura-llego-hasta-a-plaza-de-armas-y-el-amazonas-se-encuentra-en-alerta-roja/"},
    ],
    "huascaran": [
        {"title": "Geological aspects of the May 31, 1970, Perú earthquake - U.S. Geological Survey", "url": "https://www.usgs.gov/publications/geological-aspects-may-31-1970-peru-earthquake"},
    ],
    "villarrica": [
        {"title": "Chile's Villarrica Sputters - NASA Earth Observatory", "url": "https://science.nasa.gov/earth/earth-observatory/chiles-villarrica-sputters-150898/"},
    ],
    "popocatepetl": [
        {"title": "Another Puff of Ash from Popocatépetl - NASA Earth Observatory (31-ene-2024)", "url": "https://science.nasa.gov/earth/earth-observatory/another-puff-of-ash-from-popocatepetl-152388"},
        {"title": "Popocatépetl hoy: volcán registró 14 exhalaciones este 27 de enero - Infobae México", "url": "https://www.infobae.com/mexico/2026/01/27/popocatepetl-hoy-volcan-registro-14-exhalaciones-este-27-de-enero/"},
    ],
    "phoenix": [
        {"title": "Assessing the U.S. Climate in July 2023 - NOAA National Centers for Environmental Information", "url": "https://www.ncei.noaa.gov/news/national-climate-202307"},
    ],
    "etna": [
        {"title": "ETNA FABRIC - Istituto Nazionale di Geofisica e Vulcanologia (INGV)", "url": "https://www.ingv.it/en/etna"},
        {"title": "Steaming Mount Etna - NASA Earth Observatory (1-oct-2010)", "url": "https://science.nasa.gov/earth/earth-observatory/steaming-mount-etna-46212/"},
    ],
    "chamonix": [
        {"title": "Mont Blanc & Mountaineering - Office de Tourisme de la Vallée de Chamonix-Mont-Blanc", "url": "https://en.chamonix.com/node/273"},
        {"title": "Avalanche risk assessment bulletin - Office de Tourisme de la Vallée de Chamonix-Mont-Blanc (boletín de Météo-France)", "url": "https://en.chamonix.com/bulletin-avalanche"},
    ],
    "merapi": [
        {"title": "Volcano Watch — Thousands saved by accurate eruption forecasts of Mount Merapi, Indonesia - USGS Hawaiian Volcano Observatory (3-feb-2011)", "url": "https://www.usgs.gov/center-news/volcano-watch-thousands-saved-accurate-eruption-forecasts-mount-merapi-indonesia"},
        {"title": "Eruption at Mount Merapi, Indonesia - NASA Earth Observatory (6-nov-2010)", "url": "https://science.nasa.gov/earth/earth-observatory/eruption-at-mount-merapi-indonesia-46837/"},
    ],
    "kilauea": [
        {"title": "Kīlauea - U.S. Geological Survey, Hawaiian Volcano Observatory", "url": "https://www.usgs.gov/volcanoes/kilauea"},
        {"title": "2018 lower East Rift Zone eruption and summit collapse - U.S. Geological Survey", "url": "https://www.usgs.gov/volcanoes/kilauea/science/2018-lower-east-rift-zone-eruption-and-summit-collapse"},
    ],
}

VARIABLES = {"T2M": "temperature", "PRECTOTCORR": "rain", "ALLSKY_SFC_SW_DWN": "sun"}

# Misiones de aire (ADR-050): aerosoles en la columna de aire, AOD a 550 nm de NASA POWER (comunidad RE, fuente CERES
# SYN1deg, que combina satélites con un modelo de transporte de aerosoles: por eso MODEL_ESTIMATE). Medias anuales que
# entrega la propia API (mes «13»), de 2001 al último año completo. Se prueba aparte de las variables de clima, con la
# misma función de la plataforma (Mann–Kendall con Hamed–Rao y pendiente de Sen), familia de una prueba y alfa 0,05.
AIR_PLACES = {"lima"}
POWER_MONTHLY = os.environ.get("POWER_API_BASE", "https://power.larc.nasa.gov/api") + "/temporal/monthly/point"
AIR_NOTE = "Estimación de NASA POWER (CERES SYN1deg): combina satélites y un modelo. No es una medición de estación."


def air_trend(lat: float, lon: float) -> dict:
    """Tendencia de AOD_55 en el punto, con su serie anual, procedencia y fecha de descarga."""
    sys.path.insert(0, str(ROOT))
    from backend.app.schemas.analysis import Observation  # noqa: PLC0415 — solo hace falta en misiones de aire
    from backend.app.statistics.trends import analyze_trend  # noqa: PLC0415

    last_year = date.today().year - 1
    url = f"{POWER_MONTHLY}?parameters=AOD_55&community=RE&longitude={lon}&latitude={lat}&start=2001&end={last_year}&format=JSON"
    with urllib.request.urlopen(url, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    downloaded = datetime.now(timezone.utc).isoformat()
    fill = payload.get("header", {}).get("fill_value", -999.0)
    raw = payload["properties"]["parameter"]["AOD_55"]
    series = []
    for year in range(2001, last_year + 1):
        value = raw.get(f"{year}13")
        series.append({"year": year, "value": None if value is None or value == fill else float(value)})
    valid = [item for item in series if item["value"] is not None]
    result = analyze_trend([Observation(timestamp=date(item["year"], 1, 1), value=item["value"]) for item in valid], already_annual=True)
    sources = ", ".join(payload.get("header", {}).get("sources", [])) or "sin fuente declarada"
    return {
        "label": "Aerosoles en la columna de aire (AOD a 550 nm)", "unit": None,
        "mean": round(sum(item["value"] for item in valid) / len(valid), 4) if valid else None,
        "direction": result.direction, "slope_per_year": result.slope_per_year,
        "confidence_interval": list(result.confidence_interval) if result.confidence_interval else None,
        "p_value_adjusted": result.p_value_modified, "significant": bool(result.significant), "valid_years": result.valid_observations,
        "annual_series": series, "second_source": None,
        "dataset": f"NASA POWER · AOD_55 (fuente {sources})", "provenance": "MODEL_ESTIMATE", "source_url": url, "downloaded_at": downloaded,
        "note": AIR_NOTE,
    }



def method_text(missions: list[dict]) -> str:
    """El campo «method» del archivo. Los productos de contraste se leen de las propias marcas: se nombra lo que hay, no lo que se esperaba."""
    products = sorted({source for mission in missions for flag in mission.get("flagged_extremes", []) for source in flag.get("countercheck_values", {})})
    return ("Una consulta /projects/climate-screening por lugar, 2001 hasta dos días antes de construir. Tendencia: Mann–Kendall con corrección "
            "de Hamed–Rao y pendiente de Sen sobre medias anuales; significancia tras Benjamini–Hochberg entre las variables del lugar. "
            "Segunda fuente de la temperatura: ERA5, donde la API la devolvió. Años atípicos de lluvia extrema: se guardan con el valor del "
            "mismo año en cada producto de contraste que devolvió la API; en este archivo: " + ("; ".join(products) if products else "ninguno") + ". "
            "La regla de «artefacto probable» (ADR-036) se aplica al servir las misiones. «built_at» es la última escritura del archivo con "
            "análisis nuevos; la fecha de cada análisis está en «analysis.generated_at» de su misión.")


def call(path: str, body: dict) -> dict:
    request = urllib.request.Request(f"{API}{path}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read().decode("utf-8"))


def trend_of(item: dict) -> dict:
    trend = item["trend"]
    era5 = next((check for check in item.get("counterchecks", []) if check.get("source", "").startswith("ERA5")), None)
    return {
        "label": item["label"],
        "unit": item.get("display_unit") or item.get("unit"),
        "mean": item.get("mean"),
        "direction": trend["direction"],
        "slope_per_year": trend.get("slope_per_year"),
        "confidence_interval": trend.get("confidence_interval"),
        "p_value_adjusted": item.get("adjusted_p_value"),
        "significant": bool(item.get("significant_after_bh")),
        "valid_years": trend.get("valid_observations"),
        "annual_series": item.get("annual_series", []),
        "second_source": {"source": era5["source"], "agreement": era5.get("agreement"), "period": era5.get("period")} if era5 else None,
    }


def heat_class(temperature: dict | None) -> str:
    if not temperature or not temperature["significant"]:
        return "sin_evidencia"
    return "calienta" if temperature["direction"] == "increasing" else "enfria" if temperature["direction"] == "decreasing" else "sin_evidencia"


KEY_ORDER = ("id", "continent", "country", "name", "latitude", "longitude", "context", "context_sources", "not_measured", "scale", "hazard")


def with_texts(mission: dict, place: tuple) -> dict:
    """La misión con los campos estáticos del guion encima (no salen del análisis).

    Es el único lugar donde se arman: lo usan la construcción y el modo --textos, para que no puedan divergir. Las claves
    que la misión ya tiene conservan su lugar; una clave nueva entra detrás de su vecina en KEY_ORDER, así reaplicar
    textos a un archivo existente no mueve líneas.
    """
    pid, continent, country, name, _lat, _lon, context, not_measured = place
    texts = {"continent": continent, "country": country, "name": name, "context": context, "context_sources": CONTEXT_SOURCES.get(pid, []),
             "not_measured": not_measured, "scale": "paisaje" if pid in LANDSCAPES else "ciudad", "hazard": HAZARDS.get(pid)}
    merged = {**mission, **texts}
    keys = list(mission)
    for index, key in enumerate(KEY_ORDER):
        if key not in keys:
            keys.insert(keys.index(KEY_ORDER[index - 1]) + 1 if index else 0, key)
    return {key: merged[key] for key in keys}


def build(place: tuple) -> dict:
    pid, _continent, _country, name, lat, lon, _context, _not_measured = place
    response = call("/projects/climate-screening", {"sites": [{"latitude": lat, "longitude": lon, "label": name}], "territories": [], "start_date": START, "end_date": END})
    site = response["sites"][0]
    data = {key: None for key in VARIABLES.values()}
    source = None
    for item in site.get("variables", []):
        if item["variable"] in VARIABLES:
            data[VARIABLES[item["variable"]]] = trend_of(item)
            source = source or item.get("source")
    extremes = [
        {"variable": item["variable"], "label": item["label"], "unit": item.get("display_unit"), "direction": item["trend"]["direction"],
         "slope_per_year": item["trend"].get("slope_per_year"), "significant": bool(item.get("significant_after_bh"))}
        for item in site.get("extremes", [])
    ]
    # La unidad va en cada marca: CDD y R10MM se miden en días, y R95P y PRCPTOT son mm del año, no de un día.
    flagged = [
        {"variable": item["variable"], "label": item["label"], "unit": item.get("display_unit"), "year": odd["year"], "value": odd.get("value"),
         "countercheck_values": odd.get("countercheck_values") or {}}
        for item in site.get("extremes", []) for odd in item.get("atypical_years", []) if odd.get("countercheck_values")
    ]
    air = air_trend(lat, lon) if pid in AIR_PLACES else None
    return with_texts({
        "id": pid, "latitude": lat, "longitude": lon,
        "heat": heat_class(data["temperature"]),
        **data,
        **({"air": air} if air else {}),
        "extremes": extremes, "flagged_extremes": flagged,
        "analysis": {
            "analysis_id": response.get("analysis_id"), "generated_at": response.get("generated_at"), "period": response.get("period"),
            "dataset": source.get("dataset") if source else None, "version": source.get("version") if source else None,
            "downloaded_at": source.get("downloaded_at") if source else None, "provenance": source.get("provenance") if source else "DATA_UNAVAILABLE",
            "source_url": source.get("source_url") if source else None,
        },
    }, place)


def write(payload: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def reapply_texts(selected: list[str]) -> None:
    """Modo --textos: reaplica al archivo existente los campos estáticos del guion, sin red.

    No consulta la API, así que no cambia «built_at», «analysis» ni ningún valor medido de ninguna misión.
    """
    if not OUT.exists():
        sys.exit(f"No existe {OUT}: primero hay que construir las misiones con la API encendida.")
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    places = {place[0]: place for place in PLACES}
    for pid in sorted(set(CONTEXT_SOURCES) - set(places)):
        print(f"  ! CONTEXT_SOURCES tiene «{pid}», que no está en PLACES: no se aplica a ninguna misión.")
    missions, changed = [], 0
    for mission in payload["missions"]:
        place = places.get(mission["id"])
        if place is None or (selected and mission["id"] not in selected):
            missions.append(mission)
            continue
        if (mission["latitude"], mission["longitude"]) != (place[4], place[5]):
            # Las coordenadas no son un texto: si cambiaron en el guion, el análisis guardado es de otro punto.
            print(f"  ! {mission['id']}: las coordenadas del guion no son las del archivo; se conservan las del archivo. Reconstruya ese lugar.")
        updated = with_texts(mission, place)
        changed += updated != mission
        missions.append(updated)
    write({**payload, "method": method_text(missions), "missions": missions})
    print(f"Textos reaplicados: {changed} de {len(missions)} misiones cambiaron en {OUT}. built_at y analysis quedan como estaban.")


def main(selected: list[str]) -> None:
    places = [place for place in PLACES if not selected or place[0] in selected]
    previous = {item["id"]: item for item in json.loads(OUT.read_text(encoding="utf-8"))["missions"]} if OUT.exists() else {}
    built: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {place[0]: pool.submit(build, place) for place in places}
        for pid, future in futures.items():
            try:
                built[pid] = future.result()
                print(f"  ✓ {pid}: {built[pid]['heat']}")
            except Exception as error:  # noqa: BLE001 — un lugar caído no detiene a los demás
                print(f"  ✗ {pid}: no se creó la misión ({error})")
    if not built:
        # Sin ningún análisis nuevo no se escribe: reescribir solo renovaría «built_at» sobre análisis que no cambiaron.
        print("Ninguna misión se construyó: el archivo queda como estaba.")
        return
    # Las misiones que no se pidieron o cuyo análisis no llegó se conservan tal cual, con su «analysis» y su fecha.
    merged = {**previous, **built}
    order = [place[0] for place in PLACES]
    missions = [merged[pid] for pid in order if pid in merged]
    # «built_at» es la fecha de esta escritura, no la de cada análisis (esa va en «analysis.generated_at» de cada misión).
    write({"built_at": datetime.now(timezone.utc).isoformat(), "method": method_text(missions), "missions": missions})
    print(f"{len(missions)} misiones en {OUT.relative_to(ROOT)} ({len(built)} con análisis nuevo, {len(missions) - len(built)} conservadas)")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if "--textos" in arguments:
        reapply_texts([item for item in arguments if item != "--textos"])
    else:
        main(arguments)
