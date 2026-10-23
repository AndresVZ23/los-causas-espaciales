"""K2 road pilot: climate exposure, territorial alerts and mitigation economics."""

from __future__ import annotations

import asyncio
import calendar
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from time import perf_counter

from shapely.geometry import shape

from ..connectors.nasa.power import PowerConnectorError
from ..connectors.nasa.power_regional import RegionalPowerConnector, RegionalPowerError
from ..connectors.peru.territory import TerritoryConnector, TerritoryConnectorError
from ..finance.engine import calculate_npv
from ..finance.sensitivity import Driver, break_even_item, tornado
from ..geospatial.geometry import GeometryValidationError, inspect_geometry
from ..orchestration.analysis import analyze_subjects
from ..orchestration.extraction import PowerDataset, elapsed_ms, extract_power, extract_terrain, max_separation_km
from ..orchestration.nasa_questions import SectorLens, SubjectSummaries, answer_nasa_questions, collect_trend_findings, millions_usd
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
from ..schemas.analysis import FinanceRequest, Point, Provenance
from ..schemas.data_sources import TerritorialQueryRequest, TerritorialQueryResponse
from ..schemas.road import (
    RoadAssumptions,
    RoadCellMetric,
    RoadCorridorSource,
    RoadFinancialProjection,
    RoadScreeningRequest,
    RoadScreeningResponse,
    RoadSegmentInput,
    RoadSegmentResult,
    RoadSpatialExposure,
    RoadTerritorialEvidence,
    RoadTerritorialSourceSummary,
)
from ..schemas.scoring import Criterion, Direction, Scorecard, ScorecardRequest, SubjectValues
from ..schemas.screening import (
    AssumptionItem,
    DataGap,
    FinanceScenario,
    PipelineStatus,
    StageEvidence,
    StudySubject,
    SubjectKind,
    SubjectSensitivity,
)
from ..schemas.spatial_sampling import SpatialSamplingRequest
from ..schemas.terrain import TerrainResponse
from ..scoring.multicriteria import build_scorecard

ROAD_VARIABLES = ["PRECTOTCORR", "T2M"]
PRECIPITATION = "PRECTOTCORR"
SECTOR_LABEL = "Infraestructura vial"
PILOT_PATH = Path(__file__).resolve().parents[2] / "data" / "pilots" / "moquegua_ilo_osm.geojson"
EXPOSURE_DAYS = 365
TERRITORIAL_SOURCE_IDS = [
    "cenepred-flood-risk",
    "cenepred-mass-movement-risk",
    "sernanp-anp",
    "cultura-archaeology",
    "cultura-archaeology-declared",
    "ingemmet-geohazards",
]

ROAD_READINGS = {
    (PRECIPITATION, "increasing"): "la precipitación media aumenta: conviene revisar drenaje, erosión y estabilidad de taludes",
    (PRECIPITATION, "decreasing"): "la precipitación media disminuye; esto no elimina episodios extremos ni riesgo de huaicos",
    ("T2M", "increasing"): "la temperatura aumenta: revisar envejecimiento de pavimento y condiciones de mantenimiento",
    ("T2M", "decreasing"): "la temperatura disminuye; la implicancia vial requiere verificación local",
}
ROAD_STABLE_NOTES = {
    PRECIPITATION: "La precipitación media no cambia con significancia en los tramos; eso no demuestra estabilidad de los extremos diarios.",
}
ASSUMPTION_LABELS = {
    "baseline_interruption_days_per_year": ("Interrupción anual base", "días/año"),
    "residual_interruption_fraction": ("Fracción residual tras mitigación", "fracción"),
    "cost_per_interruption_day_usd": ("Costo por día de interrupción", "USD/día"),
    "mitigation_capex_usd_per_km": ("CAPEX de mitigación", "USD/km"),
    "annual_maintenance_usd_per_km": ("Mantenimiento incremental", "USD/km/año"),
    "discount_rate": ("Tasa de descuento", "fracción"),
    "horizon_years": ("Horizonte", "años"),
    "heavy_rain_threshold_mm_day": ("Umbral operativo de lluvia fuerte", "mm/día"),
    "interruption_days_sensitivity": ("Rango de días interrumpidos (±)", "fracción"),
    "cost_per_day_sensitivity": ("Rango del costo diario (±)", "fracción"),
    "capex_sensitivity": ("Rango del CAPEX (±)", "fracción"),
    "maintenance_sensitivity": ("Rango del mantenimiento (±)", "fracción"),
    "residual_fraction_sensitivity": ("Rango de la fracción residual (±)", "puntos"),
    "discount_rate_sensitivity": ("Rango de la tasa (±)", "puntos"),
}


