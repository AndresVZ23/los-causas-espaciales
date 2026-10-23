import json
from pathlib import Path

from fastapi.testclient import TestClient
from shapely.geometry import shape

from backend.app.connectors.peru.admin_boundaries import DATA_ROOT, PeruTerritoryCatalog
from backend.app.main import app
from backend.app.schemas.analysis import Provenance


def test_hierarchy_has_official_counts_and_parent_links():
    catalog = PeruTerritoryCatalog()
    departments = catalog.hierarchy()
    assert departments.count == 25
    assert departments.children_level == "department"

    moquegua = next(item for item in departments.children if item.name == "Moquegua")
    assert moquegua.ubigeo == "18"
    provinces = catalog.hierarchy(moquegua.ubigeo)
    assert provinces.parent == moquegua
    assert provinces.children_level == "province"
    assert {item.name for item in provinces.children} == {"General Sanchez Cerro", "Ilo", "Mariscal Nieto"}
    assert all(item.parent_ubigeo == "18" for item in provinces.children)


def test_search_supports_accents_names_and_ubigeo():
    catalog = PeruTerritoryCatalog()
    by_name = catalog.search("sanchez cerro", level="province")
    assert by_name.count == 1
    assert by_name.results[0].name == "General Sanchez Cerro"

    by_code = catalog.search("1801", level="province")
    assert by_code.count == 1
    assert by_code.results[0].name == "Mariscal Nieto"
    assert by_code.source.provenance == Provenance.REAL
    assert by_code.source.source_created.isoformat() == "2015-07-24"


def test_geometry_is_valid_wgs84_and_declares_web_limitations():
    result = PeruTerritoryCatalog().geometry("district", "180101")
    geometry = shape(result.feature["geometry"])
    assert geometry.is_valid and not geometry.is_empty
    assert result.territory.name == "Moquegua"
    assert result.crs.startswith("EPSG:4326")
    assert result.maximum_level_area_change_percent <= 1
    assert any("2015" in item for item in result.limitations)
    minimum_x, minimum_y, maximum_x, maximum_y = geometry.bounds
    assert -82 <= minimum_x <= maximum_x <= -68
    assert -19 <= minimum_y <= maximum_y <= 1


def test_manifest_counts_reduction_and_integrity_contract():
    manifest = json.loads((Path(DATA_ROOT) / "manifest.json").read_text(encoding="utf-8"))
    assert [manifest["levels"][str(level)]["count"] for level in (1, 2, 3)] == [25, 196, 1873]
    assert all(manifest["levels"][str(level)]["maximum_geodesic_area_change_percent"] <= 1 for level in (1, 2, 3))
    assert all(manifest["levels"][str(level)]["vertex_reduction_percent"] > 90 for level in (1, 2, 3))
    assert manifest["source_sha256"] == "2f0ec51b7a0899b407546aa644621e1c3255cba59fdda76fcde6975ca6baafb3"


def test_territory_endpoints_and_errors_without_server():
    client = TestClient(app)
    response = client.get("/api/v1/territories/search", params={"q": "Moquegua", "limit": 10})
    assert response.status_code == 200
    assert response.json()["count"] == 2

    response = client.get("/api/v1/territories/hierarchy", params={"parent_ubigeo": "18"})
    assert response.status_code == 200
    assert response.json()["count"] == 3

    response = client.get("/api/v1/territories/district/180101/geometry")
    assert response.status_code == 200
    assert response.json()["feature"]["type"] == "Feature"

    response = client.get("/api/v1/territories/province/9999/geometry")
    assert response.status_code == 404

    response = client.get("/api/v1/territories/district/18/geometry")
    assert response.status_code == 422
