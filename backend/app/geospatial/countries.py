"""En qué país cae un punto o una geometría (Natural Earth 1:110m, dominio público).

Sirve para dos decisiones: qué archivo del Atlas Eólico Global leer y si tiene sentido consultar las capas oficiales
del Perú. Los límites a 1:110m son gruesos: la costa y las fronteras se resuelven con una holgura declarada, y un punto
que no cae en ningún país (mar adentro, islas pequeñas) devuelve None en vez de un país adivinado.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.prepared import PreparedGeometry, prep

COUNTRIES_PATH = Path(__file__).resolve().parents[2] / "data" / "world" / "countries_110m.geojson"
# Holgura para costas y fronteras simplificadas: Ilo o Marcona quedan fuera del polígono a 1:110m por unos kilómetros.
NEAR_DEGREES = 0.5
PERU = "PER"
OUTSIDE_PERU = "las capas oficiales conectadas son del Perú y el área está en otro país: no se consultan, para no leer un cero como ausencia."


@dataclass(frozen=True)
class Country:
    iso3: str
    name: str


@lru_cache(maxsize=1)
def _countries() -> list[tuple[Country, BaseGeometry, PreparedGeometry]]:
    payload = json.loads(COUNTRIES_PATH.read_text(encoding="utf-8"))
    out = []
    for feature in payload["features"]:
        properties = feature["properties"]
        if not properties.get("iso3"):
            continue
        geometry = shape(feature["geometry"])
        out.append((Country(iso3=properties["iso3"], name=properties["name"]), geometry, prep(geometry)))
    return out


def country_at(longitude: float, latitude: float) -> Country | None:
    """El país que contiene el punto; si ninguno lo contiene, el más cercano dentro de la holgura."""
    point = ShapelyPoint(longitude, latitude)
    for country, _, prepared in _countries():
        if prepared.contains(point):
            return country
    nearest = min(((geometry.distance(point), country) for country, geometry, _ in _countries()), key=lambda item: item[0], default=None)
    return nearest[1] if nearest and nearest[0] <= NEAR_DEGREES else None


def touches_peru(geometry: dict[str, Any]) -> bool:
    """Si la geometría toca el Perú o queda a menos de la holgura: solo entonces se consultan sus capas oficiales."""
    peru = next((item for country, item, _ in _countries() if country.iso3 == PERU), None)
    return peru is not None and peru.distance(shape(geometry)) <= NEAR_DEGREES