class RoadScreeningError(RuntimeError):
    pass


def _default_segments() -> tuple[list[RoadSegmentInput], RoadCorridorSource]:
    payload = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    segments = [
        RoadSegmentInput(
            id=str(feature["properties"]["id"]),
            label=str(feature["properties"]["name"]),
            geometry=feature["geometry"],
        )
        for feature in payload["features"]
    ]
    return segments, RoadCorridorSource(
        name=str(payload["name"]),
        source=str(payload["source"]),
        source_url=str(payload["source_url"]),
        license=str(payload["license"]),
        retrieved_at=str(payload["retrieved_at"]),
        provenance=Provenance.REAL,
        limitations=[
            "Geometría simplificada de screening calculada sobre OpenStreetMap; no es un eje oficial del MTC.",
            "No contiene inventario de puentes, drenajes, estado del pavimento ni derecho de vía.",
        ],
    )


def _subjects(request: RoadScreeningRequest) -> tuple[list[RoadSegmentInput], list[StudySubject], list[float], RoadCorridorSource]:
    if request.segments is None:
        segments, source = _default_segments()
    else:
        segments = request.segments
        source = RoadCorridorSource(
            name="Corredor proporcionado por el usuario",
            source="GeoJSON del usuario",
            provenance=Provenance.ASSUMPTION,
            limitations=["La plataforma valida geometría, CRS y longitud; no verifica titularidad ni origen legal del archivo."],
        )
    subjects: list[StudySubject] = []
    lengths: list[float] = []
    for segment in segments:
        try:
            inspected = inspect_geometry(segment.geometry)
            line = shape(segment.geometry)
        except (GeometryValidationError, ValueError) as exc:
            raise RoadScreeningError(f"{segment.label}: {exc}") from exc
        if inspected.geometry_type != "LineString" or inspected.length_km is None:
            raise RoadScreeningError(f"{segment.label}: cada tramo debe ser un LineString WGS84 válido.")
        midpoint = line.interpolate(0.5, normalized=True)
        point = Point(latitude=midpoint.y, longitude=midpoint.x, label=segment.label)
        subjects.append(StudySubject(
            id=segment.id,
            label=segment.label,
            kind=SubjectKind.SEGMENT,
            geometry=segment.geometry,
            representative_point=point,
        ))
        lengths.append(inspected.length_km)
    return segments, subjects, lengths, source


def _heavy_rain_days(dataset: PowerDataset, threshold: float) -> tuple[float | None, int]:
    observations = dataset[PRECIPITATION][0]
    by_year: dict[int, list] = defaultdict(list)
    for item in observations:
        by_year[item.timestamp.year].append(item)
    counts = []
    for year, values in by_year.items():
        expected = 366 if calendar.isleap(year) else 365
        if len(values) / expected >= 0.95:
            counts.append(sum(item.value >= threshold for item in values))
    return (round(fmean(counts), 3), len(counts)) if counts else (None, 0)


async def _spatial_exposure(subject: StudySubject, request: RoadScreeningRequest) -> tuple[RoadSpatialExposure | None, str | None]:
    end = request.end_date
    start = max(request.start_date, end - timedelta(days=EXPOSURE_DAYS - 1))
    try:
        sampled = await RegionalPowerConnector().sample(SpatialSamplingRequest(
            subject={
                "type": "Feature",
                "properties": {"kind": "segment", "name": subject.label, "origin": "K2"},
                "geometry": subject.geometry,
            },
            variable=PRECIPITATION,
            start_date=start,
            end_date=end,
            corridor_buffer_km=request.corridor_buffer_km,
        ))
    except RegionalPowerError as exc:
        return None, str(exc)
    aggregate_values = [item.value for item in sampled.aggregate]
    cells = []
    for cell in sampled.cells:
        values = [item.value for item in cell.observations]
        cells.append(RoadCellMetric(
            cell_id=cell.cell_id,
            center=cell.center,
            weight=cell.weight,
            mean_precipitation_mm_day=round(fmean(values), 4) if values else None,
            rx1day_mm=round(max(values), 4) if values else None,
        ))
    return RoadSpatialExposure(
        period=f"{start.isoformat()}/{end.isoformat()}",
        unit=sampled.unit,
        cell_count=len(sampled.cells),
        spatial_coverage_percent=sampled.spatial_coverage_percent,
        mean_precipitation_mm_day=round(fmean(aggregate_values), 4) if aggregate_values else None,
        rx1day_mm=round(max(aggregate_values), 4) if aggregate_values else None,
        cells=cells,
        provenance=sampled.source.provenance,
        source_url=sampled.source.source_url,
        method=sampled.method,
        limitations=sampled.limitations,
    ), None


