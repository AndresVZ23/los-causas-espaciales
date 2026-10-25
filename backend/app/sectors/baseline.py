"""Línea base territorial sobre el contrato C2: módulo 4 (ambiental) y módulo 5 (patrimonio y dimensión social).

Ambos módulos comparten las áreas de estudio y el orden de una línea base de EIA peruana. El ambiental suma
vegetación MODIS con tendencia, relieve NASADEM y capas del ANA, MINAM y SERNANP; el patrimonial consulta las
capas del Ministerio de Cultura y no mide cambios en el tiempo, por lo que declara las preguntas de tendencia
como evidencia insuficiente en lugar de forzarlas.
"""

import asyncio
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

from shapely.geometry import shape

from ..connectors.peru.admin_boundaries import PeruTerritoryCatalog, TerritoryCatalogError
from ..connectors.peru.territory import LAYERS, TerritoryConnector, TerritoryConnectorError
from ..geospatial.buffers import buffer_km, window_km
from ..geospatial.geometry import GEOD, GeometryValidationError, inspect_geometry
from ..orchestration.extraction import elapsed_ms, extract_terrain, max_separation_km
from ..orchestration.nasa_questions import INSUFFICIENT, SectorLens, SubjectSummaries, answer_nasa_questions, collect_trend_findings, join_es
from ..orchestration.stages import analysis_stage, assemble_pipeline, export_stage, results_stage, selection_stage, stage, unique
from ..schemas.analysis import Point, Provenance
from ..schemas.baseline import BaselineLayer, BaselineRequest, BaselineScreeningResponse, Component, SubjectBaseline
from ..schemas.data_sources import TerritorialQueryRequest
from ..schemas.pipeline import VariableSummary
from ..schemas.screening import DataGap, NasaQuestionAnswer, PipelineStatus, QuestionStatus, Sector, StageEvidence, StudySubject, SubjectKind
from ..statistics.multiple_testing import benjamini_hochberg
from ..statistics.trends import decision_p_value
from .baseline_layers import COMPONENT_SOURCES, summarize_layer
from .baseline_vegetation import VEGETATION_VARIABLES, subject_vegetation
from .climate import LEVEL_SUFFIX

SECTOR_LABELS = {Sector.ENVIRONMENT: "Línea base ambiental", Sector.HERITAGE: "Patrimonio y dimensión social"}
COMPONENTS: dict[Sector, list[Component]] = {Sector.ENVIRONMENT: ["fisico", "biologico"], Sector.HERITAGE: ["sociocultural"]}
COMPONENT_LABELS: dict[Component, str] = {"fisico": "Medio físico", "biologico": "Medio biológico", "sociocultural": "Medio sociocultural"}

