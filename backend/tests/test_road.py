"""K2 road pilot: controlled science, economics, gaps and C2 conformance."""

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.orchestration.conformance import envelope_violations
from backend.app.orchestration.discoveries import NO_TERRAIN_CHECK
from backend.app.orchestration.slope_check import LEAD as SLOPE_LEAD
from backend.app.schemas.analysis import Observation, Provenance, SourceMetadata
from backend.app.schemas.road import (
    RoadAssumptions,
    RoadScreeningRequest,
    RoadSpatialExposure,
    RoadTerritorialEvidence,
    RoadTerritorialSourceSummary,
)
from backend.app.schemas.screening import DiscoveryKind
from backend.app.schemas.terrain import TerrainCrosscheck, TerrainMetrics, TerrainResponse, TerrainSiteResult
from backend.app.sectors import road
from backend.app.statistics.extremes import linear_percentile


def _source(variable: str) -> SourceMetadata:
    return SourceMetadata(
        source_id=f"power-{variable}",
        dataset="NASA POWER Daily Point",
        version="2.10.1",
        variable=variable,
        unit="mm/day" if variable == "PRECTOTCORR" else "°C",
        temporal_resolution="daily",
        spatial_resolution="0.5° × 0.625°",
        downloaded_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        source_url="https://power.larc.nasa.gov/api/temporal/daily/point",
        provenance=Provenance.CACHED,
    )


async def _power(points, variables, start_date, end_date):
    days = [start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)]
    datasets = []
    for index, _point in enumerate(points):
        dataset = {}
        for variable in variables:
            if variable == "PRECTOTCORR":
                values = [
                    25.0 + index if offset % 31 == 0 else 1.0 + 0.1 * (day.year - start_date.year)
                    for offset, day in enumerate(days)
                ]
            else:
                values = [18.0 + index + 0.1 * (day.year - start_date.year) for day in days]
            dataset[variable] = (
                [Observation(timestamp=day, value=value) for day, value in zip(days, values, strict=True)],
                _source(variable),
            )
        datasets.append(dataset)
    return datasets, 12.3


async def _terrain(points):
    return TerrainResponse(
        generated_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        sites=[
            TerrainSiteResult(
                location=point,
                status="READY",
                metrics=TerrainMetrics(elevation_m=1500 + index, slope_degrees=4 + index),
                granules=[],
                provenance=Provenance.CACHED,
                limitations=["Fixture controlado sin red."],
            )
            for index, point in enumerate(points)
        ],
        note="Fixture controlado.",
    ), None, 1.2


async def _spatial(subjects, request):
    return [
        RoadSpatialExposure(
            period=f"{request.end_date - timedelta(days=364)}/{request.end_date}",
            unit="mm/day",
            cell_count=2,
            spatial_coverage_percent=100,
            mean_precipitation_mm_day=1.5 + index,
            rx1day_mm=30 + index,
            p99_precipitation_mm_day=10 + index,
            cells=[],
            provenance=Provenance.CACHED,
            source_url="https://power.larc.nasa.gov/api/temporal/daily/regional",
            method="Promedio ponderado por área con pesos diarios renormalizados.",
            limitations=["Grilla POWER; no reemplaza estaciones."],
        )
        for index, _subject in enumerate(subjects)
    ], [None] * len(subjects)


async def _territory(subjects, enabled):
    assert enabled
    evidence = []
    for subject in subjects:
        evidence.append(RoadTerritorialEvidence(
            subject=subject.label,
            sources=[
                RoadTerritorialSourceSummary(
                    source_id="cenepred-flood-risk",
                    status="READY",
                    intersection_count=1,
                    provenance=Provenance.CACHED,
                    downloaded_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
                    limitations=["Intersección de screening; no equivale a nivel de riesgo."],
                ),
                RoadTerritorialSourceSummary(
                    source_id="ingemmet-geohazards",
                    status="DATA_UNAVAILABLE",
                    intersection_count=None,
                    provenance=Provenance.UNAVAILABLE,
                    downloaded_at=None,
                    limitations=["Servicio oficial no disponible en la prueba."],
                ),
            ],
        ))
    return evidence, [None] * len(subjects)


