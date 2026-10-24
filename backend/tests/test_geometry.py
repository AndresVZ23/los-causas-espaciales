import pytest

from backend.app.geospatial.geometry import GeometryValidationError, inspect_geometry


def test_inspects_linestring_with_geodesic_length():
    result = inspect_geometry({"type": "LineString", "coordinates": [[-71.0, -17.0], [-70.9, -17.1]]})
    assert result.geometry_type == "LineString"
    assert result.length_km is not None and result.length_km > 10
    assert result.vertex_count == 2


def test_inspects_polygon_area():
    result = inspect_geometry({"type": "Polygon", "coordinates": [[[-71, -17], [-70.9, -17], [-70.9, -17.1], [-71, -17.1], [-71, -17]]]})
    assert result.area_km2 is not None and result.area_km2 > 100
    assert result.length_km is not None


def test_inspects_multipolygon_area_and_vertices():
    result = inspect_geometry({
        "type": "MultiPolygon",
        "coordinates": [
            [[[-71, -17], [-70.99, -17], [-70.99, -17.01], [-71, -17.01], [-71, -17]]],
            [[[-70.98, -17], [-70.97, -17], [-70.97, -17.01], [-70.98, -17.01], [-70.98, -17]]],
        ],
    })
    assert result.geometry_type == "MultiPolygon"
    assert result.area_km2 is not None and result.area_km2 > 2
    assert result.vertex_count == 10


def test_rejects_out_of_range_coordinates():
    with pytest.raises(GeometryValidationError):
        inspect_geometry({"type": "Point", "coordinates": [190, -17]})
