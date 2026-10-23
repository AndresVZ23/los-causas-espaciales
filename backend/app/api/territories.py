"""Read-only endpoints for Peru's administrative territory selector."""

from fastapi import APIRouter, HTTPException, Query

from ..connectors.peru.admin_boundaries import (
    PeruTerritoryCatalog,
    TerritoryCatalogError,
    TerritoryNotFoundError,
)
from ..schemas.territory import (
    TerritoryGeometryResponse,
    TerritoryHierarchyResponse,
    TerritoryLevel,
    TerritorySearchResponse,
)

router = APIRouter(prefix="/api/v1/territories", tags=["territories"])


@router.get("/search", response_model=TerritorySearchResponse)
def search_territories(
    q: str = Query(min_length=1, max_length=120),
    level: TerritoryLevel | None = None,
    parent_ubigeo: str | None = Query(default=None, pattern=r"^\d{2}(\d{2})?$"),
    limit: int = Query(default=20, ge=1, le=100),
):
    try:
        return PeruTerritoryCatalog().search(q, level=level, parent_ubigeo=parent_ubigeo, limit=limit)
    except TerritoryCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/hierarchy", response_model=TerritoryHierarchyResponse)
def territory_hierarchy(parent_ubigeo: str | None = Query(default=None, pattern=r"^\d{2}(\d{2})?$")):
    try:
        return PeruTerritoryCatalog().hierarchy(parent_ubigeo)
    except TerritoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TerritoryCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{level}/{ubigeo}/geometry", response_model=TerritoryGeometryResponse)
def territory_geometry(level: TerritoryLevel, ubigeo: str):
    try:
        return PeruTerritoryCatalog().geometry(level, ubigeo)
    except TerritoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TerritoryCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
