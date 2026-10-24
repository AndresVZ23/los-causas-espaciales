"""HTTP contract for the K3 real-estate screening pilot."""

from fastapi import APIRouter, HTTPException

from ..connectors.nasa.power import PowerConnectorError
from ..schemas.real_estate import RealEstateScreeningRequest, RealEstateScreeningResponse
from ..sectors.real_estate import RealEstateScreeningError, run_real_estate_screening

router = APIRouter(prefix="/api/v1/projects", tags=["real-estate-pilot"])


@router.post("/real-estate-screening", response_model=RealEstateScreeningResponse)
async def real_estate_screening(request: RealEstateScreeningRequest) -> RealEstateScreeningResponse:
    """Compare polygons or IGN territories without presenting screening as property feasibility."""
    try:
        return await run_real_estate_screening(request)
    except RealEstateScreeningError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PowerConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
