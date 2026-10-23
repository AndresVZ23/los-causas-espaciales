"""Backend-only K1 endpoint for point, corridor, polygon and territory sampling."""

from fastapi import APIRouter, HTTPException

from ..connectors.nasa.power_regional import RegionalPowerConnector, RegionalPowerError
from ..schemas.spatial_sampling import SpatialSamplingRequest, SpatialSamplingResponse

router = APIRouter(prefix="/api/v1/spatial-sampling", tags=["spatial-sampling"])


@router.post("/power/daily", response_model=SpatialSamplingResponse)
async def sample_power_daily(request: SpatialSamplingRequest):
    try:
        return await RegionalPowerConnector().sample(request)
    except RegionalPowerError as exc:
        raise HTTPException(status_code=422 if "geometr" in str(exc).lower() or "extensión" in str(exc).lower() else 502, detail=str(exc)) from exc
