"""Construye las misiones del «modo jugador» y las guarda en backend/data/missions/missions.json.

Cada misión es un lugar del mundo con su análisis climático real, pedido a la API local en el momento de construir
(NASA POWER desde 2001, con ERA5 como segunda fuente y GPM IMERG / CHIRPS para la lluvia extrema). El texto de
«contexto» es cualitativo y está marcado como tal: no lleva cifras ni sale de la plataforma. Si el análisis de un lugar
no llega, la misión no se crea y el guion lo dice.

    python3 scripts/missions/build_missions.py              # todas
    python3 scripts/missions/build_missions.py nazca taal   # algunas

Requiere la API en http://localhost:8000 (variable MISSIONS_API para otra dirección). Un sitio por consulta, para que la
familia de Benjamini–Hochberg sea siempre la de las variables de ese sitio y no dependa de con quién se agrupe.
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
     "Geoglifos del desierto costero, Patrimonio Mundial de la UNESCO. Las lluvias raras, sobre todo en años de El Niño, y la erosión son su mayor amenaza física.",
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
     "Junto a la estación científica del Perú en la Antártida, en la península Antártica, una de las zonas que más se han calentado en el último medio siglo.",
     "El hielo marino ni los glaciares."),
    ("chosica", "Sudamérica", "Perú", "Chosica, Lurigancho", -11.94, -76.70,
     "Cada temporada de lluvias en la sierra, los huaicos bajan por las quebradas que cruzan Chosica.",
     "La inestabilidad de las laderas ni el caudal de las quebradas."),
    ("piura", "Sudamérica", "Perú", "Piura", -5.19, -80.63,
     "En 2017 el Niño Costero desbordó el río Piura e inundó buena parte de la ciudad.",
     "El caudal del río ni la temperatura del mar."),
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
     "Uno de los volcanes más activos de Indonesia; en 2010 una gran erupción obligó a evacuar a miles de personas.",
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
    "mocoa": "huaico", "porto-alegre": "inundacion", "chosica": "huaico", "piura": "inundacion", "huascaran": "avalancha", "villarrica": "erupcion",
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

VARIABLES = {"T2M": "temperature", "PRECTOTCORR": "rain", "ALLSKY_SFC_SW_DWN": "sun"}


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


def build(place: tuple) -> dict:
    pid, continent, country, name, lat, lon, context, not_measured = place
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
    flagged = [
        {"variable": item["variable"], "label": item["label"], "year": odd["year"], "value": odd.get("value"), "countercheck_values": odd.get("countercheck_values") or {}}
        for item in site.get("extremes", []) for odd in item.get("atypical_years", []) if odd.get("countercheck_values")
    ]
    return {
        "id": pid, "continent": continent, "country": country, "name": name, "latitude": lat, "longitude": lon,
        "context": context, "not_measured": not_measured, "scale": "paisaje" if pid in LANDSCAPES else "ciudad", "hazard": HAZARDS.get(pid),
        "heat": heat_class(data["temperature"]),
        **data,
        "extremes": extremes, "flagged_extremes": flagged,
        "analysis": {
            "analysis_id": response.get("analysis_id"), "generated_at": response.get("generated_at"), "period": response.get("period"),
            "dataset": source.get("dataset") if source else None, "version": source.get("version") if source else None,
            "downloaded_at": source.get("downloaded_at") if source else None, "provenance": source.get("provenance") if source else "DATA_UNAVAILABLE",
            "source_url": source.get("source_url") if source else None,
        },
    }


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
    merged = {**previous, **built}
    order = [place[0] for place in PLACES]
    missions = [merged[pid] for pid in order if pid in merged]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "built_at": datetime.now(timezone.utc).isoformat(),
        "method": "Una consulta /projects/climate-screening por lugar, 2001 hasta dos días antes de construir. Tendencia: Mann–Kendall con corrección "
                  "de Hamed–Rao y pendiente de Sen sobre medias anuales; significancia tras Benjamini–Hochberg entre las variables del lugar.",
        "missions": missions,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(missions)} misiones en {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
