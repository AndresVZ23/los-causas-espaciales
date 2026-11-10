"""K3 real-estate pilot: controlled geospatial, financial and C2 checks."""

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pyproj import Geod
from shapely.geometry import shape

from backend.app.main import app
from backend.app.orchestration.conformance import envelope_violations
from backend.app.orchestration.discoveries import NO_TERRAIN_CHECK
from backend.app.schemas.analysis import Observation, Provenance, SourceMetadata
from backend.app.schemas.real_estate import (
    RealEstateAssumptions,
    RealEstateScreeningRequest,
    RealEstateSiteInput,
    RealEstateSpatialExposure,
    RealEstateTerritorialEvidence,
    RealEstateTerritorialSourceSummary,
    RealEstateTerritoryReference,
)
from backend.app.schemas.screening import DiscoveryKind
from backend.app.schemas.terrain import TerrainCrosscheck, TerrainMetrics, TerrainResponse, TerrainSiteResult
from backend.app.sectors import real_estate

GEOD = Geod(ellps="WGS84")


def _polygon(west: float, south: float, size: float = 0.01):
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south], [west + size, south], [west + size, south + size],
            [west, south + size], [west, south],
        ]],
    }


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
            values = [
                (2.0 + index + (12.0 if offset % 97 == 0 else 0.0))
                if variable == "PRECTOTCORR"
                else 18.0 + index + 0.08 * (day.year - start_date.year)
                for offset, day in enumerate(days)
            ]
            dataset[variable] = (
                [Observation(timestamp=day, value=value) for day, value in zip(days, values, strict=True)],
                _source(variable),
            )
        datasets.append(dataset)
    return datasets, 10.0


async def _terrain(points):
    return TerrainResponse(
        generated_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        sites=[TerrainSiteResult(
            location=point,
            status="READY",
            metrics=TerrainMetrics(elevation_m=1400 + index, slope_degrees=3 + index),
            granules=[],
            provenance=Provenance.CACHED,
            limitations=["Fixture controlado sin red."],
        ) for index, point in enumerate(points)],
        note="Fixture controlado.",
    ), None, 1.0


async def _spatial(subjects, request):
    return [RealEstateSpatialExposure(
        period=f"{request.end_date - timedelta(days=364)}/{request.end_date}",
        unit="mm/day",
        mode="REGIONAL",
        cell_count=2,
        spatial_coverage_percent=100,
        mean_precipitation_mm_day=2 + index,
        rx1day_mm=80 + index,
        p99_precipitation_mm_day=12 + index,
        cells=[],
        provenance=Provenance.CACHED,
        source_url="https://power.larc.nasa.gov/api/temporal/daily/regional",
        method="Promedio ponderado por área geodésica.",
        limitations=["P99 no es lluvia de diseño."],
    ) for index, _subject in enumerate(subjects)], [None] * len(subjects)


async def _territory(subjects, enabled):
    assert enabled
    evidence = []
    for subject in subjects:
        evidence.append(RealEstateTerritorialEvidence(
            subject=subject.label,
            sources=[RealEstateTerritorialSourceSummary(
                source_id=source_id,
                status="READY",
                intersection_count=0,
                provenance=Provenance.CACHED,
                downloaded_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
                limitations=["Cero cruces no prueba ausencia de riesgo o restricción."],
            ) for source_id in real_estate.TERRITORIAL_SOURCE_IDS],
        ))
    return evidence, [None] * len(subjects)


def _request() -> RealEstateScreeningRequest:
    return RealEstateScreeningRequest(
        sites=[
            RealEstateSiteInput(id="a", label="Terreno A", geometry=_polygon(-70.94, -17.20)),
            RealEstateSiteInput(id="b", label="Terreno B", geometry=_polygon(-71.55, -16.40)),
        ],
        start_date=date(2018, 1, 1),
        end_date=date(2023, 12, 31),
    )


@pytest.fixture
def estate_response(monkeypatch):
    monkeypatch.setattr(real_estate, "extract_power", _power)
    monkeypatch.setattr(real_estate, "extract_terrain", _terrain)
    monkeypatch.setattr(real_estate, "_spatial_exposures", _spatial)
    monkeypatch.setattr(real_estate, "_territorial_evidence", _territory)
    return asyncio.run(real_estate.run_real_estate_screening(_request()))


