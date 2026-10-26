from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response
from pydantic import ValidationError

from ..reports.executive_pdf import render_executive_pdf
from ..schemas.baseline import BaselineScreeningResponse
from ..schemas.climate import ClimateScreeningResponse
from ..schemas.screening import ScreeningEnvelope, Sector

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

MAX_SUBJECTS = 50
MAX_FINDINGS = 400
# Sectores cuyo reporte necesita sus propios campos además del sobre común.
SECTOR_SCHEMAS: dict[str, type[ScreeningEnvelope]] = {
    Sector.ENVIRONMENT: BaselineScreeningResponse, Sector.HERITAGE: BaselineScreeningResponse, Sector.HAZARDS: BaselineScreeningResponse,
    Sector.CLIMATE: ClimateScreeningResponse,   # sus extremos dicen si CHIRPS entró como fuente
}


@router.post(
    "/executive-pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "Reporte ejecutivo PDF del screening."}},
)
def executive_pdf(payload: dict[str, Any] = Body(..., description="Respuesta completa de un screening (sobre C2 y campos del sector).")) -> Response:
    """Genera el reporte ejecutivo de cualquier sector a partir del sobre común C2.

    La línea base (ambiente, amenazas y patrimonio) y Clima se validan con su esquema completo para conservar áreas,
    capas, vegetación y contrastes de lluvia; en los demás sectores los campos propios se ignoran. Es una función síncrona: FastAPI la ejecuta en su pool de
    hilos y no bloquea el bucle de eventos.
    """
    schema = SECTOR_SCHEMAS.get(str(payload.get("sector")), ScreeningEnvelope)
    try:
        envelope = schema.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"El cuerpo no cumple el contrato C2: {exc.error_count()} error(es) de validación.") from exc
    if len(envelope.subjects) > MAX_SUBJECTS or len(envelope.trend_findings) > MAX_FINDINGS:
        raise HTTPException(status_code=422, detail=f"El reporte admite hasta {MAX_SUBJECTS} sujetos y {MAX_FINDINGS} tendencias.")
    pdf = render_executive_pdf(envelope)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="reporte-ejecutivo-{envelope.sector}-{envelope.analysis_id}.pdf"'},
    )
