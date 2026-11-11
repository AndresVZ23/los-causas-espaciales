"""Piloto hidroeléctrico de pasada: screening comparativo de aprovechamientos sobre el contrato común C2.

Cada sitio es una toma sobre el río y una casa de máquinas aguas abajo. El caudal diario sale de GloFAS (la celda
del cauce más cercana, con regla declarada) y se contrasta con GEOGLOWS; el salto sale de NASADEM y se contrasta con
Copernicus GLO-30; las tendencias del caudal, la lluvia y la temperatura en la toma usan Mann–Kendall corregido. La
energía se calcula día por día para una central sin embalse. Lo que una fuente no entrega queda declarado, nunca en
cero. Sin token de Earthdata, el salto se toma de Copernicus y se dice.
"""

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from time import perf_counter

import numpy as np

from ..connectors.copernicus.dem import SOURCE as COPERNICUS_SOURCE
from ..connectors.copernicus.glofas import API as GLOFAS_URL
from ..connectors.copernicus.glofas import FIRST_DAY, GlofasConnector, GlofasSeries, NoRiverError
from ..connectors.copernicus.glofas import SOURCE as GLOFAS_SOURCE
from ..connectors.copernicus.glofas import VERSION as GLOFAS_VERSION
from ..connectors.geoglows.streamflow import BASE as GEOGLOWS_URL
from ..connectors.geoglows.streamflow import SEARCH_KM
from ..connectors.geoglows.streamflow import SOURCE as GEOGLOWS_SOURCE
from ..connectors.geoglows.streamflow import GeoglowsConnector, GeoglowsError, RiverChoice
from ..finance.sensitivity import Driver, break_even_item, tornado
from ..geospatial.geometry import GEOD
from ..orchestration import extraction
from ..orchestration.analysis import analyze_subjects
from ..orchestration.annual_crosscheck import MIN_COMMON_YEARS, attach_annual_countercheck
from ..orchestration.discoveries import flow_verdict, hydro_discoveries, record_in_pipeline, variable_discoveries
from ..orchestration.extraction import elapsed_ms, extract_power, extract_terrain, max_separation_km
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
from ..schemas.analysis import Point, Provenance, SourceMetadata
from ..schemas.hydro import (
    FlowDurationPoint,
    HydroAssumptions,
    HydroFlowCell,
    HydroFlowCheck,
    HydroHead,
    HydroResource,
    HydroScreeningRequest,
    HydroScreeningResponse,
    HydroSite,
    HydroSiteResult,
)
from ..schemas.pipeline import AnnualObservation, DataGap, VariableSummary
from ..schemas.scoring import Criterion, Direction, Scorecard, ScorecardRequest, SubjectValues
from ..schemas.screening import AssumptionItem, FinanceScenario, PipelineStatus, StageEvidence, StudySubject, SubjectKind, SubjectSensitivity
from ..schemas.terrain import TerrainCrosscheck, TerrainResponse, TerrainSiteResult
from ..scoring.multicriteria import build_scorecard
from ..statistics.trends import partial_years
from .energy_common import BREAK_EVEN_SPAN, break_even_note, fmt_value, lower_first, scenario_npv
from .hydro_energy import (
    FIRM_EXCEEDANCE,
    annual_energy_mwh,
    calculate_hydro_projection,
    design_flow,
    exceedance_flow,
    flow_duration,
    plant_factor,
    power_mw,
)

DISCHARGE = "RIVER_DISCHARGE"
POWER_VARIABLES = ["PRECTOTCORR", "T2M"]
HYDRO_VARIABLES = [DISCHARGE, *POWER_VARIABLES]
SECTOR_LABEL = "Hidroeléctrico"
GEOGLOWS_WAIT_SECONDS = 40.0     # la búsqueda de un punto nuevo tarda ~1 minuto: si no llega, sigue en segundo plano
GEOGLOWS_PENDING = "La búsqueda del río en GEOGLOWS sigue en curso; vuelva a ejecutar en uno o dos minutos para ver la segunda opinión del caudal"
_inflight: dict[str, asyncio.Task] = {}
LOW_HEAD_M = 20.0            # por debajo, el error vertical de los modelos de elevación pesa demasiado
RESOURCE_LOW_PERCENTILE, RESOURCE_HIGH_PERCENTILE = 10, 90
ADVERSE_KEYS = {"plant_factor", "energy_price_usd_mwh", "capex_usd_per_mw", "opex_fraction_of_capex"}
NASADEM_SOURCE = "NASADEM"

