"""Piloto solar: screening comparativo de sitios sobre el contrato común C2."""

import asyncio
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from time import perf_counter

import numpy as np

from ..finance.engine import calculate_npv
from ..finance.sensitivity import Driver, break_even_item, tornado
from ..orchestration.analysis import analyze_subjects
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
from ..schemas.analysis import FinanceRequest, Provenance
from ..schemas.pipeline import (
    DataGap,
    SolarAssumptions,
    SolarFinancialProjection,
    SolarScreeningRequest,
    SolarScreeningResponse,
    SolarSiteResult,
    VariableSummary,
)
from ..schemas.screening import (
    AssumptionItem,
    FinanceScenario,
    PipelineStatus,
    StageEvidence,
    StudySubject,
    SubjectKind,
    SubjectSensitivity,
)
from ..schemas.terrain import TerrainResponse

SOLAR_VARIABLES = ["ALLSKY_SFC_SW_DWN", "T2M", "WS10M", "PRECTOTCORR"]
IRRADIANCE = "ALLSKY_SFC_SW_DWN"
SECTOR_LABEL = "Solar fotovoltaico"

# Lecturas sectoriales por variable y dirección: explican consecuencias, no las cuantifican.
SOLAR_READINGS: dict[tuple[str, str], str] = {
    (IRRADIANCE, "decreasing"): "la irradiancia cae: la media histórica sobrestima el recurso futuro y el VAN debe sensibilizarse a la baja",
    (IRRADIANCE, "increasing"): "la irradiancia sube: la media histórica es conservadora para el recurso",
    ("T2M", "increasing"): "la temperatura sube: aumentan las pérdidas térmicas de los módulos, que el cálculo de energía actual no modela",
    ("T2M", "decreasing"): "la temperatura baja: reduce pérdidas térmicas de los módulos, que el cálculo de energía actual no modela",
    ("WS10M", "decreasing"): "el viento a 10 m disminuye: menor enfriamiento convectivo de los módulos",
    ("WS10M", "increasing"): "el viento a 10 m aumenta: revisar cargas de diseño de estructuras",
    ("PRECTOTCORR", "increasing"): "la precipitación aumenta: revisar drenaje y exposición hidrometeorológica",
    ("PRECTOTCORR", "decreasing"): "la precipitación disminuye: más ensuciamiento de módulos y menos limpieza natural",
}
SOLAR_STABLE_NOTES = {
    IRRADIANCE: "El recurso solar no muestra deriva significativa en ningún sitio: no hay evidencia para castigar la media histórica por tendencia, lo que no prueba que sea constante.",
}
ASSUMPTION_LABELS = {
    "capacity_mw": ("Capacidad", "MW"), "performance_ratio": ("Performance ratio", ""), "initial_capex_usd": ("CAPEX inicial", "USD"),
    "annual_opex_usd": ("OPEX anual", "USD/año"), "energy_price_usd_mwh": ("Precio de energía", "USD/MWh"),
    "mitigation_capex_usd": ("CAPEX de mitigación", "USD"), "discount_rate": ("Tasa de descuento", "fracción"), "horizon_years": ("Horizonte", "años"),
    "price_sensitivity": ("Rango del precio (±)", "fracción"), "capex_sensitivity": ("Rango del CAPEX (±)", "fracción"),
    "opex_sensitivity": ("Rango del OPEX (±)", "fracción"), "performance_ratio_sensitivity": ("Rango del performance ratio (±)", "puntos"),
    "discount_rate_sensitivity": ("Rango de la tasa (±)", "puntos"),
}
# Percentiles de las medias anuales observadas que definen el año de recurso bajo y alto.
RESOURCE_LOW_PERCENTILE, RESOURCE_HIGH_PERCENTILE = 10, 90
BREAK_EVEN_SPAN = 20  # el equilibrio se busca entre 0 y 20 veces el supuesto
# Los escenarios mueven recurso y factores comerciales; performance ratio y tasa solo aparecen en el tornado.
ADVERSE_KEYS = {"irradiance", "energy_price_usd_mwh", "initial_capex_usd", "annual_opex_usd"}


