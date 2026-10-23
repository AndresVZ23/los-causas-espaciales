from fastapi import APIRouter

from ..maplayers.catalog import map_layers
from ..schemas.map_layers import MapLayersResponse

router = APIRouter(prefix="/api/v1/map", tags=["map"])


@router.get("/layers", response_model=MapLayersResponse)
async def layers() -> MapLayersResponse:
    """Capas visuales NASA GIBS con su última fecha publicada, nivel de zoom y leyenda oficial."""
    return await map_layers()
