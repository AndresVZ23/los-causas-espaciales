from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ..assistant.service import ask
from ..core.config import get_settings
from ..schemas.assistant import AssistantRequest, AssistantResponse, AssistantStatus

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.get("/status", response_model=AssistantStatus)
def assistant_status() -> AssistantStatus:
    """Indica si hay clave de Gemini para ofrecer la opción; no la valida ni gasta cuota."""
    return AssistantStatus(gemini_available=bool(get_settings().gemini_api_key))


@router.post("/ask", response_model=AssistantResponse)
async def ask_assistant(request: AssistantRequest) -> AssistantResponse:
    """Responde una pregunta usando solo el análisis recibido; Gemini si hay clave, reglas si no o si falla."""
    try:
        return await ask(request)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="El contexto no es un análisis válido del contrato C2.") from exc
