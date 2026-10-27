"""Puntos de muestreo y polígonos ArcGIS para capas que se leen por punto o por `identify`.

CENEPRED (ráster por `identify`) y las capas de deslizamientos de NASA (`getSamples`) usan los mismos puntos: así sus
niveles se comparan punto por punto, sin interpolar ninguna de las dos fuentes.
"""

from typing import Any

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import shape
from shapely.prepared import prep

SAMPLE_GRID = 4          # 4 × 4 puntos sobre la caja del área, más el punto representativo
MAX_VERTICES = 200


def sample_points(geometry: dict[str, Any], representative: tuple[float, float]) -> list[tuple[float, float]]:
    """Punto representativo más una grilla regular dentro del área (longitud, latitud)."""
    area = shape(geometry)
    inside = prep(area)
    xmin, ymin, xmax, ymax = area.bounds
    points = [representative]
    for i in range(SAMPLE_GRID):
        for j in range(SAMPLE_GRID):
            x = xmin + (i + 0.5) * (xmax - xmin) / SAMPLE_GRID
            y = ymin + (j + 0.5) * (ymax - ymin) / SAMPLE_GRID
            if inside.contains(ShapelyPoint(x, y)):
                points.append((round(x, 5), round(y, 5)))
    return list(dict.fromkeys(points))


def esri_polygon(geometry: dict[str, Any]) -> dict[str, Any]:
    """Polígono ArcGIS (anillos exteriores) simplificado hasta ~200 vértices para que la solicitud no sea rechazada."""
    area = shape(geometry)
    tolerance = 0.0005
    while sum(len(polygon.exterior.coords) for polygon in getattr(area, "geoms", [area])) > MAX_VERTICES and tolerance < 0.05:
        area = shape(geometry).simplify(tolerance, preserve_topology=True)
        tolerance *= 2
    polygons = getattr(area, "geoms", [area])
    # 5 decimales ≈ 1 m: suficiente para cruzar con mapas de peligro y mantiene corta la solicitud.
    return {"rings": [[[round(x, 5), round(y, 5)] for x, y in polygon.exterior.coords] for polygon in polygons], "spatialReference": {"wkid": 4326}}
