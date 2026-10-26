"""Módulo 1 · Inteligencia climática: tendencias de variables NASA POWER y de extremos de precipitación (ETCCDI)."""

import asyncio
import hashlib
import json
from collections.abc import Sequence
from datetime import datetime, timezone
from time import perf_counter

from ..connectors.nasa.power import PowerConnectorError
from ..orchestration.analysis import analyze_extremes, analyze_subjects, attach_countercheck
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
from ..connectors.peru.admin_boundaries import PeruTerritoryCatalog, TerritoryCatalogError
from ..orchestration.territory import TerritoryAnalysisError, TerritoryExtraction, cell_trends, extract_territories
from ..schemas.analysis import Point, Provenance
from ..schemas.climate import (
    Agreement,
    CellTrend,
    ClimateScreeningRequest,
    ClimateScreeningResponse,
    ClimateSiteResult,
    ExtremeIndexSummary,
    TerritoryInfo,
)
from ..schemas.territory import TerritoryGeometryResponse
from ..schemas.pipeline import DataGap
from ..schemas.screening import PipelineStatus, StageEvidence, StudySubject, SubjectKind
from ..schemas.terrain import TerrainResponse
from ..statistics.extremes import METHOD_NOTES

CLIMATE_VARIABLES = ["T2M", "PRECTOTCORR", "WS10M", "ALLSKY_SFC_SW_DWN"]
# Contraste satelital independiente de los extremos: GPM IMERG servido por la misma API de NASA POWER.
COUNTERCHECK = "IMERG_PRECTOT"
COUNTERCHECK_SOURCE = "GPM IMERG (NASA POWER · IMERG_PRECTOT)"
REQUEST_VARIABLES = [*CLIMATE_VARIABLES, COUNTERCHECK]
COUNTERCHECK_NOTE = (
    "Contraste: los mismos índices se calculan con GPM IMERG (precipitación satelital, 0.1°), independiente del reanálisis MERRA-2 "
    "de PRECTOTCORR. Una tendencia de extremos es robusta cuando ambas fuentes coinciden en significancia y dirección."
)
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


LEVEL_SUFFIX = {"department": "depto.", "province": "prov.", "district": "dist."}
# Tendencias por celda que se dibujan en el mapa: las dos variables con lectura territorial más directa.
CELL_TREND_VARIABLES = ["T2M", "PRECTOTCORR"]
TERRITORY_NOTE = (
    "Territorios: cada variable es el promedio diario ponderado por área de las celdas NASA POWER que lo cubren. "
    "Los extremos de lluvia de un promedio areal son más suaves que los de un punto; la dispersión entre celdas y las "
    "tendencias por celda muestran la variación interna."
)


def _subjects(request: ClimateScreeningRequest, geometries: list[TerritoryGeometryResponse]) -> list[StudySubject]:
    sites = [
        StudySubject(
            id=f"sitio-{index + 1}", label=site.label or f"Sitio {index + 1}", kind=SubjectKind.POINT,
            geometry={"type": "Point", "coordinates": [site.longitude, site.latitude]}, representative_point=site,
        )
        for index, site in enumerate(request.sites)
    ]
    territories = []
    for geometry in geometries:
        summary = geometry.territory
        label = f"{summary.name} ({LEVEL_SUFFIX[summary.level]})"
        territories.append(StudySubject(
            id=f"territorio-{summary.ubigeo}", label=label, kind=SubjectKind.POLYGON,
            geometry=geometry.feature.get("geometry", geometry.feature),
            representative_point=Point(latitude=summary.center.latitude, longitude=summary.center.longitude, label=label),
        ))
    return sites + territories


def _territory_info(extraction: TerritoryExtraction) -> TerritoryInfo:
    summary = extraction.summary
    return TerritoryInfo(level=summary.level, ubigeo=summary.ubigeo, name=summary.name, area_km2=summary.area_sqkm, mode=extraction.mode,
                         cells=len(extraction.cells), coverage_percent=extraction.coverage_percent, grid_degrees=extraction.grid_degrees,
                         geometry=extraction.geometry)


