"""K3 real-estate pilot: polygon exposure, territorial alerts and transparent screening economics."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from statistics import fmean
from time import perf_counter

from shapely.geometry import shape

from ..connectors.nasa.power import PowerConnectorError
from ..connectors.nasa.power_regional import RegionalPowerConnector, RegionalPowerError
from ..connectors.peru.admin_boundaries import PeruTerritoryCatalog, TerritoryCatalogError
from ..connectors.peru.territory import TerritoryConnector, TerritoryConnectorError
from ..finance.sensitivity import Driver, break_even_item, tornado
from ..geospatial.countries import OUTSIDE_PERU, touches_peru
from ..geospatial.geometry import GEOD, GeometryValidationError, inspect_geometry
from ..orchestration.analysis import analyze_subjects
from ..orchestration.discoveries import NO_TERRAIN_CHECK, record_in_pipeline, terrain_discoveries
from ..orchestration.extraction import elapsed_ms, extract_power, extract_terrain, max_separation_km
from ..orchestration.nasa_questions import SectorLens, SubjectSummaries, answer_nasa_questions, collect_trend_findings, millions_usd
from ..orchestration.slope_check import scorecard_with_slope_check
from ..orchestration.stale_copies import stale_gap
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
from ..schemas.analysis import Point, Provenance
from ..schemas.data_sources import TerritorialQueryRequest, TerritorialQueryResponse
from ..schemas.real_estate import (
    RealEstateAssumptions,
    RealEstateCellMetric,
    RealEstateFinancialProjection,
    RealEstateScreeningRequest,
    RealEstateScreeningResponse,
    RealEstateSiteResult,
    RealEstateSiteSource,
    RealEstateSpatialExposure,
    RealEstateTerritorialEvidence,
    RealEstateTerritorialSourceSummary,
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
from ..statistics.extremes import linear_percentile

ESTATE_VARIABLES = ["PRECTOTCORR", "T2M"]
PRECIPITATION = "PRECTOTCORR"
SECTOR_LABEL = "Desarrollo inmobiliario"
EXPOSURE_DAYS = 365
PROJECT_SCALE_KM2 = 2.0
PROJECT_SCALE_HECTARES = 200
TERRITORIAL_SOURCE_IDS = [
    "cenepred-flood-risk",
    "cenepred-mass-movement-risk",
    "sernanp-anp",
    "cultura-archaeology",
    "cultura-archaeology-declared",
    "ingemmet-geohazards",
]
HAZARD_SOURCES = {"cenepred-flood-risk", "cenepred-mass-movement-risk"}
RESTRICTION_SOURCES = {"sernanp-anp", "cultura-archaeology", "cultura-archaeology-declared"}

ESTATE_READINGS = {
    (PRECIPITATION, "increasing"): "la precipitación media aumenta: revisar drenaje, inundación y estabilidad del terreno",
    (PRECIPITATION, "decreasing"): "la precipitación media disminuye; esto no descarta extremos, inundación ni escasez hídrica",
    ("T2M", "increasing"): "la temperatura aumenta: revisar confort térmico, demanda de enfriamiento y espacio público",
    ("T2M", "decreasing"): "la temperatura disminuye; su implicancia inmobiliaria requiere diseño bioclimático local",
}
ESTATE_STABLE_NOTES = {
    PRECIPITATION: "La precipitación media no cambia con significancia; esto no demuestra estabilidad de extremos ni ausencia de inundación.",
}
ASSUMPTION_LABELS = {
    "developable_fraction": ("Fracción desarrollable", "fracción"),
    "floor_area_ratio": ("Índice de edificabilidad supuesto", "m² vendible/m² desarrollable"),
    "sale_price_usd_m2": ("Precio de venta", "USD/m²"),
    "construction_cost_usd_m2": ("Costo de construcción", "USD/m²"),
    "land_cost_usd_m2": ("Costo del suelo", "USD/m² de terreno"),
    "mitigation_cost_usd_m2_land": ("Mitigación inicial", "USD/m² de terreno"),
    "selling_cost_fraction": ("Costo comercial sobre ventas", "fracción"),
    "annual_absorption_fraction": ("Absorción anual", "fracción del área vendible/año"),
    "discount_rate": ("Tasa de descuento", "fracción"),
    "horizon_years": ("Horizonte", "años"),
    "sale_price_sensitivity": ("Rango del precio (±)", "fracción"),
    "construction_cost_sensitivity": ("Rango del costo de obra (±)", "fracción"),
    "land_cost_sensitivity": ("Rango del costo del suelo (±)", "fracción"),
    "mitigation_cost_sensitivity": ("Rango de mitigación (±)", "fracción"),
    "absorption_sensitivity": ("Rango de absorción (±)", "puntos"),
    "discount_rate_sensitivity": ("Rango de la tasa (±)", "puntos"),
}


class RealEstateScreeningError(RuntimeError):
    pass


def _resolve_subjects(
    request: RealEstateScreeningRequest,
) -> tuple[list[StudySubject], list[float], list[RealEstateSiteSource]]:
    catalog = PeruTerritoryCatalog()
    subjects: list[StudySubject] = []
    areas: list[float] = []
    sources: list[RealEstateSiteSource] = []
    for site in request.sites:
        if site.territory is not None:
            try:
                territory = catalog.geometry(site.territory.level, site.territory.ubigeo)
            except TerritoryCatalogError as exc:
                raise RealEstateScreeningError(f"{site.label}: {exc}") from exc
            geometry = territory.feature["geometry"]
            source = RealEstateSiteSource(
                subject=site.label,
                origin=f"territory:{site.territory.level}/{site.territory.ubigeo}",
                dataset=territory.source.dataset,
                source_url=territory.source.source_url,
                license=territory.source.license,
                source_created=territory.source.source_created,
                provenance=Provenance.REAL,
                limitations=[*territory.limitations, "Un territorio administrativo no equivale a un predio ni acredita zonificación o titularidad."],
            )
        else:
            geometry = site.geometry
            source = RealEstateSiteSource(
                subject=site.label,
                origin="user_geometry",
                dataset="GeoJSON proporcionado por el usuario",
                provenance=Provenance.ASSUMPTION,
                limitations=[
                    "La plataforma valida geometría, CRS y área; no verifica titularidad, catastro, zonificación ni origen legal.",
                    "La geometría se interpreta como WGS84 longitud/latitud (GeoJSON RFC 7946).",
                ],
            )
        try:
            inspected = inspect_geometry(geometry)
            polygon = shape(geometry)
        except (GeometryValidationError, ValueError) as exc:
            raise RealEstateScreeningError(f"{site.label}: {exc}") from exc
        if inspected.geometry_type not in {"Polygon", "MultiPolygon"} or inspected.area_km2 is None:
            raise RealEstateScreeningError(f"{site.label}: cada terreno debe ser un Polygon o MultiPolygon WGS84 válido.")
        if inspected.area_km2 <= 0:
            raise RealEstateScreeningError(f"{site.label}: el polígono debe tener área positiva.")
        inside = polygon.representative_point()
        point = Point(latitude=inside.y, longitude=inside.x, label=site.label)
        subjects.append(StudySubject(
            id=site.id,
            label=site.label,
            kind=SubjectKind.POLYGON,
            geometry=geometry,
            representative_point=point,
        ))
        precise_area_m2, _perimeter_m = GEOD.geometry_area_perimeter(polygon)
        areas.append(abs(precise_area_m2) / 1_000_000)
        sources.append(source)
    return subjects, areas, sources


async def _spatial_exposure(
    subject: StudySubject, request: RealEstateScreeningRequest
) -> tuple[RealEstateSpatialExposure | None, str | None]:
    end = request.end_date
    start = max(request.start_date, end - timedelta(days=EXPOSURE_DAYS - 1))
    try:
        sampled = await RegionalPowerConnector().sample(SpatialSamplingRequest(
            subject={
                "type": "Feature",
                "properties": {"kind": "polygon", "name": subject.label, "origin": "K3"},
                "geometry": subject.geometry,
            },
            variable=PRECIPITATION,
            start_date=start,
            end_date=end,
        ))
    except RegionalPowerError as exc:
        return None, str(exc)
    values = [item.value for item in sampled.aggregate]
    rx1day = max(values) if values else None
    p99 = linear_percentile(values, 0.99)
    limitations = [
        *sampled.limitations,
        "P99 describe exposición climática de screening; no es una lluvia de diseño ni prueba suficiencia del drenaje.",
        "RX1DAY se conserva para trazabilidad y requiere contraste IMERG/estaciones si se separa materialmente de P99.",
    ]
    if rx1day is not None and p99 is not None and rx1day - p99 >= 50 and rx1day >= 3 * max(p99, 0.1):
        limitations.append(
            f"RX1DAY ({rx1day:.2f} mm/día) es materialmente mayor que P99 ({p99:.2f} mm/día); revisar con IMERG/estaciones."
        )
    cells = []
    for cell in sampled.cells:
        cell_values = [item.value for item in cell.observations]
        cells.append(RealEstateCellMetric(
            cell_id=cell.cell_id,
            center=cell.center,
            weight=cell.weight,
            mean_precipitation_mm_day=round(fmean(cell_values), 4) if cell_values else None,
            rx1day_mm=round(max(cell_values), 4) if cell_values else None,
        ))
    return RealEstateSpatialExposure(
        period=f"{start.isoformat()}/{end.isoformat()}",
        unit=sampled.unit,
        mode=sampled.mode,
        cell_count=len(sampled.cells),
        spatial_coverage_percent=sampled.spatial_coverage_percent,
        mean_precipitation_mm_day=round(fmean(values), 4) if values else None,
        rx1day_mm=round(rx1day, 4) if rx1day is not None else None,
        p99_precipitation_mm_day=round(p99, 4) if p99 is not None else None,
        cells=cells,
        provenance=sampled.source.provenance,
        source_url=sampled.source.source_url,
        method=sampled.method,
        limitations=limitations,
    ), None


async def _spatial_exposures(subjects: list[StudySubject], request: RealEstateScreeningRequest):
    results, errors = [], []
    for subject in subjects:
        result, error = await _spatial_exposure(subject, request)
        results.append(result)
        errors.append(error)
    return results, errors


def _territorial_summary(subject: StudySubject, response: TerritorialQueryResponse) -> RealEstateTerritorialEvidence:
    return RealEstateTerritorialEvidence(
        subject=subject.label,
        sources=[RealEstateTerritorialSourceSummary(
            source_id=item.source_id,
            status=item.status,
            intersection_count=item.intersection_count,
            provenance=item.provenance,
            downloaded_at=item.downloaded_at,
            limitations=item.limitations,
            stale_note=item.stale_note,
        ) for item in response.sources],
    )


async def _territorial_evidence(subjects: list[StudySubject], enabled: bool):
    if not enabled:
        return [RealEstateTerritorialEvidence(subject=item.label, sources=[]) for item in subjects], [
            "Consulta territorial desactivada por el usuario."
        ] * len(subjects)
    connector = TerritoryConnector()
    evidence, errors = [], []
    for subject in subjects:
        if not touches_peru(subject.geometry):
            # Un servicio peruano devolvería cero objetos para un terreno en otro país: no se consulta y se declara.
            evidence.append(RealEstateTerritorialEvidence(subject=subject.label, sources=[]))
            errors.append(OUTSIDE_PERU)
            continue
        try:
            response = await connector.query(TerritorialQueryRequest(
                geometry=subject.geometry,
                source_ids=TERRITORIAL_SOURCE_IDS,
            ))
            evidence.append(_territorial_summary(subject, response))
            errors.append(None)
        except TerritoryConnectorError as exc:
            evidence.append(RealEstateTerritorialEvidence(subject=subject.label, sources=[]))
            errors.append(str(exc))
    return evidence, errors


def _base_finance(area_km2: float, assumptions: RealEstateAssumptions) -> dict[str, float]:
    return {
        "land_area_m2": area_km2 * 1_000_000,
        "developable_fraction": assumptions.developable_fraction,
        "floor_area_ratio": assumptions.floor_area_ratio,
        "sale_price": assumptions.sale_price_usd_m2,
        "construction_cost": assumptions.construction_cost_usd_m2,
        "land_cost": assumptions.land_cost_usd_m2,
        "mitigation_cost": assumptions.mitigation_cost_usd_m2_land,
        "selling_cost_fraction": assumptions.selling_cost_fraction,
        "annual_absorption": assumptions.annual_absorption_fraction,
        "discount_rate": assumptions.discount_rate,
    }


def _estate_npv(inputs: Mapping[str, float], assumptions: RealEstateAssumptions) -> RealEstateFinancialProjection:
    land_area = inputs["land_area_m2"]
    developable = land_area * inputs["developable_fraction"]
    saleable = developable * inputs["floor_area_ratio"]
    land_acquisition = land_area * inputs["land_cost"]
    mitigation = land_area * inputs["mitigation_cost"]
    cash_flows = [-(land_acquisition + mitigation)]
    remaining = 1.0
    sold_fraction = 0.0
    revenue = construction = selling = 0.0
    for _year in range(1, assumptions.horizon_years + 1):
        fraction = max(0.0, min(inputs["annual_absorption"], remaining))
        sold_area = saleable * fraction
        year_revenue = sold_area * inputs["sale_price"]
        year_construction = sold_area * inputs["construction_cost"]
        year_selling = year_revenue * inputs["selling_cost_fraction"]
        cash_flows.append(year_revenue - year_construction - year_selling)
        revenue += year_revenue
        construction += year_construction
        selling += year_selling
        sold_fraction += fraction
        remaining = max(0.0, remaining - fraction)
    npv = sum(value / (1 + inputs["discount_rate"]) ** year for year, value in enumerate(cash_flows))
    return RealEstateFinancialProjection(
        land_area_m2=round(land_area, 2),
        developable_area_m2=round(developable, 2),
        saleable_floor_area_m2=round(saleable, 2),
        land_acquisition_usd=round(land_acquisition, 2),
        initial_mitigation_usd=round(mitigation, 2),
        projected_revenue_usd=round(revenue, 2),
        projected_construction_cost_usd=round(construction, 2),
        projected_selling_cost_usd=round(selling, 2),
        sold_fraction_within_horizon=round(sold_fraction, 6),
        npv_usd=round(npv, 2),
        cash_flows_usd=[round(value, 2) for value in cash_flows],
        formula=(
            "VAN = −(área de suelo × costo suelo + área de suelo × mitigación) + "
            "Σ[área vendida_t × (precio − costo obra) − costo comercial_t] / (1+r)^t"
        ),
        limitations=[
            "Precio, costos, edificabilidad, fracción desarrollable, absorción, tasa y horizonte son supuestos del usuario.",
            "El modelo no incluye impuestos, financiamiento, licencias, cronograma de obra, inflación ni valor residual.",
            "La construcción se imputa en el mismo año de la venta y el área no absorbida al horizonte no recibe valor residual.",
            "Un territorio IGN es una unidad administrativa, no un predio; su VAN solo ilustra sensibilidad a los supuestos.",
        ],
    )


def _estate_sensitivity(label: str, area_km2: float, assumptions: RealEstateAssumptions) -> SubjectSensitivity:
    base = _base_finance(area_km2, assumptions)

    def model(inputs: Mapping[str, float]) -> float:
        return _estate_npv(inputs, assumptions).npv_usd

    user = "Supuesto del usuario"
    drivers = [
        Driver("sale_price", "Precio de venta", "USD/m²", base["sale_price"] * (1 - assumptions.sale_price_sensitivity),
               base["sale_price"] * (1 + assumptions.sale_price_sensitivity), Provenance.ASSUMPTION,
               f"{user}: ±{assumptions.sale_price_sensitivity:.0%}."),
        Driver("construction_cost", "Costo de construcción", "USD/m²",
               base["construction_cost"] * (1 - assumptions.construction_cost_sensitivity),
               base["construction_cost"] * (1 + assumptions.construction_cost_sensitivity), Provenance.ASSUMPTION,
               f"{user}: ±{assumptions.construction_cost_sensitivity:.0%}."),
        Driver("land_cost", "Costo del suelo", "USD/m²",
               base["land_cost"] * (1 - assumptions.land_cost_sensitivity),
               base["land_cost"] * (1 + assumptions.land_cost_sensitivity), Provenance.ASSUMPTION,
               f"{user}: ±{assumptions.land_cost_sensitivity:.0%}."),
        Driver("mitigation_cost", "Mitigación inicial", "USD/m² de terreno",
               base["mitigation_cost"] * (1 - assumptions.mitigation_cost_sensitivity),
               base["mitigation_cost"] * (1 + assumptions.mitigation_cost_sensitivity), Provenance.ASSUMPTION,
               f"{user}: ±{assumptions.mitigation_cost_sensitivity:.0%}."),
        Driver("annual_absorption", "Absorción anual", "fracción/año",
               max(0.01, base["annual_absorption"] - assumptions.absorption_sensitivity),
               min(1.0, base["annual_absorption"] + assumptions.absorption_sensitivity), Provenance.ASSUMPTION,
               f"{user}: ±{assumptions.absorption_sensitivity:.2f}."),
        Driver("discount_rate", "Tasa de descuento", "fracción",
               max(0.0, base["discount_rate"] - assumptions.discount_rate_sensitivity),
               min(1.0, base["discount_rate"] + assumptions.discount_rate_sensitivity), Provenance.ASSUMPTION,
               f"{user}: ±{assumptions.discount_rate_sensitivity * 100:.1f} puntos."),
    ]
    lower = {item.key: item.low for item in drivers}
    upper = {item.key: item.high for item in drivers}
    adverse = {
        **base,
        **upper,
        "sale_price": lower["sale_price"],
        "annual_absorption": lower["annual_absorption"],
    }
    favorable = {
        **base,
        **lower,
        "sale_price": upper["sale_price"],
        "annual_absorption": upper["annual_absorption"],
    }
    scenarios = [
        FinanceScenario(key="base", label="Base", npv=round(model(base), 2), changes=["Todos los supuestos en su valor declarado."]),
        FinanceScenario(key="adverso", label="Adverso", npv=round(model(adverse), 2), changes=[
            "Precio y absorción en su rango bajo; costos y tasa en su rango alto."
        ]),
        FinanceScenario(key="favorable", label="Favorable", npv=round(model(favorable), 2), changes=[
            "Precio y absorción en su rango alto; costos y tasa en su rango bajo."
        ]),
    ]
    break_evens = [
        break_even_item(model, base, "sale_price", "Precio de venta de equilibrio", "USD/m²", 0,
                        max(base["sale_price"] * 10, 1),
                        lambda value: "No hay cruce dentro del rango." if value is None else f"El VAN llega a cero con USD {value:,.2f}/m²."),
        break_even_item(model, base, "land_cost", "Costo máximo del suelo", "USD/m²", 0,
                        max(base["land_cost"] * 20, base["sale_price"] * 5, 1),
                        lambda value: "No hay cruce dentro del rango." if value is None else f"El VAN llega a cero con suelo a USD {value:,.2f}/m²."),
        break_even_item(model, base, "developable_fraction", "Fracción desarrollable de equilibrio", "fracción", 0.001, 1,
                        lambda value: "No hay cruce entre 0.1 % y 100 %." if value is None else f"El VAN llega a cero con {value:.1%} desarrollable."),
    ]
    return SubjectSensitivity(
        subject=label,
        base_npv=round(model(base), 2),
        scenarios=scenarios,
        tornado=tornado(model, base, drivers),
        break_evens=break_evens,
    )


ESTATE_CRITERIA = [
    ("recent_p99_precip", "P99 de lluvia espacial reciente", "mm/día", Direction.LOWER_IS_BETTER, 0.15, 30.0, 0.0,
     "P99 diario del agregado K1; no es lluvia de diseño ni prueba ausencia de inundación."),
    ("terrain_slope", "Pendiente NASADEM", "°", Direction.LOWER_IS_BETTER, 0.15, 20.0, 0.0,
     "Pendiente en un punto interior representativo; no sustituye topografía ni geotecnia predial."),
    ("hazard_alerts", "Intersecciones CENEPRED devueltas", "conteo", Direction.LOWER_IS_BETTER, 0.15, 5.0, 0.0,
     "Conteo de inundación y movimientos en masa CENEPRED; cero intersecciones no significa riesgo cero e INGEMMET sigue como brecha separada."),
    ("restriction_alerts", "Intersecciones de restricción devueltas", "conteo", Direction.LOWER_IS_BETTER, 0.20, 5.0, 0.0,
     "Alertas SERNANP/Cultura; no constituyen opinión legal ni reemplazan CIRA."),
    ("npv_ratio", "VAN / inversión inicial", "fracción", Direction.HIGHER_IS_BETTER, 0.25, -1.0, 1.0,
     "VAN sobre suelo más mitigación; depende exclusivamente de supuestos comerciales."),
    ("developable_fraction", "Fracción desarrollable supuesta", "fracción", Direction.HIGHER_IS_BETTER, 0.10, 0.0, 1.0,
     "Supuesto del usuario pendiente de zonificación, catastro y diseño."),
]


def _source_count(evidence: RealEstateTerritorialEvidence, source_ids: set[str]) -> int | None:
    selected = [item for item in evidence.sources if item.source_id in source_ids]
    if len(selected) != len(source_ids) or any(item.status != "READY" for item in selected):
        return None
    return sum(item.intersection_count or 0 for item in selected)


def _scorecard(
    subjects: list[StudySubject],
    results: list[RealEstateSiteResult],
    territorial: list[RealEstateTerritorialEvidence],
    assumptions: RealEstateAssumptions,
    terrain: TerrainResponse | None = None,
) -> Scorecard:
    territorial_by_subject = {item.subject: item for item in territorial}
    rows = []
    for subject, result in zip(subjects, results, strict=True):
        evidence = territorial_by_subject.get(subject.label, RealEstateTerritorialEvidence(subject=subject.label, sources=[]))
        initial = result.finance.land_acquisition_usd + result.finance.initial_mitigation_usd
        rows.append(SubjectValues(subject=subject.label, values={
            "recent_p99_precip": result.spatial_exposure.p99_precipitation_mm_day if result.spatial_exposure else None,
            "terrain_slope": result.terrain_slope_degrees,
            "hazard_alerts": _source_count(evidence, HAZARD_SOURCES),
            "restriction_alerts": _source_count(evidence, RESTRICTION_SOURCES),
            "npv_ratio": result.finance.npv_usd / initial if initial > 0 else None,
            "developable_fraction": assumptions.developable_fraction,
        }))
    criteria = [Criterion(
        key=key, label=label, unit=unit, direction=direction, weight=weight, worst=worst, best=best,
        provenance=Provenance.ASSUMPTION if key in {"npv_ratio", "developable_fraction"} else Provenance.MODEL,
        basis=basis,
    ) for key, label, unit, direction, weight, worst, best, basis in ESTATE_CRITERIA]
    notes = [
        "El puntaje compara prioridad preliminar de debida diligencia y atractivo condicionado; no declara edificabilidad ni factibilidad.",
        "Cero intersecciones significa solo que el servicio consultado no devolvió cruces; nunca equivale a cero riesgo o restricción.",
        "Una fuente incompleta elimina el criterio relacionado y reduce la cobertura, en vez de convertir el faltante en cero.",
    ]
    card = scorecard_with_slope_check(ScorecardRequest(criteria=criteria, subjects=rows), notes, terrain)
    if len(rows) == 1:
        card.margin = None
        card.tie = False
        card.notes.append(
            "Con un solo terreno no existe comparación: margin=None y tie=False no implican liderazgo frente a una alternativa."
        )
    return card


def _assumption_items(request: RealEstateScreeningRequest) -> list[AssumptionItem]:
    return [
        AssumptionItem(key=key, label=label, value=float(getattr(request.assumptions, key)), unit=unit)
        for key, (label, unit) in ASSUMPTION_LABELS.items()
    ]


def _terrain_slope(terrain: TerrainResponse | None, label: str) -> float | None:
    site = next((item for item in (terrain.sites if terrain else []) if item.location.label == label), None)
    return site.metrics.slope_degrees if site and site.status == "READY" else None


def _territorial_counts(evidence: RealEstateTerritorialEvidence) -> dict[str, int | None]:
    return {item.source_id: item.intersection_count if item.status == "READY" else None for item in evidence.sources}


def _data_gaps(
    terrain: TerrainResponse | None,
    subjects: list[StudySubject],
    spatial_errors: list[str | None],
    territorial: list[RealEstateTerritorialEvidence],
    territorial_errors: list[str | None],
) -> list[DataGap]:
    gaps = []
    if terrain is None or any(item.status != "READY" for item in terrain.sites):
        gaps.append(DataGap(
            dataset="Métricas raster NASADEM",
            impact="No hay pendiente disponible para todos los terrenos; el score redistribuye ese peso.",
            next_action="Precargar las teselas y volver a ejecutar; confirmar con topografía de detalle.",
        ))
    for subject, error in zip(subjects, spatial_errors, strict=True):
        if error:
            gaps.append(DataGap(
                dataset=f"Muestreo espacial POWER · {subject.label}",
                impact="No se calculó exposición climática por celdas para este terreno.",
                next_action=f"Reintentar K1 y revisar el error del proveedor: {error}",
            ))
    unavailable: dict[str, str] = {}
    stale: dict[str, str] = {}
    for item in territorial:
        for source in item.sources:
            if source.status == "DATA_UNAVAILABLE":
                unavailable[source.source_id] = source.limitations[0] if source.limitations else "Fuente no disponible."
            elif source.stale_note:
                stale.setdefault(source.source_id, source.stale_note)
    for subject, error in zip(subjects, territorial_errors, strict=True):
        if error:
            unavailable[f"consulta-territorial-{subject.id}"] = error
    for source_id, reason in unavailable.items():
        gaps.append(DataGap(
            dataset=source_id,
            impact=f"La capa no pudo verificarse: {reason}",
            next_action="Restablecer el servicio oficial o usar una fuente vigente con licencia, fecha, escala y cobertura documentadas.",
        ))
    gaps.extend(stale_gap(source_id, note) for source_id, note in stale.items())
    gaps.extend([
        DataGap(
            dataset="Catastro, titularidad y parámetros urbanísticos",
            impact="La geometría no acredita propiedad, zonificación, habilitación urbana, edificabilidad ni cargas legales.",
            next_action="Solicitar partida, catastro municipal, zonificación, parámetros urbanísticos y certificado de inexistencia de restos cuando corresponda.",
        ),
        DataGap(
            dataset="Capacidad de servicios urbanos",
            impact="No se verifican factibilidad ni capacidad de agua, saneamiento, energía, movilidad y telecomunicaciones.",
            next_action="Obtener factibilidades y costos de conexión de cada prestador competente.",
        ),
        DataGap(
            dataset="Mercado y absorción observados",
            impact="Precio y absorción son supuestos; no hay comparables, inventario, velocidad de ventas ni segmentación de demanda.",
            next_action="Calibrar con estudio de mercado trazable y transacciones/comparables verificables.",
        ),
        DataGap(
            dataset="Geotecnia, topografía e hidráulica predial",
            impact="NASA y las capas regionales no resuelven capacidad portante, rellenos, nivel freático ni drenaje de diseño.",
            next_action="Ejecutar levantamiento topográfico, mecánica de suelos e hidrología/hidráulica de detalle.",
        ),
        DataGap(
            dataset="Comunidades, ocupación y conflictos",
            impact="No se descartan posesión, comunidades, consulta previa, servidumbres ni conflictos sociales.",
            next_action="Revisar catastro, SUNARP, Defensoría, SENACE y trabajo de campo con especialistas.",
        ),
    ])
    return gaps


def _evaluation_and_finance_stages(
    scorecard: Scorecard,
    results: list[RealEstateSiteResult],
    sensitivities: list[SubjectSensitivity],
    finance_ms: float,
):
    ranked = sorted((item for item in scorecard.subjects if item.score is not None), key=lambda item: item.score, reverse=True)
    evaluation = stage(
        "evaluation",
        PipelineStatus.COMPLETED,
        f"Comparación multicriterio calculada para {len(results)} terrenos; "
        + (f"líder condicionado {scorecard.leader}." if scorecard.leader else "sin líder por falta de datos."),
        [Provenance.MODEL, Provenance.ASSUMPTION],
        [StageEvidence(
            label=f"{item.rank}.º {item.subject}",
            value=f"{item.score:.1f}/100 · cobertura {item.coverage:.0%}",
            provenance=Provenance.MODEL,
        ) for item in ranked] + [StageEvidence(
            label="Lectura del score",
            value="Mayor puntaje = mejor combinación condicionada a evidencia y supuestos; no acredita edificabilidad ni inversión.",
        )],
        answers=["so_what"],
    )
    npvs = [item.finance.npv_usd for item in results]
    adverse = [next(scenario.npv for scenario in item.scenarios if scenario.key == "adverso") for item in sensitivities]
    finance = stage(
        "finance",
        PipelineStatus.COMPLETED,
        f"VAN positivo en {sum(value >= 0 for value in npvs)} de {len(npvs)} terrenos en el caso base "
        f"y en {sum(value >= 0 for value in adverse)} de {len(adverse)} en el adverso.",
        [Provenance.MODEL, Provenance.ASSUMPTION],
        [StageEvidence(
            label=item.label,
            value=f"VAN USD {item.finance.npv_usd:,.0f} · absorción {item.finance.sold_fraction_within_horizon:.0%}",
            provenance=Provenance.MODEL,
        ) for item in results] + [StageEvidence(
            label=f"Factor dominante · {item.subject}", value=item.tornado[0].label, provenance=item.tornado[0].provenance
        ) for item in sensitivities if item.tornado],
        finance_ms,
        ["so_what"],
    )
    return evaluation, finance


async def run_real_estate_screening(request: RealEstateScreeningRequest) -> RealEstateScreeningResponse:
    timings = StageTimings()
    subjects, areas, site_sources = _resolve_subjects(request)
    points = [item.representative_point for item in subjects]

    (datasets, timings.extraction_ms), (terrain, terrain_error, timings.terrain_ms), (spatial, spatial_errors), (
        territorial, territorial_errors,
    ) = await asyncio.gather(
        extract_power(points, ESTATE_VARIABLES, request.start_date, request.end_date),
        extract_terrain(points),
        _spatial_exposures(subjects, request),
        _territorial_evidence(subjects, request.include_territorial_layers),
    )
    expected_days = (request.end_date - request.start_date).days + 1
    analysis_start = perf_counter()
    summaries_by_subject = analyze_subjects(datasets, ESTATE_VARIABLES, expected_days)
    timings.analysis_ms = elapsed_ms(analysis_start)

    finance_start = perf_counter()
    sensitivities = [
        _estate_sensitivity(subject.label, area, request.assumptions)
        for subject, area in zip(subjects, areas, strict=True)
    ]
    territorial_by_subject = {item.subject: item for item in territorial}
    results = []
    for subject, area, summaries, exposure in zip(subjects, areas, summaries_by_subject, spatial, strict=True):
        evidence = territorial_by_subject.get(subject.label, RealEstateTerritorialEvidence(subject=subject.label, sources=[]))
        finance = _estate_npv(_base_finance(area, request.assumptions), request.assumptions)
        slope = _terrain_slope(terrain, subject.label)
        cautions = [
            "POWER y NASADEM son productos de grilla; no sustituyen topografía, geotecnia, hidrología ni diseño predial.",
            "Precio, costos, edificabilidad y absorción son supuestos del usuario, no observaciones de mercado.",
            "Cero intersecciones en una capa no demuestra ausencia de amenaza, patrimonio o restricción.",
        ]
        if area > PROJECT_SCALE_KM2:
            cautions.append(
                f"Área de análisis de escala territorial (más de {PROJECT_SCALE_HECTARES} ha): el VAN aplica la "
                "fracción desarrollable y los demás supuestos a toda la geometría, por lo que no describe un "
                "proyecto inmobiliario. Úsela para comparar exposición y dibuje o cargue un polígono predial "
                "para evaluar un proyecto."
            )
        if exposure is None:
            cautions.append("El muestreo K1 no estuvo disponible; no se interpreta como exposición climática nula.")
        if slope is None:
            cautions.append("La pendiente NASADEM no estuvo disponible; no se interpreta como terreno plano.")
        results.append(RealEstateSiteResult(
            subject_id=subject.id,
            label=subject.label,
            representative_point=subject.representative_point,
            area_km2=round(area, 6),
            variables=summaries,
            spatial_exposure=exposure,
            terrain_slope_degrees=slope,
            territorial_intersections=_territorial_counts(evidence),
            finance=finance,
            opportunities=[
                f"Polígono WGS84 de {area:.4f} km² medido geodésicamente.",
                f"VAN condicionado de {millions_usd(finance.npv_usd)} bajo los supuestos declarados.",
            ],
            cautions=cautions,
        ))
    timings.finance_ms = elapsed_ms(finance_start)

    scorecard = _scorecard(subjects, results, territorial, request.assumptions, terrain)
    labelled = [
        SubjectSummaries(label=subject.label, summaries=summaries)
        for subject, summaries in zip(subjects, summaries_by_subject, strict=True)
    ]
    trend_findings = collect_trend_findings(labelled)
    gaps = _data_gaps(terrain, subjects, spatial_errors, territorial, territorial_errors)
    pending = sum(item.status == Provenance.UNAVAILABLE for item in gaps)
    npvs = [item.finance.npv_usd for item in results]
    oversized = [item.label for item in results if item.area_km2 > PROJECT_SCALE_KM2]
    scale_note = ""
    if oversized:
        scale_note = (
            f" {', '.join(oversized)} superan {PROJECT_SCALE_HECTARES} ha y se tratan como áreas de análisis "
            "territorial: sus VAN no describen proyectos; se requiere un polígono predial para evaluar uno."
        )
    lens = SectorLens(
        readings=ESTATE_READINGS,
        stable_notes=ESTATE_STABLE_NOTES,
        economics=(
            f"Con supuestos del usuario, el VAN condicionado va de {millions_usd(min(npvs))} a {millions_usd(max(npvs))}; "
            f"{sum(value >= 0 for value in npvs)} de {len(npvs)} terrenos son no negativos. "
            "No acredita zonificación, titularidad, mercado ni factibilidad."
            f"{scale_note}"
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
    ] + [item.provenance for item in spatial if item is not None] + [item.provenance for item in site_sources])
    all_provenance = unique(source_provenance + [Provenance.MODEL, Provenance.ASSUMPTION] + ([Provenance.UNAVAILABLE] if pending else []))
    years = max(len(item.annual_series) for summaries in summaries_by_subject for item in summaries)
    evaluation, finance_stage = _evaluation_and_finance_stages(scorecard, results, sensitivities, timings.finance_ms)
    selection = selection_stage(subjects, max_separation_km(points))
    selection.provenance = unique([*selection.provenance, *[item.provenance for item in site_sources]])
    selection.evidence.append(StageEvidence(
        label="Origen geométrico",
        value=" · ".join(f"{item.subject}: {item.origin}" for item in site_sources),
    ))
    territorial_result = territorial_stage(terrain, terrain_error, gaps, timings.terrain_ms)
    territorial_result.summary = territorial_result.summary.replace(
        "capas oficiales siguen pendientes", "brechas de debida diligencia siguen pendientes"
    )
    for item in territorial_result.evidence:
        if item.label == "Capas pendientes":
            item.label = "Brechas pendientes"
    ready_intersections = sum(
        source.intersection_count or 0 for item in territorial for source in item.sources if source.status == "READY"
    )
    territorial_result.evidence.append(StageEvidence(
        label="Intersecciones devueltas por capas oficiales",
        value=f"{ready_intersections}; cero no demuestra ausencia de amenaza o restricción",
        provenance=Provenance.MODEL,
    ))
    pipeline = assemble_pipeline([
        selection,
        configuration_stage(
            SECTOR_LABEL,
            ESTATE_VARIABLES,
            request.start_date,
            request.end_date,
            years,
            f"precio USD {request.assumptions.sale_price_usd_m2:,.0f}/m² · "
            f"absorción {request.assumptions.annual_absorption_fraction:.0%}/año · "
            f"tasa {request.assumptions.discount_rate:.0%}",
        ),
        extraction_stage(labelled, timings.extraction_ms),
        analysis_stage(labelled, trend_findings, timings.analysis_ms),
        territorial_result,
        evaluation,
        finance_stage,
        results_stage(trend_findings, gaps, all_provenance),
        export_stage(all_provenance),
    ])
    # La pendiente puntúa en la comparación de terrenos: se contrasta con el segundo modelo de elevación y se registra.
    discoveries = terrain_discoveries(terrain)
    record_in_pipeline(pipeline, discoveries, empty=NO_TERRAIN_CHECK)
    fingerprint_payload = request.model_dump(mode="json")
    fingerprint_payload["resolved_geometries"] = [item.geometry for item in subjects]
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode()).hexdigest()[:16]
    return RealEstateScreeningResponse(
        analysis_id=fingerprint,
        generated_at=datetime.now(timezone.utc),
        title="Screening inmobiliario preliminar — comparación de terrenos",
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}",
        subjects=subjects,
        pipeline=pipeline,
        nasa_questions=nasa_questions,
        trend_findings=trend_findings,
        terrain=terrain,
        data_gaps=gaps,
        assumption_items=_assumption_items(request),
        financial_sensitivity=sensitivities,
        scorecard=scorecard,
        discoveries=discoveries,
        disclaimer=(
            "Screening preliminar con datos NASA, límites IGN/capas públicas y supuestos del usuario. No acredita "
            "propiedad, catastro, zonificación, parámetros urbanísticos, ausencia de riesgo o patrimonio, factibilidad "
            "de servicios, estudio de mercado, topografía, geotecnia, hidrología, presupuesto ni decisión de inversión."
        ),
        site_sources=site_sources,
        sites=results,
        territorial_evidence=territorial,
        assumptions=request.assumptions,
    )