async def _spatial_exposures(subjects: list[StudySubject], request: RoadScreeningRequest):
    results = []
    errors = []
    for subject in subjects:
        result, error = await _spatial_exposure(subject, request)
        results.append(result)
        errors.append(error)
    return results, errors


def _territorial_summary(subject: StudySubject, response: TerritorialQueryResponse) -> RoadTerritorialEvidence:
    return RoadTerritorialEvidence(
        subject=subject.label,
        sources=[RoadTerritorialSourceSummary(
            source_id=item.source_id,
            status=item.status,
            intersection_count=item.intersection_count,
            provenance=item.provenance,
            downloaded_at=item.downloaded_at,
            limitations=item.limitations,
        ) for item in response.sources],
    )


async def _territorial_evidence(subjects: list[StudySubject], enabled: bool):
    if not enabled:
        return [], ["Consulta territorial desactivada por el usuario."] * len(subjects)
    connector = TerritoryConnector()
    evidence = []
    errors: list[str | None] = []
    for subject in subjects:
        try:
            response = await connector.query(TerritorialQueryRequest(
                geometry=subject.geometry,
                source_ids=TERRITORIAL_SOURCE_IDS,
            ))
            evidence.append(_territorial_summary(subject, response))
            errors.append(None)
        except TerritoryConnectorError as exc:
            evidence.append(RoadTerritorialEvidence(subject=subject.label, sources=[]))
            errors.append(str(exc))
    return evidence, errors


def _road_npv(inputs: Mapping[str, float], length_km: float, assumptions: RoadAssumptions) -> RoadFinancialProjection:
    days = inputs["interruption_days"]
    residual_fraction = inputs["residual_fraction"]
    avoided_days = days * (1 - residual_fraction)
    annual_avoided_cost = avoided_days * inputs["cost_per_day"]
    request = FinanceRequest(
        initial_capex=inputs["mitigation_capex"],
        annual_revenue=annual_avoided_cost,
        annual_opex=inputs["annual_maintenance"],
        discount_rate=inputs["discount_rate"],
        horizon_years=assumptions.horizon_years,
    )
    result = calculate_npv(request)
    return RoadFinancialProjection(
        baseline_interruption_days_per_year=days,
        residual_interruption_days_per_year=round(days * residual_fraction, 4),
        avoided_interruption_days_per_year=round(avoided_days, 4),
        cost_per_interruption_day_usd=inputs["cost_per_day"],
        annual_avoided_cost_usd=round(annual_avoided_cost, 2),
        mitigation_capex_usd=inputs["mitigation_capex"],
        annual_maintenance_usd=inputs["annual_maintenance"],
        npv_usd=result.npv,
        cash_flows_usd=result.cash_flows,
        formula="VAN mitigación = −CAPEX + Σ[(días evitados × costo/día) − mantenimiento] / (1+r)^t",
        limitations=[
            "Los días de interrupción, costo diario, CAPEX, mantenimiento, tasa y horizonte son supuestos del usuario.",
            "NASA no observa cierres viales ni pérdidas económicas; la lluvia y el relieve solo describen exposición.",
            f"El CAPEX por defecto escala linealmente con {length_km:.3f} km; requiere presupuesto de ingeniería.",
        ],
    )


def _base_finance(segment: RoadSegmentInput, length_km: float, assumptions: RoadAssumptions) -> dict[str, float]:
    return {
        "interruption_days": segment.expected_interruption_days_per_year
        if segment.expected_interruption_days_per_year is not None
        else assumptions.baseline_interruption_days_per_year,
        "residual_fraction": assumptions.residual_interruption_fraction,
        "cost_per_day": assumptions.cost_per_interruption_day_usd,
        "mitigation_capex": segment.mitigation_capex_usd
        if segment.mitigation_capex_usd is not None
        else assumptions.mitigation_capex_usd_per_km * length_km,
        "annual_maintenance": assumptions.annual_maintenance_usd_per_km * length_km,
        "discount_rate": assumptions.discount_rate,
    }