def test_real_estate_response_conforms_and_preserves_provenance(estate_response):
    assert envelope_violations(estate_response) == []
    assert estate_response.sector == "real_estate"
    assert len(estate_response.pipeline) == 9
    assert len(estate_response.financial_sensitivity) == 2
    assert estate_response.scorecard is not None
    assert all(item.kind == "polygon" for item in estate_response.subjects)
    assert all(item.provenance == Provenance.ASSUMPTION for item in estate_response.site_sources)
    assert all(item.finance.assumption_provenance == Provenance.ASSUMPTION for item in estate_response.sites)
    assert all(item.spatial_exposure.p99_precipitation_mm_day is not None for item in estate_response.sites)
    for sensitivity in estate_response.financial_sensitivity:
        scenarios = {item.key: item.npv for item in sensitivity.scenarios}
        assert scenarios["adverso"] < scenarios["base"] < scenarios["favorable"]
    assert "No acredita propiedad" in estate_response.disclaimer
    assert any(item.dataset == "Catastro, titularidad y parámetros urbanísticos" for item in estate_response.data_gaps)
    exact_area = abs(GEOD.geometry_area_perimeter(shape(estate_response.subjects[0].geometry))[0])
    assert estate_response.sites[0].finance.land_area_m2 == pytest.approx(exact_area, abs=0.01)


def test_real_estate_npv_matches_independent_discounted_cash_flow():
    assumptions = RealEstateAssumptions(
        horizon_years=3,
        developable_fraction=0.5,
        floor_area_ratio=1,
        annual_absorption_fraction=0.4,
        sale_price_usd_m2=1000,
        construction_cost_usd_m2=500,
        land_cost_usd_m2=100,
        mitigation_cost_usd_m2_land=10,
        selling_cost_fraction=0.05,
        discount_rate=0.10,
    )
    inputs = real_estate._base_finance(0.01, assumptions)  # 10,000 m² of land
    result = real_estate._estate_npv(inputs, assumptions)
    saleable = 10_000 * 0.5
    initial = -(10_000 * 100 + 10_000 * 10)
    annual_40 = saleable * 0.4 * (1000 - 500 - 50)
    final_20 = saleable * 0.2 * (1000 - 500 - 50)
    independent = initial + annual_40 / 1.1 + annual_40 / 1.1**2 + final_20 / 1.1**3
    assert result.npv_usd == pytest.approx(independent, abs=0.01)
    assert result.sold_fraction_within_horizon == 1
    assert len(result.cash_flows_usd) == 4


def test_ign_territory_resolves_to_real_polygon_and_declares_2015_limit():
    request = RealEstateScreeningRequest(
        sites=[RealEstateSiteInput(
            id="moquegua-dept",
            label="Moquegua departamento",
            territory=RealEstateTerritoryReference(level="department", ubigeo="18"),
        )],
        start_date=date(2018, 1, 1),
        end_date=date(2023, 12, 31),
    )
    subjects, areas, sources = real_estate._resolve_subjects(request)
    assert subjects[0].kind == "polygon"
    assert areas[0] > 1_000
    assert sources[0].provenance == Provenance.REAL
    assert "CC BY-IGO" in sources[0].license
    assert any("2015" in item for item in sources[0].limitations)


def test_ign_multipolygon_territory_is_supported_end_to_end_before_external_io():
    request = RealEstateScreeningRequest(
        sites=[RealEstateSiteInput(
            id="lima-dept",
            label="Lima departamento",
            territory=RealEstateTerritoryReference(level="department", ubigeo="15"),
        )],
        start_date=date(2018, 1, 1),
        end_date=date(2023, 12, 31),
    )
    subjects, areas, sources = real_estate._resolve_subjects(request)
    assert subjects[0].geometry["type"] == "MultiPolygon"
    assert subjects[0].kind == "polygon"
    assert areas[0] > 30_000
    assert sources[0].provenance == Provenance.REAL


def test_missing_evidence_becomes_gap_and_reduces_score_coverage(monkeypatch):
    async def missing_terrain(points):
        return None, "Earthdata no disponible (prueba)", 1.0

    async def missing_spatial(subjects, request):
        return [None] * len(subjects), ["POWER regional no disponible"] * len(subjects)

    async def missing_territory(subjects, enabled):
        return [RealEstateTerritorialEvidence(subject=item.label, sources=[]) for item in subjects], [
            "capas no disponibles"
        ] * len(subjects)

    monkeypatch.setattr(real_estate, "extract_power", _power)
    monkeypatch.setattr(real_estate, "extract_terrain", missing_terrain)
    monkeypatch.setattr(real_estate, "_spatial_exposures", missing_spatial)
    monkeypatch.setattr(real_estate, "_territorial_evidence", missing_territory)
    response = asyncio.run(real_estate.run_real_estate_screening(_request()))

    assert envelope_violations(response) == []
    assert any(item.dataset == "Métricas raster NASADEM" for item in response.data_gaps)
    assert all(item.terrain_slope_degrees is None and item.spatial_exposure is None for item in response.sites)
    assert all(item.coverage < 1 for item in response.scorecard.subjects)
    assert any("no se interpreta como terreno plano" in item for item in response.sites[0].cautions)


