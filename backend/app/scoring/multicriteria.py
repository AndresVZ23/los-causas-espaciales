"""Puntaje multicriterio transparente: escala de referencia declarada, pesos explícitos, cobertura y estabilidad.

Suma ponderada simple (WSM) sobre puntajes 0–100 en una escala fija por criterio, no relativa entre sujetos: con dos
sitios, una normalización mín–máx daría siempre 0 y 100. Un criterio sin dato sale del cálculo de ese sujeto y su peso
se reparte entre los demás; la cobertura lo deja a la vista. Funciones puras.
"""

from collections.abc import Sequence

import numpy as np

from ..schemas.scoring import Criterion, CriterionScore, Scorecard, ScorecardRequest, SubjectScore, SubjectValues, WeightSensitivity

STABILITY_DRAWS = 2000
STABILITY_CONCENTRATION = 20.0  # Dirichlet α = peso × 20: las combinaciones giran alrededor de los pesos del usuario
SEED = 20261107
# Empate práctico: diferencia menor que 5 puntos o un líder que no gana en 3 de cada 4 combinaciones de pesos.
TIE_POINTS = 5.0
STABLE_SHARE = 0.75
METHOD = (
    "Suma ponderada de puntajes 0–100. Cada criterio se lleva a 0–100 con una escala de referencia declarada "
    "(peor valor = 0, mejor valor = 100, con recorte fuera del rango). Sin dato, el criterio sale y su peso se reparte "
    f"entre los demás. Estabilidad: {STABILITY_DRAWS:,} combinaciones de pesos Dirichlet centradas en los pesos elegidos. "
    f"Empate práctico: menos de {TIE_POINTS:g} puntos entre el primero y el segundo, o un primero que gana en menos del "
    f"{STABLE_SHARE * 100:.0f} % de las combinaciones."
)


def criterion_score(criterion: Criterion, value: float | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    fraction = (value - criterion.worst) / (criterion.best - criterion.worst)
    return float(np.clip(fraction, 0.0, 1.0) * 100)


def _scores_matrix(criteria: Sequence[Criterion], subjects: Sequence[SubjectValues]) -> np.ndarray:
    """Matriz sujetos × criterios con NaN donde falta el dato."""
    return np.array([[np.nan if (s := criterion_score(c, subject.values.get(c.key))) is None else s for c in criteria] for subject in subjects])


def weighted(scores: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Puntaje total por sujeto y cobertura de peso; los pesos se renormalizan sobre los criterios con dato."""
    available = ~np.isnan(scores)
    covered = (available * weights).sum(axis=1)
    totals = np.where(available, scores, 0.0) @ weights
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.where(covered > 0, totals / covered, np.nan)
    return result, covered


def _leader(labels: Sequence[str], totals: np.ndarray) -> str | None:
    if np.all(np.isnan(totals)):
        return None
    return labels[int(np.nanargmax(totals))]


def build_scorecard(request: ScorecardRequest, notes: Sequence[str] = ()) -> Scorecard:
    criteria, subjects = request.criteria, request.subjects
    labels = [subject.subject for subject in subjects]
    weights = np.array([criterion.weight for criterion in criteria], dtype=float)
    scores = _scores_matrix(criteria, subjects)
    totals, coverage = weighted(scores, weights)

    rng = np.random.default_rng(SEED)
    alpha = np.maximum(weights, 1e-3) * STABILITY_CONCENTRATION
    draws = rng.dirichlet(alpha, size=STABILITY_DRAWS)  # combinaciones × criterios
    available = ~np.isnan(scores)
    with np.errstate(invalid="ignore", divide="ignore"):
        draw_totals = (draws @ np.where(available, scores, 0.0).T) / (draws @ available.T)  # combinaciones × sujetos
    valid_rows = ~np.all(np.isnan(draw_totals), axis=1)
    winners = np.nanargmax(np.where(np.isnan(draw_totals[valid_rows]), -np.inf, draw_totals[valid_rows]), axis=1)
    wins = np.bincount(winners, minlength=len(subjects)).astype(float)

    order = [index for index in np.argsort(-np.nan_to_num(totals, nan=-1.0)) if not np.isnan(totals[index])]
    ranks = {int(index): position + 1 for position, index in enumerate(order)}
    leader = _leader(labels, totals)

    sensitivity = []
    for position, criterion in enumerate(criteria):
        leaders = []
        for factor in (0.5, 1.5):
            varied = weights.copy()
            varied[position] *= factor
            varied /= varied.sum()
            leaders.append(_leader(labels, weighted(scores, varied)[0]))
        sensitivity.append(WeightSensitivity(key=criterion.key, leader_at_half=leaders[0], leader_at_one_and_half=leaders[1],
                                             changes_leader=any(item != leader for item in leaders)))

    subject_scores = []
    for row, subject in enumerate(subjects):
        covered = coverage[row]
        items = []
        for column, criterion in enumerate(criteria):
            score = scores[row, column]
            present = not np.isnan(score)
            items.append(CriterionScore(
                key=criterion.key, value=subject.values.get(criterion.key),
                score=round(float(score), 1) if present else None,
                contribution=round(float(score * criterion.weight / covered), 1) if present and covered > 0 else None,
            ))
        subject_scores.append(SubjectScore(
            subject=subject.subject, score=None if np.isnan(totals[row]) else round(float(totals[row]), 1),
            coverage=round(float(covered), 4), rank=ranks.get(row), first_place_share=round(float(wins[row] / STABILITY_DRAWS), 4), criteria=items,
        ))
    ranked = sorted((item for item in subject_scores if item.score is not None), key=lambda item: item.score, reverse=True)
    margin = round(ranked[0].score - ranked[1].score, 1) if len(ranked) > 1 else None
    tie = margin is not None and (margin < TIE_POINTS or ranked[0].first_place_share < STABLE_SHARE)
    return Scorecard(method=METHOD, criteria=list(criteria), subjects=subject_scores, leader=leader, margin=margin, tie=tie,
                     stability_draws=STABILITY_DRAWS, weight_sensitivity=sensitivity, notes=list(notes))