def _road_sensitivity(segment: RoadSegmentInput, label: str, length_km: float, assumptions: RoadAssumptions) -> SubjectSensitivity:
    base = _base_finance(segment, length_km, assumptions)

    def model(inputs: Mapping[str, float]) -> float:
        return _road_npv(inputs, length_km, assumptions).npv_usd

    user = "Supuesto del usuario"
    drivers = [
        Driver("interruption_days", "Días de interrupción base", "días/año",
               base["interruption_days"] * (1 - assumptions.interruption_days_sensitivity),
               base["interruption_days"] * (1 + assumptions.interruption_days_sensitivity),
               Provenance.ASSUMPTION, f"{user}: ±{assumptions.interruption_days_sensitivity:.0%}."),
        Driver("cost_per_day", "Costo por día interrumpido", "USD/día",
               base["cost_per_day"] * (1 - assumptions.cost_per_day_sensitivity),
               base["cost_per_day"] * (1 + assumptions.cost_per_day_sensitivity),
               Provenance.ASSUMPTION, f"{user}: ±{assumptions.cost_per_day_sensitivity:.0%}."),
        Driver("mitigation_capex", "CAPEX de mitigación", "USD",
               base["mitigation_capex"] * (1 + assumptions.capex_sensitivity),
               base["mitigation_capex"] * (1 - assumptions.capex_sensitivity),
               Provenance.ASSUMPTION, f"{user}: ±{assumptions.capex_sensitivity:.0%}."),
        Driver("annual_maintenance", "Mantenimiento incremental", "USD/año",
               base["annual_maintenance"] * (1 + assumptions.maintenance_sensitivity),
               base["annual_maintenance"] * (1 - assumptions.maintenance_sensitivity),
               Provenance.ASSUMPTION, f"{user}: ±{assumptions.maintenance_sensitivity:.0%}."),
        Driver("residual_fraction", "Fracción residual de interrupción", "fracción",
               min(1.0, base["residual_fraction"] + assumptions.residual_fraction_sensitivity),
               max(0.0, base["residual_fraction"] - assumptions.residual_fraction_sensitivity),
               Provenance.ASSUMPTION, f"{user}: ±{assumptions.residual_fraction_sensitivity:.2f}."),
        Driver("discount_rate", "Tasa de descuento", "fracción",
               min(1.0, base["discount_rate"] + assumptions.discount_rate_sensitivity),
               max(0.0, base["discount_rate"] - assumptions.discount_rate_sensitivity),
               Provenance.ASSUMPTION, f"{user}: ±{assumptions.discount_rate_sensitivity * 100:.1f} puntos."),
    ]
    adverse = {item.key: item.low for item in drivers}
    favorable = {item.key: item.high for item in drivers}
    scenarios = [
        FinanceScenario(key="base", label="Base", npv=round(model(base), 2), changes=["Todos los supuestos en su valor declarado."]),
        FinanceScenario(key="adverso", label="Adverso", npv=round(model({**base, **adverse}), 2),
                        changes=[f"{item.label}: {item.low:,.2f} {item.unit}" for item in drivers]),
        FinanceScenario(key="favorable", label="Favorable", npv=round(model({**base, **favorable}), 2),
                        changes=[f"{item.label}: {item.high:,.2f} {item.unit}" for item in drivers]),
    ]
    break_evens = [
        break_even_item(model, base, "cost_per_day", "Costo diario de equilibrio", "USD/día", 0,
                        max(base["cost_per_day"] * 20, 1),
                        lambda value: "No hay cruce dentro del rango." if value is None else f"El VAN llega a cero con USD {value:,.0f} por día."),
        break_even_item(model, base, "mitigation_capex", "CAPEX máximo", "USD", 1,
                        max(base["mitigation_capex"] * 20, 2),
                        lambda value: "No hay cruce dentro del rango." if value is None else f"El VAN llega a cero con CAPEX de USD {value:,.0f}."),
        break_even_item(model, base, "interruption_days", "Días base de equilibrio", "días/año", 0, 365,
                        lambda value: "No hay cruce entre 0 y 365 días." if value is None else f"El VAN llega a cero con {value:.2f} días/año."),
    ]
    return SubjectSensitivity(
        subject=label,
        base_npv=round(model(base), 2),
        scenarios=scenarios,
        tornado=tornado(model, base, drivers),
        break_evens=break_evens,
    )