def solar_npv(inputs: Mapping[str, float], assumptions: SolarAssumptions) -> float:
    """VAN solar con factores sobrescritos; reutiliza la proyección para no duplicar fórmulas."""
    updated = assumptions.model_copy(update={key: value for key, value in inputs.items() if key != "irradiance"})
    return calculate_solar_projection(inputs["irradiance"], updated).npv_usd


def _resource_range(solar: VariableSummary) -> tuple[float, float, str] | None:
    values = [item.value for item in solar.annual_series]
    if len(values) < 5:
        return None
    low, high = (float(np.percentile(values, q)) for q in (RESOURCE_LOW_PERCENTILE, RESOURCE_HIGH_PERCENTILE))
    first, last = solar.annual_series[0].year, solar.annual_series[-1].year
    return low, high, f"Percentiles {RESOURCE_LOW_PERCENTILE} y {RESOURCE_HIGH_PERCENTILE} de {len(values)} medias anuales observadas ({first}–{last}), NASA POWER."


def solar_sensitivity(label: str, solar: VariableSummary, assumptions: SolarAssumptions) -> SubjectSensitivity:
    a = assumptions
    base = {"irradiance": solar.mean, "energy_price_usd_mwh": a.energy_price_usd_mwh, "initial_capex_usd": a.initial_capex_usd,
            "annual_opex_usd": a.annual_opex_usd, "performance_ratio": a.performance_ratio, "discount_rate": a.discount_rate}

    def model(inputs: Mapping[str, float]) -> float:
        return solar_npv(inputs, a)

    user = "Supuesto del usuario"
    drivers = [
        Driver("energy_price_usd_mwh", "Precio de energía", "USD/MWh", a.energy_price_usd_mwh * (1 - a.price_sensitivity),
               a.energy_price_usd_mwh * (1 + a.price_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.price_sensitivity:.0%}."),
        Driver("initial_capex_usd", "CAPEX inicial", "USD", a.initial_capex_usd * (1 + a.capex_sensitivity),
               a.initial_capex_usd * (1 - a.capex_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.capex_sensitivity:.0%}."),
        Driver("annual_opex_usd", "OPEX anual", "USD/año", a.annual_opex_usd * (1 + a.opex_sensitivity),
               a.annual_opex_usd * (1 - a.opex_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.opex_sensitivity:.0%}."),
        Driver("performance_ratio", "Performance ratio", "", max(0.01, a.performance_ratio - a.performance_ratio_sensitivity),
               min(1.0, a.performance_ratio + a.performance_ratio_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.performance_ratio_sensitivity:.2f}."),
        Driver("discount_rate", "Tasa de descuento", "fracción", a.discount_rate + a.discount_rate_sensitivity,
               max(0.0, a.discount_rate - a.discount_rate_sensitivity), Provenance.ASSUMPTION, f"{user}: ±{a.discount_rate_sensitivity * 100:.1f} puntos."),
    ]
    resource = _resource_range(solar)
    if resource:
        low, high, basis = resource
        drivers.insert(0, Driver("irradiance", "Recurso solar (año bajo / alto)", solar.display_unit, low, high, Provenance.MODEL, basis))
    # Cada Driver va del lado desfavorable (low) al favorable (high), así el tornado y los escenarios leen igual.
    adverse = {driver.key: driver.low for driver in drivers if driver.key in ADVERSE_KEYS}
    favorable = {driver.key: driver.high for driver in drivers if driver.key in ADVERSE_KEYS}
    moved = [driver for driver in drivers if driver.key in ADVERSE_KEYS]
    scenarios = [
        FinanceScenario(key="base", label="Base", npv=round(model(base), 2), changes=["Todos los supuestos en su valor declarado; recurso = media observada."]),
        FinanceScenario(key="adverso", label="Adverso", npv=round(model({**base, **adverse}), 2),
                        changes=[f"{driver.label}: {_fmt(driver.low, driver.unit)}" for driver in moved]),
        FinanceScenario(key="favorable", label="Favorable", npv=round(model({**base, **favorable}), 2),
                        changes=[f"{driver.label}: {_fmt(driver.high, driver.unit)}" for driver in moved]),
    ]
    observed = [item.value for item in solar.annual_series]
    break_evens = [
        break_even_item(model, base, "energy_price_usd_mwh", "Precio de equilibrio", "USD/MWh", 0.0, BREAK_EVEN_SPAN * max(a.energy_price_usd_mwh, 1.0),
                        lambda value: _break_even_note(value, base["energy_price_usd_mwh"], "USD/MWh", "precio mínimo", higher_is_better=True)),
        break_even_item(model, base, "initial_capex_usd", "CAPEX máximo", "USD", 1.0, BREAK_EVEN_SPAN * a.initial_capex_usd,
                        lambda value: _break_even_note(value, base["initial_capex_usd"], "USD", "CAPEX máximo", higher_is_better=False)),
        break_even_item(model, base, "irradiance", "Irradiancia de equilibrio", solar.display_unit, 0.0, BREAK_EVEN_SPAN * solar.mean,
                        lambda value: _irradiance_note(value, observed, solar.display_unit)),
    ]
    return SubjectSensitivity(subject=label, base_npv=scenarios[0].npv, scenarios=scenarios, tornado=tornado(model, base, drivers), break_evens=break_evens)


def _fmt(value: float, unit: str) -> str:
    if unit == "USD" or unit == "USD/año":
        amount = f"USD {value / 1e6:,.2f} M" if abs(value) >= 1e6 else f"USD {value:,.0f}"
        return amount + ("/año" if unit == "USD/año" else "")
    if unit == "fracción":
        return f"{value * 100:.1f} %"
    return f"{value:,.2f} {unit}".strip()


def _break_even_note(value: float | None, assumed: float, unit: str, name: str, *, higher_is_better: bool) -> str:
    if value is None:
        return f"El VAN no cruza cero entre 0 y {BREAK_EVEN_SPAN} veces el supuesto."
    if value == 0:
        return f"El VAN es positivo incluso con {name} cero."
    margin = (assumed - value) / value
    position = "por encima" if margin >= 0 else "por debajo"
    reading = "holgura" if (margin >= 0) == higher_is_better else "déficit"
    return f"{name[:1].upper() + name[1:]} para VAN ≥ 0: {_fmt(value, unit)}; el supuesto está {abs(margin) * 100:.0f} % {position} ({reading})."


def _irradiance_note(value: float | None, observed: list[float], unit: str) -> str:
    if value is None:
        return "El VAN no cruza cero en el rango de irradiancia buscado."
    if not observed:
        return f"Irradiancia mínima para VAN ≥ 0: {value:.2f} {unit}."
    best = max(observed)
    reach = "ningún año observado la alcanza" if value > best else f"{sum(1 for item in observed if item >= value)} de {len(observed)} años observados la superan"
    return f"Irradiancia mínima para VAN ≥ 0: {value:.2f} {unit}; {reach} (mejor año: {best:.2f})."


def calculate_solar_projection(mean_irradiance: float, assumptions: SolarAssumptions) -> SolarFinancialProjection:
    specific_yield = mean_irradiance * 365 * assumptions.performance_ratio
    annual_energy = assumptions.capacity_mw * specific_yield
    annual_revenue = annual_energy * assumptions.energy_price_usd_mwh
    npv_result = calculate_npv(
        FinanceRequest(
            initial_capex=assumptions.initial_capex_usd,
            annual_revenue=annual_revenue,
            annual_opex=assumptions.annual_opex_usd,
            mitigation_capex=assumptions.mitigation_capex_usd,
            annual_interruption_cost=0,
            discount_rate=assumptions.discount_rate,
            horizon_years=assumptions.horizon_years,
        )
    )
    return SolarFinancialProjection(
        specific_yield_kwh_kwp_year=round(specific_yield, 2),
        annual_energy_mwh=round(annual_energy, 2),
        annual_revenue_usd=round(annual_revenue, 2),
        npv_usd=npv_result.npv,
        cash_flows_usd=npv_result.cash_flows,
        formula="Energía anual = capacidad MW × irradiancia media diaria × 365 × performance ratio.",
        limitations=[
            "Estimación preliminar sin modelo de temperatura de módulo, pérdidas eléctricas detalladas, degradación ni disponibilidad.",
            "El precio, CAPEX, OPEX, performance ratio, tasa y horizonte son supuestos del usuario.",
            "No se cuantifican interrupciones ni mitigaciones sin datos territoriales y de ingeniería.",
        ],
    )


def _data_gaps(terrain: TerrainResponse | None) -> list[DataGap]:
    gaps = []
    if terrain is not None and any(site.status == "PENDING" for site in terrain.sites):
        gaps.append(DataGap(dataset="Métricas raster NASADEM", impact="Las teselas de algunos sitios se están descargando; elevación, pendiente y orientación aún no están disponibles para ellos.", next_action="Volver a ejecutar el análisis cuando termine la descarga en segundo plano."))
    elif terrain is None or any(site.status != "READY" for site in terrain.sites):
        gaps.append(DataGap(dataset="Métricas raster NASADEM", impact="No se calcularon elevación, pendiente ni orientación para todos los sitios (token ausente o descarga no completada).", next_action="Verificar EARTHDATA_TOKEN y completar la descarga de NASADEM_HGT.001 y NASADEM_SC.001."))
    return gaps + [
        DataGap(dataset="Red eléctrica y subestaciones", impact="No se estima distancia ni capacidad de conexión.", next_action="Validar servicios oficiales de MINEM y COES."),
        DataGap(dataset="Áreas protegidas y restricciones ambientales", impact="No se emite una conclusión de compatibilidad ambiental.", next_action="Integrar fuentes oficiales con licencia y fecha de actualización."),
        DataGap(dataset="Patrimonio, comunidades y conflictos", impact="No se descartan restricciones sociales o arqueológicas.", next_action="Validar fuentes del Ministerio de Cultura, Defensoría y SENACE."),
        DataGap(dataset="GPM IMERG V07", impact="La precipitación proviene de POWER; IMERG todavía no se usa como producto especializado.", next_action="Configurar Earthdata y verificar producto, unidad y versión."),
    ]


def _subjects(request: SolarScreeningRequest) -> list[StudySubject]:
    return [
        StudySubject(
            id=f"sitio-{index + 1}", label=site.label or f"Sitio {index + 1}", kind=SubjectKind.POINT,
            geometry={"type": "Point", "coordinates": [site.longitude, site.latitude]}, representative_point=site,
        )
        for index, site in enumerate(request.sites)
    ]


def _assumption_items(assumptions: SolarAssumptions) -> list[AssumptionItem]:
    return [AssumptionItem(key=key, label=label, value=float(getattr(assumptions, key)), unit=unit) for key, (label, unit) in ASSUMPTION_LABELS.items()]


def _site_result(site, summaries, position: int, total: int, assumptions: SolarAssumptions) -> SolarSiteResult:
    solar = next(item for item in summaries if item.variable == IRRADIANCE)
    opportunities = [
        f"Irradiancia histórica media de {solar.mean:.2f} {solar.display_unit} con {solar.completeness_percent:.1f}% de cobertura diaria.",
        f"Posición {position} de {total} entre las ubicaciones comparadas por irradiancia media.",
    ]
    if solar.significant_after_bh and solar.trend.direction == "increasing":
        opportunities.append("La tendencia de irradiancia es creciente y conserva significancia después del ajuste BH.")
    cautions = [
        "NASA POWER representa una estimación en grilla y no sustituye mediciones en sitio.",
        "El análisis no incluye conexión eléctrica, predios ni restricciones ambientales o sociales.",
    ]
    if solar.significant_after_bh and solar.trend.direction == "decreasing":
        cautions.append("La irradiancia presenta una tendencia decreciente significativa después del ajuste BH.")
    elif not solar.significant_after_bh:
        cautions.append("No existe evidencia suficiente de una tendencia de irradiancia significativa después del ajuste BH.")
    return SolarSiteResult(
        location=site, relative_solar_position=position, relative_position_text=f"{position} de {total} por irradiancia histórica media",
        variables=summaries, finance=calculate_solar_projection(solar.mean, assumptions), opportunities=opportunities, cautions=cautions,
    )


def _lower_first(text: str) -> str:
    """Minúscula inicial para usar una etiqueta dentro de una frase, salvo siglas (CAPEX, OPEX)."""
    return text if text[:2].isupper() else text[:1].lower() + text[1:]


def _scenario(sensitivity: SubjectSensitivity, key: str) -> float:
    return next(item.npv for item in sensitivity.scenarios if item.key == key)


def _evaluation_and_finance_stages(results: list[SolarSiteResult], sensitivities: list[SubjectSensitivity], source_provenance: list[Provenance], finance_ms: float):
    ranked = sorted(results, key=lambda item: item.relative_solar_position)
    irradiance = [next(v for v in item.variables if v.variable == IRRADIANCE) for item in ranked]
    unit = irradiance[0].display_unit
    delta = irradiance[0].mean - irradiance[-1].mean
    evaluation_evidence = [StageEvidence(label=f"{index + 1}.º {item.location.label}", value=f"{solar.mean:.3f} {unit}") for index, (item, solar) in enumerate(zip(ranked, irradiance, strict=True))]
    evaluation_evidence.append(StageEvidence(label="Criterio", value="Irradiancia histórica media; sin score compuesto"))
    evaluation = stage("evaluation", PipelineStatus.COMPLETED, f"Orden relativo por irradiancia; diferencia entre extremos de {delta:.3f} {unit}.",
                       source_provenance + [Provenance.MODEL], evaluation_evidence, answers=["so_what"])
    npvs = [item.finance.npv_usd for item in results]
    finance_evidence = [StageEvidence(label=item.location.label or "Sitio", value=f"USD {item.finance.npv_usd:,.0f} · {item.finance.annual_energy_mwh:,.0f} MWh/año", provenance=Provenance.MODEL) for item in results]
    finance_evidence.append(StageEvidence(label="Fórmula", value="Energía = MW × irradiancia × 365 × PR; VAN a tasa del usuario"))
    adverse = [_scenario(item, "adverso") for item in sensitivities]
    finance_evidence += [StageEvidence(label=f"Adverso · {item.subject}", value=f"USD {value:,.0f}", provenance=Provenance.MODEL) for item, value in zip(sensitivities, adverse, strict=True)]
    finance_evidence += [StageEvidence(label=f"Factor dominante · {item.subject}", value=item.tornado[0].label, provenance=item.tornado[0].provenance) for item in sensitivities if item.tornado]
    finance = stage("finance", PipelineStatus.COMPLETED,
                    f"VAN positivo en {sum(1 for value in npvs if value >= 0)} de {len(npvs)} sitios con los supuestos del usuario "
                    f"y en {sum(1 for value in adverse if value >= 0)} de {len(adverse)} en el escenario adverso.",
                    [Provenance.MODEL, Provenance.ASSUMPTION], finance_evidence, finance_ms, ["so_what"])
    return evaluation, finance


async def run_solar_screening(request: SolarScreeningRequest) -> SolarScreeningResponse:
    timings = StageTimings()
    subjects = _subjects(request)
    points = [subject.representative_point for subject in subjects]
    (datasets, timings.extraction_ms), (terrain, terrain_error, timings.terrain_ms) = await asyncio.gather(
        extract_power(points, SOLAR_VARIABLES, request.start_date, request.end_date), extract_terrain(points)
    )
    expected_days = (request.end_date - request.start_date).days + 1

    analysis_start = perf_counter()
    summaries_by_site = analyze_subjects(datasets, SOLAR_VARIABLES, expected_days)
    timings.analysis_ms = elapsed_ms(analysis_start)

    irradiance_means = [next(item for item in summaries if item.variable == IRRADIANCE).mean for summaries in summaries_by_site]
    ordered = sorted(range(len(irradiance_means)), key=lambda index: irradiance_means[index], reverse=True)
    positions = {index: position + 1 for position, index in enumerate(ordered)}
    finance_start = perf_counter()
    site_results = [
        _site_result(site, summaries, positions[index], len(request.sites), request.assumptions)
        for index, (site, summaries) in enumerate(zip(request.sites, summaries_by_site, strict=True))
    ]
    sensitivities = [
        solar_sensitivity(subject.label, next(item for item in result.variables if item.variable == IRRADIANCE), request.assumptions)
        for subject, result in zip(subjects, site_results, strict=True)
    ]
    timings.finance_ms = elapsed_ms(finance_start)

    ranked = sorted(site_results, key=lambda item: item.relative_solar_position)
    best_solar = next(item for item in ranked[0].variables if item.variable == IRRADIANCE)
    worst_solar = next(item for item in ranked[-1].variables if item.variable == IRRADIANCE)
    delta = best_solar.mean - worst_solar.mean
    delta_percent = delta / worst_solar.mean * 100 if worst_solar.mean else 0
    comparative = [
        f"{ranked[0].location.label or 'La primera ubicación'} registra la mayor irradiancia media: {best_solar.mean:.2f} {best_solar.display_unit}.",
        f"La diferencia entre la mayor y menor irradiancia media es {delta:.2f} {best_solar.display_unit} ({delta_percent:.1f}%).",
        "La posición relativa considera únicamente irradiancia histórica; no es una recomendación de inversión ni un score de factibilidad.",
    ]

    labelled = [SubjectSummaries(label=subject.label, summaries=summaries) for subject, summaries in zip(subjects, summaries_by_site, strict=True)]
    trend_findings = collect_trend_findings(labelled)
    gaps = _data_gaps(terrain)
    pending = sum(1 for gap in gaps if gap.status == Provenance.UNAVAILABLE)
    npvs = [result.finance.npv_usd for result in site_results]
    adverse = [_scenario(item, "adverso") for item in sensitivities]
    dominant = {item.tornado[0].label for item in sensitivities if item.tornado}
    lens = SectorLens(
        readings=SOLAR_READINGS,
        stable_notes=SOLAR_STABLE_NOTES,
        economics=(
            f"Con los supuestos del usuario, el VAN es positivo en {sum(1 for value in npvs if value >= 0)} de {len(npvs)} sitios "
            f"(de {millions_usd(min(npvs))} a {millions_usd(max(npvs))}); en el escenario adverso, en {sum(1 for value in adverse if value >= 0)} de {len(adverse)}. "
            + (f"El factor que más mueve el VAN es el {_lower_first(next(iter(dominant)))}." if len(dominant) == 1
               else f"Los factores que más mueven el VAN son: {', '.join(_lower_first(item) for item in sorted(dominant))}.")
        ),
    )
    nasa_questions = answer_nasa_questions(
        labelled, trend_findings,
        {subject.label: (subject.representative_point.latitude, subject.representative_point.longitude) for subject in subjects},
        pending, lens,
    )

    source_provenance = unique([item.source.provenance for summaries in summaries_by_site for item in summaries])
    all_provenance = unique(source_provenance + [Provenance.MODEL, Provenance.ASSUMPTION] + ([Provenance.UNAVAILABLE] if pending else []))
    years = max(len(item.annual_series) for summaries in summaries_by_site for item in summaries)
    a = request.assumptions
    evaluation, finance = _evaluation_and_finance_stages(site_results, sensitivities, source_provenance, timings.finance_ms)
    pipeline = assemble_pipeline([
        selection_stage(subjects, max_separation_km(points)),
        configuration_stage(SECTOR_LABEL, SOLAR_VARIABLES, request.start_date, request.end_date, years,
                            f"{a.capacity_mw:g} MW · tasa {a.discount_rate:.0%} · {a.horizon_years} años"),
        extraction_stage(labelled, timings.extraction_ms),
        analysis_stage(labelled, trend_findings, timings.analysis_ms),
        territorial_stage(terrain, terrain_error, gaps, timings.terrain_ms),
        evaluation,
        finance,
        results_stage(trend_findings, gaps, all_provenance),
        export_stage(all_provenance),
    ])
    fingerprint = hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:16]
    return SolarScreeningResponse(
        analysis_id=fingerprint,
        generated_at=datetime.now(timezone.utc),
        title="Screening solar comparativo — sur del Perú",
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}",
        subjects=subjects,
        pipeline=pipeline,
        nasa_questions=nasa_questions,
        trend_findings=trend_findings,
        sites=site_results,
        terrain=terrain,
        comparative_findings=comparative,
        data_gaps=gaps,
        assumptions=request.assumptions,
        assumption_items=_assumption_items(request.assumptions),
        financial_sensitivity=sensitivities,
        disclaimer="Screening preliminar basado en datos NASA y supuestos del usuario. No sustituye estudios de recurso, conexión, ingeniería, impacto ambiental, patrimonio, debida diligencia legal ni factibilidad financiera.",
    )