HYDRO_READINGS: dict[tuple[str, str], str] = {
    (DISCHARGE, "decreasing"): "el caudal cae: la curva de duración histórica sobrestima la energía futura; conviene sensibilizarla a la baja y revisar el caudal de diseño",
    (DISCHARGE, "increasing"): "el caudal sube: la historia es conservadora para la energía; revisar crecidas de diseño y sedimentos",
    ("PRECTOTCORR", "decreasing"): "la precipitación en la toma disminuye: menos recarga local; confirmarlo con la lluvia de toda la cuenca",
    ("PRECTOTCORR", "increasing"): "la precipitación en la toma aumenta: más escorrentía y sedimentos; revisar crecidas",
    ("T2M", "increasing"): "la temperatura sube: más evaporación y, en cuencas con nieve o glaciares, cambia la estacionalidad del caudal",
    ("T2M", "decreasing"): "la temperatura baja: menos evaporación en la cuenca",
}
HYDRO_STABLE_NOTES = {
    DISCHARGE: "El caudal no muestra deriva significativa en ningún sitio: no hay evidencia para castigar la curva de duración por tendencia, lo que no prueba que sea constante.",
}
ASSUMPTION_LABELS = {
    "design_exceedance_percent": ("Excedencia del caudal de diseño", "%"), "ecological_flow_fraction": ("Caudal ecológico (del caudal medio)", "fracción"),
    "min_turbine_flow_fraction": ("Mínimo técnico (del caudal de diseño)", "fracción"), "efficiency": ("Eficiencia", "fracción"),
    "head_loss_fraction": ("Pérdidas de carga", "fracción"), "availability": ("Disponibilidad", "fracción"),
    "capex_usd_per_mw": ("CAPEX por MW", "USD/MW"), "opex_fraction_of_capex": ("OPEX anual (del CAPEX)", "fracción"),
    "energy_price_usd_mwh": ("Precio de energía", "USD/MWh"), "mitigation_capex_usd": ("CAPEX de mitigación", "USD"),
    "discount_rate": ("Tasa de descuento", "fracción"), "horizon_years": ("Horizonte", "años"),
    "price_sensitivity": ("Rango del precio (±)", "fracción"), "capex_sensitivity": ("Rango del CAPEX (±)", "fracción"),
    "opex_sensitivity": ("Rango del OPEX (±)", "fracción"), "discount_rate_sensitivity": ("Rango de la tasa (±)", "puntos"),
}
# Criterios del puntaje: (clave, etiqueta, unidad, dirección, peso, peor, mejor, fundamento). Pesos y escalas son editables.
HYDRO_CRITERIA = [
    ("plant_factor", "Factor de planta", "fracción", Direction.HIGHER_IS_BETTER, 0.20, 0.20, 0.80,
     "Caudal turbinado medio sobre el de diseño, con disponibilidad. Escala 20 % (central ociosa) a 80 %."),
    ("firm_flow", "Caudal firme en estiaje", "fracción", Direction.HIGHER_IS_BETTER, 0.10, 0.0, 0.6,
     "Caudal del río excedido el 95 % del tiempo sobre el caudal de diseño: cuánto de la central sigue operando en estiaje."),
    ("resource_drift", "Deriva del caudal", "% por década", Direction.HIGHER_IS_BETTER, 0.10, -10.0, 10.0,
     "Pendiente de Sen × 10 sobre el caudal medio, solo si es significativa tras BH; sin evidencia de cambio cuenta como 0."),
    ("flow_confidence", "Confianza del caudal", "%", Direction.LOWER_IS_BETTER, 0.15, 100.0, 0.0,
     "Diferencia absoluta entre GloFAS y GEOGLOWS en la media común; si no ubican el mismo río, cuenta como 100 %."),
    ("head_confidence", "Confianza del salto", "%", Direction.LOWER_IS_BETTER, 0.10, 20.0, 0.0,
     "Diferencia absoluta del salto entre NASADEM y Copernicus GLO-30."),
    ("npv_ratio", "VAN / CAPEX", "fracción", Direction.HIGHER_IS_BETTER, 0.35, -0.5, 0.5,
     "VAN base sobre CAPEX con los supuestos del usuario. Escala −50 % a +50 %."),
]
SCORE_NOTES = [
    "Ordena prioridades de estudio entre aprovechamientos; no es una recomendación de inversión ni un índice de factibilidad.",
    "Escalas de referencia y pesos son supuestos editables; el resultado debe leerse junto con su estabilidad.",
]
# Validación del método (ADR-042), no un resultado del análisis en curso: se reproduce con scripts/qa/validate_hydro.py.
METHOD_VALIDATION = [
    "Validación del método con producción real (COES, registros diarios de 2024; medida el 10-nov-2026): la C.H. Machupicchu produjo "
    "1,252 GWh con 192.45 MW, un factor de planta de 74.1 %. Para ese año este modelo da 64.7 % con caudal ecológico de 10 %, 71.8 % con "
    "5 % y 77.1 % sin caudal ecológico, y 163 MW de potencia con el salto leído sobre el relieve. Es un solo caso: respalda a GloFAS como "
    "caso base, no la exactitud del modelo en otro río.",
]


class HydroSiteError(ValueError):
    """Los puntos del sitio no permiten calcular una central: la API responde 422 con el motivo."""


class HydroDataError(RuntimeError):
    """Una fuente necesaria (caudal o relieve) no respondió: la API responde 502."""


def _km(a: Point, b: Point) -> float:
    return GEOD.inv(a.longitude, a.latitude, b.longitude, b.latitude)[2] / 1000


def _subjects(request: HydroScreeningRequest) -> list[StudySubject]:
    return [
        StudySubject(
            id=f"sitio-{index + 1}", label=site.label.strip(), kind=SubjectKind.SEGMENT,
            geometry={"type": "LineString", "coordinates": [[site.intake.longitude, site.intake.latitude], [site.powerhouse.longitude, site.powerhouse.latitude]]},
            representative_point=Point(latitude=site.intake.latitude, longitude=site.intake.longitude, label=site.label.strip()),
        )
        for index, site in enumerate(request.sites)
    ]


def _terrain_points(request: HydroScreeningRequest) -> list[Point]:
    """Toma y casa de máquinas de cada sitio. La toma lleva el nombre del sitio: es su punto representativo en el relieve."""
    points = []
    for site in request.sites:
        label = site.label.strip()
        points.append(Point(latitude=site.intake.latitude, longitude=site.intake.longitude, label=label))
        points.append(Point(latitude=site.powerhouse.latitude, longitude=site.powerhouse.longitude, label=f"{label} · casa de máquinas"))
    return points


async def _flows(request: HydroScreeningRequest) -> tuple[list[GlofasSeries], float]:
    start = perf_counter()
    connector = GlofasConnector()

    async def one(site: HydroSite) -> GlofasSeries:
        try:
            return await connector.discharge(site.intake.latitude, site.intake.longitude, request.start_date, request.end_date)
        except NoRiverError as exc:
            raise HydroSiteError(f"{site.label.strip()}: {exc}") from exc
    series = await asyncio.gather(*(one(site) for site in request.sites))
    return list(series), elapsed_ms(start)


def _second_task(site: HydroSite) -> asyncio.Task:
    """Una búsqueda de GEOGLOWS por toma, compartida entre consultas simultáneas y que sobrevive al presupuesto de espera."""
    key = f"{site.intake.latitude:.4f},{site.intake.longitude:.4f}"
    task = _inflight.get(key)
    if task is None or (task.done() and (task.cancelled() or task.exception() is not None)):
        task = asyncio.get_running_loop().create_task(GeoglowsConnector().river_near(site.intake.latitude, site.intake.longitude))
        _inflight[key] = task
        task.add_done_callback(lambda t, k=key: _inflight.pop(k, None) if not t.cancelled() and t.exception() is None else None)
    return task


async def _second_flows(tasks: Sequence[asyncio.Task], started: float) -> list["RiverChoice | str | None"]:
    """El río de GEOGLOWS de cada toma. Un fallo vuelve como texto y una búsqueda que no terminó en el presupuesto
    de espera, como None: sigue en segundo plano y queda en caché para la siguiente ejecución. Nunca un caudal cero."""
    remaining = max(0.0, GEOGLOWS_WAIT_SECONDS - (perf_counter() - started))
    done, _ = await asyncio.wait(tasks, timeout=remaining)
    out: list[RiverChoice | str | None] = []
    for task in tasks:
        if task not in done:
            out.append(None)
        elif isinstance(task.exception(), GeoglowsError):
            out.append(str(task.exception()))
        else:
            out.append(task.result())      # un error que no es del proveedor se propaga
    return out


async def _copernicus_only(points: Sequence[Point]) -> list[TerrainCrosscheck | None]:
    """Si NASADEM no respondió, el relieve se lee solo de Copernicus GLO-30."""
    checks = await asyncio.gather(*(extraction._copernicus(point) for point in points))
    return [check if isinstance(check, TerrainCrosscheck) else None for check in checks]