ROAD_CRITERIA = [
    ("recent_rx1day", "Máximo diario espacial reciente", "mm/día", Direction.HIGHER_IS_BETTER, 0.20, 0.0, 100.0,
     "Máximo del agregado K1 del último año; mayor exposición implica mayor prioridad de estudio."),
    ("heavy_rain_days", "Días de lluvia fuerte", "días/año", Direction.HIGHER_IS_BETTER, 0.15, 0.0, 30.0,
     "Promedio de años con ≥95% de cobertura que superan el umbral del usuario."),
    ("terrain_slope", "Pendiente NASADEM", "°", Direction.HIGHER_IS_BETTER, 0.15, 0.0, 20.0,
     "Pendiente en el punto representativo; mayor pendiente eleva la prioridad geotécnica."),
    ("length", "Longitud expuesta", "km", Direction.HIGHER_IS_BETTER, 0.10, 0.0, 30.0,
     "Longitud geodésica WGS84 del tramo; no sustituye inventario de activos."),
    ("interruption_days", "Interrupción base", "días/año", Direction.HIGHER_IS_BETTER, 0.15, 0.0, 30.0,
     "Supuesto del usuario, no observado por NASA; mayor valor eleva prioridad."),
    ("npv_ratio", "VAN / CAPEX", "fracción", Direction.HIGHER_IS_BETTER, 0.25, -1.0, 1.0,
     "VAN de mitigación sobre CAPEX, basado exclusivamente en supuestos del usuario."),
]


def _scorecard(
    subjects: list[StudySubject],
    segments: list[RoadSegmentInput],
    results: list[RoadSegmentResult],
    assumptions: RoadAssumptions,
) -> Scorecard:
    rows = []
    for subject, segment, result in zip(subjects, segments, results, strict=True):
        base = _base_finance(segment, result.length_km, assumptions)
        rows.append(SubjectValues(subject=subject.label, values={
            "recent_rx1day": result.spatial_exposure.rx1day_mm if result.spatial_exposure else None,
            "heavy_rain_days": result.heavy_rain_days_per_year,
            "terrain_slope": result.terrain_slope_degrees,
            "length": result.length_km,
            "interruption_days": base["interruption_days"],
            "npv_ratio": result.finance.npv_usd / result.finance.mitigation_capex_usd,
        }))
    criteria = [Criterion(
        key=key, label=label, unit=unit, direction=direction, weight=weight, worst=worst, best=best,
        provenance=Provenance.ASSUMPTION if key == "interruption_days" else Provenance.MODEL,
        basis=basis,
    ) for key, label, unit, direction, weight, worst, best, basis in ROAD_CRITERIA]
    notes = [
        "El puntaje ordena prioridad de estudio/mitigación; no declara seguridad vial ni factibilidad.",
        "Más exposición aumenta la prioridad, mientras que un mayor VAN/CAPEX mejora el caso económico preliminar.",
        "Los criterios sin dato salen del cálculo y su peso se redistribuye; revise la cobertura por tramo.",
    ]
    missing_slope = [item.label for item in results if item.terrain_slope_degrees is None]
    if missing_slope:
        notes.append(f"Sin pendiente NASADEM para {', '.join(missing_slope)}; el criterio se omite para esos tramos.")
    return build_scorecard(ScorecardRequest(criteria=criteria, subjects=rows), notes)


def _assumption_items(request: RoadScreeningRequest, segments: list[RoadSegmentInput]) -> list[AssumptionItem]:
    items = [
        AssumptionItem(key=key, label=label, value=float(getattr(request.assumptions, key)), unit=unit)
        for key, (label, unit) in ASSUMPTION_LABELS.items()
    ]
    for segment in segments:
        if segment.expected_interruption_days_per_year is not None:
            items.append(AssumptionItem(
                key=f"{segment.id}.expected_interruption_days_per_year",
                label=f"{segment.label} · interrupción base",
                value=segment.expected_interruption_days_per_year,
                unit="días/año",
            ))
        if segment.mitigation_capex_usd is not None:
            items.append(AssumptionItem(
                key=f"{segment.id}.mitigation_capex_usd",
                label=f"{segment.label} · CAPEX de mitigación",
                value=segment.mitigation_capex_usd,
                unit="USD",
            ))
    return items