async def _extract(request: ClimateScreeningRequest) -> tuple[list, list[TerritoryExtraction]]:
    async def sites():
        if not request.sites:
            return []
        return (await extract_power(request.sites, REQUEST_VARIABLES, request.start_date, request.end_date))[0]

    refs = [(item.level, item.ubigeo) for item in request.territories]
    site_data, territories = await asyncio.gather(sites(), extract_territories(refs, REQUEST_VARIABLES, request.start_date, request.end_date))
    return site_data + [item.dataset for item in territories], territories


def _data_gaps(terrain: TerrainResponse | None, countercheck_error: str | None) -> list[DataGap]:
    gaps = [DataGap(dataset="Estaciones SENAMHI", impact="El contraste es satélite contra reanálisis; no hay mediciones en sitio.", next_action="Verificar acceso a series diarias de estaciones cercanas.")]
    if countercheck_error:
        gaps.insert(0, DataGap(dataset="GPM IMERG", impact=f"Sin contraste satelital de los extremos: {countercheck_error}", next_action="Reintentar la consulta IMERG_PRECTOT en NASA POWER."))
    if terrain is None or any(site.status != "READY" for site in terrain.sites):
        gaps.append(DataGap(dataset="Métricas raster NASADEM", impact="El relieve no está disponible para todos los sitios.", next_action="Completar la descarga de NASADEM para los sitios nuevos."))
    return gaps


def countercheck_summary(sites: Sequence[tuple[str, Sequence[ExtremeIndexSummary]]]) -> str:
    """Frase para la pregunta de significancia: cuántas tendencias de extremos repite IMERG y qué valores atípicos desmiente.

    Recibe pares (etiqueta del sujeto, índices de extremos); la usan Clima y Amenazas.
    """
    significant = [(label, item) for label, extremes in sites for item in extremes if item.significant_after_bh and item.countercheck]
    refuted = [
        f"{item.variable} {label} {year.year} ({year.value:.0f} mm en MERRA-2, {year.countercheck_value:.0f} mm en IMERG)"
        for label, extremes in sites for item in extremes if item.unit == "mm" for year in item.atypical_years
        if year.countercheck_value is not None and year.countercheck_value < year.value / 5
    ]
    parts = []
    if significant:
        backed = [f"{item.label.lower()} en {label}" for label, item in significant if item.countercheck.agreement == Agreement.COINCIDE]
        if not backed:
            subject = "la única tendencia significativa de extremos de lluvia no se repite" if len(significant) == 1 \
                else f"ninguna de las {len(significant)} tendencias significativas de extremos de lluvia se repite"
            parts.append(f"Contraste con GPM IMERG: {subject} con el satélite; sin respaldo independiente, "
                         + ("se lee como indicio y no como hallazgo." if len(significant) == 1 else "se leen como indicio y no como hallazgo."))
        else:
            parts.append(f"Contraste con GPM IMERG: {len(backed)} de {len(significant)} tendencias de extremos se repiten con el satélite ({', '.join(backed)})"
                         + ("; las demás no tienen respaldo independiente." if len(backed) < len(significant) else "."))
    if refuted:
        parts.append(f"IMERG no respalda {len(refuted)} valor(es) atípico(s) del reanálisis: {'; '.join(refuted)}.")
    return " ".join(parts)