def _cell_note(series: GlofasSeries) -> str:
    cell = series.cell
    if cell.moved:
        seen = "sin dato" if cell.point_cell_mean is None else f"{cell.point_cell_mean:.2f} m³/s"
        return (f"El cauce de GloFAS no pasa por la celda de la toma ({seen} en {cell.scan_year}); se usó la celda vecina "
                f"{cell.latitude:.3f}, {cell.longitude:.3f}, a {cell.distance_km:.1f} km, con {cell.used_cell_mean:.2f} m³/s.")
    return f"Celda GloFAS {cell.latitude:.3f}, {cell.longitude:.3f}: la de la toma, sobre el cauce del modelo ({cell.used_cell_mean:.2f} m³/s en {cell.scan_year})."


def _discharge_source(series: GlofasSeries) -> SourceMetadata:
    return SourceMetadata(
        source_id="glofas-openmeteo", dataset=GLOFAS_SOURCE, version=GLOFAS_VERSION, variable=DISCHARGE, unit="m3/s",
        temporal_resolution="diaria; análisis agregado a escala anual", spatial_resolution="0.05° (~5 km); caudal simulado, no aforado",
        downloaded_at=series.downloaded_at, source_url=GLOFAS_URL, provenance=series.provenance, quality_notes=[_cell_note(series)],
    )


def build_head(site: HydroSite, intake: tuple[float | None, float | None], powerhouse: tuple[float | None, float | None],
               provenance: Provenance) -> HydroHead:
    """Salto bruto con NASADEM y, como contraste, Copernicus. Cada tupla es (elevación NASADEM, elevación Copernicus)."""
    label = site.label.strip()
    nasadem = (intake[0], powerhouse[0]) if intake[0] is not None and powerhouse[0] is not None else None
    copernicus = (intake[1], powerhouse[1]) if intake[1] is not None and powerhouse[1] is not None else None
    if nasadem is None and copernicus is None:
        raise HydroDataError(f"{label}: ni NASADEM ni Copernicus devolvieron la elevación de la toma y de la casa de máquinas; reintente.")
    limitations = ["Modelos de elevación de 30 m (superficie): el error vertical es de varios metros y no sustituyen un levantamiento topográfico."]
    if nasadem is not None:
        source, (up, down), second = NASADEM_SOURCE, nasadem, copernicus
    else:
        source, (up, down), second = COPERNICUS_SOURCE, copernicus, None
        limitations.append("NASADEM no entregó elevación (sin token de Earthdata o tesela en descarga): el salto se lee de Copernicus GLO-30, sin contraste.")
    gross = up - down
    if gross <= 0:
        raise HydroSiteError(f"{label}: la casa de máquinas ({down:,.0f} m) no está por debajo de la toma ({up:,.0f} m) según {source}. "
                             f"Revise los dos puntos: la casa de máquinas va aguas abajo.")
    conduction = _km(site.intake, site.powerhouse)
    second_gross = second[0] - second[1] if second is not None else None
    if gross < LOW_HEAD_M:
        limitations.append(f"Salto menor de {LOW_HEAD_M:.0f} m: el error vertical de los modelos de elevación pesa mucho en saltos bajos.")
    return HydroHead(
        source=source, intake_elevation_m=round(up, 1), powerhouse_elevation_m=round(down, 1), gross_head_m=round(gross, 1),
        second_source=COPERNICUS_SOURCE if second is not None else None, second_gross_head_m=round(second_gross, 1) if second_gross is not None else None,
        gap_m=round(second_gross - gross, 1) if second_gross is not None else None,
        gap_percent=round((second_gross - gross) / gross * 100, 1) if second_gross is not None else None,
        conduction_km=round(conduction, 2), mean_slope_percent=round(gross / (conduction * 1000) * 100, 2) if conduction > 0 else 0.0,
        provenance=provenance, limitations=limitations,
    )


def _complete_years(series: GlofasSeries) -> dict[int, np.ndarray]:
    """Caudal diario de los años con al menos el 90 % de sus días: un año a medias sesgaría la curva de duración."""
    incomplete = set(partial_years(series.observations))
    by_year: dict[int, list[float]] = {}
    for item in series.observations:
        if item.timestamp.year not in incomplete:
            by_year.setdefault(item.timestamp.year, []).append(item.value)
    return {year: np.array(values, dtype=np.float64) for year, values in sorted(by_year.items())}


def build_resource(site: HydroSite, series: GlofasSeries, head: HydroHead, assumptions: HydroAssumptions) -> tuple[HydroResource, np.ndarray]:
    by_year = _complete_years(series)
    if not by_year:
        raise HydroDataError(f"{site.label.strip()}: GloFAS no tiene ningún año completo de caudal en el período pedido.")
    years = list(by_year)
    flows = np.concatenate([by_year[year] for year in years])
    mean_flow = float(flows.mean())
    ecological = mean_flow * assumptions.ecological_flow_fraction
    if site.design_flow_m3s is not None:
        design, basis = site.design_flow_m3s, "Declarado por el usuario para este sitio."
    else:
        design = design_flow(flows, ecological, assumptions.design_exceedance_percent)
        basis = f"Caudal aprovechable (río − ecológico) excedido el {assumptions.design_exceedance_percent:g} % del tiempo."
    net_head = head.gross_head_m * (1 - assumptions.head_loss_fraction)
    minimum = assumptions.min_turbine_flow_fraction
    cell = series.cell
    resource = HydroResource(
        period=f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0]), days=int(flows.size), mean_flow_m3s=round(mean_flow, 3),
        firm_flow_m3s=round(exceedance_flow(flows, FIRM_EXCEEDANCE), 3), ecological_flow_m3s=round(ecological, 3), design_flow_m3s=round(design, 3),
        design_basis=basis, min_turbine_flow_m3s=round(minimum * design, 3),
        flow_duration=[FlowDurationPoint(exceedance_percent=percent, flow_m3s=round(value, 3)) for percent, value in flow_duration(flows)],
        net_head_m=round(net_head, 1), capacity_mw=round(power_mw(design, net_head, assumptions.efficiency), 3),
        plant_factor=round(plant_factor(flows, ecological, design, minimum), 4),
        annual_plant_factors=[AnnualObservation(year=year, value=round(plant_factor(by_year[year], ecological, design, minimum), 4)) for year in years],
        cell=HydroFlowCell(latitude=cell.latitude, longitude=cell.longitude, distance_km=cell.distance_km, moved=cell.moved,
                           point_cell_mean_m3s=cell.point_cell_mean, used_cell_mean_m3s=cell.used_cell_mean,
                           neighborhood_max_m3s=cell.neighborhood_max, scan_year=cell.scan_year),
        source=GLOFAS_SOURCE, source_url=GLOFAS_URL, provenance=series.provenance, downloaded_at=series.downloaded_at,
    )
    return resource, flows


