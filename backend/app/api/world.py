from fastapi import APIRouter, HTTPException, Query

from ..connectors.http_json import JsonSourceError
from ..connectors.openmeteo.geocoding import SOURCE as GEOCODING_SOURCE
from ..connectors.openmeteo.geocoding import GeocodingConnector
from ..orchestration.world_alerts import world_alerts
from ..schemas.world import Place, PlaceSearchResponse, WorldAlertsResponse

router = APIRouter(prefix="/api/v1/world", tags=["world"])


@router.get("/alerts", response_model=WorldAlertsResponse)
async def alerts() -> WorldAlertsResponse:
    """Alertas naranja y roja de GDACS en el mundo (y las del Perú), cruzadas con los eventos abiertos de NASA EONET."""
    return await world_alerts()


@router.get("/places", response_model=PlaceSearchResponse)
async def places(q: str = Query(min_length=2, max_length=80, description="Nombre de una ciudad, región o lugar.")) -> PlaceSearchResponse:
    """Busca un lugar del mundo por nombre para ubicarlo como sitio de análisis."""
    try:
        found, provenance, stamp, stale = await GeocodingConnector().search(q.strip())
    except JsonSourceError as exc:
        raise HTTPException(status_code=502, detail=f"El buscador de lugares no respondió: {exc}") from exc
    return PlaceSearchResponse(query=q.strip(), places=[Place(**item) for item in found], source=GEOCODING_SOURCE, provenance=provenance, downloaded_at=stamp,
                               note=stale or "Solo ubica el sitio; no aporta datos al análisis.")