ENVIRONMENT_READINGS = {
    ("VCF_BARE", "increasing"): "aumenta la proporción de suelo sin vegetación: la línea base debe verificar en campo si es degradación, expansión urbana o la variabilidad propia de las lomas",
    ("VCF_BARE", "decreasing"): "disminuye el suelo sin vegetación: puede reflejar expansión agrícola o años más húmedos; contrastar con la cobertura del MINAM y en campo",
    ("VCF_NONTREE", "increasing"): "aumenta la vegetación no arbórea (matorral, pastos o cultivos): revisar si corresponde a riego o a regeneración",
    ("VCF_NONTREE", "decreasing"): "disminuye la vegetación no arbórea: conviene priorizar la línea base de flora y revisar la pérdida de cobertura",
    ("VCF_TREE", "increasing"): "aumenta la cobertura arbórea",
    ("VCF_TREE", "decreasing"): "disminuye la cobertura arbórea: posible pérdida de bosque o de árboles en zonas de riego",
    ("NPP", "increasing"): "sube la producción primaria neta: la vegetación es más productiva que al inicio de la serie",
    ("NPP", "decreasing"): "baja la producción primaria neta: señal indirecta de estrés o pérdida de vegetación",
}
ENVIRONMENT_STABLE = {
    "VCF_BARE": "La proporción de suelo sin vegetación no cambia con significancia: el promedio del período, con su variabilidad, sirve como referencia satelital para la línea base.",
}
DISCLAIMERS = {
    Sector.ENVIRONMENT: (
        "Insumos de screening para preparar la línea base de un EIA: indicadores satelitales indirectos (MODIS a 250–500 m) y capas oficiales "
        "consultadas en línea. No sustituye la línea base de campo, el EIA ni la opinión de SENACE, ANA, SERNANP o MINAM; una capa sin registros "
        "no prueba la ausencia del recurso o del ecosistema."
    ),
    Sector.HERITAGE: (
        "Identificación preliminar de restricciones y antecedentes registrados por el Ministerio de Cultura. No sustituye el CIRA, el plan de "
        "monitoreo arqueológico, la consulta previa ni la evaluación del Ministerio de Cultura. La ausencia de registros no prueba la ausencia de "
        "patrimonio arqueológico, pueblos indígenas o conflictos, y nada de esto es opinión legal."
    ),
}
SENACE_GAP = DataGap(
    dataset="SENACE · instrumentos ambientales aprobados",
    impact="No se listan los EIA ni otros instrumentos ya aprobados en el área: el servidor de mapas de SENACE presenta un certificado TLS inválido (verificado el 24-oct-2026).",
    next_action="Consultar el registro de SENACE en su portal o esperar un servicio geográfico con TLS válido.",
)
STATIC_GAPS = {
    Sector.ENVIRONMENT: [
        SENACE_GAP,
        DataGap(dataset="ANA · monitoreo de calidad de agua", impact="La categoría ECA es el uso asignado al cuerpo de agua, no su calidad medida.",
                next_action="Integrar resultados de monitoreo de calidad de agua publicados por la ANA."),
        DataGap(dataset="Inventarios de flora y fauna", impact="Los satélites no registran especies ni hábitats a escala de proyecto.",
                next_action="Levantar la línea base biológica en campo como parte del EIA."),
    ],
    Sector.HERITAGE: [
        DataGap(dataset="Base de Datos de Pueblos Indígenas (Ministerio de Cultura)",
                impact="No se identifican pueblos ni localidades indígenas: la base se publica como sitio web, sin servicio geográfico consultable.",
                next_action="Consultar la BDPI y solicitar información al Viceministerio de Interculturalidad."),
        DataGap(dataset="Comunidades campesinas y nativas (MIDAGRI)",
                impact="Sin límites de comunidades: el geoportal de MIDAGRI presenta un certificado TLS no verificable (24-oct-2026).",
                next_action="Solicitar la información de comunidades a MIDAGRI o al gobierno regional."),
        DataGap(dataset="Conflictos socioambientales (Defensoría del Pueblo)",
                impact="Se publican como reportes mensuales en PDF, no como datos geográficos consultables.",
                next_action="Revisar el reporte mensual vigente de la Defensoría para los distritos del área."),
        SENACE_GAP,
        DataGap(dataset="Evaluación arqueológica del propio proyecto",
                impact="Los registros y antecedentes de otros proyectos no reemplazan el CIRA ni el diagnóstico propio.",
                next_action="Tramitar el CIRA o el procedimiento que corresponda ante el Ministerio de Cultura."),
    ],
}


class BaselineScreeningError(RuntimeError):
    pass


@dataclass(frozen=True)
class StudyArea:
    subject: StudySubject
    origin: str
    area_km2: float
    window_km: int


def _area_km2(geometry: dict) -> float:
    area_m2, _ = GEOD.geometry_area_perimeter(shape(geometry))
    return abs(area_m2) / 1_000_000


