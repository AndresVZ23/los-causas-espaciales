"""Módulo 1 · Inteligencia climática: tendencias de variables NASA POWER y de extremos de precipitación (ETCCDI)."""

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from time import perf_counter

from ..orchestration.analysis import analyze_extremes, analyze_subjects
from ..orchestration.extraction import elapsed_ms, extract_power, extract_terrain, max_separation_km
from ..orchestration.nasa_questions import SectorLens, SubjectSummaries, answer_nasa_questions, collect_trend_findings
from ..orchestration.stages import (
    StageTimings,
    analysis_stage,
    assemble_pipeline,
    configuration_stage,
    export_stage,
    extraction_stage,
    results_stage,
    selection_stage,
    stage,
    territorial_stage,
    unique,
)
from ..schemas.analysis import Provenance
from ..schemas.climate import ClimateScreeningRequest, ClimateScreeningResponse, ClimateSiteResult
from ..schemas.pipeline import DataGap
from ..schemas.screening import PipelineStatus, StageEvidence, StudySubject, SubjectKind
from ..schemas.terrain import TerrainResponse
from ..statistics.extremes import METHOD_NOTES

CLIMATE_VARIABLES = ["T2M", "PRECTOTCORR", "WS10M", "ALLSKY_SFC_SW_DWN"]
SECTOR_LABEL = "Inteligencia climática"

# Lectura territorial de cada cambio: explica la consecuencia para activos, sin cuantificarla.
CLIMATE_READINGS: dict[tuple[str, str], str] = {
    ("T2M", "increasing"): "la temperatura media sube: más estrés térmico para personas, equipos y materiales, y mayor demanda de enfriamiento",
    ("T2M", "decreasing"): "la temperatura media baja: revisar heladas y demanda de calefacción",
    ("PRECTOTCORR", "increasing"): "la precipitación media aumenta: revisar drenaje y escorrentía",
    ("PRECTOTCORR", "decreasing"): "la precipitación media disminuye: más estrés hídrico",
    ("WS10M", "increasing"): "el viento aumenta: revisar cargas de diseño y erosión eólica",
    ("WS10M", "decreasing"): "el viento disminuye: menos ventilación natural y dispersión",
    ("ALLSKY_SFC_SW_DWN", "increasing"): "la radiación solar sube: más recurso fotovoltaico y más carga térmica",
    ("ALLSKY_SFC_SW_DWN", "decreasing"): "la radiación solar baja: menos recurso fotovoltaico",
    ("RX1DAY", "increasing"): "la lluvia máxima de un día se intensifica: más exigencia sobre drenajes y más riesgo de huaicos en quebradas",
    ("RX1DAY", "decreasing"): "la lluvia máxima de un día se reduce",
    ("RX5DAY", "increasing"): "los episodios de varios días de lluvia se intensifican: más riesgo de saturación del suelo y deslizamientos",
    ("RX5DAY", "decreasing"): "los episodios de varios días de lluvia se reducen",
    ("R95P", "increasing"): "llueve más en los días extremos: mayor proporción de lluvia concentrada",
    ("R95P", "decreasing"): "llueve menos en los días extremos",
    ("PRCPTOT", "increasing"): "la lluvia anual en días húmedos aumenta",
    ("PRCPTOT", "decreasing"): "la lluvia anual en días húmedos disminuye: más estrés hídrico para cultivos y operaciones",
    ("R10MM", "increasing"): "hay más días de lluvia intensa: más interrupciones potenciales en vías y obras",
    ("R10MM", "decreasing"): "hay menos días de lluvia intensa",
    ("CDD", "increasing"): "las rachas secas se alargan: más estrés hídrico, polvo y riesgo de incendio de vegetación",
    ("CDD", "decreasing"): "las rachas secas se acortan",
}
CLIMATE_STABLE_NOTES = {
    "RX1DAY": "La lluvia máxima de un día no muestra cambio significativo en ningún sitio, lo que no descarta que ocurra un evento extremo.",
}
ECONOMICS_NOTE = "El módulo climático no usa supuestos financieros: el impacto económico de estos cambios se cuantifica en los pilotos sectoriales, con supuestos explícitos del usuario."


def _subjects(request: ClimateScreeningRequest) -> list[StudySubject]:
    return [
        StudySubject(
            id=f"sitio-{index + 1}", label=site.label or f"Sitio {index + 1}", kind=SubjectKind.POINT,
            geometry={"type": "Point", "coordinates": [site.longitude, site.latitude]}, representative_point=site,
        )
        for index, site in enumerate(request.sites)
    ]


def _data_gaps(terrain: TerrainResponse | None) -> list[DataGap]:
    gaps = [
        DataGap(dataset="GPM IMERG V07", impact="Los extremos usan la precipitación de NASA POWER, una grilla gruesa que suaviza tormentas locales.", next_action="Integrar IMERG y contrastar los índices ETCCDI con ambas fuentes."),
        DataGap(dataset="Estaciones SENAMHI", impact="No hay contraste con mediciones en sitio.", next_action="Verificar acceso a series diarias de estaciones cercanas."),
    ]
    if terrain is None or any(site.status != "READY" for site in terrain.sites):
        gaps.append(DataGap(dataset="Métricas raster NASADEM", impact="El relieve no está disponible para todos los sitios.", next_action="Completar la descarga de NASADEM para los sitios nuevos."))
    return gaps


