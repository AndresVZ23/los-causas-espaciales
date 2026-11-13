"""Misiones del modo jugador: contrato del archivo versionado y ruta de la API, sin red."""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.api import world
from backend.app.main import app
from backend.app.missions.store import MISSIONS_FILE, load_missions
from backend.app.schemas.missions import MissionsResponse

client = TestClient(app)


def _mission(**overrides) -> dict:
    trend = {"label": "Temperatura del aire a 2 m", "unit": "°C", "mean": 20.0, "direction": "increasing", "slope_per_year": 0.03,
             "confidence_interval": [0.01, 0.05], "p_value_adjusted": 0.01, "significant": True, "valid_years": 25,
             "annual_series": [{"year": 2001, "value": 19.8}, {"year": 2002, "value": None}], "second_source": None}
    base = {"id": "prueba", "continent": "Sudamérica", "country": "Perú", "name": "Prueba", "latitude": -14.7, "longitude": -75.1,
            "context": "Texto cualitativo.", "not_measured": "El nivel del mar.", "heat": "calienta", "temperature": trend, "rain": None, "sun": None,
            "extremes": [], "flagged_extremes": [],
            "analysis": {"analysis_id": "a", "generated_at": "2026-11-12T00:00:00Z", "period": "2001-01-01/2026-11-10", "dataset": "NASA POWER Daily Point",
                         "version": "v2.10.3", "downloaded_at": "2026-11-12T00:00:00Z", "provenance": "REAL_DATA", "source_url": "https://power.larc.nasa.gov"}}
    return {**base, **overrides}


def test_versioned_file_matches_contract_and_is_consistent():
    data = load_missions()
    assert data is not None, "Falta backend/data/missions/missions.json"
    assert len(data.missions) >= 20
    assert len({item.id for item in data.missions}) == len(data.missions)
    for item in data.missions:
        temp = item.temperature
        # La clase de color sale de la tendencia: nunca se pinta rojo o azul sin significancia.
        if item.heat == "calienta":
            assert temp and temp.significant and temp.direction == "increasing"
        elif item.heat == "enfria":
            assert temp and temp.significant and temp.direction == "decreasing"
        else:
            assert temp is None or not temp.significant or temp.direction == "no_trend"
        assert item.analysis.provenance in {"REAL_DATA", "CACHED_DATA", "DATA_UNAVAILABLE"}
        assert not re.search(r"\d", re.sub(r"\b(19|20)\d{2}\b", "", item.context)), f"{item.id}: el contexto no lleva cifras salvo años"


def test_missing_value_stays_missing_not_zero():
    parsed = MissionsResponse.model_validate({"built_at": "2026-11-12T00:00:00Z", "method": "m", "missions": [_mission()]})
    assert parsed.missions[0].temperature.annual_series[1].value is None


def test_route_serves_missions():
    response = client.get("/api/v1/world/missions")
    assert response.status_code == 200
    assert response.json()["missions"]


def test_route_declares_unbuilt_missions(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(world, "load_missions", lambda: load_missions(tmp_path / "missing.json"))
    response = client.get("/api/v1/world/missions")
    assert response.status_code == 503
    assert "build_missions.py" in response.json()["detail"]


def test_store_rejects_invalid_coordinates(tmp_path: Path):
    path = tmp_path / "missions.json"
    path.write_text(json.dumps({"built_at": "2026-11-12T00:00:00Z", "method": "m", "missions": [_mission(latitude=120)]}), encoding="utf-8")
    try:
        load_missions(path)
    except ValueError:
        return
    raise AssertionError("Una latitud fuera de rango debía rechazarse")


def test_default_file_location():
    assert MISSIONS_FILE.parts[-3:] == ("data", "missions", "missions.json")


def test_terrain_route_serves_built_terrain():
    response = client.get("/api/v1/world/missions/nazca/terrain")
    assert response.status_code == 200
    body = response.json()
    assert body["grid"] in (200, 256) and body["relief_dm"] and body["cover"]
    assert body["sources"]


def test_terrain_route_rejects_bad_ids():
    assert client.get("/api/v1/world/missions/..%2Fsecret/terrain").status_code == 404
    assert client.get("/api/v1/world/missions/NO_EXISTE/terrain").status_code == 404
