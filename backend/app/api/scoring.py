from fastapi import APIRouter

from ..schemas.scoring import Scorecard, ScorecardRequest
from ..scoring.multicriteria import build_scorecard

router = APIRouter(prefix="/api/v1/scoring", tags=["scoring"])


@router.post("/scorecard", response_model=Scorecard)
def scorecard(request: ScorecardRequest) -> Scorecard:
    """Recalcula el puntaje multicriterio con pesos o escalas editados; sin consultar fuentes externas."""
    return build_scorecard(request)
