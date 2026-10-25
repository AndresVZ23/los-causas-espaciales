"""Píxeles de una ventana MODIS (proyección sinusoidal) y su relación con un área de estudio WGS84.

Esfera MODIS: radio 6 371 007.181 m. Las celdas llegan por filas desde la esquina superior izquierda.
"""

from math import cos, degrees, radians
from typing import Any

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import shape
from shapely.prepared import prep

from ..connectors.nasa.modis_subsets import ModisGrid

SPHERE_RADIUS_M = 6_371_007.181


def pixel_centers(grid: ModisGrid) -> list[tuple[float, float]]:
    """(longitud, latitud) WGS84 del centro de cada celda, en el orden de los datos."""
    centers = []
    for row in range(grid.nrows):
        y = grid.yllcorner + (grid.nrows - row - 0.5) * grid.cellsize
        latitude = y / SPHERE_RADIUS_M
        for col in range(grid.ncols):
            x = grid.xllcorner + (col + 0.5) * grid.cellsize
            longitude = x / (SPHERE_RADIUS_M * cos(latitude))
            centers.append((degrees(longitude), degrees(latitude)))
    return centers


def pixels_inside(grid: ModisGrid, geometry: dict[str, Any], longitude: float, latitude: float) -> tuple[list[int], bool]:
    """Índices de las celdas cuyo centro cae dentro del área; si ninguna cae (área menor que una celda),
    la celda más cercana al punto representativo. El segundo valor indica si se usó ese recurso."""
    area = prep(shape(geometry))
    centers = pixel_centers(grid)
    inside = [index for index, (lon, lat) in enumerate(centers) if area.contains(ShapelyPoint(lon, lat))]
    if inside:
        return inside, False
    scale = cos(radians(latitude))
    nearest = min(range(len(centers)), key=lambda i: ((centers[i][0] - longitude) * scale) ** 2 + (centers[i][1] - latitude) ** 2)
    return [nearest], True
