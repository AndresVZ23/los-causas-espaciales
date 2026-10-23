"""Backend-only endpoints for asynchronous EO tasks and official territorial labels."""

from fastapi import APIRouter, HTTPException, Response

from ..connectors.energy.coes import COESConnector, COESConnectorError
from ..connectors.nasa.appeears import AppEEARSConnector, AppEEARSConnectorError
from ..connectors.peru.territory import TerritoryConnector, TerritoryConnectorError
from ..schemas.data_sources import (
    AppEEARSAreaTaskRequest,
    AppEEARSBundleResponse,
    AppEEARSPointTaskRequest,
    AppEEARSTaskResponse,
    COESMonthlyRequest,
    COESMonthlyResponse,
    TerritorialQueryRequest,
    TerritorialQueryResponse,
)

router = APIRouter(prefix="/api/v1", tags=["official-data-sources"])


@router.post("/earthdata/appeears/tasks/point", response_model=AppEEARSTaskResponse)
async def submit_appeears_point(request: AppEEARSPointTaskRequest):
    try:
        return await AppEEARSConnector().submit_points(request)
    except AppEEARSConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/earthdata/appeears/tasks/area", response_model=AppEEARSTaskResponse)
async def submit_appeears_area(request: AppEEARSAreaTaskRequest):
    try:
        return await AppEEARSConnector().submit_area(request)
    except AppEEARSConnectorError as exc:
        raise HTTPException(status_code=422 if "Polygon" in str(exc) else 502, detail=str(exc)) from exc


@router.get("/earthdata/appeears/tasks/{task_id}", response_model=AppEEARSTaskResponse)
async def get_appeears_task(task_id: str):
    try:
        return await AppEEARSConnector().task(task_id)
    except AppEEARSConnectorError as exc:
        raise HTTPException(status_code=422 if "task_id" in str(exc) else 502, detail=str(exc)) from exc


@router.get("/earthdata/appeears/tasks/{task_id}/bundle", response_model=AppEEARSBundleResponse)
async def get_appeears_bundle(task_id: str):
    try:
        return await AppEEARSConnector().bundle(task_id)
    except AppEEARSConnectorError as exc:
        raise HTTPException(status_code=422 if "task_id" in str(exc) else 502, detail=str(exc)) from exc


@router.get("/earthdata/appeears/tasks/{task_id}/bundle/{file_id}", response_class=Response)
async def download_appeears_file(task_id: str, file_id: str):
    try:
        result = await AppEEARSConnector().download(task_id, file_id)
    except AppEEARSConnectorError as exc:
        raise HTTPException(status_code=422 if "inválido" in str(exc) or "pertenece" in str(exc) else 502, detail=str(exc)) from exc
    media_types = {"csv": "text/csv", "json": "application/json", "xml": "application/xml", "txt": "text/plain"}
    return Response(
        content=result.content,
        media_type=media_types.get(result.file_type, "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{result.file_name}"',
            "X-Data-Provenance": result.provenance.value,
            "X-Source-SHA256": result.sha256,
        },
    )


@router.post("/territory/query", response_model=TerritorialQueryResponse)
async def query_territory(request: TerritorialQueryRequest):
    try:
        return await TerritoryConnector().query(request)
    except TerritoryConnectorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/energy/coes/monthly-generation", response_model=COESMonthlyResponse)
async def coes_monthly_generation(request: COESMonthlyRequest):
    try:
        return await COESConnector().monthly_generation(request)
    except COESConnectorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