def _area(identifier: str, label: str, study: dict, origin: str, window: int) -> StudyArea:
    inside = shape(study).representative_point()
    point = Point(latitude=inside.y, longitude=inside.x, label=label)
    subject = StudySubject(id=identifier, label=label, kind=SubjectKind.POLYGON, geometry=study, representative_point=point)
    return StudyArea(subject=subject, origin=origin, area_km2=round(_area_km2(study), 3), window_km=window)


def resolve_areas(request: BaselineRequest) -> list[StudyArea]:
    """Convierte sitios, territorios y geometrías en polígonos WGS84 de estudio con etiqueta única."""
    areas: list[StudyArea] = []
    radius = request.buffer_km
    for index, site in enumerate(request.sites, start=1):
        label = f"{site.label or f'Sitio {index}'} (radio {radius:g} km)"
        study = buffer_km({"type": "Point", "coordinates": [site.longitude, site.latitude]}, radius)
        areas.append(_area(f"sitio-{index}", label, study, f"Círculo de {radius:g} km de radio (supuesto del usuario)", max(1, min(10, ceil(radius)))))
    catalog = PeruTerritoryCatalog()
    for ref in request.territories:
        try:
            territory = catalog.geometry(ref.level, ref.ubigeo)
        except TerritoryCatalogError as exc:
            raise BaselineScreeningError(str(exc)) from exc
        study = territory.feature.get("geometry", territory.feature)
        label = f"{territory.territory.name} ({LEVEL_SUFFIX.get(ref.level, ref.level)})"
        level = {"department": "departamento", "province": "provincia", "district": "distrito"}.get(ref.level, ref.level)
        area = _area(f"ubigeo-{ref.ubigeo}", label, study, f"Territorio IGN: {level} {ref.ubigeo} (límites de 2015, no catastrales)", 1)
        point = area.subject.representative_point
        areas.append(StudyArea(area.subject, area.origin, area.area_km2, window_km(study, point.longitude, point.latitude)))
    for item in request.geometries:
        try:
            inspected = inspect_geometry(item.geometry)
        except (GeometryValidationError, ValueError) as exc:
            raise BaselineScreeningError(f"{item.label}: {exc}") from exc
        if inspected.geometry_type in {"Polygon", "MultiPolygon"}:
            study, origin = item.geometry, "Polígono del usuario"
        elif inspected.geometry_type in {"LineString", "MultiLineString"}:
            study, origin = buffer_km(item.geometry, radius), f"Corredor del usuario ampliado {radius:g} km a cada lado"
        else:
            raise BaselineScreeningError(f"{item.label}: use un polígono o una línea; los puntos van como sitios con radio.")
        area = _area(item.id, item.label, study, origin, 1)
        point = area.subject.representative_point
        areas.append(StudyArea(area.subject, area.origin, area.area_km2, window_km(study, point.longitude, point.latitude)))
    labels = [area.subject.label for area in areas]
    if len(set(labels)) != len(labels):
        raise BaselineScreeningError("Cada área necesita un nombre distinto.")
    return areas


# SIGDA (Cultura) corta la conexión TLS a la IP tras unas 20 consultas seguidas, aun de dos en dos (verificado el
# 24-oct-2026): una consulta a la vez por servidor y una pausa entre consultas reales; lo que sale de caché no espera.
PER_HOST = 1
PACE_SECONDS = 0.5
RETRY_SECONDS = 3.0


def _host_limits() -> dict[str, asyncio.Semaphore]:
    return defaultdict(lambda: asyncio.Semaphore(PER_HOST))


async def _one_layer(connector: TerritoryConnector, geometry: dict, source_id: str, limit: asyncio.Semaphore):
    """Una capa por consulta, con tope por servidor y un reintento si el servicio no respondió."""
    for attempt in range(2):
        async with limit:
            response = await connector.query(TerritorialQueryRequest(geometry=geometry, source_ids=[source_id]))
            result = response.sources[0]
            if result.provenance != Provenance.CACHED:
                await asyncio.sleep(PACE_SECONDS)
        if result.status == "READY" or not result.limitations[0].startswith("El servicio oficial no respondió") or attempt:
            return result
        await asyncio.sleep(RETRY_SECONDS)
    return result


