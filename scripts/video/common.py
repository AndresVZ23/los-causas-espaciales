"""Rutas y datos compartidos por la vista previa y el montaje de las cinemáticas (ADR-050)."""
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Carpeta de trabajo de los videos: recursos, voces, música, planos y resultado. Por defecto videos/ del repositorio.
VIDEOS = Path(os.environ.get("TERRA_VIDEOS", REPO / "videos"))
ASSETS = VIDEOS / "assets"
ENGINE = Path(__file__).resolve().parent / "engine"
PLACES = ["chosica", "huascaran", "piura", "chamonix", "mocoa"]
# Chrome con WebGL por software (SwiftShader): el render no depende de la tarjeta gráfica.
BROWSER_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--allow-file-access-from-files", "--disable-web-security"]
CHROME = os.environ.get("TERRA_CHROME") or None


def page_data():
    missions = {m["id"]: m for m in json.loads((REPO / "backend/data/missions/missions.json").read_text(encoding="utf-8"))["missions"]}
    keep = {k: {"name": missions[k]["name"], "temperature": missions[k]["temperature"]} for k in PLACES if k in missions}
    names = {k: f'{missions[k]["name"]}, {missions[k]["country"]}' for k in PLACES if k in missions}
    return {"missions": keep, "names": names, "credits": credits()}


def terrains():
    return {k: json.loads((REPO / f"backend/data/missions/terrain/{k}.json").read_text(encoding="utf-8")) for k in PLACES}


def credits():
    es = ["#TERRA 2045 · El último viaje", "Un proyecto de Los Causas Espaciales", "NASA Space Apps Challenge 2026 · sede Moquegua", "",
          "#Historia y juego", "Equipo Los Causas Espaciales", "Ficción: no es un pronóstico.", "Las cifras de las misiones del juego son datos reales.", "",
          "#Datos de observación de la Tierra", "NASA POWER (MERRA-2, CERES SYN1deg)", "NASA GIBS: Blue Marble y Black Marble", "NASA SVS: CGI Moon Kit (LRO · LROC y LOLA)",
          "ERA5 (ECMWF) vía PVGIS (JRC) como segunda fuente", "Copernicus DEM GLO-30 © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018,", "provisto bajo COPERNICUS por la Unión Europea y la ESA",
          "ESA WorldCover 10 m 2021 v200 · CC BY 4.0", "", "#Música",
          "Kevin MacLeod (incompetech.com)", "Licencia Creative Commons: By Attribution 4.0", "creativecommons.org/licenses/by/4.0", "",
          "#Voces sintéticas", "Voces neuronales de Microsoft (Edge): Camila y Alex (Perú),", "Jorge y Dalia (México), Salomé (Colombia), Sofía (Bolivia)", "En inglés: Christopher, Ava, Brian, Emma y Ana", "", "#Producción",
          "Guion, animación y código con asistencia de IA", "(Claude, de Anthropic), revisados por el equipo", "", "El futuro no está escrito.", "Pero cada decisión deja una huella."]
    en = ["#TERRA 2045 · The Last Journey", "A Los Causas Espaciales project", "NASA Space Apps Challenge 2026 · Moquegua", "",
          "#Story and game", "Los Causas Espaciales team", "Fiction: not a forecast.", "The figures in the game's missions are real data.", "",
          "#Earth observation data", "NASA POWER (MERRA-2, CERES SYN1deg)", "NASA GIBS: Blue Marble and Black Marble", "NASA SVS: CGI Moon Kit (LRO · LROC and LOLA)",
          "ERA5 (ECMWF) via PVGIS (JRC) as a second source", "Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018,", "provided under COPERNICUS by the European Union and ESA",
          "ESA WorldCover 10 m 2021 v200 · CC BY 4.0", "", "#Music",
          "Kevin MacLeod (incompetech.com)", "Licensed under Creative Commons: By Attribution 4.0", "creativecommons.org/licenses/by/4.0", "",
          "#Synthetic voices", "Microsoft neural voices (Edge): Christopher, Ava, Brian, Emma and Ana", "In Spanish: Camila and Alex (Peru), Jorge and Dalia (Mexico),", "Salomé (Colombia), Sofía (Bolivia)", "", "#Production",
          "Script, animation and code with AI assistance", "(Claude, by Anthropic), reviewed by the team", "", "The future is not written.", "But every decision leaves a mark."]
    return {"es": es, "en": en}


def earth_files():
    day = "bluemarble.jpg" if (ASSETS / "bluemarble.jpg").exists() else "earth_fallback.jpg"
    night = "blackmarble.jpg" if (ASSETS / "blackmarble.jpg").exists() else "landmask.png"
    return day, night


def boot_options():
    day, night = earth_files()
    return {"earth": day, "night": night, "assets": ASSETS.as_uri() + "/", "data": page_data(), "terrains": terrains()}