async def run_climate_screening(request: ClimateScreeningRequest) -> ClimateScreeningResponse:
    timings = StageTimings()
    subjects = _subjects(request)
    points = [subject.representative_point for subject in subjects]
    (datasets, timings.extraction_ms), (terrain, terrain_error, timings.terrain_ms) = await asyncio.gather(
        extract_power(points, CLIMATE_VARIABLES, request.start_date, request.end_date), extract_terrain(points)
    )
    expected_days = (request.end_date - request.start_date).days + 1

    analysis_start = perf_counter()
    variables_by_site = analyze_subjects(datasets, CLIMATE_VARIABLES, expected_days)
    extremes_by_site, thresholds = analyze_extremes(datasets)
    timings.analysis_ms = elapsed_ms(analysis_start)

    sites = [
        ClimateSiteResult(location=site, variables=variables, extremes=extremes, wet_day_p95_mm=threshold)
        for site, variables, extremes, threshold in zip(request.sites, variables_by_site, extremes_by_site, thresholds, strict=True)
    ]
    labelled = [
        SubjectSummaries(label=subject.label, summaries=[*variables, *extremes])
        for subject, variables, extremes in zip(subjects, variables_by_site, extremes_by_site, strict=True)
    ]
    variables_only = [SubjectSummaries(label=subject.label, summaries=variables) for subject, variables in zip(subjects, variables_by_site, strict=True)]
    trend_findings = collect_trend_findings(labelled)
    gaps = _data_gaps(terrain)
    pending = sum(1 for gap in gaps if gap.status == Provenance.UNAVAILABLE)
    nasa_questions = answer_nasa_questions(
        labelled, trend_findings,
        {subject.label: (subject.representative_point.latitude, subject.representative_point.longitude) for subject in subjects},
        pending, SectorLens(readings=CLIMATE_READINGS, stable_notes=CLIMATE_STABLE_NOTES, economics=ECONOMICS_NOTE),
    )

    source_provenance = unique([item.source.provenance for variables in variables_by_site for item in variables])
    all_provenance = unique(source_provenance + [Provenance.MODEL] + ([Provenance.UNAVAILABLE] if pending else []))
    years = max(len(item.annual_series) for variables in variables_by_site for item in variables)
    evaluation_evidence = []
    for site, extremes in zip(sites, extremes_by_site, strict=True):
        by_code = {item.variable: item for item in extremes}
        evaluation_evidence.append(StageEvidence(
            label=site.location.label or "Sitio",
            value=f"RX1DAY {by_code['RX1DAY'].mean:.1f} mm · CDD {by_code['CDD'].mean:.0f} días · P95 {site.wet_day_p95_mm or 0:.1f} mm",
        ))
    evaluation_evidence.append(StageEvidence(label="Índices", value="ETCCDI: RX1DAY, RX5DAY, R95P, PRCPTOT, R10MM, CDD"))
    evaluation = stage("evaluation", PipelineStatus.COMPLETED, "Extremos de precipitación comparados entre sitios con índices ETCCDI y la misma prueba de tendencia.",
                       source_provenance + [Provenance.MODEL], evaluation_evidence, answers=["so_what"])
    finance = stage("finance", PipelineStatus.UNAVAILABLE, "No aplica: el módulo climático no usa supuestos financieros.",
                    [Provenance.MODEL], [StageEvidence(label="Impacto económico", value="Se cuantifica en los pilotos sectoriales")])
    pipeline = assemble_pipeline([
        selection_stage(subjects, max_separation_km(points)),
        configuration_stage(SECTOR_LABEL, CLIMATE_VARIABLES, request.start_date, request.end_date, years, "Sin supuestos financieros"),
        extraction_stage(variables_only, timings.extraction_ms),
        analysis_stage(labelled, trend_findings, timings.analysis_ms),
        territorial_stage(terrain, terrain_error, gaps, timings.terrain_ms),
        evaluation,
        finance,
        results_stage(trend_findings, gaps, all_provenance),
        export_stage(all_provenance),
    ])
    fingerprint = hashlib.sha256(json.dumps({"sector": "climate", **request.model_dump(mode="json")}, sort_keys=True).encode()).hexdigest()[:16]
    return ClimateScreeningResponse(
        analysis_id=fingerprint,
        generated_at=datetime.now(timezone.utc),
        title="Inteligencia climática — tendencias y extremos",
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}",
        subjects=subjects,
        pipeline=pipeline,
        nasa_questions=nasa_questions,
        trend_findings=trend_findings,
        terrain=terrain,
        data_gaps=gaps,
        assumption_items=[],
        disclaimer="Análisis de tendencias con estimaciones en grilla de NASA POWER. No sustituye estaciones meteorológicas, estudios hidrológicos ni evaluaciones de riesgo de desastres.",
        sites=sites,
        method_notes=list(METHOD_NOTES),
    )
