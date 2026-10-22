from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..reports.executive_pdf import render_executive_pdf
from ..schemas.screening import ScreeningEnvelope

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

MAX_SUBJECTS = 50
MAX_FINDINGS = 400


@router.post(
    "/executive-pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "Reporte ejecutivo PDF del screening."}},
)
def executive_pdf(envelope: ScreeningEnvelope) -> Response:
    """Genera el reporte ejecutivo de cualquier sector a partir del sobre común C2.

    Acepta la respuesta completa de un screening (los campos propios del sector se ignoran). Es una función
    síncrona: FastAPI la ejecuta en su pool de hilos y no bloquea el bucle de eventos.
    """
    if len(envelope.subjects) > MAX_SUBJECTS or len(envelope.trend_findings) > MAX_FINDINGS:
        raise HTTPException(status_code=422, detail=f"El reporte admite hasta {MAX_SUBJECTS} sujetos y {MAX_FINDINGS} tendencias.")
    pdf = render_executive_pdf(envelope)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="reporte-ejecutivo-{envelope.sector}-{envelope.analysis_id}.pdf"'},
    )
