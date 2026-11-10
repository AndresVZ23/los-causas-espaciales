"""Qué le pasa al puntaje si la pendiente la da el segundo modelo de elevación.

Cuatro sectores puntúan la pendiente de NASADEM en el punto representativo. `extract_terrain` ya trae la del mismo punto
en Copernicus GLO-30: aquí se recalcula el puntaje con ella y se dice, en una nota, si el primer lugar cambia. Funciones
puras; la nota se calcula con los pesos iniciales del sector y lo declara, porque el usuario puede editarlos después.
"""

from collections.abc import Sequence

from ..schemas.scoring import Scorecard, ScorecardRequest, SubjectValues
from ..schemas.terrain import TerrainResponse
from ..scoring.multicriteria import build_scorecard

SLOPE_KEY = "terrain_slope"
LEAD = "Segundo modelo de elevación: con la pendiente de Copernicus GLO-30 en lugar de la de NASADEM y los pesos iniciales, "


def second_slope_note(terrain: TerrainResponse | None, request: ScorecardRequest, card: Scorecard, key: str = SLOPE_KEY) -> str | None:
    """Nota con el resultado del puntaje recalculado, o None si no hay con qué comparar.

    No se compara si falta el contraste en algún sujeto que sí tiene pendiente (mezclar modelos no dice nada) ni con
    menos de dos sujetos con puntaje.
    """
    checks = {site.location.label: site.crosscheck.slope_degrees for site in (terrain.sites if terrain else [])
              if site.crosscheck is not None and site.crosscheck.slope_degrees is not None}
    scored = [row.subject for row in request.subjects if row.values.get(key) is not None]
    if card.leader is None or not scored or any(subject not in checks for subject in scored):
        return None
    rows = [SubjectValues(subject=row.subject, values={**row.values, key: checks[row.subject]} if row.subject in scored else row.values)
            for row in request.subjects]
    other = build_scorecard(ScorecardRequest(criteria=request.criteria, subjects=rows))
    ranked = sorted((item for item in other.subjects if item.score is not None), key=lambda item: item.score, reverse=True)
    if other.leader is None or len(ranked) < 2:
        return None
    first, second = ranked[0], ranked[1]
    if other.leader == card.leader:
        return f"{LEAD}el primer lugar no cambia: {first.subject} ({first.score:.1f}) frente a {second.subject} ({second.score:.1f})."
    return (f"{LEAD}el primer lugar pasa de {card.leader} a {other.leader}: {first.subject} ({first.score:.1f}) frente a "
            f"{second.subject} ({second.score:.1f}). El orden depende del modelo de elevación: resolverlo con topografía antes de decidir.")


def scorecard_with_slope_check(request: ScorecardRequest, notes: Sequence[str], terrain: TerrainResponse | None, key: str = SLOPE_KEY) -> Scorecard:
    """El puntaje del sector más la nota del segundo modelo de elevación, cuando hay contraste."""
    card = build_scorecard(request, notes)
    note = second_slope_note(terrain, request, card, key)
    if note:
        card.notes.append(note)
    return card
