"""Asistente C4: Gemini acotado al análisis, con verificación de cifras y modo reglas de respaldo."""

import httpx

from ..core.config import get_settings
from ..schemas.assistant import AssistantMode, AssistantRequest, AssistantResponse
from ..schemas.screening import ScreeningEnvelope
from .context import answer_by_rules, build_context, context_text, ungrounded_numbers
from .gemini import GeminiError, generate


def _split_sources(text: str) -> tuple[str, list[str]]:
    """Separa la línea «Fuentes:» que exige el prompt y la convierte en citas."""
    lines = text.strip().splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip().lower().lstrip("*").startswith("fuentes:"):
            raw = lines[index].split(":", 1)[1]
            citations = [item.strip(" .*`") for item in raw.replace(";", ",").split(",") if item.strip(" .*`")]
            return "\n".join(lines[:index]).strip(), citations
    return text.strip(), []


def _rules(question: str, context: dict, notice: str | None) -> AssistantResponse:
    answer, citations = answer_by_rules(question, context)
    return AssistantResponse(answer=answer, mode=AssistantMode.RULES, citations=citations, notice=notice)


async def ask(request: AssistantRequest) -> AssistantResponse:
    ScreeningEnvelope.model_validate(request.envelope)  # el contexto debe ser un análisis real del contrato C2
    context = build_context(request.envelope)
    text = context_text(context)
    settings = get_settings()
    if not request.use_gemini:
        # Modo por defecto, sin costo ni llamadas externas.
        return _rules(request.question, context, None)
    if not settings.gemini_api_key:
        return _rules(request.question, context, "Gemini no está configurado (falta GEMINI_API_KEY); respuesta en modo reglas.")
    try:
        raw, model = await generate(settings.gemini_api_key, settings.gemini_model, request.question, text)
    except (GeminiError, httpx.HTTPError) as exc:
        return _rules(request.question, context, f"Gemini no respondió ({exc}); respuesta en modo reglas.")
    answer, citations = _split_sources(raw)
    missing = ungrounded_numbers(answer, text)
    if missing:
        shown = ", ".join(f"{value:g}" for value in missing[:4])
        return _rules(request.question, context, f"Gemini citó cifras que no están en el análisis ({shown}); se descartó su respuesta y se usa el modo reglas.")
    return AssistantResponse(answer=answer, mode=AssistantMode.GEMINI, model=model, citations=citations)
