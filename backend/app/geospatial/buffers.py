"""Áreas de estudio en kilómetros sobre WGS84: buffer de puntos y líneas en una proyección azimutal equidistante local."""

from math import ceil
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform

from .geometry import GEOD


def _local_aeqd(longitude: float, latitude: float) -> tuple[Transformer, Transformer]:
    local = CRS.from_proj4(f"+proj=aeqd +lat_0={latitude} +lon_0={longitude} +datum=WGS84 +units=m")
    to_local = Transformer.from_crs("EPSG:4326", local, always_xy=True)
    to_wgs84 = Transformer.from_crs(local, "EPSG:4326", always_xy=True)
    return to_local, to_wgs84


def buffer_km(geometry: dict[str, Any], km: float) -> dict[str, Any]:
    """Polígono GeoJSON (RFC 7946) a `km` kilómetros de la geometría; distancias en metros reales, no en grados."""
    geom = shape(geometry)
    center = geom.centroid
    to_local, to_wgs84 = _local_aeqd(center.x, center.y)
    buffered = transform(to_local.transform, geom).buffer(km * 1000, quad_segs=16)
    return mapping(transform(to_wgs84.transform, buffered))


def window_km(geometry: dict[str, Any], longitude: float, latitude: float, *, minimum: int = 1, maximum: int = 10) -> int:
    """Semiancho en km de una ventana centrada en el punto que cubre la caja de la geometría, acotado a [mínimo, máximo]."""
    xmin, ymin, xmax, ymax = shape(geometry).bounds
    reach = 0.0
    for lon, lat in ((xmin, latitude), (xmax, latitude), (longitude, ymin), (longitude, ymax)):
        _, _, meters = GEOD.inv(longitude, latitude, lon, lat)
        reach = max(reach, meters)
    return max(minimum, min(maximum, ceil(reach / 1000)))
