"""Construye el terreno 3D de cada misión del modo jugador (ADR-048, opción «mundo diseñado con datos reales»).

Para cada misión lee una ventana cuadrada de Copernicus DEM GLO-30 (relieve) y ESA WorldCover 2021 (cobertura) con el
mismo lector de las zonas (`backend.app.zones.builder.read_window`): píxel más cercano al centro de cada celda, sin
interpolar. Guarda elevaciones continuas (no bloques) en decímetros sobre el punto más bajo y la clase de cobertura.

Se ejecuta dentro del contenedor de la API, que tiene las dependencias:

    docker cp scripts/missions/build_terrain.py los-causas-espaciales-api-1:/app/build_terrain.py
    docker compose -p los-causas-espaciales exec api python /app/build_terrain.py            # todas
    docker compose -p los-causas-espaciales exec api python /app/build_terrain.py nazca taal # algunas

Escribe en /app/backend/data/missions/terrain/<id>.json (copiar de vuelta al repositorio con `docker cp`).
Fuera del contenedor, con el entorno local: `.venv/Scripts/python.exe scripts/missions/build_terrain.py lima` escribe
directo en backend/data/missions/terrain/ del repositorio.
"""

import asyncio
import base64
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Dentro del contenedor el repositorio está en /app; fuera (venv local, ADR-050) se usa la raíz del repositorio.
APP = Path("/app") if Path("/app/backend").is_dir() else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))
from backend.app.zones.builder import WATER, Frame, read_window  # noqa: E402

DATA = APP / "backend" / "data" / "missions"
OUT = DATA / "terrain"
# Ciudad: 4 km de lado en celdas de 20 m. Paisaje (lago, glaciar, desierto): 8 km en celdas de ~31 m.
SIZES = {"ciudad": (4.0, 200), "paisaje": (8.0, 256)}
SOURCES = [
    {"name": "Copernicus DEM GLO-30", "use": "Relieve del terreno.",
     "license": "Dato adaptado: «produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved»."},
    {"name": "ESA WorldCover 10 m 2021 v200", "use": "Cobertura del suelo: bosque, cultivo, ciudad, agua, nieve…",
     "license": "CC BY 4.0. © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium."},
]


def b64(values: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(values).tobytes()).decode("ascii")


def shape_terrain(elevation: np.ndarray, cover: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, bool]:
    """Rellena huecos con el vecino válido más bajo, aplana el agua por cuerpo y marca mar probable.

    Una celda sin cobertura (0) y elevación ≤ 0,5 m se pinta como agua: WorldCover no cubre el mar abierto. Es una
    suposición visual declarada (`sea_assumed`), no un dato.
    """
    valid = np.isfinite(elevation)
    if not valid.any():
        raise ValueError("Sin ninguna celda con elevación.")
    base = float(elevation[valid].min())
    filled = np.where(valid, elevation, base)
    sea = (cover == 0) & (filled <= 0.5)
    cover = np.where(sea, WATER, cover).astype(np.uint8)
    water = cover == WATER
    if water.any():
        padded = np.pad(np.where(water, filled, np.inf), 2, mode="constant", constant_values=np.inf)
        lowest = np.min(np.stack([padded[i:i + filled.shape[0], j:j + filled.shape[1]] for i in range(5) for j in range(5)]), axis=0)
        filled = np.where(water, lowest, filled)
    return filled, cover, base, bool(sea.any())


async def build(mission: dict) -> dict:
    size_km, grid = SIZES.get(mission.get("scale", "ciudad"), SIZES["ciudad"])
    frame = Frame(latitude=mission["latitude"], longitude=mission["longitude"], size_km=size_km, grid=grid)
    elevation, cover, urls = await read_window(frame)
    filled, cover, base, sea = shape_terrain(elevation, cover)
    relief_dm = np.clip(np.rint((filled - base) * 10), 0, 65_535).astype("<u2")
    classes, counts = np.unique(cover, return_counts=True)
    return {
        "id": mission["id"], "size_km": size_km, "grid": grid, "cell_m": round(frame.cell_m, 2), "bounds": frame.bounds,
        "base_elevation_m": round(base, 1), "max_elevation_m": round(float(filled.max()), 1),
        "relief_dm": b64(relief_dm), "cover": b64(cover),
        "cover_share": {int(c): round(int(n) / cover.size, 4) for c, n in zip(classes, counts, strict=True)},
        "missing_cells": int((~np.isfinite(elevation)).sum()), "sea_assumed": sea,
        "dem_tiles": urls["dem"], "dem_missing": urls["dem_missing"], "cover_tiles": urls["cover"], "cover_missing": urls["cover_missing"],
        "sources": SOURCES, "built_at": datetime.now(timezone.utc).isoformat(),
    }


async def main(selected: list[str]) -> None:
    missions = json.loads((DATA / "missions.json").read_text(encoding="utf-8"))["missions"]
    OUT.mkdir(parents=True, exist_ok=True)
    for mission in missions:
        if selected and mission["id"] not in selected:
            continue
        try:
            result = await build(mission)
            (OUT / f"{mission['id']}.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            print(f"  ✓ {mission['id']}: {result['grid']}×{result['grid']}, {result['base_elevation_m']}–{result['max_elevation_m']} m", flush=True)
        except Exception as error:  # noqa: BLE001 — un lugar caído no detiene a los demás
            print(f"  ✗ {mission['id']}: {error}", flush=True)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