def _terrain_slope(terrain: TerrainResponse | None, label: str) -> float | None:
    site = next((item for item in (terrain.sites if terrain else []) if item.location.label == label), None)
    return site.metrics.slope_degrees if site and site.status == "READY" else None


def _territorial_counts(evidence: RoadTerritorialEvidence) -> dict[str, int | None]:
    return {item.source_id: item.intersection_count if item.status == "READY" else None for item in evidence.sources}


def _data_gaps(
    terrain: TerrainResponse | None,
    subjects: list[StudySubject],
    spatial_errors: list[str | None],
    territorial: list[RoadTerritorialEvidence],
    territorial_errors: list[str | None],
) -> list[DataGap]:
    gaps = []
    if terrain is None or any(item.status != "READY" for item in terrain.sites):
        gaps.append(DataGap(
            dataset="Métricas raster NASADEM",
            impact="No hay pendiente/elevación disponible para todos los tramos; el score redistribuye ese peso.",
            next_action="Renovar Earthdata si corresponde y precargar las teselas del corredor.",
        ))
    for subject, error in zip(subjects, spatial_errors, strict=True):
        if error:
            gaps.append(DataGap(
                dataset=f"Muestreo espacial POWER · {subject.label}",
                impact="No se calculó exposición por celdas para este tramo.",
                next_action=f"Reintentar K1 y revisar el error del proveedor: {error}",
            ))
    unavailable = {}
    for item in territorial:
        for source in item.sources:
            if source.status == "DATA_UNAVAILABLE":
                unavailable[source.source_id] = source.limitations[0] if source.limitations else "Fuente no disponible."
    for subject, error in zip(subjects, territorial_errors, strict=True):
        if error:
            unavailable[f"consulta-territorial-{subject.id}"] = error
    for source_id, reason in unavailable.items():
        gaps.append(DataGap(
            dataset=source_id,
            impact=f"La capa territorial no pudo verificarse: {reason}",
            next_action="Restablecer el servicio oficial o seleccionar una fuente vigente con licencia y escala documentadas.",
        ))
    gaps.extend([
        DataGap(
            dataset="Eje vial e inventario de activos MTC",
            impact="La geometría OSM no acredita eje oficial, puentes, drenajes, estado ni derecho de vía.",
            next_action="Sustituir la instantánea OSM por geometría e inventario oficiales del MTC antes de prefactibilidad.",
        ),
        DataGap(
            dataset="Interrupciones, tránsito y pérdidas observadas",
            impact="Los días y costos de interrupción son supuestos del usuario; no existe calibración con cierres reales.",
            next_action="Cruzar emergencias INDECI/MTC, aforos, tiempos de cierre y costos logísticos observados.",
        ),
        DataGap(
            dataset="Comunidades y conflictos",
            impact="No se descartan afectaciones sociales, prediales ni conflictos.",
            next_action="Validar Defensoría, SENACE, consulta previa y catastro con los organismos competentes.",
        ),
    ])
    return gaps


def _evaluation_and_finance_stages(
    scorecard: Scorecard,
    results: list[RoadSegmentResult],
    sensitivities: list[SubjectSensitivity],
    finance_ms: float,
):
    ranked = sorted((item for item in scorecard.subjects if item.score is not None), key=lambda item: item.score, reverse=True)
    evaluation_evidence = [
        StageEvidence(label=f"{item.rank}.º {item.subject}", value=f"{item.score:.1f}/100 · cobertura {item.coverage:.0%}", provenance=Provenance.MODEL)
        for item in ranked
    ]
    evaluation_evidence.append(StageEvidence(
        label="Lectura del score",
        value="Mayor puntaje = mayor prioridad preliminar de estudio/mitigación; no significa tramo seguro ni proyecto factible.",
    ))
    evaluation = stage(
        "evaluation",
        PipelineStatus.COMPLETED,
        f"Prioridad multicriterio calculada para {len(results)} tramos; "
        + (f"líder {scorecard.leader}." if scorecard.leader else "sin líder por falta de datos."),
        [Provenance.MODEL, Provenance.ASSUMPTION],
        evaluation_evidence,
        answers=["so_what"],
    )
    npvs = [item.finance.npv_usd for item in results]
    adverse = [next(scenario.npv for scenario in item.scenarios if scenario.key == "adverso") for item in sensitivities]
    finance_evidence = [
        StageEvidence(
            label=item.label,
            value=f"VAN USD {item.finance.npv_usd:,.0f} · {item.finance.avoided_interruption_days_per_year:.2f} días evitados/año",
            provenance=Provenance.MODEL,
        ) for item in results
    ]
    finance_evidence += [
        StageEvidence(label=f"Factor dominante · {item.subject}", value=item.tornado[0].label, provenance=item.tornado[0].provenance)
        for item in sensitivities if item.tornado
    ]
    finance = stage(
        "finance",
        PipelineStatus.COMPLETED,
        f"VAN de mitigación positivo en {sum(value >= 0 for value in npvs)} de {len(npvs)} tramos en el caso base "
        f"y en {sum(value >= 0 for value in adverse)} de {len(adverse)} en el adverso.",
        [Provenance.MODEL, Provenance.ASSUMPTION],
        finance_evidence,
        finance_ms,
        ["so_what"],
    )
    return evaluation, finance


