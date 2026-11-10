"""El puntaje recalculado con la pendiente del segundo modelo de elevación, con casos calculados a mano."""

from datetime import datetime, timezone

from backend.app.orchestration.slope_check import LEAD, scorecard_with_slope_check, second_slope_note
from backend.app.schemas.analysis import Point, Provenance
from backend.app.schemas.scoring import Criterion, Direction, ScorecardRequest, SubjectValues
from backend.app.schemas.terrain import TerrainCrosscheck, TerrainMetrics, TerrainResponse, TerrainSiteResult
from backend.app.scoring.multicriteria import build_scorecard

WHEN = datetime(2026, 11, 10, tzinfo=timezone.utc)


def _criteria() -> list[Criterion]:
    # Pendiente de 0° a 20° (más pendiente, más prioridad) y un segundo criterio de 0 a 10, con pesos 0.5 y 0.5.
    return [
        Criterion(key="terrain_slope", label="Pendiente", unit="°", direction=Direction.HIGHER_IS_BETTER, weight=0.5, worst=0, best=20,
                  provenance=Provenance.MODEL, basis="escala de prueba"),
        Criterion(key="other", label="Otro", unit="u", direction=Direction.HIGHER_IS_BETTER, weight=0.5, worst=0, best=10,
                  provenance=Provenance.MODEL, basis="escala de prueba"),
    ]


def _terrain(slopes: dict[str, tuple[float | None, float | None]]) -> TerrainResponse:
    """Por sujeto: (pendiente NASADEM, pendiente Copernicus); None en la segunda deja el sitio sin contraste."""
    sites = []
    for label, (nasadem, copernicus) in slopes.items():
        site = TerrainSiteResult(location=Point(latitude=-17.0, longitude=-71.0, label=label), status="READY",
                                 metrics=TerrainMetrics(elevation_m=1000, slope_degrees=nasadem), granules=[], provenance=Provenance.CACHED, limitations=[])
        if copernicus is not None:
            site.crosscheck = TerrainCrosscheck(source="Copernicus GLO-30", elevation_m=1002, slope_degrees=copernicus,
                                                tile_url="https://example.invalid/tile.tif", provenance=Provenance.CACHED, downloaded_at=WHEN)
        sites.append(site)
    return TerrainResponse(generated_at=WHEN, sites=sites, note="Fixture controlado.")


def _request(values: dict[str, tuple[float | None, float]]) -> ScorecardRequest:
    return ScorecardRequest(criteria=_criteria(), subjects=[
        SubjectValues(subject=label, values={"terrain_slope": slope, "other": other}) for label, (slope, other) in values.items()])


def test_same_leader_with_second_model_reports_both_scores():
    # NASADEM: A = 0.5·90 + 0.5·20 = 55; B = 0.5·20 + 0.5·40 = 30. Copernicus: A = 0.5·60 + 10 = 40; B = 0.5·10 + 20 = 25.
    request = _request({"A": (18, 2), "B": (4, 4)})
    card = build_scorecard(request)
    note = second_slope_note(_terrain({"A": (18, 12), "B": (4, 2)}), request, card)
    assert card.leader == "A"
    assert note == f"{LEAD}el primer lugar no cambia: A (40.0) frente a B (25.0)."


def test_leader_change_is_stated_with_the_new_order():
    # NASADEM: A = 0.5·50 + 0.5·40 = 45; B = 0.5·30 + 0.5·50 = 40. Copernicus: A = 0.5·10 + 20 = 25; B = 0.5·25 + 25 = 37.5.
    request = _request({"A": (10, 4), "B": (6, 5)})
    card = build_scorecard(request)
    note = second_slope_note(_terrain({"A": (10, 2), "B": (6, 5)}), request, card)
    assert card.leader == "A"
    assert note.startswith(f"{LEAD}el primer lugar pasa de A a B: B (37.5) frente a A (25.0).")
    assert "topografía" in note


def test_no_note_when_a_scored_subject_lacks_the_second_model():
    request = _request({"A": (18, 2), "B": (4, 4)})
    card = build_scorecard(request)
    assert second_slope_note(_terrain({"A": (18, 12), "B": (4, None)}), request, card) is None
    assert second_slope_note(None, request, card) is None


def test_subject_without_nasadem_slope_keeps_its_gap():
    # C no tiene pendiente NASADEM: tampoco se le asigna la de Copernicus, para no cambiar la cobertura del puntaje.
    request = _request({"A": (18, 2), "B": (4, 4), "C": (None, 9)})
    card = build_scorecard(request)
    note = second_slope_note(_terrain({"A": (18, 12), "B": (4, 2), "C": (None, 15)}), request, card)
    # C: solo «other» = 90 con cobertura 0.5; sigue primero con ambos modelos.
    assert card.leader == "C"
    assert note == f"{LEAD}el primer lugar no cambia: C (90.0) frente a A (40.0)."


def test_single_subject_has_nothing_to_compare():
    request = _request({"A": (18, 2)})
    card = build_scorecard(request)
    assert second_slope_note(_terrain({"A": (18, 12)}), request, card) is None


def test_wrapper_appends_the_note_after_the_sector_notes():
    request = _request({"A": (18, 2), "B": (4, 4)})
    card = scorecard_with_slope_check(request, ["Nota del sector."], _terrain({"A": (18, 12), "B": (4, 2)}))
    assert card.notes[0] == "Nota del sector."
    assert card.notes[-1].startswith(LEAD)
    assert scorecard_with_slope_check(request, ["Nota del sector."], None).notes == ["Nota del sector."]
