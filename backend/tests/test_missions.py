"""Misiones del modo jugador: contrato del archivo versionado y ruta de la API, sin red."""

import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api import world
from backend.app.main import app
from backend.app.missions.store import MISSIONS_FILE, TERRAIN_DIR, load_missions, load_terrain
from backend.app.orchestration.discoveries import ARTIFACT_RATIO, rainfall_discoveries
from backend.app.schemas.analysis import TrendResult
from backend.app.schemas.climate import AtypicalYear, ExtremeIndexSummary
from backend.app.schemas.missions import Mission, MissionsResponse, MissionTerrain
from backend.app.schemas.pipeline import Agreement
from backend.app.schemas.screening import DiscoveryKind

client = TestClient(app)
IMERG = "GPM IMERG (NASA POWER · IMERG_PRECTOT)"
BUILD_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "missions" / "build_missions.py"


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


# --- Campos que el contrato deriva de los valores crudos: unit, probable_artifact, heat_support y context_sources ---

# (índice, unidad, año, valor del reanálisis, valor del mismo año en cada producto de contraste)
ATYPICAL_CASES = [
    ("RX1DAY", "mm", 2020, 490.15, {IMERG: 38.45}),      # como Lago Poopó: el satélite ve la doceava parte
    ("RX1DAY", "mm", 2021, 342.63, {IMERG: 258.92}),     # como Zhengzhou: el satélite también registró el evento
    ("RX5DAY", "mm", 2022, 100.0, {IMERG: 20.0}),        # justo cinco veces: la regla pide superar, no igualar
    ("RX5DAY", "mm", 2023, 100.0, {IMERG: 19.9}),
    ("R95P", "mm", 2024, 100.0, {IMERG: 10.0, "CHIRPS (UCSB · NASA SERVIR)": 50.0}),   # un producto sí lo registra
    ("CDD", "días", 2011, 57.0, {IMERG: 5.0}),           # once veces más, pero son días de racha seca
]


def _extremes(cases) -> list[dict]:
    return [{"variable": variable, "label": variable, "unit": unit, "direction": "no_trend", "slope_per_year": 0.0, "significant": False}
            for variable, unit in dict.fromkeys((case[0], case[1]) for case in cases)]


def _flags(cases, **extra) -> list[dict]:
    return [{"variable": variable, "label": variable, "year": year, "value": value, "countercheck_values": others, **extra}
            for variable, _unit, year, value, others in cases]


def _platform_artifact_years(cases) -> set[int]:
    """Los años que la regla de la plataforma (rainfall_discoveries, ADR-036) declara artefacto probable."""
    trend = TrendResult(method="MK", direction="no_trend", slope_per_year=0.0, p_value=0.5, confidence_interval=None, significant=False,
                        valid_observations=25, interpretation="", limitations=[])
    by_index: dict[tuple[str, str], list[AtypicalYear]] = {}
    for variable, unit, year, value, others in cases:
        by_index.setdefault((variable, unit), []).append(AtypicalYear(year=year, value=value, robust_z=20, countercheck_values=others))
    indexes = [ExtremeIndexSummary(variable=variable, label=variable, description="", unit=unit, display_unit=unit, mean=20, minimum=1, maximum=600,
                                   valid_years=25, discarded_years=0, trend=trend, annual_series=[], atypical_years=years)
               for (variable, unit), years in by_index.items()]
    found = rainfall_discoveries([("Prueba", indexes)])
    return {int(re.search(r"\b(\d{4})\b", item.title).group(1)) for item in found if item.kind == DiscoveryKind.PROBABLE_ARTIFACT}


def test_artifact_rule_matches_platform_discoveries():
    # Los mismos años pasan por las dos vías: el juego no tiene una regla propia de «pista falsa».
    mission = Mission.model_validate(_mission(extremes=_extremes(ATYPICAL_CASES), flagged_extremes=_flags(ATYPICAL_CASES)))
    game = {flag.year for flag in mission.flagged_extremes if flag.probable_artifact}
    assert game == _platform_artifact_years(ATYPICAL_CASES) == {2020, 2023}
    assert {flag.year: flag.unit for flag in mission.flagged_extremes}[2011] == "días"


