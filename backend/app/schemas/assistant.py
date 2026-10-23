"""Contrato del asistente (C4): pregunta sobre un análisis ya calculado y respuesta trazable."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AssistantMode(StrEnum):
    GEMINI = "gemini"
    RULES = "reglas"


class AssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    envelope: dict[str, Any] = Field(description="Respuesta completa de un sector (sobre C2); es el único contexto del asistente.")
    use_gemini: bool = Field(default=False, description="Solo a pedido: Gemini consume la cuota de la clave del usuario.")


class AssistantStatus(BaseModel):
    gemini_available: bool


class AssistantResponse(BaseModel):
    answer: str
    mode: AssistantMode
    model: str | None = None
    citations: list[str] = Field(default_factory=list, description="Campos del análisis en que se apoya la respuesta.")
    notice: str | None = Field(default=None, description="Por qué se usó el modo reglas o qué no se pudo verificar.")
