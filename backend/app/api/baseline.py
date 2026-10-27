from fastapi import APIRouter, HTTPException

from ..schemas.baseline import BaselineRequest, BaselineScreeningResponse
from ..schemas.screening import Sector
from ..sectors.baseline import BaselineScreeningError, run_baseline_screening

router = APIRouter(prefix="/api/v1/projects", tags=["baseline"])


async def _run(request: BaselineRequest, sector: Sector) -> BaselineScreeningResponse:
    try:
        return await run_baseline_screening(request, sector)
    except BaselineScreeningError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/environment-screening", response_model=BaselineScreeningResponse)
async def environment_screening(request: BaselineRequest) -> BaselineScreeningResponse:
    """Módulo 4: línea base ambiental (medios físico y biológico) con vegetación MODIS y capas oficiales."""
    return await _run(request, Sector.ENVIRONMENT)


@router.post("/hazards-screening", response_model=BaselineScreeningResponse)
async def hazards_screening(request: BaselineRequest) -> BaselineScreeningResponse:
    """Módulo 3: amenazas naturales con extremos de lluvia (NASA POWER, GPM IMERG y CHIRPS), relieve, capas de riesgo de CENEPRED y ANA y
    deslizamientos de NASA (susceptibilidad global, LHASA y COOLR) cruzados con CENEPRED."""
    return await _run(request, Sector.HAZARDS)


@router.post("/heritage-screening", response_model=BaselineScreeningResponse)
async def heritage_screening(request: BaselineRequest) -> BaselineScreeningResponse:
    """Módulo 5: patrimonio arqueológico, antecedentes y consulta previa (medio sociocultural)."""
    return await _run(request, Sector.HERITAGE)