def test_file_cannot_declare_an_artifact_or_a_unit():
    # Aunque el archivo diga «mm» y «artefacto», valen los valores crudos: un índice en días nunca es artefacto.
    claimed = _flags(ATYPICAL_CASES, unit="mm", probable_artifact=True)
    mission = Mission.model_validate(_mission(extremes=_extremes(ATYPICAL_CASES), flagged_extremes=claimed))
    by_year = {flag.year: flag for flag in mission.flagged_extremes}
    assert by_year[2011].unit == "días" and by_year[2011].probable_artifact is False
    assert by_year[2021].probable_artifact is False and by_year[2020].probable_artifact is True


def test_missing_values_never_prove_an_artifact():
    cases = [
        ("RX1DAY", "mm", 2020, 490.15, {IMERG: None}),   # el contraste no tiene valor ese año: no es «cero lluvia»
        ("RX1DAY", "mm", 2021, None, {IMERG: 38.45}),
        ("RX1DAY", "mm", 2022, 490.15, {}),
    ]
    mission = Mission.model_validate(_mission(extremes=_extremes(cases), flagged_extremes=_flags(cases)))
    assert [flag.probable_artifact for flag in mission.flagged_extremes] == [False, False, False]
    # Un índice que no está en `extremes` no tiene unidad conocida: tampoco se asume «mm».
    orphan = Mission.model_validate(_mission(extremes=[], flagged_extremes=_flags(ATYPICAL_CASES[:1])))
    assert orphan.flagged_extremes[0].unit is None and orphan.flagged_extremes[0].probable_artifact is False


def test_versioned_file_artifacts_follow_platform_rule():
    data = load_missions()
    by_id = {item.id: item for item in data.missions}
    for item in data.missions:
        for flag in item.flagged_extremes:
            assert flag.unit in {"mm", "días"}, f"{item.id} {flag.variable}: unidad desconocida"
            others = list(flag.countercheck_values.values())
            exceeds = bool(others) and flag.value is not None and all(other is not None and other * ARTIFACT_RATIO < flag.value for other in others)
            assert flag.probable_artifact == (flag.unit == "mm" and exceeds), f"{item.id} {flag.variable} {flag.year}"

    def artifacts(mission_id: str) -> set[tuple[str, int]]:
        return {(flag.variable, flag.year) for flag in by_id[mission_id].flagged_extremes if flag.probable_artifact}

    assert ("RX1DAY", 2020) in artifacts("poopo") and ("RX1DAY", 2020) in artifacts("jacobabad")
    # Años atípicos que el satélite también registró, o que se miden en días: no son «pista falsa».
    for mission_id in ("zhengzhou", "derna", "chosica", "lahaina", "alejandria"):
        assert by_id[mission_id].flagged_extremes and not artifacts(mission_id), mission_id


HEAT_SUPPORT_BY_AGREEMENT = {"coincide": "confirmada", "contradice": "contradicha", "sin_respaldo": "una_fuente", "solo_contraste": "una_fuente",
                             "sin_tendencia": "una_fuente", None: "sin_segunda_fuente"}


def _with_agreement(agreement: str | None, **overrides) -> dict:
    mission = _mission(**overrides)
    mission["temperature"] = {**mission["temperature"], "second_source": {"source": "ERA5 (prueba)", "agreement": agreement, "period": "2005-2023"}}
    return mission


@pytest.mark.parametrize(("agreement", "expected"), HEAT_SUPPORT_BY_AGREEMENT.items())
def test_heat_support_follows_second_source(agreement, expected):
    assert Mission.model_validate(_with_agreement(agreement)).heat_support == expected


def test_heat_support_covers_every_agreement_code_and_edge_cases():
    # Si la plataforma agrega un código de acuerdo, esta prueba obliga a decidir cómo lo lee el juego.
    assert {item.value for item in Agreement} == {code for code in HEAT_SUPPORT_BY_AGREEMENT if code}
    assert Mission.model_validate(_mission()).heat_support == "sin_segunda_fuente"                      # sin contraste con ERA5
    assert Mission.model_validate(_with_agreement("coincide", heat="sin_evidencia")).heat_support is None
    # Lo que diga el archivo no cuenta: se deriva del código de acuerdo.
    assert Mission.model_validate(_with_agreement("sin_respaldo", heat_support="confirmada")).heat_support == "una_fuente"


def test_versioned_file_heat_support_is_consistent():
    for item in load_missions().missions:
        assert (item.heat_support is None) == (item.heat == "sin_evidencia"), item.id
        second = item.temperature.second_source if item.temperature else None
        if item.heat_support == "confirmada":
            assert second and second.agreement == "coincide", item.id


