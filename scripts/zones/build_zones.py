"""Construye las «zonas para explorar» (ADR-047) y las guarda en backend/data/zones/.

Cada zona es una maqueta en bloques (Copernicus DEM GLO-30 y ESA WorldCover) más balizas con resultados reales de la
plataforma, pedidos a la API local en el momento de construir. Nada se escribe a mano: si un resultado no llega, la
baliza no se crea y el guion lo dice.

    .venv\\Scripts\\python.exe scripts\\zones\\build_zones.py            # las dos zonas
    .venv\\Scripts\\python.exe scripts\\zones\\build_zones.py taal       # una sola

Requiere la API en http://localhost:8000 (variable ZONES_API para otra dirección).
"""

import asyncio
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.zones.builder import Frame, build_grid, encode, place, read_window  # noqa: E402

API = os.environ.get("ZONES_API", "http://localhost:8000") + "/api/v1"
OUT = ROOT / "backend" / "data" / "zones"
END = (date.today() - timedelta(days=2)).isoformat()
STEEP = 15
MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
SOURCES = [
    {"name": "Copernicus DEM GLO-30 (ESA · Airbus, TanDEM-X)", "use": "Relieve: la altura de cada columna de bloques.",
     "license": "Dato adaptado: «produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS "
                "by the European Union and ESA; all rights reserved».",
     "url": "https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM"},
    {"name": "ESA WorldCover 10 m 2021 v200", "use": "Cobertura del suelo: el material de cada bloque.",
     "license": "CC BY 4.0. © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium.",
     "url": "https://esa-worldcover.org/en/data-access"},
]


def day(text: str) -> str:
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return f"{value.day}-{MONTHS[value.month - 1]}-{value.year}"


def call(path: str, body: dict | None = None):
    request = urllib.request.Request(f"{API}{path}", data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read().decode("utf-8"))


def variable(site: dict, code: str) -> dict | None:
    return next((item for item in site.get("variables", []) if item["variable"] == code), None)


