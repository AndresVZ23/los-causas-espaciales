from typing import Any

from pyproj import Geod
from shapely.geometry import shape
from shapely.validation import explain_validity

from ..schemas.analysis import GeometryResponse, Point

GEOD = Geod(ellps="WGS84")
SUPPORTED_TYPES = {"Point", "LineString", "Polygon", "MultiPolygon"}


class GeometryValidationError(ValueError):
    pass


def _count_vertices(coordinates: Any) -> int:
    if not isinstance(coordinates, list):
        return 0
    if len(coordinates) >= 2 and all(isinstance(value, (int, float)) for value in coordinates[:2]):
        return 1
    return sum(_count_vertices(item) for item in coordinates)


def inspect_geometry(geojson: dict[str, Any]) -> GeometryResponse:
    geometry_type = geojson.get("type")
    if geometry_type not in SUPPORTED_TYPES:
        raise GeometryValidationError("Solo se admiten geometrías Point, LineString, Polygon y MultiPolygon.")
    try:
        geometry = shape(geojson)
    except Exception as exc:
        raise GeometryValidationError(f"Coordenadas GeoJSON inválidas: {exc}") from exc
    if geometry.is_empty:
        raise GeometryValidationError("La geometría no puede estar vacía.")
    if not geometry.is_valid:
        raise GeometryValidationError(f"Geometría inválida: {explain_validity(geometry)}")
    min_x, min_y, max_x, max_y = geometry.bounds
    if min_x < -180 or max_x > 180 or min_y < -90 or max_y > 90:
        raise GeometryValidationError("Las coordenadas deben respetar rangos de longitud/latitud WGS84.")

    centroid = geometry.centroid
    length_km = None
    area_km2 = None
    if geometry_type == "LineString":
        length_km = abs(GEOD.geometry_length(geometry)) / 1000
    elif geometry_type in {"Polygon", "MultiPolygon"}:
        area_m2, perimeter_m = GEOD.geometry_area_perimeter(geometry)
        area_km2 = abs(area_m2) / 1_000_000
        length_km = abs(perimeter_m) / 1000

    return GeometryResponse(
        geometry_type=geometry_type,
        centroid=Point(latitude=centroid.y, longitude=centroid.x),
        bounding_box=(min_x, min_y, max_x, max_y),
        length_km=round(length_km, 4) if length_km is not None else None,
        area_km2=round(area_km2, 4) if area_km2 is not None else None,
        vertex_count=_count_vertices(geojson.get("coordinates")),
        method="Medición geodésica elipsoidal WGS84 con PROJ/Geod y validación geométrica con Shapely.",
        limitations=[
            "Este endpoint valida y mide la geometría; no evalúa amenazas, propiedad ni restricciones legales.",
            "El centroide puede quedar fuera de polígonos altamente cóncavos.",
        ],
    )
