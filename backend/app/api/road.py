"""HTTP contract for the K2 road-resilience screening pilot."""

from fastapi import APIRouter, HTTPException

from ..connectors.nasa.power import PowerConnectorError
from ..schemas.road import RoadScreeningRequest, RoadScreeningResponse
from ..sectors.road import RoadScreeningError, run_road_screening

router = APIRouter(prefix="/api/v1/projects", tags=["road-pilot"])


@router.post("/road-screening", response_model=RoadScreeningResponse)
async def road_screening(request: RoadScreeningRequest) -> RoadScreeningResponse:
    """Screen a road corridor without presenting exposure as engineering feasibility."""
    try:
        return await run_road_screening(request)
    except RoadScreeningError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PowerConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
