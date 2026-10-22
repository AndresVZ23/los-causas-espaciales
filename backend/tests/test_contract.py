"""Conformidad con el contrato común C2 (ScreeningEnvelope).

Cada piloto nuevo (vial, inmobiliario) debe agregar una prueba equivalente a
`test_solar_response_conforms_to_envelope` sobre su propio orquestador.
"""

import asyncio
import json

import pytest

from backend.app.orchestration import extraction
from backend.app.orchestration.conformance import envelope_violations
from backend.app.orchestration.stages import assemble_pipeline
from backend.app.schemas.screening import CONTRACT_VERSION, ScreeningEnvelope, Sector
from backend.app.sectors import solar
from backend.tests.test_solar import FakePowerConnector, FlatPowerConnector, MetadataOnlyNasadem, _request


@pytest.fixture
def solar_response(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FakePowerConnector)
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)
    return asyncio.run(solar.run_solar_screening(_request()))


def test_solar_response_conforms_to_envelope(solar_response):
    assert envelope_violations(solar_response) == []
    assert solar_response.contract_version == CONTRACT_VERSION
    assert solar_response.sector == Sector.SOLAR
    assert [subject.kind for subject in solar_response.subjects] == ["point", "point"]
    assert {item.key for item in solar_response.assumption_items} >= {"capacity_mw", "discount_rate", "horizon_years"}


def test_envelope_is_readable_without_sector_fields(solar_response):
    # Un consumidor genérico (PDF, asistente) valida el JSON solar como sobre común e ignora lo propio del sector.
    generic = ScreeningEnvelope.model_validate(json.loads(solar_response.model_dump_json()))
    assert envelope_violations(generic) == []
    assert not hasattr(generic, "sites")


def test_insufficient_evidence_run_also_conforms(monkeypatch):
    monkeypatch.setattr(extraction, "PowerConnector", FlatPowerConnector)
    monkeypatch.setattr(extraction, "NasademConnector", MetadataOnlyNasadem)
    response = asyncio.run(solar.run_solar_screening(_request()))
    assert envelope_violations(response) == []


def test_conformance_detects_broken_envelopes(solar_response):
    broken = solar_response.model_copy(deep=True)
    broken.pipeline = broken.pipeline[:-1]
    broken.nasa_questions = list(reversed(broken.nasa_questions))
    broken.trend_findings[0].site = "Sitio inexistente"
    broken.subjects[0].geometry = {"type": "Polygon", "coordinates": []}
    problems = envelope_violations(broken)
    assert any("orden canónico" in problem for problem in problems)
    assert any("Preguntas NASA" in problem for problem in problems)
    assert any("sujeto inexistente" in problem for problem in problems)
    assert any("geometría es Polygon" in problem for problem in problems)


def test_assemble_pipeline_rejects_missing_stage(solar_response):
    with pytest.raises(ValueError, match="nueve etapas"):
        assemble_pipeline(solar_response.pipeline[:8])