def _request() -> RoadScreeningRequest:
    return RoadScreeningRequest(start_date=date(2018, 1, 1), end_date=date(2023, 12, 31))


@pytest.fixture
def road_response(monkeypatch):
    monkeypatch.setattr(road, "extract_power", _power)
    monkeypatch.setattr(road, "extract_terrain", _terrain)
    monkeypatch.setattr(road, "_spatial_exposures", _spatial)
    monkeypatch.setattr(road, "_territorial_evidence", _territory)
    return asyncio.run(road.run_road_screening(_request()))


def test_road_response_conforms_and_preserves_provenance(road_response):
    assert envelope_violations(road_response) == []
    assert road_response.sector == "road"
    assert len(road_response.pipeline) == 9
    assert [item.key for item in road_response.nasa_questions] == ["what", "where", "how_much", "significant", "so_what"]
    assert road_response.corridor_source.license == "ODbL 1.0"
    assert "OpenStreetMap" in road_response.corridor_source.source
    assert len(road_response.financial_sensitivity) == len(road_response.subjects)
    assert road_response.scorecard is not None
    assert all(item.finance.assumption_provenance == Provenance.ASSUMPTION for item in road_response.segments)
    assert all(item.spatial_exposure.provenance == Provenance.CACHED for item in road_response.segments)
    assert any(item.dataset == "ingemmet-geohazards" for item in road_response.data_gaps)
    assert "No sustituye ingeniería vial" in road_response.disclaimer
    rain = next(item for item in road_response.scorecard.subjects[0].criteria if item.key == "recent_p99_precip")
    assert rain.value == 10


def test_road_npv_matches_independent_discounted_cash_flow():
    assumptions = RoadAssumptions(horizon_years=3, discount_rate=0.10)
    inputs = {
        "interruption_days": 5.0,
        "residual_fraction": 0.4,
        "cost_per_day": 200_000.0,
        "mitigation_capex": 1_000_000.0,
        "annual_maintenance": 30_000.0,
        "discount_rate": 0.10,
    }
    result = road._road_npv(inputs, 8.0, assumptions)
    annual_net = 5 * (1 - 0.4) * 200_000 - 30_000
    independent = -1_000_000 + sum(annual_net / 1.1**year for year in range(1, 4))
    assert result.npv_usd == pytest.approx(independent, abs=0.01)
    assert result.avoided_interruption_days_per_year == 3


def test_p99_prevents_one_provider_artifact_from_dominating_the_score():
    values = [1.0] * 361 + [2.0, 3.0, 4.0, 151.0]
    p99 = linear_percentile(values, 0.99)
    assert max(values) == 151
    assert p99 == pytest.approx(1.36)
    assert p99 < 0.02 * max(values)


def test_missing_evidence_becomes_gap_and_reduces_score_coverage(monkeypatch):
    async def missing_terrain(points):
        return None, "Earthdata no disponible (prueba)", 1.0

    async def missing_spatial(subjects, request):
        return [None] * len(subjects), ["POWER regional no disponible"] * len(subjects)

    async def missing_territory(subjects, enabled):
        return [RoadTerritorialEvidence(subject=item.label, sources=[]) for item in subjects], ["capas no disponibles"] * len(subjects)

    monkeypatch.setattr(road, "extract_power", _power)
    monkeypatch.setattr(road, "extract_terrain", missing_terrain)
    monkeypatch.setattr(road, "_spatial_exposures", missing_spatial)
    monkeypatch.setattr(road, "_territorial_evidence", missing_territory)
    response = asyncio.run(road.run_road_screening(_request()))

    assert envelope_violations(response) == []
    assert any(item.dataset == "Métricas raster NASADEM" for item in response.data_gaps)
    assert all(item.terrain_slope_degrees is None and item.spatial_exposure is None for item in response.segments)
    assert all(item.coverage < 1 for item in response.scorecard.subjects)
    assert any("no se interpreta como terreno plano" in item for item in response.segments[0].cautions)


