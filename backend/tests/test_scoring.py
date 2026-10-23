"""Puntaje multicriterio con casos calculados a mano (solo pruebas)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.schemas.analysis import Provenance
from backend.app.schemas.scoring import Criterion, Direction, ScorecardRequest, SubjectValues
from backend.app.scoring.multicriteria import build_scorecard, criterion_score


def _criterion(key, weight, worst, best, direction=Direction.HIGHER_IS_BETTER):
    return Criterion(key=key, label=key, unit="u", direction=direction, weight=weight, worst=worst, best=best,
                     provenance=Provenance.MODEL, basis="escala de prueba")


def test_reference_scale_clips_and_respects_direction():
    up = _criterion("a", 1, 0, 10)
    down = _criterion("b", 1, 10, 0, Direction.LOWER_IS_BETTER)
    assert criterion_score(up, 2.5) == 25 and criterion_score(up, -3) == 0 and criterion_score(up, 99) == 100
    assert criterion_score(down, 2.5) == 75
    assert criterion_score(up, None) is None


def test_weighted_sum_matches_hand_calculation():
    request = ScorecardRequest(
        criteria=[_criterion("a", 0.6, 0, 10), _criterion("b", 0.4, 0, 10)],
        subjects=[SubjectValues(subject="X", values={"a": 10, "b": 0}), SubjectValues(subject="Y", values={"a": 5, "b": 10})],
    )
    card = build_scorecard(request)
    scores = {item.subject: item.score for item in card.subjects}
    assert scores == {"X": 60.0, "Y": 70.0}            # X: 0.6·100; Y: 0.6·50 + 0.4·100
    assert card.leader == "Y"
    y = next(item for item in card.subjects if item.subject == "Y")
    assert [c.contribution for c in y.criteria] == [30.0, 40.0]
    assert sum(item.first_place_share for item in card.subjects) == pytest.approx(1.0)


def test_missing_value_renormalizes_weight_and_reports_coverage():
    request = ScorecardRequest(
        criteria=[_criterion("a", 0.5, 0, 10), _criterion("b", 0.5, 0, 10)],
        subjects=[SubjectValues(subject="X", values={"a": 8, "b": None})],
    )
    item = build_scorecard(request).subjects[0]
    assert item.score == 80.0 and item.coverage == 0.5
    assert item.criteria[1].score is None and item.criteria[1].contribution is None


def test_weight_sensitivity_detects_a_fragile_leader():
    # Con pesos iguales gana X por poco; al bajar el peso de «a» a la mitad gana Y.
    request = ScorecardRequest(
        criteria=[_criterion("a", 0.5, 0, 10), _criterion("b", 0.5, 0, 10)],
        subjects=[SubjectValues(subject="X", values={"a": 10, "b": 4}), SubjectValues(subject="Y", values={"a": 4, "b": 9})],
    )
    card = build_scorecard(request)
    assert card.leader == "X"
    a = next(item for item in card.weight_sensitivity if item.key == "a")
    assert a.leader_at_half == "Y" and a.changes_leader
    x = next(item for item in card.subjects if item.subject == "X")
    assert 0.2 < x.first_place_share < 0.9                 # liderazgo frágil: no gana en todas las combinaciones
    # X = 0.5·100 + 0.5·40 = 70; Y = 0.5·40 + 0.5·90 = 65 → margen 5: el empate lo decide la estabilidad.
    assert card.margin == 5.0 and card.tie == (x.first_place_share < 0.75)


def test_clear_leader_is_not_a_tie():
    request = ScorecardRequest(
        criteria=[_criterion("a", 0.5, 0, 10), _criterion("b", 0.5, 0, 10)],
        subjects=[SubjectValues(subject="X", values={"a": 9, "b": 9}), SubjectValues(subject="Y", values={"a": 3, "b": 4})],
    )
    card = build_scorecard(request)
    assert card.leader == "X" and card.margin == 55.0 and not card.tie


def test_invalid_requests_are_rejected():
    with pytest.raises(ValidationError, match="sumar 1"):
        ScorecardRequest(criteria=[_criterion("a", 0.7, 0, 10)], subjects=[SubjectValues(subject="X", values={"a": 1})])
    with pytest.raises(ValidationError, match="contradice"):
        _criterion("a", 1, 10, 0)   # mayor es mejor con la escala invertida


def test_scorecard_endpoint_recomputes_with_new_weights():
    body = {
        "criteria": [_criterion("a", 0.9, 0, 10).model_dump(mode="json"), _criterion("b", 0.1, 0, 10).model_dump(mode="json")],
        "subjects": [{"subject": "X", "values": {"a": 10, "b": 4}}, {"subject": "Y", "values": {"a": 4, "b": 9}}],
    }
    response = TestClient(app).post("/api/v1/scoring/scorecard", json=body)
    assert response.status_code == 200
    assert response.json()["leader"] == "X"