def _common_means(summary: VariableSummary, choice: RiverChoice) -> tuple[str, float, float] | None:
    """(período, media GloFAS, media GEOGLOWS) en los años que tienen ambas fuentes; None con menos de diez."""
    primary = {point.year: point.value for point in summary.annual_series}
    pairs = [(item.timestamp.year, primary[item.timestamp.year], item.value) for item in choice.annual if item.timestamp.year in primary]
    if len(pairs) < MIN_COMMON_YEARS:
        return None
    return f"{pairs[0][0]}–{pairs[-1][0]}", sum(p[1] for p in pairs) / len(pairs), sum(p[2] for p in pairs) / len(pairs)


def build_flow_check(choice: RiverChoice, summary: VariableSummary, resource: HydroResource, flows: np.ndarray,
                     assumptions: HydroAssumptions) -> HydroFlowCheck | None:
    common = _common_means(summary, choice)
    if common is None:
        return None
    period, mine, theirs = common
    ratio = theirs / mine if mine > 0 else None
    verdict = flow_verdict(ratio)
    factor = None
    if verdict != "no_comparable":
        factor = plant_factor(flows, resource.ecological_flow_m3s, resource.design_flow_m3s, assumptions.min_turbine_flow_fraction, level=ratio)
    limitations = [
        "Segunda opinión de modelo, no medición: GEOGLOWS y GloFAS comparten la lluvia de ERA5; cambian el modelo de tránsito y la red de ríos.",
        f"Río elegido: el de mayor caudal medio entre {choice.candidates} tramo(s) que GEOGLOWS devuelve en una malla de ±{SEARCH_KM:.1f} km alrededor de la toma.",
    ]
    if choice.river_id != choice.nearest_river_id:
        nearest = "sin dato" if choice.nearest_mean is None else f"{choice.nearest_mean:.2f} m³/s"
        limitations.append(f"El tramo más cercano a la toma (n.º {choice.nearest_river_id}) lleva {nearest}; se usó el n.º {choice.river_id}, de mayor caudal.")
    return HydroFlowCheck(
        source=GEOGLOWS_SOURCE, river_id=choice.river_id, nearest_river_id=choice.nearest_river_id, candidates=choice.candidates, period=period,
        mean_m3s=round(theirs, 3), primary_mean_m3s=round(mine, 3), ratio=round(ratio, 4) if ratio is not None else None,
        gap_percent=round((ratio - 1) * 100, 1) if ratio is not None else None, verdict=verdict,
        plant_factor_at_second=round(factor, 4) if factor is not None else None,
        annual_energy_mwh_at_second=round(annual_energy_mwh(resource.capacity_mw, factor, assumptions.availability), 2) if factor is not None else None,
        provenance=choice.provenance, downloaded_at=choice.downloaded_at, source_url=GEOGLOWS_URL, limitations=limitations,
    )


def hydro_npv(inputs: Mapping[str, float], capacity_mw: float, assumptions: HydroAssumptions) -> float:
    """VAN con factores sobrescritos; reutiliza la proyección para no duplicar fórmulas. `flow_ratio` y `head_ratio`
    escalan la energía de una central ya dimensionada (su CAPEX no cambia)."""
    updated = assumptions.model_copy(update={key: inputs[key] for key in ("energy_price_usd_mwh", "capex_usd_per_mw", "opex_fraction_of_capex", "discount_rate")})
    factor = inputs["plant_factor"] * inputs.get("flow_ratio", 1.0) * inputs.get("head_ratio", 1.0)
    return calculate_hydro_projection(capacity_mw, factor, updated).npv_usd


def _plant_factor_note(value: float | None, observed: list[float]) -> str:
    if value is None:
        return "El VAN no cruza cero en el rango de factor de planta buscado."
    if not observed:
        return f"Factor de planta mínimo para VAN ≥ 0: {value * 100:.1f} %."
    best = max(observed)
    reach = "ningún año observado lo alcanza" if value > best else f"{sum(1 for item in observed if item >= value)} de {len(observed)} años observados lo superan"
    return f"Factor de planta mínimo para VAN ≥ 0: {value * 100:.1f} %; {reach} (mejor año: {best * 100:.1f} %)."