async def _layers(area: StudyArea, components: Sequence[Component], limits: dict[str, asyncio.Semaphore]) -> tuple[list[BaselineLayer], str | None]:
    component_of = {source: component for component in components for source in COMPONENT_SOURCES[component]}
    connector = TerritoryConnector()
    try:
        results = await asyncio.gather(*(_one_layer(connector, area.subject.geometry, source_id, limits[urlparse(LAYERS[source_id].base_url).hostname or ""])
                                         for source_id in component_of))
    except TerritoryConnectorError as exc:
        return [], f"Consulta de capas oficiales: {exc}"
    return [summarize_layer(result, component_of[result.source_id]) for result in results], None


def _adjust_by_variable(summaries: Sequence[VariableSummary]) -> None:
    """Benjamini–Hochberg por variable entre las áreas que tienen serie (la familia puede ser menor que el total)."""
    families: dict[str, list[VariableSummary]] = defaultdict(list)
    for item in summaries:
        families[item.variable].append(item)
    for family in families.values():
        adjusted = benjamini_hochberg([decision_p_value(item.trend) for item in family])
        for item, value in zip(family, adjusted, strict=True):
            item.adjusted_p_value = value
            item.significant_after_bh = value is not None and value < item.trend.alpha


def _layer_sentences(baselines: Sequence[SubjectBaseline]) -> list[str]:
    """Una frase por área con lo que las capas sí registran, en palabras de la fuente."""
    sentences = []
    for baseline in baselines:
        present = [f"{layer.dataset.lower()} ({layer.intersection_count}{'+' if layer.truncated else ''})"
                   for layer in baseline.layers if layer.status == "READY" and layer.intersection_count]
        if present:
            sentences.append(f"{baseline.subject} se superpone con {join_es(present)}.")
    return sentences


def _heritage_questions(baselines: Sequence[SubjectBaseline], pending: int) -> list[NasaQuestionAnswer]:
    not_temporal = f"{INSUFFICIENT} Este módulo no mide cambios en el tiempo: identifica restricciones y antecedentes registrados."
    questions = [
        NasaQuestionAnswer(key=key, question=question, question_es=question_es, status=QuestionStatus.INSUFFICIENT, answer=not_temporal,
                           evidence=["Los registros del Ministerio de Cultura no son series temporales."], provenance=[Provenance.UNAVAILABLE], stage_steps=steps)
        for key, question, question_es, steps in (
            ("what", "What is changing?", "¿Qué está cambiando?", [3, 4]),
            ("where", "Where is it changing?", "¿Dónde está cambiando?", [1, 5]),
            ("how_much", "How much is it changing?", "¿Cuánto está cambiando?", [4]),
            ("significant", "Is the change statistically significant?", "¿El cambio es estadísticamente significativo?", [4]),
        )
    ]
    sentences = _layer_sentences(baselines) or ["Las capas consultadas no devuelven registros en las áreas analizadas; eso no prueba ausencia de patrimonio."]
    questions.append(NasaQuestionAnswer(
        key="so_what", question="What do these changes mean for investment decisions?", question_es="¿Qué significan estos cambios para invertir?",
        status=QuestionStatus.PARTIAL, answer=" ".join(sentences) + " Toda superposición es una alerta de debida diligencia, no una conclusión legal.",
        evidence=[f"{pending} fuentes sociales o patrimoniales siguen sin servicio consultable.", "Registros en palabras de la fuente; sin inferencias desde imágenes satelitales."],
        provenance=[Provenance.REAL, Provenance.UNAVAILABLE], stage_steps=[5, 6],
    ))
    return questions