def test_context_sources_default_empty_and_validated():
    assert Mission.model_validate(_mission()).context_sources == []
    source = {"title": "Fuente de prueba", "url": "https://example.org/lugar"}
    assert Mission.model_validate(_mission(context_sources=[source])).context_sources[0].url == source["url"]
    with pytest.raises(ValueError):
        Mission.model_validate(_mission(context_sources=[{"title": "Sin enlace", "url": "example.org/lugar"}]))


def test_route_serves_derived_fields():
    missions = client.get("/api/v1/world/missions").json()["missions"]
    for item in missions:
        assert "heat_support" in item and isinstance(item["context_sources"], list)
        for flag in item["flagged_extremes"]:
            assert flag["unit"] in {"mm", "días"} and isinstance(flag["probable_artifact"], bool)
    poopo = next(item for item in missions if item["id"] == "poopo")
    assert any(flag["probable_artifact"] and flag["variable"] == "RX1DAY" and flag["year"] == 2020 for flag in poopo["flagged_extremes"])
    assert {item["heat_support"] for item in missions} <= {None, "confirmada", "contradicha", "una_fuente", "sin_segunda_fuente"}


# --- Terreno: contrato tipado sobre lo que ya hay, sin cambiar la respuesta ---

def test_every_built_terrain_matches_contract():
    files = sorted(TERRAIN_DIR.glob("*.json"))
    assert files, "Faltan los terrenos en backend/data/missions/terrain"
    for path in files:
        terrain = MissionTerrain.model_validate_json(path.read_text(encoding="utf-8"))
        assert terrain.id == path.stem


def test_terrain_is_served_exactly_as_built():
    on_disk = json.loads((TERRAIN_DIR / "nazca.json").read_text(encoding="utf-8"))
    assert load_terrain("nazca") == on_disk
    assert client.get("/api/v1/world/missions/nazca/terrain").json() == on_disk


def test_truncated_terrain_is_rejected(tmp_path: Path):
    terrain = json.loads((TERRAIN_DIR / "nazca.json").read_text(encoding="utf-8"))
    terrain["relief_dm"] = terrain["relief_dm"][:-8]
    (tmp_path / "nazca.json").write_text(json.dumps(terrain), encoding="utf-8")
    with pytest.raises(ValueError, match="relief_dm"):
        load_terrain("nazca", tmp_path)


# --- Guion scripts/missions/build_missions.py, sin red ---