async def run_climate_screening(request: ClimateScreeningRequest) -> ClimateScreeningResponse:
    timings = StageTimings()
    try:
        geometries = [PeruTerritoryCatalog().geometry(item.level, item.ubigeo) for item in request.territories]
    except TerritoryCatalogError as exc:
        raise TerritoryAnalysisError(str(exc)) from exc
    subjects = _subjects(request, geometries)
    points = [subject.representative_point for subject in subjects]
    extraction_start = perf_counter()
    ((datasets, territories), (terrain, terrain_error, timings.terrain_ms)) = await asyncio.gather(_extract(request), extract_terrain(points))
    timings.extraction_ms = elapsed_ms(extraction_start)
    expected_days = (request.end_date - request.start_date).days + 1

    analysis_start = perf_counter()
    variables_by_site = analyze_subjects(datasets, CLIMATE_VARIABLES, expected_days)
    extremes_by_site, thresholds = analyze_extremes(datasets)
    countercheck_error = None
    try:
        countercheck_by_site, _ = analyze_extremes(datasets, COUNTERCHECK)
        attach_countercheck(extremes_by_site, countercheck_by_site, COUNTERCHECK_SOURCE)
    except PowerConnectorError as exc:
        countercheck_error = str(exc)
    timings.analysis_ms = elapsed_ms(analysis_start)

    extra = {len(request.sites) + index: territory for index, territory in enumerate(territories)}
    sites = []
    for index, (subject, variables, extremes, threshold) in enumerate(zip(subjects, variables_by_site, extremes_by_site, thresholds, strict=True)):
        point = subject.representative_point
        territory = extra.get(index)
        sites.append(ClimateSiteResult(
            location=Point(latitude=point.latitude, longitude=point.longitude, label=subject.label), variables=variables, extremes=extremes,
            wet_day_p95_mm=threshold, territory=_territory_info(territory) if territory else None,
            cell_trends=[CellTrend(**vars(item)) for item in cell_trends(territory, CELL_TREND_VARIABLES)] if territory and territory.mode == "REGIONAL" else [],
        ))
    labelled = [
        SubjectSummaries(label=subject.label, summaries=[*variables, *extremes])
        for subject, variables, extremes in zip(subjects, variables_by_site, extremes_by_site, strict=True)
    ]
    variables_only = [SubjectSummaries(label=subject.label, summaries=variables) for subject, variables in zip(subjects, variables_by_site, strict=True)]
    trend_findings = collect_trend_findings(labelled)
    gaps = _data_gaps(terrain, countercheck_error)
    pending = sum(1 for gap in gaps if gap.status == Provenance.UNAVAILABLE)
    nasa_questions = answer_nasa_questions(
        labelled, trend_findings,
        {subject.label: (subject.representative_point.latitude, subject.representative_point.longitude) for subject in subjects},
        pending, SectorLens(readings=CLIMATE_READINGS, stable_notes=CLIMATE_STABLE_NOTES, economics=ECONOMICS_NOTE),
    )
    contrast = countercheck_summary([(site.location.label, site.extremes) for site in sites])
    if contrast:
        significant = next(question for question in nasa_questions if question.key == "significant")
        significant.answer = f"{significant.answer} {contrast}"
        significant.evidence.append(COUNTERCHECK_NOTE)
    # La lectura de inversión no debe afirmar un cambio de extremos que el satélite no confirma.
    unbacked = [f"{item.label.lower()} en {site.location.label}" for site in sites for item in site.extremes
                if item.significant_after_bh and item.countercheck and item.countercheck.agreement != Agreement.COINCIDE]
    if unbacked:
        so_what = next(question for question in nasa_questions if question.key == "so_what")
        so_what.answer = f"{so_what.answer} Salvedad: {', '.join(unbacked)} no se confirma con GPM IMERG; tómese como indicio a verificar."

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
    if countercheck_error is None:
        imerg_last = max((dataset[COUNTERCHECK][0][-1].timestamp for dataset in datasets if dataset[COUNTERCHECK][0]), default=None)
        counts = {value: sum(1 for site in sites for item in site.extremes if item.countercheck and item.countercheck.agreement == value) for value in Agreement}
        evaluation_evidence.append(StageEvidence(
            label="Contraste GPM IMERG",
            value=f"coinciden {counts[Agreement.COINCIDE]} · sin respaldo {counts[Agreement.SIN_RESPALDO]} · solo IMERG {counts[Agreement.SOLO_CONTRASTE]} · "
                  f"contradicen {counts[Agreement.CONTRADICE]}" + (f" · IMERG hasta {imerg_last:%d-%m-%Y}" if imerg_last else ""),
            provenance=Provenance.MODEL,
        ))
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
        method_notes=[*METHOD_NOTES, *([COUNTERCHECK_NOTE] if countercheck_error is None else []), *([TERRITORY_NOTE] if territories else [])],
    )
