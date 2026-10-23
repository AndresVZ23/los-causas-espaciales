import asyncio
import io
import json

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.app.main import app
from backend.app.orchestration import extraction
from backend.app.reports.executive_pdf import fingerprint, render_executive_pdf
from backend.app.schemas.screening import ScreeningEnvelope
from backend.app.sectors import solar
from backend.tests.test_solar import FakePowerConnector, FlatPowerConnector, MetadataOnlyNasadem, _request


def _run(monkeypatch, connector):
    monkeypatch.setattr(extraction, "PowerConnector", connector)
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)
    return asyncio.run(solar.run_solar_screening(_request()))


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)


def test_pdf_contains_questions_trends_and_traceability(monkeypatch):
    response = _run(monkeypatch, FakePowerConnector)
    pdf = render_executive_pdf(response)
    reader = PdfReader(io.BytesIO(pdf))
    text = _text(pdf)

    assert pdf.startswith(b"%PDF")
    assert len(reader.pages) >= 2
    assert reader.metadata.author == "Los Causas Espaciales"
    for expected in ("Las preguntas del reto NASA", "¿Qué está cambiando?", "Tendencias significativas", "Pipeline de análisis",
                     "Supuestos del usuario", "Escenarios y sensibilidad del VAN", "Precio mínimo para VAN", "Adverso", "Puntaje multicriterio",
                     "Brechas antes de invertir", response.analysis_id, fingerprint(response)):
        assert expected in text.replace("\n", " ") or expected in text, expected
    # Sin glifo en las fuentes: se escribe en texto, nunca como un cuadro vacío.
    assert "α" not in text and "alfa = 0.05" in text


def test_pdf_states_insufficient_evidence_without_trends(monkeypatch):
    response = _run(monkeypatch, FlatPowerConnector)
    text = _text(render_executive_pdf(response))
    assert "Evidencia insuficiente para establecer una tendencia estadísticamente significativa" in text.replace("\n", " ")


def test_fingerprint_is_deterministic_and_content_sensitive(monkeypatch):
    response = _run(monkeypatch, FakePowerConnector)
    copy = ScreeningEnvelope.model_validate(json.loads(response.model_dump_json()))
    assert fingerprint(copy) == fingerprint(ScreeningEnvelope.model_validate(json.loads(response.model_dump_json())))
    copy.disclaimer += " (editado)"
    assert fingerprint(copy) != fingerprint(ScreeningEnvelope.model_validate(json.loads(response.model_dump_json())))


def test_endpoint_returns_pdf_for_full_sector_response(monkeypatch):
    response = _run(monkeypatch, FakePowerConnector)
    client = TestClient(app)
    reply = client.post("/api/v1/reports/executive-pdf", content=response.model_dump_json(), headers={"Content-Type": "application/json"})
    assert reply.status_code == 200
    assert reply.headers["content-type"] == "application/pdf"
    assert f"reporte-ejecutivo-solar-{response.analysis_id}.pdf" in reply.headers["content-disposition"]
    assert reply.content.startswith(b"%PDF")


def test_endpoint_rejects_invalid_or_oversized_envelopes(monkeypatch):
    client = TestClient(app)
    assert client.post("/api/v1/reports/executive-pdf", json={"title": "incompleto"}).status_code == 422
    response = _run(monkeypatch, FakePowerConnector)
    payload = json.loads(response.model_dump_json())
    payload["subjects"] = [dict(payload["subjects"][0], id=f"s{i}", label=f"S{i}") for i in range(51)]
    assert client.post("/api/v1/reports/executive-pdf", json=payload).status_code == 422


@pytest.mark.parametrize("connector", [FakePowerConnector, FlatPowerConnector])
def test_pdf_renders_for_generic_envelope_without_sector_fields(monkeypatch, connector):
    response = _run(monkeypatch, connector)
    generic = ScreeningEnvelope.model_validate(json.loads(response.model_dump_json()))
    assert render_executive_pdf(generic).startswith(b"%PDF")