@pytest.fixture
def build_script(monkeypatch, tmp_path: Path):
    """El guion cargado como módulo, escribiendo en una copia del archivo versionado."""
    spec = importlib.util.spec_from_file_location("build_missions_script", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    copy = tmp_path / "missions.json"
    copy.write_bytes(MISSIONS_FILE.read_bytes())
    monkeypatch.setattr(module, "OUT", copy)
    monkeypatch.setattr(module, "ROOT", tmp_path)

    def no_network(*args, **kwargs):
        raise AssertionError("La prueba no debe llamar a la API")

    monkeypatch.setattr(module, "call", no_network)
    return module


def _screening_response() -> dict:
    """Respuesta mínima de /projects/climate-screening con un año atípico en mm y otro en días."""
    source = {"dataset": "NASA POWER Daily Point", "version": "v2.10.3", "downloaded_at": "2026-11-13T10:00:00Z", "provenance": "REAL_DATA",
              "source_url": "https://power.larc.nasa.gov"}
    temperature = {"variable": "T2M", "label": "Temperatura del aire a 2 m", "display_unit": "°C", "mean": 20.0, "adjusted_p_value": 0.01,
                   "significant_after_bh": True, "annual_series": [{"year": 2001, "value": 19.8}], "source": source,
                   "trend": {"direction": "increasing", "slope_per_year": 0.03, "confidence_interval": [0.01, 0.05], "valid_observations": 25},
                   "counterchecks": [{"source": "ERA5 (prueba)", "agreement": "sin_respaldo", "period": "2005-2023"}]}

    def extreme(variable: str, unit: str, value: float, other: float) -> dict:
        return {"variable": variable, "label": variable, "display_unit": unit, "significant_after_bh": False,
                "trend": {"direction": "no_trend", "slope_per_year": 0.0},
                "atypical_years": [{"year": 2020, "value": value, "countercheck_values": {IMERG: other}}]}

    return {"analysis_id": "nuevo", "generated_at": "2026-11-13T10:00:00Z", "period": "2001-01-01/2026-11-11",
            "sites": [{"variables": [temperature], "extremes": [extreme("RX1DAY", "mm", 490.15, 38.45), extreme("CDD", "días", 57.0, 5.0)]}]}


def test_versioned_file_has_the_script_texts(build_script):
    # Si esta prueba falla, alguien cambió un texto o una fuente en el guion y no corrió: build_missions.py --textos
    build_script.reapply_texts([])
    assert json.loads(build_script.OUT.read_text(encoding="utf-8")) == json.loads(MISSIONS_FILE.read_text(encoding="utf-8"))


def test_texts_mode_changes_only_script_fields(build_script, monkeypatch):
    before = json.loads(build_script.OUT.read_text(encoding="utf-8"))
    source = {"title": "Fuente de prueba", "url": "https://example.org/nazca"}
    monkeypatch.setattr(build_script, "CONTEXT_SOURCES", {"nazca": [source]})
    monkeypatch.setattr(build_script, "PLACES", [(*place[:6], "Contexto nuevo.", place[7]) if place[0] == "nazca" else place for place in build_script.PLACES])
    build_script.reapply_texts([])
    after = json.loads(build_script.OUT.read_text(encoding="utf-8"))
    assert after["built_at"] == before["built_at"]
    static = {"continent", "country", "name", "context", "context_sources", "not_measured", "scale", "hazard"}
    for old, new in zip(before["missions"], after["missions"], strict=True):
        assert {key: value for key, value in new.items() if key not in static} == {key: value for key, value in old.items() if key not in static}
    nazca = next(item for item in after["missions"] if item["id"] == "nazca")
    assert nazca["context"] == "Contexto nuevo." and nazca["context_sources"] == [source]
    assert all(item["context_sources"] == [] for item in after["missions"] if item["id"] != "nazca")
    MissionsResponse.model_validate(after)


def test_every_context_has_verified_sources():
    # Las fuentes de contexto se verificaron abriendo cada página (13-nov-2026): toda misión lleva una o dos, con título y enlace https.
    for item in load_missions().missions:
        assert 1 <= len(item.context_sources) <= 2, f"{item.id}: fuentes de contexto"
        assert all(source.title.strip() and source.url.startswith("https://") for source in item.context_sources)


def test_method_names_only_the_contrast_products_in_the_file():
    method = json.loads(MISSIONS_FILE.read_text(encoding="utf-8"))["method"]
    products = {source for item in load_missions().missions for flag in item.flagged_extremes for source in flag.countercheck_values}
    assert all(product in method for product in products)
    for name in ("IMERG", "CHIRPS"):
        assert (name in method) == any(name in product for product in products), f"«method» y las marcas no dicen lo mismo de {name}"


def test_partial_rebuild_keeps_other_analyses(build_script, monkeypatch):
    before = json.loads(build_script.OUT.read_text(encoding="utf-8"))
    monkeypatch.setattr(build_script, "call", lambda path, body: _screening_response())
    build_script.main(["nazca"])
    after = json.loads(build_script.OUT.read_text(encoding="utf-8"))
    assert after["built_at"] != before["built_at"]            # fecha de esta escritura
    for old, new in zip(before["missions"], after["missions"], strict=True):
        if old["id"] != "nazca":
            assert new == old                                   # las conservadas mantienen su análisis y su fecha
    nazca = next(item for item in after["missions"] if item["id"] == "nazca")
    # Una misión reconstruida lleva las fuentes de contexto del guion, igual que las demás.
    assert nazca["analysis"]["analysis_id"] == "nuevo" and nazca["context_sources"] == build_script.CONTEXT_SOURCES.get("nazca", [])
    assert {flag["variable"]: flag["unit"] for flag in nazca["flagged_extremes"]} == {"RX1DAY": "mm", "CDD": "días"}
    served = next(item for item in MissionsResponse.model_validate(after).missions if item.id == "nazca")
    assert served.heat_support == "una_fuente"
    assert {flag.variable: flag.probable_artifact for flag in served.flagged_extremes} == {"RX1DAY": True, "CDD": False}


def test_failed_rebuild_leaves_file_untouched(build_script):
    before = build_script.OUT.read_bytes()
    build_script.main(["nazca"])                                # la API «falla»: no hay análisis nuevo
    assert build_script.OUT.read_bytes() == before              # ni siquiera se renueva built_at