def _extraction_stage(sector: Sector, baselines: Sequence[SubjectBaseline], duration_ms: float) -> "object":
    layers = [layer for baseline in baselines for layer in baseline.layers]
    ready = sum(1 for layer in layers if layer.status == "READY")
    evidence = [StageEvidence(label="Consultas a capas oficiales", value=f"{ready} de {len(layers)} respondieron", provenance=Provenance.REAL if ready else Provenance.UNAVAILABLE)]
    provenance = [layer.provenance for layer in layers]
    errors = [error for baseline in baselines for error in baseline.errors]
    if sector == Sector.ENVIRONMENT:
        summaries = [item for baseline in baselines for item in baseline.vegetation]
        cached = sum(1 for item in summaries if item.source.provenance == Provenance.CACHED)
        years = max((len(item.annual_series) for item in summaries), default=0)
        evidence += [
            StageEvidence(label="Series MODIS anuales", value=f"{len(summaries)} · hasta {years} años", provenance=Provenance.REAL if summaries else Provenance.UNAVAILABLE),
            StageEvidence(label="Series desde caché", value=f"{cached} de {len(summaries)}", provenance=Provenance.CACHED if cached else Provenance.REAL),
        ]
        provenance += [item.source.provenance for item in summaries]
    if errors:
        evidence.append(StageEvidence(label="Fuentes con error", value=" · ".join(errors)[:300], provenance=Provenance.UNAVAILABLE))
    status = PipelineStatus.PARTIAL if errors or ready < len(layers) else PipelineStatus.COMPLETED
    summary = f"{ready} de {len(layers)} consultas a capas oficiales respondieron" + (
        f" y MODIS entregó {sum(len(b.vegetation) for b in baselines)} series anuales." if sector == Sector.ENVIRONMENT else ".")
    return stage("extraction", status, summary, unique(provenance) or [Provenance.UNAVAILABLE], evidence, duration_ms, ["what"])


def _territorial_stage(sector: Sector, baselines: Sequence[SubjectBaseline], terrain, terrain_error: str | None, gaps: Sequence[DataGap], duration_ms: float):
    evidence = []
    for component in COMPONENTS[sector]:
        layers = [layer for b in baselines for layer in b.layers if layer.component == component]
        with_records = sorted({layer.dataset for layer in layers if layer.intersection_count})
        evidence.append(StageEvidence(label=COMPONENT_LABELS[component], value=f"{len(with_records)} capas con registros: {', '.join(with_records) or 'ninguna'}",
                                      provenance=Provenance.REAL))
    if sector == Sector.ENVIRONMENT:
        ready = sum(1 for site in terrain.sites if site.status == "READY") if terrain else 0
        evidence.append(StageEvidence(label="Relieve NASADEM", value=f"{ready} de {len(baselines)} áreas" if terrain else (terrain_error or "No consultado"),
                                      provenance=Provenance.REAL if ready else Provenance.UNAVAILABLE))
    pending = [gap.dataset for gap in gaps if gap.status == Provenance.UNAVAILABLE]
    evidence.append(StageEvidence(label="Fuentes pendientes", value=", ".join(pending) or "Ninguna", provenance=Provenance.UNAVAILABLE if pending else None))
    status = PipelineStatus.PARTIAL if pending else PipelineStatus.COMPLETED
    return stage("territorial", status, f"Capas oficiales leídas por medio de la línea base; {len(pending)} fuentes pendientes no se interpretan como ausencia.",
                 [Provenance.REAL, Provenance.UNAVAILABLE] if pending else [Provenance.REAL], evidence, duration_ms, ["where", "so_what"])


def _period(baselines: Sequence[SubjectBaseline], is_environment: bool) -> str:
    """Período «inicio/fin» del contrato: años MODIS en el ambiental; fecha de consulta en el patrimonial (registros vigentes)."""
    years = [item.annual_series[i].year for b in baselines for item in b.vegetation for i in (0, -1)]
    if is_environment and years:
        return f"{min(years)}-01-01/{max(years)}-12-31"
    today = datetime.now(timezone.utc).date().isoformat()
    return f"{today}/{today}"


