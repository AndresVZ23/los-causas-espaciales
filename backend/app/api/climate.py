from fastapi import APIRouter, HTTPException

from ..connectors.nasa.power import PowerConnectorError
from ..schemas.climate import ClimateScreeningRequest, ClimateScreeningResponse
from ..sectors.climate import run_climate_screening

router = APIRouter(prefix="/api/v1/projects", tags=["climate"])


@router.post("/climate-screening", response_model=ClimateScreeningResponse)
async def climate_screening(request: ClimateScreeningRequest) -> ClimateScreeningResponse:
    """Módulo 1: tendencias de variables NASA POWER y de extremos de precipitación ETCCDI por sitio."""
    try:
        return await run_climate_screening(request)
    except PowerConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
