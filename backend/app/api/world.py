from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..connectors.http_json import JsonSourceError
from ..connectors.openmeteo.geocoding import SOURCE as GEOCODING_SOURCE
from ..connectors.openmeteo.geocoding import GeocodingConnector
from ..missions.store import load_missions, load_terrain
from ..orchestration.world_alerts import world_alerts
from ..schemas.world import Place, PlaceSearchResponse, WorldAlertsResponse
from ..schemas.missions import MissionsResponse
from ..schemas.zones import Zone, ZoneSummary
from ..zones.store import get_zone, list_zones

router = APIRouter(prefix="/api/v1/world", tags=["world"])


@router.get("/missions", response_model=MissionsResponse)
def missions() -> MissionsResponse:
    """Misiones del modo jugador: lugares del mundo con su tendencia climática real (NASA POWER y su segunda fuente)."""
    found = load_missions()
    if found is None:
        raise HTTPException(status_code=503, detail="Las misiones todavía no están construidas. Ejecuta scripts/missions/build_missions.py con la API encendida.")
    return found


@router.get("/missions/{mission_id}/terrain")
def mission_terrain(mission_id: str) -> JSONResponse:
    """Terreno 3D de una misión: relieve Copernicus DEM GLO-30 (decímetros sobre el punto más bajo) y cobertura ESA WorldCover."""
    found = load_terrain(mission_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Ese terreno no está construido. Ejecuta scripts/missions/build_terrain.py.")
    return JSONResponse(found, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/zones", response_model=list[ZoneSummary])
def zones() -> list[ZoneSummary]:
    """Zonas que se pueden recorrer como maqueta en bloques (ADR-047)."""
    return list_zones()


@router.get("/zones/{zone_id}", response_model=Zone)
def zone(zone_id: str) -> Zone:
    """Maqueta de una zona: relieve Copernicus DEM, cobertura ESA WorldCover y balizas con lo que la plataforma sabe del lugar."""
    found = get_zone(zone_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Esa zona no está construida. Las disponibles están en /api/v1/world/zones.")
    return found


@router.get("/alerts", response_model=WorldAlertsResponse)
async def alerts() -> WorldAlertsResponse:
    """Alertas naranja y roja de GDACS en el mundo (y las del Perú), cruzadas con los eventos abiertos de NASA EONET."""
    return await world_alerts()


@router.get("/places", response_model=PlaceSearchResponse)
async def places(q: str = Query(min_length=2, max_length=80, description="Nombre de una ciudad, región o lugar.")) -> PlaceSearchResponse:
    """Busca un lugar del mundo por nombre para ubicarlo como sitio de análisis."""
    # La longitud mínima se exige sobre el texto sin espacios: una consulta en blanco no debe llegar al proveedor.
    text = q.strip()
    if len(text) < 2:
        raise HTTPException(status_code=422, detail="Escriba al menos dos letras del nombre del lugar.")
    try:
        found, provenance, stamp, stale = await GeocodingConnector().search(text)
    except JsonSourceError as exc:
        raise HTTPException(status_code=502, detail=f"El buscador de lugares no respondió: {exc}") from exc
    return PlaceSearchResponse(query=text, places=[Place(**item) for item in found], source=GEOCODING_SOURCE, provenance=provenance, downloaded_at=stamp,
                               note=stale or "Solo ubica el sitio; no aporta datos al análisis.")