def test_second_elevation_model_becomes_discoveries_in_results_stage(monkeypatch):
    async def checked_terrain(points):
        terrain, error, elapsed = await _terrain(points)
        for index, site in enumerate(terrain.sites):
            site.crosscheck = TerrainCrosscheck(
                source="Copernicus GLO-30",
                elevation_m=site.metrics.elevation_m + (120 if index == 0 else 3),
                slope_degrees=site.metrics.slope_degrees + 0.5,
                tile_url="https://example.invalid/Copernicus_DSM_COG_10.tif",
                provenance=Provenance.CACHED,
                downloaded_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
            )
        return terrain, error, elapsed

    monkeypatch.setattr(road, "extract_power", _power)
    monkeypatch.setattr(road, "extract_terrain", checked_terrain)
    monkeypatch.setattr(road, "_spatial_exposures", _spatial)
    monkeypatch.setattr(road, "_territorial_evidence", _territory)
    response = asyncio.run(road.run_road_screening(_request()))

    assert envelope_violations(response) == []
    assert [item.subjects for item in response.discoveries] == [[subject.label] for subject in response.subjects]
    assert response.discoveries[0].kind == DiscoveryKind.CONTRADICTION
    assert "+120 m" in response.discoveries[0].detail
    assert all(item.kind == DiscoveryKind.AGREEMENT for item in response.discoveries[1:])
    results = next(item for item in response.pipeline if item.key == "results")
    recorded = next(item for item in results.evidence if item.label == "Descubrimientos al cruzar fuentes")
    assert "1 contradicciones" in recorded.value and "coincidencias" in recorded.value
    # El puntaje se recalcula con la pendiente de Copernicus (+0.5° en cada tramo) y dice que el primer lugar no cambia.
    slope_note = next(item for item in response.scorecard.notes if item.startswith(SLOPE_LEAD))
    assert f"el primer lugar no cambia: {response.scorecard.leader}" in slope_note


def test_no_second_elevation_model_is_declared_not_read_as_agreement(road_response):
    assert road_response.discoveries == []
    assert not any(item.startswith(SLOPE_LEAD) for item in road_response.scorecard.notes)
    results = next(item for item in road_response.pipeline if item.key == "results")
    recorded = next(item for item in results.evidence if item.label == "Descubrimientos al cruzar fuentes")
    assert recorded.value == NO_TERRAIN_CHECK


def test_layer_from_last_valid_copy_keeps_its_count_and_becomes_a_declared_gap(monkeypatch):
    note = "El servicio oficial no respondió hoy (Token Required); se muestra la última copia válida, del 27-oct-2026."

    async def closed_cenepred(subjects, enabled):
        evidence, errors = await _territory(subjects, enabled)
        for item in evidence:
            flood = next(source for source in item.sources if source.source_id == "cenepred-flood-risk")
            flood.stale_note = note
        return evidence, errors

    monkeypatch.setattr(road, "extract_power", _power)
    monkeypatch.setattr(road, "extract_terrain", _terrain)
    monkeypatch.setattr(road, "_spatial_exposures", _spatial)
    monkeypatch.setattr(road, "_territorial_evidence", closed_cenepred)
    response = asyncio.run(road.run_road_screening(_request()))

    assert envelope_violations(response) == []
    assert all(item.territorial_intersections["cenepred-flood-risk"] == 1 for item in response.segments)   # el conteo de la copia se conserva
    stale = [item for item in response.data_gaps if item.dataset.endswith("última copia válida")]
    assert len(stale) == 1 and stale[0].status == Provenance.CACHED and stale[0].impact == note            # una brecha, no una por tramo
    assert stale[0].dataset.startswith("Escenario de riesgo por inundaciones")
    assert "CENEPRED" in stale[0].next_action


def test_road_endpoint_rejects_non_linestring_before_external_io():
    response = TestClient(app).post("/api/v1/projects/road-screening", json={
        "start_date": "2018-01-01",
        "end_date": "2023-12-31",
        "segments": [{
            "id": "bad",
            "label": "Polígono inválido",
            "geometry": {"type": "Polygon", "coordinates": [[[-71, -17], [-70, -17], [-70, -16], [-71, -17]]]},
        }],
    })
    assert response.status_code == 422
    assert "LineString" in response.json()["detail"]
