"""Zonas para explorar (ADR-047): maqueta en bloques con relieve sintético, ubicación de puntos y rutas de la API. Sin red."""

import base64

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.zones import store
from backend.app.zones.builder import WATER, Frame, build_grid, encode, horn_slopes, place


def test_frame_is_square_in_meters_and_rows_run_north_to_south():
    frame = Frame(-17.193, -70.934, 6.0, 200)
    west, south, east, north = frame.bounds
    assert frame.cell_m == 30
    assert (north - south) * 111_320 == pytest.approx(6000, rel=1e-3)
    assert (east - west) * 111_320 * np.cos(np.radians(-17.193)) == pytest.approx(6000, rel=1e-3)
    lats, lons = frame.centers()
    assert lats[0, 0] > lats[-1, 0] and lons[0, 0] < lons[0, -1]
    assert place(frame, float(lats[10, 20]), float(lons[10, 20])) == (10, 20)
    assert place(frame, north, east) == (0, 199) and place(frame, south, west) == (199, 0)
    assert place(frame, north + 0.01, east) is None


def test_horn_slope_of_a_known_ramp():
    ramp = np.tile(np.arange(8) * 30.0, (8, 1))          # sube 30 m cada 30 m hacia el este: 45°
    assert horn_slopes(ramp, 30.0)[3, 3] == pytest.approx(45.0)
    assert horn_slopes(np.full((5, 5), 100.0), 30.0).max() == 0


def test_grid_measures_blocks_over_the_lowest_point_and_slope_before_exaggeration():
    elevation = np.tile(1000 + np.arange(6) * 30.0, (6, 1))
    cover = np.full((6, 6), 60, dtype=np.uint8)
    plain, tall = build_grid(elevation, cover, 30.0, 1.0), build_grid(elevation, cover, 30.0, 3.0)
    assert plain["heights"][0].tolist() == [0, 1, 2, 3, 4, 5] and tall["heights"][0].tolist() == [0, 3, 6, 9, 12, 15]
    assert (plain["slope"] == tall["slope"]).all() and plain["slope"][2, 2] == 45          # la exageración no toca la pendiente
    assert plain["base_elevation_m"] == 1000 and plain["max_elevation_m"] == 1150
    assert plain["heights"].dtype == np.dtype("<u2")


def test_missing_elevation_is_marked_without_data_and_never_becomes_terrain():
    elevation = np.full((4, 4), 500.0)
    elevation[1, 1] = np.nan
    grid = build_grid(elevation, np.full((4, 4), 30, dtype=np.uint8), 30.0, 1.0)
    assert grid["cover"][1, 1] == 0 and grid["cover"][0, 0] == 30
    assert grid["heights"][1, 1] == 0
    with pytest.raises(ValueError):
        build_grid(np.full((3, 3), np.nan), np.zeros((3, 3), dtype=np.uint8), 30.0, 1.0)


def test_water_is_flattened_and_has_no_slope():
    elevation = np.full((6, 6), 20.0)
    elevation[2:4, 2:4] = [[3.0, 5.5], [4.2, 2.0]]     # ruido del modelo de elevación sobre un lago
    cover = np.full((6, 6), 30, dtype=np.uint8)
    cover[2:4, 2:4] = WATER
    grid = build_grid(elevation, cover, 30.0, 1.0)
    assert len(set(grid["heights"][2:4, 2:4].ravel().tolist())) == 1
    assert (grid["slope"][2:4, 2:4] == 0).all()
    assert grid["min_elevation_m"] == 2.0


def test_encode_round_trips_little_endian():
    values = np.array([[0, 1], [258, 65535]], dtype="<u2")
    assert np.frombuffer(base64.b64decode(encode(values)), dtype="<u2").tolist() == [0, 1, 258, 65535]


def test_built_zones_are_consistent_with_their_grid():
    zones = store.list_zones()
    assert {zone.id for zone in zones} >= {"moquegua", "taal"}
    for summary in zones:
        zone = store.get_zone(summary.id)
        cells = zone.grid * zone.grid
        heights = np.frombuffer(base64.b64decode(zone.heights_b64), dtype="<u2")
        cover = np.frombuffer(base64.b64decode(zone.cover_b64), dtype=np.uint8)
        slope = np.frombuffer(base64.b64decode(zone.slope_b64), dtype=np.uint8)
        assert heights.size == cover.size == slope.size == cells
        assert heights.max() == round((zone.max_elevation_m - zone.base_elevation_m) * zone.vertical_exaggeration / zone.cell_m)
        frame = Frame(zone.latitude, zone.longitude, zone.size_km, zone.grid)
        assert zone.beacons and all(place(frame, beacon.latitude, beacon.longitude) for beacon in zone.beacons)
        assert all(beacon.sources and beacon.look_first and beacon.placement for beacon in zone.beacons)
        assert all(place(frame, lat, lon) for path in zone.paths for lon, lat in path.coordinates)
        assert {source.name.split(" ")[0] for source in zone.sources} == {"Copernicus", "ESA"}
        assert any("exagerado" in note for note in zone.notes)


def test_zone_routes_list_serve_and_reject():
    client = TestClient(app)
    listed = client.get("/api/v1/world/zones")
    assert listed.status_code == 200 and {item["id"] for item in listed.json()} >= {"moquegua", "taal"}
    assert "heights_b64" not in listed.json()[0]
    zone = client.get("/api/v1/world/zones/taal")
    assert zone.status_code == 200 and zone.json()["country"] == "Filipinas" and zone.json()["grid"] == 200
    assert client.get("/api/v1/world/zones/no-existe").status_code == 404
    assert client.get("/api/v1/world/zones/..%2F..%2Fsecret").status_code == 404
    assert store.get_zone("../world/countries_110m") is None
