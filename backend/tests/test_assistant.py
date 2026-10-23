"""Asistente C4: modo reglas sobre análisis sintéticos, verificación de cifras y Gemini simulado (sin red)."""

import asyncio
import json

import pytest

from backend.app.assistant import service
from backend.app.assistant.context import answer_by_rules, build_context, context_text, ungrounded_numbers
from backend.app.orchestration import extraction
from backend.app.schemas.assistant import AssistantMode, AssistantRequest
from backend.app.sectors import climate, solar
from backend.tests.test_climate import _request as climate_request
from backend.tests.test_solar import FakePowerConnector, MetadataOnlyNasadem, _request as solar_request


@pytest.fixture(scope="module")
def envelopes():
    patch = pytest.MonkeyPatch()
    patch.setattr(extraction, "PowerConnector", FakePowerConnector)
    patch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)
    solar_env = json.loads(asyncio.run(solar.run_solar_screening(solar_request())).model_dump_json())
    climate_env = json.loads(asyncio.run(climate.run_climate_screening(climate_request())).model_dump_json())
    patch.undo()
    return {"solar": solar_env, "climate": climate_env}


@pytest.fixture(autouse=True)
def no_gemini(monkeypatch):
    monkeypatch.setattr(service.get_settings(), "gemini_api_key", None)


def _ask(envelope, question, use_gemini=False):
    return asyncio.run(service.ask(AssistantRequest(question=question, envelope=envelope, use_gemini=use_gemini)))


@pytest.mark.parametrize(("question", "citation"), [
    ("¿Qué está cambiando?", "nasa_questions.what"),
    ("¿Es estadísticamente significativo?", "nasa_questions.significant"),
    ("¿Qué significa para invertir?", "nasa_questions.so_what"),
    ("¿Cuál es el mejor sitio según el puntaje?", "scorecard"),
    ("¿Qué pasa con el VAN en el escenario adverso?", "financial_sensitivity"),
    ("¿Qué brechas faltan cubrir?", "data_gaps"),
    ("¿Sube la temperatura?", "trend_findings"),
])
def test_rules_route_solar_questions(envelopes, question, citation):
    response = _ask(envelopes["solar"], question)
    assert response.mode == AssistantMode.RULES and response.notice is None
    assert citation in response.citations
    assert response.answer.strip()


def test_rules_answer_climate_extremes_and_current_year(envelopes):
    extremes = _ask(envelopes["climate"], "¿Hay más lluvias extremas en Moquegua?")
    assert "sites.extremes" in extremes.citations
    assert "Moquegua" in extremes.answer and "Arequipa" not in extremes.answer


def test_rules_answers_come_from_the_context(envelopes):
    # Todo número de una respuesta por reglas debe salir del contexto: la misma verificación que se exige a Gemini.
    context = build_context(envelopes["solar"])
    text = context_text(context)
    for question in ("¿Qué pasa con el VAN?", "¿Cuál es el mejor sitio?", "¿Cuánto cambia?", "¿Sube la temperatura?"):
        answer, _ = answer_by_rules(question, context)
        assert ungrounded_numbers(answer, text) == [], (question, answer)


def test_unknown_question_lists_topics(envelopes):
    response = _ask(envelopes["solar"], "¿Quién ganó el mundial?")
    assert response.citations == [] and "puedo responder" in response.answer


def test_number_check_accepts_rounding_and_scales_and_rejects_inventions():
    context = '{"npv":-3080123.5,"share":0.59,"slope":0.0335,"mean":6.5716}'
    assert ungrounded_numbers("VAN de −USD 3.08 M, primero en 59 %, 6.57 kWh y +0.335 por década", context) == []
    assert ungrounded_numbers("El VAN sería USD 12.4 M", context) == [12.4]


def test_invalid_context_is_rejected(envelopes):
    with pytest.raises(Exception):
        _ask({"hola": "mundo"}, "¿Qué cambia?")


def test_gemini_answer_with_invented_number_falls_back_to_rules(envelopes, monkeypatch):
    async def fake_generate(api_key, model, question, context_json):
        return "El VAN de Moquegua es USD 987.6 M.\nFuentes: sensibilidad_van", "modelo-de-prueba"

    monkeypatch.setattr(service.get_settings(), "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(service, "generate", fake_generate)
    response = _ask(envelopes["solar"], "¿Qué pasa con el VAN?", use_gemini=True)
    assert response.mode == AssistantMode.RULES and "987.6" in (response.notice or "")


def test_grounded_gemini_answer_keeps_its_citations(envelopes, monkeypatch):
    async def fake_generate(api_key, model, question, context_json):
        return "Hay tendencias significativas en ambos sitios.\nFuentes: preguntas_nasa.what, tendencias_significativas", "modelo-de-prueba"

    monkeypatch.setattr(service.get_settings(), "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(service, "generate", fake_generate)
    response = _ask(envelopes["solar"], "¿Qué cambia?", use_gemini=True)
    assert response.mode == AssistantMode.GEMINI and response.model == "modelo-de-prueba"
    assert response.citations == ["preguntas_nasa.what", "tendencias_significativas"]
    assert "Fuentes" not in response.answer


def test_gemini_is_never_called_unless_requested(envelopes, monkeypatch):
    # Con clave configurada, una pregunta normal no debe gastar cuota.
    async def must_not_run(*args):
        raise AssertionError("Gemini no debía llamarse")

    monkeypatch.setattr(service.get_settings(), "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(service, "generate", must_not_run)
    response = _ask(envelopes["solar"], "¿Qué cambia?")
    assert response.mode == AssistantMode.RULES and response.notice is None