def hydro_sensitivity(label: str, resource: HydroResource, head: HydroHead, check: HydroFlowCheck | None, assumptions: HydroAssumptions) -> SubjectSensitivity:
    a = assumptions
    base = {"plant_factor": resource.plant_factor, "flow_ratio": 1.0, "head_ratio": 1.0, "energy_price_usd_mwh": a.energy_price_usd_mwh,
            "capex_usd_per_mw": a.capex_usd_per_mw, "opex_fraction_of_capex": a.opex_fraction_of_capex, "discount_rate": a.discount_rate}

    def model(inputs: Mapping[str, float]) -> float:
        return hydro_npv(inputs, resource.capacity_mw, a)

    user = "Supuesto del usuario"
    drivers = [
        Driver("energy_price_usd_mwh", "Precio de energía", "USD/MWh", a.energy_price_usd_mwh * (1 - a.price_sensitivity),
               a.energy_price_usd_mwh * (1 + a.price_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.price_sensitivity:.0%}."),
        Driver("capex_usd_per_mw", "CAPEX por MW", "USD/MW", a.capex_usd_per_mw * (1 + a.capex_sensitivity),
               a.capex_usd_per_mw * (1 - a.capex_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.capex_sensitivity:.0%}."),
        Driver("opex_fraction_of_capex", "OPEX anual (del CAPEX)", "fracción", a.opex_fraction_of_capex * (1 + a.opex_sensitivity),
               a.opex_fraction_of_capex * (1 - a.opex_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.opex_sensitivity:.0%}."),
        Driver("discount_rate", "Tasa de descuento", "fracción", a.discount_rate + a.discount_rate_sensitivity,
               max(0.0, a.discount_rate - a.discount_rate_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.discount_rate_sensitivity * 100:.1f} puntos."),
    ]
    observed = [item.value for item in resource.annual_plant_factors]
    if len(observed) >= 5:
        low, high = (float(np.percentile(observed, q)) for q in (RESOURCE_LOW_PERCENTILE, RESOURCE_HIGH_PERCENTILE))
        drivers.insert(0, Driver("plant_factor", "Recurso hídrico (año seco / húmedo)", "fracción", low, high, Provenance.MODEL,
                                 f"Percentiles {RESOURCE_LOW_PERCENTILE} y {RESOURCE_HIGH_PERCENTILE} del factor de planta de {len(observed)} años ({resource.period}), GloFAS."))
    # La segunda fuente de cada dato físico es el otro extremo de su factor: no se sabe cuál de las dos acierta.
    if check is not None and check.plant_factor_at_second is not None and resource.plant_factor > 0:
        ratio = check.plant_factor_at_second / resource.plant_factor
        if abs(ratio - 1) > 1e-3:
            drivers.append(Driver("flow_ratio", "Caudal (GloFAS ↔ GEOGLOWS)", "×", min(1.0, ratio), max(1.0, ratio), Provenance.MODEL,
                                  f"Con el caudal medio de GEOGLOWS ({check.gap_percent:+.0f} %), la energía sería {ratio:.2f} veces la del caso base."))
    if head.second_gross_head_m is not None and head.gross_head_m > 0:
        ratio = head.second_gross_head_m / head.gross_head_m
        if abs(ratio - 1) > 1e-3 and ratio > 0:
            drivers.append(Driver("head_ratio", "Salto (NASADEM ↔ Copernicus)", "×", min(1.0, ratio), max(1.0, ratio), Provenance.MODEL,
                                  f"Con el salto de Copernicus GLO-30 ({head.gap_percent:+.1f} %), la energía sería {ratio:.2f} veces la del caso base."))
    adverse = {driver.key: driver.low for driver in drivers if driver.key in ADVERSE_KEYS}
    favorable = {driver.key: driver.high for driver in drivers if driver.key in ADVERSE_KEYS}
    moved = [driver for driver in drivers if driver.key in ADVERSE_KEYS]
    shown = lambda driver, value: f"{value * 100:.1f} %" if driver.unit == "fracción" else fmt_value(value, driver.unit)  # noqa: E731
    scenarios = [
        FinanceScenario(key="base", label="Base", npv=round(model(base), 2), changes=["Todos los supuestos en su valor declarado; caudal = serie completa de GloFAS."]),
        FinanceScenario(key="adverso", label="Adverso", npv=round(model({**base, **adverse}), 2), changes=[f"{d.label}: {shown(d, d.low)}" for d in moved]),
        FinanceScenario(key="favorable", label="Favorable", npv=round(model({**base, **favorable}), 2), changes=[f"{d.label}: {shown(d, d.high)}" for d in moved]),
    ]
    break_evens = [
        break_even_item(model, base, "energy_price_usd_mwh", "Precio de equilibrio", "USD/MWh", 0.0, BREAK_EVEN_SPAN * max(a.energy_price_usd_mwh, 1.0),
                        lambda value: break_even_note(value, base["energy_price_usd_mwh"], "USD/MWh", "precio mínimo", higher_is_better=True)),
        break_even_item(model, base, "capex_usd_per_mw", "CAPEX máximo por MW", "USD/MW", 1.0, BREAK_EVEN_SPAN * a.capex_usd_per_mw,
                        lambda value: break_even_note(value, base["capex_usd_per_mw"], "USD/MW", "CAPEX máximo por MW", higher_is_better=False)),
        break_even_item(model, base, "plant_factor", "Factor de planta de equilibrio", "fracción", 0.0, 1.0,
                        lambda value: _plant_factor_note(value, observed)),
    ]
    return SubjectSensitivity(subject=label, base_npv=scenarios[0].npv, scenarios=scenarios, tornado=tornado(model, base, drivers), break_evens=break_evens)


def _site_result(site: HydroSite, summaries: list[VariableSummary], head: HydroHead, resource: HydroResource, check: HydroFlowCheck | None,
                 second_error: str | None, position: int, total: int, assumptions: HydroAssumptions) -> HydroSiteResult:
    label = site.label.strip()
    discharge = next(item for item in summaries if item.variable == DISCHARGE)
    finance = calculate_hydro_projection(resource.capacity_mw, resource.plant_factor, assumptions)
    cell = resource.cell
    opportunities = [
        f"Caudal medio de {resource.mean_flow_m3s:,.1f} m³/s y salto bruto de {head.gross_head_m:,.0f} m: central de pasada de "
        f"{resource.capacity_mw:,.1f} MW con un caudal de diseño de {resource.design_flow_m3s:,.1f} m³/s.",
        f"Factor de planta neto de {finance.plant_factor_net * 100:.0f} %: {finance.annual_energy_mwh:,.0f} MWh al año ({resource.period}).",
    ]
    if total > 1:
        opportunities.append(f"Posición {position} de {total} entre los aprovechamientos comparados por energía anual.")
    if discharge.significant_after_bh and discharge.trend.direction == "increasing":
        opportunities.append("El caudal tiene una tendencia creciente que conserva significancia tras el ajuste BH.")
    cautions = ["El caudal sale de GloFAS, un modelo global con celdas de 5 km: la decisión de inversión exige un aforo en la toma."]
    if cell.moved:
        cautions.append(f"El cauce de GloFAS no pasa por la celda de la toma: se usó la celda vecina a {cell.distance_km:.1f} km. Verifique que es su río.")
    elif cell.neighborhood_max_m3s >= 2 * cell.used_cell_mean_m3s:
        cautions.append(f"Una celda vecina lleva {cell.neighborhood_max_m3s:,.1f} m³/s frente a {cell.used_cell_mean_m3s:,.1f} en la de la toma "
                        f"({cell.scan_year}): si su toma está en el cauce principal, acerque el punto a ese cauce.")
    if check is None:
        cautions.append(f"Sin segunda opinión del caudal: {lower_first(second_error or 'GEOGLOWS no tiene diez años comunes con GloFAS').rstrip('.')}.")
    elif check.verdict == "no_comparable":
        cautions.append(f"GEOGLOWS no ubica un río comparable junto a la toma ({check.mean_m3s:,.2f} m³/s frente a {check.primary_mean_m3s:,.1f} de GloFAS): "
                        f"el caudal queda con una sola fuente.")
    elif check.verdict == "difieren":
        cautions.append(f"GEOGLOWS da {check.mean_m3s:,.1f} m³/s frente a {check.primary_mean_m3s:,.1f} de GloFAS ({check.gap_percent:+.0f} %): "
                        f"el nivel del caudal no está resuelto entre modelos.")
    if discharge.significant_after_bh and discharge.trend.direction == "decreasing":
        cautions.append("El caudal presenta una tendencia decreciente significativa tras el ajuste BH.")
    if resource.capacity_mw <= 0:
        cautions.append("El caudal aprovechable con esta regla de diseño es nulo: no hay central que dimensionar.")
    elif resource.firm_flow_m3s - resource.ecological_flow_m3s < resource.min_turbine_flow_m3s:
        cautions.append(f"En estiaje (caudal excedido el 95 % del tiempo: {resource.firm_flow_m3s:,.2f} m³/s) la central queda bajo su mínimo técnico y para.")
    cautions += [item for item in head.limitations[1:]]
    cautions.append("No incluye derechos de agua, caudal ecológico oficial, sedimentos, geología de la conducción ni conexión eléctrica.")
    return HydroSiteResult(
        location=Point(latitude=site.intake.latitude, longitude=site.intake.longitude, label=label),
        powerhouse=Point(latitude=site.powerhouse.latitude, longitude=site.powerhouse.longitude, label=f"{label} · casa de máquinas"),
        relative_position=position, relative_position_text=f"{position} de {total} por energía anual", variables=summaries, head=head,
        resource=resource, flow_check=check, finance=finance, opportunities=opportunities, cautions=cautions,
    )


def hydro_scorecard(subjects: list[StudySubject], results: list[HydroSiteResult], assumptions: HydroAssumptions) -> Scorecard:
    rows = []
    for subject, result in zip(subjects, results, strict=True):
        discharge = next(item for item in result.variables if item.variable == DISCHARGE)
        resource, check, head, finance = result.resource, result.flow_check, result.head, result.finance
        drift = 0.0
        if discharge.significant_after_bh and discharge.trend.slope_per_year is not None and discharge.mean > 0:
            drift = discharge.trend.slope_per_year * 10 / discharge.mean * 100
        if check is None:
            confidence = None
        else:
            confidence = 100.0 if check.verdict == "no_comparable" else min(abs(check.gap_percent), 100.0)
        rows.append(SubjectValues(subject=subject.label, values={
            "plant_factor": finance.plant_factor_net,
            "firm_flow": resource.firm_flow_m3s / resource.design_flow_m3s if resource.design_flow_m3s > 0 else None,
            "resource_drift": drift, "flow_confidence": confidence,
            "head_confidence": abs(head.gap_percent) if head.gap_percent is not None else None,
            "npv_ratio": finance.npv_usd / finance.initial_capex_usd if finance.initial_capex_usd > 0 else None,
        }))
    criteria = [Criterion(key=key, label=label, unit=unit, direction=direction, weight=weight, worst=worst, best=best, provenance=Provenance.MODEL, basis=basis)
                for key, label, unit, direction, weight, worst, best, basis in HYDRO_CRITERIA]
    notes = list(SCORE_NOTES)
    for key, name in (("flow_confidence", "segunda opinión del caudal (GEOGLOWS)"), ("head_confidence", "contraste del salto (Copernicus)")):
        missing = [row.subject for row in rows if row.values[key] is None]
        if missing:
            notes.append(f"Sin {name} para {', '.join(missing)}: ese criterio queda fuera y su peso se reparte (ver cobertura).")
    if len(rows) == 1:
        notes.append("Con un solo aprovechamiento no hay comparación: el puntaje lo ubica en las escalas de referencia.")
    return build_scorecard(ScorecardRequest(criteria=criteria, subjects=rows), notes)


def _data_gaps(second_errors: list[str], pending: list[str], terrain_error: str | None, heads: list[HydroHead]) -> list[DataGap]:
    gaps = []
    if pending:
        gaps.append(DataGap(dataset="GEOGLOWS · segunda opinión del caudal (en consulta)",
                            impact=f"La búsqueda del río en GEOGLOWS sigue en curso para: {', '.join(pending)}. Esta ejecución usa solo GloFAS en esos sitios.",
                            next_action="Volver a ejecutar en uno o dos minutos: la consulta continúa en segundo plano y queda en caché."))
    if terrain_error:
        gaps.append(DataGap(dataset="NASADEM (elevación de toma y casa de máquinas)", impact=f"{terrain_error} El salto se leyó solo de Copernicus GLO-30, sin contraste.",
                            next_action="Volver a ejecutar cuando NASADEM responda."))
    elif any(head.second_source is None for head in heads):
        gaps.append(DataGap(dataset="Contraste del salto (NASADEM y Copernicus)", impact="En algún sitio solo uno de los dos modelos de elevación entregó dato: el salto queda sin contraste.",
                            next_action="Configurar EARTHDATA_TOKEN o volver a ejecutar cuando termine la descarga de la tesela."))
    if second_errors:
        gaps.append(DataGap(dataset=GEOGLOWS_SOURCE, impact="; ".join(second_errors)[:400], next_action="Reintentar; un sitio sin GEOGLOWS queda sin segunda opinión del caudal, no con ceros."))
    return gaps + [
        DataGap(dataset="Aforo en la toma (estación hidrométrica)", impact="El caudal proviene de modelos globales, no de mediciones; en cuencas pequeñas, áridas o reguladas el error puede ser grande.",
                next_action="Usar o instalar una estación (ANA, SENAMHI) al menos un año hidrológico y correlacionarla con la serie larga."),
        DataGap(dataset="Disponibilidad hídrica y caudal ecológico (ANA)", impact="El caudal ecológico es un supuesto y los usos aguas arriba (riego, minería, trasvases) no están descontados.",
                next_action="Solicitar a la ANA la acreditación de disponibilidad hídrica y el caudal ecológico de la cuenca."),
        DataGap(dataset="Topografía, geología y sedimentos", impact="El salto sale de modelos de 30 m; la conducción, el desarenador y las crecidas de diseño no están evaluados.",
                next_action="Levantamiento topográfico, geotecnia de la conducción y estudio de sedimentos."),
        DataGap(dataset="Red eléctrica y subestaciones", impact="No se estima distancia ni capacidad de conexión.", next_action="Validar servicios oficiales de MINEM y COES."),
        DataGap(dataset="Restricciones ambientales y sociales", impact="Este módulo no cruza áreas protegidas, patrimonio ni comunidades.", next_action="Usar los módulos Ambiente y Territorio sobre la toma y la conducción."),
    ]


def _evaluation_and_finance_stages(results: list[HydroSiteResult], sensitivities: list[SubjectSensitivity], source_provenance: list[Provenance], finance_ms: float):
    ranked = sorted(results, key=lambda item: item.relative_position)
    evidence = [StageEvidence(label=f"{index + 1}.º {item.location.label}",
                              value=f"{item.finance.annual_energy_mwh:,.0f} MWh/año · {item.resource.capacity_mw:,.1f} MW · factor de planta {item.finance.plant_factor_net * 100:.0f} %")
                for index, item in enumerate(ranked)]
    evidence.append(StageEvidence(label="Criterio", value="Energía anual de una central de pasada: caudal GloFAS, salto NASADEM y supuestos del usuario"))
    summary = (f"Orden relativo por energía anual; de {ranked[-1].finance.annual_energy_mwh:,.0f} a {ranked[0].finance.annual_energy_mwh:,.0f} MWh." if len(ranked) > 1
               else f"Un aprovechamiento: {ranked[0].finance.annual_energy_mwh:,.0f} MWh al año.")
    evaluation = stage("evaluation", PipelineStatus.COMPLETED, summary, source_provenance + [Provenance.MODEL], evidence, answers=["so_what"])
    npvs = [item.finance.npv_usd for item in results]
    finance_evidence = [StageEvidence(label=item.location.label or "Sitio", value=f"USD {item.finance.npv_usd:,.0f} · CAPEX USD {item.finance.initial_capex_usd:,.0f}",
                                      provenance=Provenance.MODEL) for item in results]
    finance_evidence.append(StageEvidence(label="Fórmula", value="P = ρ·g·Q·H·η; energía = P × 8,760 h × factor de planta × disponibilidad; VAN a tasa del usuario"))
    adverse = [scenario_npv(item, "adverso") for item in sensitivities]
    finance_evidence += [StageEvidence(label=f"Adverso · {item.subject}", value=f"USD {value:,.0f}", provenance=Provenance.MODEL) for item, value in zip(sensitivities, adverse, strict=True)]
    finance_evidence += [StageEvidence(label=f"Factor dominante · {item.subject}", value=item.tornado[0].label, provenance=item.tornado[0].provenance) for item in sensitivities if item.tornado]
    finance = stage("finance", PipelineStatus.COMPLETED,
                    f"VAN positivo en {sum(1 for value in npvs if value >= 0)} de {len(npvs)} sitios con los supuestos del usuario "
                    f"y en {sum(1 for value in adverse if value >= 0)} de {len(adverse)} en el escenario adverso.",
                    [Provenance.MODEL, Provenance.ASSUMPTION], finance_evidence, finance_ms, ["so_what"])
    return evaluation, finance


def _elevations(terrain: TerrainResponse | None, fallback: list[TerrainCrosscheck | None], index: int) -> tuple[float | None, float | None]:
    """(NASADEM, Copernicus) del punto `index` de la lista toma/casa de máquinas."""
    if terrain is not None:
        site: TerrainSiteResult = terrain.sites[index]
        return site.metrics.elevation_m, site.crosscheck.elevation_m if site.crosscheck else None
    check = fallback[index] if fallback else None
    return None, check.elevation_m if check else None


async def run_hydro_screening(request: HydroScreeningRequest) -> HydroScreeningResponse:
    if request.start_date < FIRST_DAY:
        raise HydroSiteError(f"El caudal de GloFAS empieza el {FIRST_DAY.isoformat()}: use una fecha inicial igual o posterior.")
    timings = StageTimings()
    subjects = _subjects(request)
    intakes = [subject.representative_point for subject in subjects]
    terrain_points = _terrain_points(request)
    second_started = perf_counter()
    second_tasks = [_second_task(site) for site in request.sites]
    (datasets, power_ms), (terrain, terrain_error, timings.terrain_ms), (flows, flow_ms) = await asyncio.gather(
        extract_power(intakes, POWER_VARIABLES, request.start_date, request.end_date), extract_terrain(terrain_points), _flows(request),
    )
    seconds = await _second_flows(second_tasks, second_started)
    if terrain is not None and len(terrain.sites) != len(terrain_points):
        terrain, terrain_error = None, "NASADEM devolvió un número de puntos distinto del pedido."
    fallback = await _copernicus_only(terrain_points) if terrain is None else []
    timings.extraction_ms = max(power_ms, flow_ms)
    expected_days = (request.end_date - request.start_date).days + 1

    analysis_start = perf_counter()
    merged = [{**dataset, DISCHARGE: (series.observations, _discharge_source(series))} for dataset, series in zip(datasets, flows, strict=True)]
    summaries_by_site = analyze_subjects(merged, HYDRO_VARIABLES, expected_days)
    discharge_by_site = [next(item for item in summaries if item.variable == DISCHARGE) for summaries in summaries_by_site]
    # La tendencia solo se contrasta donde las dos fuentes hablan del mismo río; lo demás se declara como «no comparable».
    pairs = []
    for summary, second in zip(discharge_by_site, seconds, strict=True):
        common = _common_means(summary, second) if isinstance(second, RiverChoice) else None
        if common is not None and flow_verdict(common[2] / common[1] if common[1] > 0 else None) != "no_comparable":
            pairs.append((summary, second.annual))
    attach_annual_countercheck(pairs, GEOGLOWS_SOURCE)
    timings.analysis_ms = elapsed_ms(analysis_start)

    finance_start = perf_counter()
    a = request.assumptions
    heads, resources, checks = [], [], []
    error_by_label: dict[str, str] = {}
    second_errors: list[str] = []
    pending_labels: list[str] = []
    for index, (site, series, summary, second) in enumerate(zip(request.sites, flows, discharge_by_site, seconds, strict=True)):
        intake, powerhouse = _elevations(terrain, fallback, 2 * index), _elevations(terrain, fallback, 2 * index + 1)
        if terrain is not None:
            both = [terrain.sites[2 * index].provenance, terrain.sites[2 * index + 1].provenance]
            provenance = Provenance.CACHED if all(item == Provenance.CACHED for item in both) else Provenance.REAL
        else:
            provenance = Provenance.REAL
        head = build_head(site, intake, powerhouse, provenance)
        resource, site_flows = build_resource(site, series, head, a)
        check = build_flow_check(second, summary, resource, site_flows, a) if isinstance(second, RiverChoice) else None
        if second is None:
            pending_labels.append(site.label.strip())
            error_by_label[site.label.strip()] = GEOGLOWS_PENDING
        elif isinstance(second, str):
            error_by_label[site.label.strip()] = second
            second_errors.append(f"{site.label.strip()}: {second}")
        heads.append(head)
        resources.append(resource)
        checks.append(check)
    energies = [annual_energy_mwh(resource.capacity_mw, resource.plant_factor, a.availability) for resource in resources]
    ordered = sorted(range(len(resources)), key=lambda index: energies[index], reverse=True)
    positions = {index: position + 1 for position, index in enumerate(ordered)}
    site_results = [
        _site_result(site, summaries, head, resource, check, error_by_label.get(site.label.strip()), positions[index], len(request.sites), a)
        for index, (site, summaries, head, resource, check) in enumerate(zip(request.sites, summaries_by_site, heads, resources, checks, strict=True))
    ]
    sensitivities = [hydro_sensitivity(subject.label, result.resource, result.head, result.flow_check, a) for subject, result in zip(subjects, site_results, strict=True)]
    timings.finance_ms = elapsed_ms(finance_start)

    ranked = sorted(site_results, key=lambda item: item.relative_position)
    best, worst = ranked[0], ranked[-1]
    comparative = [
        f"{best.location.label} entregaría {'más energía' if len(ranked) > 1 else 'esta energía'}: {best.finance.annual_energy_mwh:,.0f} MWh al año con "
        f"{best.resource.capacity_mw:,.1f} MW y un factor de planta neto de {best.finance.plant_factor_net * 100:.0f} %.",
    ]
    if len(ranked) > 1:
        comparative.append(f"La energía anual va de {worst.finance.annual_energy_mwh:,.0f} a {best.finance.annual_energy_mwh:,.0f} MWh entre los aprovechamientos comparados.")
    comparative.append("La posición relativa usa el caudal de GloFAS, el salto de los modelos de elevación y una central de pasada con los supuestos del usuario; "
                       "no es una recomendación de inversión ni un estudio de factibilidad.")

    labelled = [SubjectSummaries(label=subject.label, summaries=summaries) for subject, summaries in zip(subjects, summaries_by_site, strict=True)]
    trend_findings = collect_trend_findings(labelled)
    gaps = _data_gaps(second_errors, pending_labels, terrain_error, heads)
    pending = sum(1 for gap in gaps if gap.status == Provenance.UNAVAILABLE)
    discoveries = variable_discoveries([(subject.label, summaries) for subject, summaries in zip(subjects, summaries_by_site, strict=True)]) \
        + hydro_discoveries(site_results)
    npvs = [result.finance.npv_usd for result in site_results]
    adverse = [scenario_npv(item, "adverso") for item in sensitivities]
    dominant = {item.tornado[0].label for item in sensitivities if item.tornado}
    lens = SectorLens(
        readings=HYDRO_READINGS, stable_notes=HYDRO_STABLE_NOTES,
        economics=(
            f"Con los supuestos del usuario, el VAN es positivo en {sum(1 for value in npvs if value >= 0)} de {len(npvs)} sitios "
            f"(de {millions_usd(min(npvs))} a {millions_usd(max(npvs))}); en el escenario adverso, en {sum(1 for value in adverse if value >= 0)} de {len(adverse)}. "
            + (f"El factor que más mueve el VAN es el {lower_first(next(iter(dominant)))}." if len(dominant) == 1
               else f"Los factores que más mueven el VAN son: {', '.join(lower_first(item) for item in sorted(dominant))}.")
        ),
        location_note="toma · caudal de la celda GloFAS de 5 km y clima de la celda NASA POWER; ninguno es una medición en sitio",
    )
    nasa_questions = answer_nasa_questions(
        labelled, trend_findings, {subject.label: (subject.representative_point.latitude, subject.representative_point.longitude) for subject in subjects},
        pending, lens,
    )

    source_provenance = unique([item.source.provenance for summaries in summaries_by_site for item in summaries])
    all_provenance = unique(source_provenance + [Provenance.MODEL, Provenance.ASSUMPTION] + ([Provenance.UNAVAILABLE] if pending else []))
    years_count = max(len(item.annual_series) for summaries in summaries_by_site for item in summaries)
    scorecard = hydro_scorecard(subjects, site_results, a)
    evaluation, finance = _evaluation_and_finance_stages(site_results, sensitivities, source_provenance, timings.finance_ms)
    leader = next((item for item in scorecard.subjects if item.subject == scorecard.leader), None)
    if leader and leader.score is not None:
        evaluation.evidence.append(StageEvidence(
            label="Puntaje multicriterio", provenance=Provenance.MODEL,
            value=(f"Empate práctico: {leader.subject} {leader.score:.0f}/100 por {scorecard.margin:.1f} punto(s), primero en {leader.first_place_share:.0%} de las combinaciones de pesos"
                   if scorecard.tie else
                   f"{leader.subject} {leader.score:.0f}/100 · primero en {leader.first_place_share:.0%} de {scorecard.stability_draws} combinaciones de pesos"),
        ))
    configuration = configuration_stage(SECTOR_LABEL, POWER_VARIABLES, request.start_date, request.end_date, years_count,
                                        f"excedencia {a.design_exceedance_percent:g} % · ecológico {a.ecological_flow_fraction:.0%} · tasa {a.discount_rate:.0%} · {a.horizon_years} años")
    configuration.evidence.insert(2, StageEvidence(label="Caudal", value="GloFAS v4 diario (Copernicus EMS) · segunda opinión: GEOGLOWS v2"))
    extraction_step = extraction_stage(labelled, timings.extraction_ms, provider="NASA POWER y GloFAS")
    for result in site_results:
        cell, check = result.resource.cell, result.flow_check
        extraction_step.evidence.append(StageEvidence(
            label=f"GloFAS · {result.location.label}", provenance=result.resource.provenance,
            value=f"celda {cell.latitude:.3f}, {cell.longitude:.3f} a {cell.distance_km:.1f} km de la toma{' (vecina)' if cell.moved else ''} · media {result.resource.mean_flow_m3s:,.1f} m³/s"))
        extraction_step.evidence.append(StageEvidence(
            label=f"GEOGLOWS · {result.location.label}", provenance=check.provenance if check else Provenance.UNAVAILABLE,
            value=f"río n.º {check.river_id} · media {check.mean_m3s:,.1f} m³/s · {check.verdict.replace('_', ' ')}" if check else "Sin respuesta"))
    pipeline = assemble_pipeline([
        selection_stage(subjects, max_separation_km(intakes)),
        configuration,
        extraction_step,
        analysis_stage(labelled, trend_findings, timings.analysis_ms),
        territorial_stage(terrain, terrain_error, gaps, timings.terrain_ms),
        evaluation,
        finance,
        results_stage(trend_findings, gaps, all_provenance),
        export_stage(all_provenance),
    ])
    record_in_pipeline(pipeline, discoveries)
    fingerprint = hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:16]
    return HydroScreeningResponse(
        analysis_id=fingerprint, generated_at=datetime.now(timezone.utc), title="Screening hidroeléctrico comparativo",
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}", subjects=subjects, pipeline=pipeline,
        nasa_questions=nasa_questions, trend_findings=trend_findings, sites=site_results, terrain=terrain, comparative_findings=comparative,
        data_gaps=gaps, assumptions=a,
        assumption_items=[AssumptionItem(key=key, label=label, value=float(getattr(a, key)), unit=unit) for key, (label, unit) in ASSUMPTION_LABELS.items()],
        financial_sensitivity=sensitivities, scorecard=scorecard, discoveries=discoveries, method_validation=METHOD_VALIDATION,
        disclaimer="Screening preliminar basado en modelos globales de caudal, modelos de elevación y supuestos del usuario. No sustituye el aforo, "
                   "la disponibilidad hídrica de la ANA, la topografía, la geología, el estudio de conexión, el impacto ambiental ni la factibilidad financiera.",
    )