async def run_road_screening(request: RoadScreeningRequest) -> RoadScreeningResponse:
    timings = StageTimings()
    segments, subjects, lengths, corridor_source = _subjects(request)
    points = [item.representative_point for item in subjects]

    (datasets, timings.extraction_ms), (terrain, terrain_error, timings.terrain_ms), (spatial, spatial_errors), (
        territorial,
        territorial_errors,
    ) = await asyncio.gather(
        extract_power(points, ROAD_VARIABLES, request.start_date, request.end_date),
        extract_terrain(points),
        _spatial_exposures(subjects, request),
        _territorial_evidence(subjects, request.include_territorial_layers),
    )
    expected_days = (request.end_date - request.start_date).days + 1
    analysis_start = perf_counter()
    summaries_by_subject = analyze_subjects(datasets, ROAD_VARIABLES, expected_days)
    timings.analysis_ms = elapsed_ms(analysis_start)

    finance_start = perf_counter()
    sensitivities = [
        _road_sensitivity(segment, subject.label, length, request.assumptions)
        for segment, subject, length in zip(segments, subjects, lengths, strict=True)
    ]
    territorial_by_subject = {item.subject: item for item in territorial}
    results = []
    for segment, subject, length, dataset, summaries, exposure, sensitivity in zip(
        segments, subjects, lengths, datasets, summaries_by_subject, spatial, sensitivities, strict=True
    ):
        heavy_days, heavy_years = _heavy_rain_days(dataset, request.assumptions.heavy_rain_threshold_mm_day)
        slope = _terrain_slope(terrain, subject.label)
        base = _base_finance(segment, length, request.assumptions)
        finance = _road_npv(base, length, request.assumptions)
        evidence = territorial_by_subject.get(subject.label, RoadTerritorialEvidence(subject=subject.label, sources=[]))
        opportunities = [
            f"La geometría pública del tramo mide {length:.3f} km geodésicos.",
            f"El VAN preliminar de mitigación es USD {finance.npv_usd:,.0f} bajo los supuestos declarados.",
        ]
        cautions = [
            "La lluvia NASA POWER es una estimación de grilla y no reemplaza estaciones ni estudios hidráulicos.",
            "Los días/costos de cierre y el presupuesto son supuestos, no observaciones de la carretera.",
        ]
        if exposure is None:
            cautions.append("El muestreo por celdas K1 no estuvo disponible para este tramo.")
        if slope is None:
            cautions.append("La pendiente NASADEM no estuvo disponible; no se interpreta como terreno plano.")
        results.append(RoadSegmentResult(
            subject_id=subject.id,
            label=subject.label,
            representative_point=subject.representative_point,
            length_km=round(length, 6),
            variables=summaries,
            heavy_rain_days_per_year=heavy_days,
            heavy_rain_years=heavy_years,
            spatial_exposure=exposure,
            terrain_slope_degrees=slope,
            territorial_intersections=_territorial_counts(evidence),
            finance=finance,
            opportunities=opportunities,
            cautions=cautions,
        ))
    timings.finance_ms = elapsed_ms(finance_start)

    scorecard = _scorecard(subjects, segments, results, request.assumptions)
    labelled = [
        SubjectSummaries(label=subject.label, summaries=summaries)
        for subject, summaries in zip(subjects, summaries_by_subject, strict=True)
    ]
    trend_findings = collect_trend_findings(labelled)
    gaps = _data_gaps(terrain, subjects, spatial_errors, territorial, territorial_errors)
    pending = sum(item.status == Provenance.UNAVAILABLE for item in gaps)
    npvs = [item.finance.npv_usd for item in results]
    lens = SectorLens(
        readings=ROAD_READINGS,
        stable_notes=ROAD_STABLE_NOTES,
        economics=(
            f"Con supuestos del usuario, el VAN de mitigación va de {millions_usd(min(npvs))} a {millions_usd(max(npvs))}; "
            f"{sum(value >= 0 for value in npvs)} de {len(npvs)} tramos son no negativos. "
            "Esto prioriza estudios y no constituye una decisión de inversión."
        ),
    )
    nasa_questions = answer_nasa_questions(
        labelled,
        trend_findings,
        {item.label: (item.representative_point.latitude, item.representative_point.longitude) for item in subjects},
        pending,
        lens,
    )

    source_provenance = unique([
        item.source.provenance for summaries in summaries_by_subject for item in summaries
    ] + [item.provenance for item in spatial if item is not None])
    all_provenance = unique(
        source_provenance
        + [corridor_source.provenance, Provenance.MODEL, Provenance.ASSUMPTION]
        + ([Provenance.UNAVAILABLE] if pending else [])
    )
    years = max(len(item.annual_series) for summaries in summaries_by_subject for item in summaries)
    evaluation, finance_stage = _evaluation_and_finance_stages(scorecard, results, sensitivities, timings.finance_ms)
    selection = selection_stage(subjects, max_separation_km(points))
    selection.provenance = unique([*selection.provenance, corridor_source.provenance])
    selection.evidence.append(StageEvidence(
        label="Geometría del corredor",
        value=f"{corridor_source.source} · {sum(lengths):.3f} km en {len(subjects)} tramos",
        provenance=corridor_source.provenance,
    ))
    territorial_stage_result = territorial_stage(terrain, terrain_error, gaps, timings.terrain_ms)
    ready_intersections = sum(
        source.intersection_count or 0
        for item in territorial
        for source in item.sources
        if source.status == "READY"
    )
    territorial_stage_result.evidence.append(StageEvidence(
        label="Intersecciones de capas oficiales",
        value=f"{ready_intersections}; cero no demuestra ausencia de amenaza o restricción",
        provenance=Provenance.MODEL,
    ))
    pipeline = assemble_pipeline([
        selection,
        configuration_stage(
            SECTOR_LABEL,
            ROAD_VARIABLES,
            request.start_date,
            request.end_date,
            years,
            f"{request.assumptions.baseline_interruption_days_per_year:g} días/año · "
            f"USD {request.assumptions.cost_per_interruption_day_usd:,.0f}/día · "
            f"tasa {request.assumptions.discount_rate:.0%}",
        ),
        extraction_stage(labelled, timings.extraction_ms),
        analysis_stage(labelled, trend_findings, timings.analysis_ms),
        territorial_stage_result,
        evaluation,
        finance_stage,
        results_stage(trend_findings, gaps, all_provenance),
        export_stage(all_provenance),
    ])
    fingerprint_payload = request.model_dump(mode="json")
    fingerprint_payload["resolved_segments"] = [item.model_dump(mode="json") for item in segments]
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()).hexdigest()[:16]
    return RoadScreeningResponse(
        analysis_id=fingerprint,
        generated_at=datetime.now(timezone.utc),
        title="Screening vial preliminar — corredor Moquegua–Ilo",
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}",
        subjects=subjects,
        pipeline=pipeline,
        nasa_questions=nasa_questions,
        trend_findings=trend_findings,
        terrain=terrain,
        data_gaps=gaps,
        assumption_items=_assumption_items(request, segments),
        financial_sensitivity=sensitivities,
        scorecard=scorecard,
        disclaimer=(
            "Screening preliminar de resiliencia vial con datos NASA, capas públicas y supuestos del usuario. "
            "No sustituye ingeniería vial, hidrología/hidráulica, geotecnia, inventario de activos, tránsito, "
            "debida diligencia ambiental/social, presupuesto ni factibilidad financiera."
        ),
        corridor_source=corridor_source,
        segments=results,
        territorial_evidence=territorial,
        assumptions=request.assumptions,
    )