def number(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def cell_point(frame: Frame, row: int, col: int) -> tuple[float, float]:
    lats, lons = frame.centers()
    return round(float(lats[row, col]), 5), round(float(lons[row, col]), 5)


def steepest(frame: Frame, grid: dict) -> tuple[float, float, int]:
    """La celda de mayor pendiente, lejos del borde de la maqueta."""
    slope = grid["slope"].astype(int).copy()
    margin = frame.grid // 12
    slope[:margin, :] = slope[-margin:, :] = slope[:, :margin] = slope[:, -margin:] = 0
    row, col = np.unravel_index(int(slope.argmax()), slope.shape)
    return (*cell_point(frame, int(row), int(col)), int(slope[row, col]))


def flat_bare(frame: Frame, grid: dict, cover_codes: tuple[int, ...]) -> tuple[float, float] | None:
    """Celda llana (< 3°) de las coberturas indicadas más cercana al centro, fuera del casco urbano inmediato."""
    slope, cover = grid["slope"], grid["cover"]
    rows, cols = np.nonzero((slope < 3) & np.isin(cover, cover_codes))
    if rows.size == 0:
        return None
    center = frame.grid / 2
    distance = np.hypot(rows - center, cols - center)
    ring = distance > frame.grid * 0.2
    pick = int(np.argmin(np.where(ring, distance, np.inf))) if ring.any() else int(np.argmin(distance))
    return cell_point(frame, int(rows[pick]), int(cols[pick]))


def lowest(frame: Frame, grid: dict, cover_codes: tuple[int, ...]) -> tuple[float, float] | None:
    heights, cover = grid["heights"].astype(int), grid["cover"]
    mask = np.isin(cover, cover_codes)
    if not mask.any():
        return None
    row, col = np.unravel_index(int(np.where(mask, heights, 10**6).argmin()), heights.shape)
    return cell_point(frame, int(row), int(col))


def beacon(frame: Frame, **fields) -> dict | None:
    if place(frame, fields["latitude"], fields["longitude"]) is None:
        print(f"  - baliza «{fields['title']}» fuera de la maqueta: no se crea")
        return None
    return fields


def slope_beacon(frame: Frame, grid: dict) -> dict:
    latitude, longitude, degrees = steepest(frame, grid)
    share = float((grid["slope"] >= STEEP).mean() * 100)
    return dict(
        id="pendiente", kind="amenaza", title="Laderas de pendiente fuerte",
        body=f"El {number(share, 0)} % de la maqueta supera los {STEEP}° de pendiente; aquí está la celda más empinada, con {degrees}°. "
             "En la maqueta esas laderas se ven en rojo al activar «Pendientes».",
        figures=[{"label": "Pendiente máxima", "value": f"{degrees}°"}, {"label": f"Área sobre {STEEP}°", "value": f"{number(share, 0)} %"}],
        sources=["Copernicus DEM GLO-30 (pendiente de Horn sobre la cuadrícula de la maqueta)"],
        second_source="No hay segunda fuente por celda en la maqueta; en el análisis de un punto la pendiente se contrasta con NASADEM.",
        look_first="Topografía de detalle y estabilidad de taludes antes de ubicar obras o viviendas al pie de estas laderas.",
        latitude=latitude, longitude=longitude, placement="Celda de mayor pendiente de la maqueta.")


def moquegua() -> dict:
    frame = Frame(-17.193, -70.934, 6.0, 200)
    site = {"latitude": -17.193, "longitude": -70.934, "label": "Moquegua"}
    arequipa = {"latitude": -16.409, "longitude": -71.537, "label": "Arequipa"}
    elevation, cover, urls = asyncio.run(read_window(frame))
    grid = build_grid(elevation, cover, frame.cell_m, 2.0)
    beacons: list[dict | None] = [beacon(frame, **slope_beacon(frame, grid))]
    notes = []

    climate = call("/projects/climate-screening", {"sites": [site], "territories": [], "start_date": "2001-01-01", "end_date": END})
    here = climate["sites"][0]
    rx1 = next((item for item in here.get("extremes", []) if item["variable"] == "RX1DAY"), None)
    odd = next((item for item in (rx1 or {}).get("atypical_years", []) if item["year"] == 2022), None)
    if odd:
        others = odd.get("countercheck_values") or {}
        said = " y ".join(f"{name.split(' (')[0]} {number(value)} mm" for name, value in others.items())
        beacons.append(beacon(
            frame, id="lluvia-2022", kind="pista_falsa", title="El día de 300 mm que solo ve un modelo",
            body=f"NASA POWER (MERRA-2) registra {number(odd['value'])} mm de lluvia en un día de 2022 para esta zona. Los dos productos satelitales no lo ven: {said}. "
                 "La plataforma lo marca como artefacto probable y no lo usa como amenaza.",
            figures=[{"label": "MERRA-2, día más lluvioso de 2022", "value": f"{number(odd['value'])} mm"}, *({"label": name.split(" (")[0], "value": f"{number(value)} mm"} for name, value in others.items())],
            sources=["NASA POWER Daily (MERRA-2)", "GPM IMERG", "CHIRPS v2.0"], second_source=f"Los satélites lo desmienten: {said}.",
            look_first="Antes de diseñar drenajes con ese valor, pedir la serie de una estación meteorológica cercana.",
            latitude=site["latitude"], longitude=site["longitude"], placement="Punto del análisis; el dato es de una celda de unos 55 km que cubre toda la maqueta."))
    temperature = variable(here, "T2M")
    if temperature and temperature.get("significant_after_bh") and temperature["trend"].get("slope_per_year"):
        check = next((item for item in temperature.get("counterchecks", []) if item["source"].startswith("ERA5")), None)
        slope = temperature["trend"]["slope_per_year"]
        latitude, longitude = cell_point(frame, frame.grid // 3, frame.grid // 3)
        beacons.append(beacon(
            frame, id="temperatura", kind="amenaza", title="La zona se calienta",
            body=f"La temperatura media sube {number(slope * 10, 2)} °C por década desde 2001, con evidencia estadística tras corregir la autocorrelación y las pruebas múltiples.",
            figures=[{"label": "Tendencia", "value": f"+{number(slope * 10, 2)} °C/década"}],
            sources=["NASA POWER Daily (MERRA-2)"],
            second_source=(f"ERA5 {('confirma la tendencia' if check.get('agreement') == 'coincide' else 'no la repite con significancia')} en {check.get('period', '2005–2023')}." if check else None),
            look_first="Demanda de agua y de riego en el valle, y confort térmico en vivienda y escuelas.",
            latitude=latitude, longitude=longitude, placement="Ubicación ilustrativa: la tendencia es de la celda que cubre toda la maqueta."))

    solar = call("/projects/solar-screening", {"sites": [site, arequipa], "start_date": "2001-01-01", "end_date": END})
    sun_site = next(item for item in solar["sites"] if item["location"]["label"] == "Moquegua")
    irradiance = variable(sun_site, "ALLSKY_SFC_SW_DWN")
    sensitivity = next((item for item in solar.get("financial_sensitivity", []) if item["subject"] == "Moquegua"), None)
    price = next((item for item in (sensitivity or {}).get("break_evens", []) if item["key"] == "energy_price"), None) if sensitivity else None
    spot = flat_bare(frame, grid, (60, 20, 30))
    if irradiance and spot:
        era5 = next((item["title"] for item in solar.get("discoveries", []) if item["title"].startswith("Moquegua") and "recurso solar" in item["title"]), None)
        assumed = solar["assumptions"]["energy_price_usd_mwh"]
        beacons.append(beacon(
            frame, id="sol", kind="oportunidad", title="Mucho sol; el freno es el precio",
            body=f"El recurso solar medio es de {number(irradiance['mean'], 2)} kWh/m² por día, alto y estable. Con los supuestos por defecto el proyecto de ejemplo no cierra "
                 f"(VAN {number(sun_site['finance']['npv_usd'] / 1e6, 2)} millones de dólares): lo que falta no es sol."
                 + (f" Necesitaría {number(price['value'], 1)} USD/MWh y el supuesto es {number(assumed, 0)}." if price and price.get("value") else ""),
            figures=[{"label": "Irradiancia media", "value": f"{number(irradiance['mean'], 2)} kWh/m²/día"},
                     {"label": "VAN del ejemplo", "value": f"USD {number(sun_site['finance']['npv_usd'] / 1e6, 2)} M"},
                     *([{"label": "Precio de equilibrio", "value": f"{number(price['value'], 1)} USD/MWh"}] if price and price.get("value") else [])],
            sources=["NASA POWER Daily (CERES)", "Supuestos financieros del usuario"], second_source=(lambda text: text[0].upper() + text[1:] + ".")(era5.split(": ", 1)[1]) if era5 else None,
            look_first="Contratos de energía y costo de conexión a la red, antes que más mediciones de sol.",
            latitude=spot[0], longitude=spot[1], placement="Terreno llano y sin vegetación más cercano al centro; el recurso es el de la celda que cubre toda la maqueta."))

    hazards = call("/projects/hazards-screening", {"sites": [site], "territories": []})
    flood = next((layer for layer in hazards["baselines"][0]["layers"] if layer["source_id"] == "cenepred-flood-risk" and layer["status"] == "READY"), None)
    valley = lowest(frame, grid, (40, 10, 30))
    if flood and flood["highlights"] and valley:
        item = flood["highlights"][0]
        beacons.append(beacon(
            frame, id="inundacion", kind="amenaza", title="Riesgo de inundación del distrito",
            body=f"CENEPRED clasifica el distrito así: {item['label']}, {item['detail']}. Es un dato por distrito: no dice qué manzana se inunda. "
                 + (f"{flood['stale_note']}" if flood.get("stale_note") else ""),
            figures=[{"label": item["label"], "value": item["detail"]}],
            sources=["CENEPRED · escenario de riesgo por inundaciones (lluvias intensas / El Niño)"],
            second_source=next((d["detail"] for d in hazards.get("discoveries", []) if "inundación" in d["title"]), None),
            look_first="Faja marginal del río y drenaje pluvial del valle; un estudio hidráulico ubica lo que este mapa no ubica.",
            latitude=valley[0], longitude=valley[1], placement="Celda más baja del valle cultivado; la clasificación es de todo el distrito."))
    else:
        notes.append("Sin la capa de riesgo por inundación de CENEPRED al construir: la baliza no se creó.")

    road = call("/projects/road-screening", {"start_date": "2001-01-01", "end_date": END})
    first = road["segments"][0]
    pilot = json.loads((ROOT / "backend" / "data" / "pilots" / "moquegua_ilo_osm.geojson").read_text(encoding="utf-8"))
    line = pilot["features"][0]["geometry"]["coordinates"]
    inside = [(lon, lat) for lon, lat in line if place(frame, lat, lon) is not None]
    score = next((item for item in road["scorecard"]["subjects"] if item["subject"] == first["label"]), None)
    paths = []
    if len(inside) >= 2:
        paths.append({"label": "Corredor Moquegua–Ilo, tramo 1", "coordinates": inside, "source": pilot["source"]})
        lon, lat = inside[-1]
        beacons.append(beacon(
            frame, id="corredor", kind="infraestructura", title="Aquí empieza el corredor Moquegua–Ilo",
            body=f"La línea amarilla es el primer tramo de un corredor de 86.5 km hacia el puerto de Ilo. Este tramo mide {number(first['length_km'])} km y "
                 f"queda {score['rank']}.º de 5 en prioridad de estudio ({number(score['score'], 0)}/100). El tramo que lidera está cerca de la costa, por su pendiente.",
            figures=[{"label": "Longitud del tramo", "value": f"{number(first['length_km'])} km"}, {"label": "Prioridad", "value": f"{score['rank']}.º de 5"},
                     {"label": "VAN de mitigar", "value": f"USD {number(first['finance']['npv_usd'] / 1e6, 2)} M"}],
            sources=["OpenStreetMap (geometría de la vía)", "NASA POWER", "Supuestos del usuario"],
            second_source=next((d["detail"] for d in road.get("discoveries", []) if d["title"].startswith(first["label"])), None),
            look_first="Inventario real de puentes y drenajes del MTC; la geometría es de OpenStreetMap, no el eje oficial.",
            latitude=lat, longitude=lon, placement="Último punto del tramo 1 dentro de la maqueta."))

    return assemble("moquegua", "Moquegua", "Perú", "Un valle verde en el desierto: sol, calor, el río y el arranque del corredor al puerto.", frame, grid, 2.0,
                    beacons, paths, urls, [*notes, "Capas oficiales del Perú disponibles en esta zona (CENEPRED desde su última copia válida)."])


def taal() -> dict:
    frame = Frame(14.0106, 120.9975, 7.0, 200)
    site = {"latitude": 14.0106, "longitude": 120.9975, "label": "Volcán Taal"}
    elevation, cover, urls = asyncio.run(read_window(frame))
    grid = build_grid(elevation, cover, frame.cell_m, 3.0)
    beacons: list[dict | None] = [beacon(frame, **slope_beacon(frame, grid))]
    notes = ["Fuera del Perú solo se usan fuentes globales: no hay capas oficiales nacionales conectadas."]

    alerts = call("/world/alerts")
    event = next((item for item in alerts["alerts"] if item["kind"] == "volcano" and "Taal" in item["title"]), None)
    if event:
        beacons.append(beacon(
            frame, id="erupcion", kind="evento", title=f"Erupción del Taal: alerta {'naranja' if event['level'] == 'orange' else 'roja' if event['level'] == 'red' else 'verde'} de GDACS",
            body=f"GDACS (ONU y Comisión Europea) publicó este evento el {day(event['started'])}. El nivel de alerta es de GDACS; la plataforma no lo calcula. "
                 + ("NASA EONET también lo lista." if event["also_seen_by"] else "NASA EONET no lista un evento equivalente en esas fechas."),
            figures=[{"label": "Nivel GDACS", "value": {"orange": "Naranja", "red": "Roja", "green": "Verde"}.get(event["level"], "Sin nivel")}, {"label": "Fecha", "value": day(event["started"])}],
            sources=["GDACS", "NASA EONET v3"], second_source="NASA EONET lo confirma." if event["also_seen_by"] else "Sin segundo testigo en NASA EONET.",
            look_first="Los boletines del instituto vulcanológico del país (PHIVOLCS) y las rutas de evacuación de los pueblos del lago.",
            latitude=event["latitude"], longitude=event["longitude"], placement="Punto que publica GDACS para el evento."))
    else:
        notes.append("GDACS ya no lista la erupción del Taal en su ventana de 60 días: la baliza del evento no se creó.")

    hazards = call("/projects/hazards-screening", {"sites": [site], "territories": [], "buffer_km": 3})
    area = hazards["baselines"][0]
    layers = {layer["source_id"]: layer for layer in area["layers"] if layer["status"] == "READY"}
    susceptibility, reports = layers.get("nasa-landslide-susceptibility"), layers.get("nasa-coolr-reports")
    if susceptibility and susceptibility["highlights"]:
        levels = "; ".join(f"{item['label'].split(': ')[1]} ×{item['count']}" for item in susceptibility["highlights"])
        count = reports["intersection_count"] if reports else None
        latitude, longitude = cell_point(frame, int(frame.grid * 0.42), int(frame.grid * 0.56))
        beacons.append(beacon(
            frame, id="deslizamientos", kind="amenaza", title="Susceptibilidad a deslizamientos según NASA",
            body=f"En {susceptibility['intersection_count']} puntos de muestreo a 3 km del cráter, el mapa global de NASA marca: {levels}. "
                 + ("" if count is None else "El catálogo COOLR de NASA no tiene reportes en el área; eso no significa que no ocurran." if count == 0
                    else f"El catálogo COOLR de NASA registra {count} deslizamiento(s) reportado(s) en el área."),
            figures=[{"label": "Puntos de muestreo", "value": str(susceptibility["intersection_count"])}, *([{"label": "Deslizamientos reportados", "value": str(count)}] if count is not None else [])],
            sources=["NASA Global Landslide Susceptibility", "NASA COOLR"],
            second_source="No hay mapa nacional conectado para contrastar; en el Perú este mapa se cruza con el de CENEPRED.",
            look_first="El mapa de peligros del instituto geológico del país, que tiene más detalle que un mapa global de 1 km.",
            latitude=latitude, longitude=longitude, placement="Ubicación ilustrativa sobre la isla; el muestreo cubre un círculo de 3 km."))
    rx1 = next((item for item in area.get("extremes", []) if item["variable"] == "RX1DAY"), None)
    if rx1:
        checks = "; ".join(f"{item['source'].split(' (')[0]}: {item['agreement'].replace('_', ' ')}" for item in rx1.get("counterchecks", []))
        latitude, longitude = cell_point(frame, int(frame.grid * 0.6), int(frame.grid * 0.4))
        beacons.append(beacon(
            frame, id="lluvia", kind="amenaza", title="Lluvia extrema sobre el volcán",
            body=f"El día más lluvioso de cada año promedia {number(rx1['mean'])} mm desde 2001. "
                 + ("La tendencia es significativa." if rx1.get("significant_after_bh") else "No hay evidencia estadística de que esté cambiando.")
                 + " Sobre ceniza suelta, la lluvia intensa puede generar flujos de lodo.",
            figures=[{"label": "Lluvia máxima diaria media", "value": f"{number(rx1['mean'])} mm"}],
            sources=["NASA POWER Daily (MERRA-2)"], second_source=f"Contraste satelital — {checks}." if checks else None,
            look_first="Quebradas que bajan del cráter hacia los pueblos de la orilla.",
            latitude=latitude, longitude=longitude, placement="Ubicación ilustrativa: el dato es de la celda que cubre toda la maqueta."))
    gap = next((item for item in hazards["data_gaps"] if item["dataset"].startswith("Capas oficiales nacionales")), None)
    shore = lowest(frame, grid, (50, 40, 10, 30, 60))
    if gap and shore:
        beacons.append(beacon(
            frame, id="brecha", kind="brecha", title="Lo que esta maqueta no sabe",
            body="El mapa oficial de peligro volcánico de Filipinas no está conectado. " + gap["impact"],
            figures=[], sources=["Brechas declaradas por la plataforma"], second_source=None,
            look_first=gap["next_action"], latitude=shore[0], longitude=shore[1], placement="Celda de tierra más baja de la maqueta, junto al lago."))

    return assemble("taal", "Volcán Taal", "Filipinas", "Un volcán activo dentro de un lago, con pueblos en la orilla.", frame, grid, 3.0, beacons, [], urls, notes)


def assemble(zone_id: str, name: str, country: str, tagline: str, frame: Frame, grid: dict, exaggeration: float, beacons: list, paths: list, urls: dict, notes: list[str]) -> dict:
    kept = [item for item in beacons if item]
    missing = [*urls["dem_missing"], *urls["cover_missing"]]
    return {
        "id": zone_id, "name": name, "country": country, "tagline": tagline, "latitude": frame.latitude, "longitude": frame.longitude, "size_km": frame.size_km,
        "built_at": datetime.now(timezone.utc).isoformat(), "bounds": frame.bounds, "grid": frame.grid, "cell_m": frame.cell_m, "vertical_exaggeration": exaggeration,
        "base_elevation_m": grid["base_elevation_m"], "min_elevation_m": grid["min_elevation_m"], "max_elevation_m": grid["max_elevation_m"],
        "heights_b64": encode(grid["heights"]), "cover_b64": encode(grid["cover"]), "slope_b64": encode(grid["slope"]),
        "beacons": kept, "paths": paths, "sources": SOURCES,
        "notes": [f"Cada bloque representa {frame.cell_m:g} m de terreno. El relieve está exagerado ×{exaggeration:g} en vertical para que se lea; la pendiente se calcula antes de exagerar.",
                  "La maqueta no reproduce edificios ni calles reales. Los árboles y los volúmenes claros solo señalan celdas que WorldCover clasifica como arboladas o construidas.",
                  "Las cifras de las balizas se pidieron a la plataforma al construir la zona; la fecha está arriba.",
                  *notes, *([f"Sin tesela publicada para parte del área ({len(missing)} archivo(s)): esas celdas figuran sin dato."] if missing else [])],
    }


BUILDERS = {"moquegua": moquegua, "taal": taal}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for zone_id in sys.argv[1:] or list(BUILDERS):
        print(f"== {zone_id}")
        zone = BUILDERS[zone_id]()
        target = OUT / f"{zone_id}.json"
        target.write_text(json.dumps(zone, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"  {target.name}: {target.stat().st_size / 1024:.0f} KB · {zone['grid']}×{zone['grid']} celdas de {zone['cell_m']:g} m · {zone['min_elevation_m']}–{zone['max_elevation_m']} m")
        for item in zone["beacons"]:
            print(f"  [{item['kind']}] {item['title']}\n      {item['body'][:230]}\n      2.ª fuente: {item['second_source']}")
        for note in zone["notes"]:
            print("  nota:", note)