def test_zero_intersections_remain_qualified_not_zero_risk(estate_response):
    assert all(value == 0 for value in estate_response.sites[0].territorial_intersections.values())
    assert any("nunca equivale a cero riesgo" in item for item in estate_response.scorecard.notes)
    territorial_stage = next(item for item in estate_response.pipeline if item.key == "territorial")
    assert any("cero no demuestra ausencia" in item.value for item in territorial_stage.evidence)


def test_large_ign_territory_is_analysis_area_and_single_subject_is_not_comparison(monkeypatch):
    request = RealEstateScreeningRequest(
        sites=[RealEstateSiteInput(
            id="samegua",
            label="Samegua",
            territory=RealEstateTerritoryReference(level="district", ubigeo="180104"),
        )],
        start_date=date(2018, 1, 1),
        end_date=date(2023, 12, 31),
    )
    monkeypatch.setattr(real_estate, "extract_power", _power)
    monkeypatch.setattr(real_estate, "extract_terrain", _terrain)
    monkeypatch.setattr(real_estate, "_spatial_exposures", _spatial)
    monkeypatch.setattr(real_estate, "_territorial_evidence", _territory)

    response = asyncio.run(real_estate.run_real_estate_screening(request))

    assert envelope_violations(response) == []
    assert 60 < response.sites[0].area_km2 < 70
    assert response.sites[0].area_km2 > real_estate.PROJECT_SCALE_KM2
    assert any(
        "más de 200 ha" in caution and "no describe un proyecto inmobiliario" in caution
        for caution in response.sites[0].cautions
    )
    fifth_answer = next(item.answer for item in response.nasa_questions if item.key == "so_what")
    assert "Samegua" in fifth_answer
    assert "sus VAN no describen proyectos" in fifth_answer
    assert response.scorecard is not None
    assert response.scorecard.margin is None
    assert response.scorecard.tie is False
    assert any("no existe comparación" in note for note in response.scorecard.notes)


def test_second_elevation_model_becomes_discoveries_in_results_stage(monkeypatch):
    async def checked_terrain(points):
        terrain, error, elapsed = await _terrain(points)
        for index, site in enumerate(terrain.sites):
            site.crosscheck = TerrainCrosscheck(
                source="Copernicus GLO-30",
                elevation_m=site.metrics.elevation_m + 2,
                slope_degrees=site.metrics.slope_degrees + (14 if index == 0 else 0.4),
                tile_url="https://example.invalid/Copernicus_DSM_COG_10.tif",
                provenance=Provenance.CACHED,
                downloaded_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
            )
        return terrain, error, elapsed

    monkeypatch.setattr(real_estate, "extract_power", _power)
    monkeypatch.setattr(real_estate, "extract_terrain", checked_terrain)
    monkeypatch.setattr(real_estate, "_spatial_exposures", _spatial)
    monkeypatch.setattr(real_estate, "_territorial_evidence", _territory)
    response = asyncio.run(real_estate.run_real_estate_screening(_request()))

    assert envelope_violations(response) == []
    assert [item.subjects for item in response.discoveries] == [["Terreno A"], ["Terreno B"]]
    # Terreno A: 3° en NASADEM y 17° en Copernicus, a ambos lados del umbral de pendiente fuerte.
    assert response.discoveries[0].kind == DiscoveryKind.CONTRADICTION
    assert "cruza el umbral" in response.discoveries[0].title
    assert response.discoveries[1].kind == DiscoveryKind.AGREEMENT
    results = next(item for item in response.pipeline if item.key == "results")
    recorded = next(item for item in results.evidence if item.label == "Descubrimientos al cruzar fuentes")
    assert recorded.value == "1 contradicciones · 1 coincidencias"


def test_no_second_elevation_model_is_declared_not_read_as_agreement(estate_response):
    assert estate_response.discoveries == []
    results = next(item for item in estate_response.pipeline if item.key == "results")
    recorded = next(item for item in results.evidence if item.label == "Descubrimientos al cruzar fuentes")
    assert recorded.value == NO_TERRAIN_CHECK


def test_real_estate_endpoint_rejects_non_polygon_before_external_io():
    response = TestClient(app).post("/api/v1/projects/real-estate-screening", json={
        "start_date": "2018-01-01",
        "end_date": "2023-12-31",
        "sites": [{
            "id": "bad",
            "label": "Línea inválida",
            "geometry": {"type": "LineString", "coordinates": [[-71, -17], [-70, -16]]},
        }],
    })
    assert response.status_code == 422
    assert "Polygon" in response.json()["detail"]