async def run_baseline_screening(request: BaselineRequest, sector: Sector) -> BaselineScreeningResponse:
    if sector not in COMPONENTS:
        raise BaselineScreeningError(f"Sector sin línea base: {sector}.")
    components = COMPONENTS[sector]
    areas = resolve_areas(request)
    points = [area.subject.representative_point for area in areas]
    started = perf_counter()

    async def nothing():
        return None

    is_environment = sector == Sector.ENVIRONMENT
    limits = _host_limits()   # compartidos entre áreas: el tope es por servidor, no por área
    layer_results, vegetation, terrain_result = await asyncio.gather(
        asyncio.gather(*(_layers(area, components, limits) for area in areas)),
        asyncio.gather(*(subject_vegetation(area.subject.representative_point, area.subject.geometry, area.window_km, area.area_km2) for area in areas)) if is_environment else nothing(),
        extract_terrain(points) if is_environment else nothing(),
    )
    extraction_ms = elapsed_ms(started)
    terrain, terrain_error, terrain_ms = terrain_result if terrain_result else (None, None, 0.0)

    baselines: list[SubjectBaseline] = []
    for index, area in enumerate(areas):
        layers, layer_error = layer_results[index]
        veg = vegetation[index] if vegetation else None
        baselines.append(SubjectBaseline(
            subject=area.subject.label, origin=area.origin, area_km2=area.area_km2, study_area=area.subject.geometry,
            modis_window_km=area.window_km if is_environment else None, modis_pixels=veg.pixels if veg else {},
            vegetation=veg.summaries if veg else [], vegetation_notes=veg.notes if veg else [],
            land_cover=veg.land_cover if veg else None, layers=layers,
            errors=[e for e in [layer_error, *(veg.errors if veg else [])] if e],
        ))

    analysis_started = perf_counter()
    _adjust_by_variable([item for baseline in baselines for item in baseline.vegetation])
    labelled = [SubjectSummaries(label=b.subject, summaries=b.vegetation) for b in baselines]
    findings = collect_trend_findings(labelled) if is_environment else []
    analysis_ms = elapsed_ms(analysis_started)

    gaps = list(STATIC_GAPS[sector])
    for baseline in baselines:
        for layer in baseline.layers:
            if layer.status == "DATA_UNAVAILABLE" and all(gap.dataset != layer.dataset for gap in gaps):
                gaps.append(DataGap(dataset=layer.dataset, impact=layer.limitations[0] if layer.limitations else "El servicio no respondió.",
                                    next_action=f"Reintentar la consulta a {layer.organization}."))
        for error in baseline.errors:
            gaps.append(DataGap(dataset=f"{baseline.subject} · fuente con error", impact=error, next_action="Reintentar; el análisis no rellena el faltante."))
    pending = sum(1 for gap in gaps if gap.status == Provenance.UNAVAILABLE)

    if is_environment:
        coordinates = {b.subject: (p.latitude, p.longitude) for b, p in zip(baselines, points, strict=True)}
        questions = answer_nasa_questions(labelled, findings, coordinates, pending, SectorLens(readings=ENVIRONMENT_READINGS, stable_notes=ENVIRONMENT_STABLE))
        questions[1].evidence = [
            f"{b.subject}: ventana MODIS de ±{b.modis_window_km} km alrededor de {p.latitude:.3f}, {p.longitude:.3f}; "
            f"{b.modis_pixels.get('MOD44B', 0)} píxeles de 250 m con centro dentro del área"
            for b, p in zip(baselines, points, strict=True)
        ]
        extra = _layer_sentences(baselines)
        if extra:
            questions[4].answer = f"{questions[4].answer} {' '.join(extra)}".strip()
    else:
        questions = _heritage_questions(baselines, pending)

    all_layers = [layer for b in baselines for layer in b.layers]
    provenance = unique([*(layer.provenance for layer in all_layers), Provenance.MODEL, *([Provenance.UNAVAILABLE] if pending else [])])
    label = SECTOR_LABELS[sector]
    variables = [v.key for v in VEGETATION_VARIABLES] if is_environment else []
    configuration = stage("configuration", PipelineStatus.COMPLETED, f"{label}: {', '.join(COMPONENT_LABELS[c].lower() for c in components)}.", [Provenance.ASSUMPTION], [
        StageEvidence(label="Sector", value=label),
        StageEvidence(label="Medios de la línea base", value=", ".join(COMPONENT_LABELS[c] for c in components)),
        StageEvidence(label="Capas oficiales", value=str(sum(len(COMPONENT_SOURCES[c]) for c in components))),
        StageEvidence(label="Indicadores NASA", value="MODIS MOD44B, MOD17A3HGF, MCD12Q1 y NASADEM" if is_environment else "No aplica: registros oficiales"),
        StageEvidence(label="Radio para sitios y corredores", value=f"{request.buffer_km:g} km", provenance=Provenance.ASSUMPTION),
    ])
    if is_environment:
        analysis = analysis_stage(labelled, findings, analysis_ms)
    else:
        analysis = stage("analysis", PipelineStatus.UNAVAILABLE, "No aplica: los registros patrimoniales no son series temporales.", [Provenance.UNAVAILABLE],
                         [StageEvidence(label="Pruebas de tendencia", value="No aplica", provenance=Provenance.UNAVAILABLE)], analysis_ms)
    evaluation = stage("evaluation", PipelineStatus.COMPLETED,
                       " ".join(_layer_sentences(baselines)) or "Ninguna capa registra objetos en las áreas; eso no prueba ausencia.", [Provenance.REAL, Provenance.MODEL],
                       [StageEvidence(label=b.subject, value=f"{sum(1 for layer in b.layers if layer.intersection_count)} capas con registros · {b.area_km2:,.2f} km²") for b in baselines])
    finance = stage("finance", PipelineStatus.UNAVAILABLE, "No aplica: la línea base no evalúa finanzas.", [Provenance.UNAVAILABLE],
                    [StageEvidence(label="Impacto económico", value="No aplica en este módulo", provenance=Provenance.UNAVAILABLE)])
    pipeline = assemble_pipeline([
        selection_stage([a.subject for a in areas], max_separation_km(points)),
        configuration,
        _extraction_stage(sector, baselines, extraction_ms),
        analysis,
        _territorial_stage(sector, baselines, terrain, terrain_error, gaps, terrain_ms),
        evaluation,
        finance,
        results_stage(findings, gaps, provenance),
        export_stage(provenance),
    ])
    method_notes = [
        "Áreas de estudio en WGS84; los sitios se convierten en círculos y los corredores se amplían con un buffer geodésico.",
        "Capas oficiales consultadas en línea por intersección espacial; los registros se citan con los atributos que publica cada fuente.",
    ]
    if is_environment:
        method_notes += [
            "MODIS anual (servicio ORNL DAAC): promedio de los píxeles con centro dentro del área; un año entra si al menos la mitad de esos píxeles es válida.",
            "Tendencia de cada indicador con Mann–Kendall corregido por Hamed–Rao y pendiente de Sen; Benjamini–Hochberg por indicador entre áreas.",
            "Cobertura del suelo MCD12Q1 (IGBP): composición del primer y del último año publicados y porcentaje de píxeles que cambiaron de clase.",
        ]
    return BaselineScreeningResponse(
        analysis_id=uuid4().hex[:16], generated_at=datetime.now(timezone.utc), sector=sector, sector_label=label,
        title=f"{label} — {join_es([a.subject.label for a in areas])}",
        period=_period(baselines, is_environment),
        subjects=[a.subject for a in areas], pipeline=pipeline, nasa_questions=questions, trend_findings=findings, terrain=terrain,
        data_gaps=gaps, assumption_items=[], disclaimer=DISCLAIMERS[sector],
        components=components, baselines=baselines, method_notes=method_notes,
    )
