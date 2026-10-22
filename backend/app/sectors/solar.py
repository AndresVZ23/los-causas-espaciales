import asyncio
import hashlib
import json
from datetime import datetime, timezone
from itertools import combinations
from statistics import fmean, pstdev
from time import perf_counter

from ..connectors.nasa.nasadem import NasademConnector, NasademConnectorError
from ..connectors.nasa.power import PowerConnector, PowerConnectorError
from ..core.units import display_unit
from ..finance.engine import calculate_npv
from ..geospatial.geometry import GEOD
from ..orchestration.nasa_questions import SiteSummaries, answer_nasa_questions, collect_trend_findings
from ..orchestration.stages import StageTimings, build_solar_pipeline
from ..schemas.analysis import FinanceRequest, Point, Provenance
from ..schemas.pipeline import (
    AnnualObservation,
    DataGap,
    SolarAssumptions,
    SolarFinancialProjection,
    SolarScreeningRequest,
    SolarScreeningResponse,
    SolarSiteResult,
    VariableSummary,
)
from ..schemas.terrain import TerrainResponse
from ..statistics.multiple_testing import benjamini_hochberg
from ..statistics.trends import analyze_trend, annual_means

TERRAIN_TIMEOUT_SECONDS = 45

SOLAR_VARIABLES = ["ALLSKY_SFC_SW_DWN", "T2M", "WS10M", "PRECTOTCORR"]
VARIABLE_LABELS = {
    "ALLSKY_SFC_SW_DWN": "Irradiancia solar superficial",
    "T2M": "Temperatura del aire a 2 m",
    "WS10M": "Velocidad del viento a 10 m",
    "PRECTOTCORR": "Precipitación corregida",
}


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


def _summary(variable: str, observations, source, expected_days: int) -> VariableSummary:
    if not observations:
        raise PowerConnectorError(f"NASA POWER no devolvió observaciones válidas para {variable}.")
    values = [observation.value for observation in observations]
    annual_observations = annual_means(observations)
    annual_values = [observation.value for observation in annual_observations]
    annual_variability = None
    if len(annual_values) >= 2 and abs(fmean(annual_values)) > 1e-12:
        annual_variability = pstdev(annual_values) / abs(fmean(annual_values)) * 100
    return VariableSummary(
        variable=variable,
        label=VARIABLE_LABELS[variable],
        mean=fmean(values),
        minimum=min(values),
        maximum=max(values),
        unit=source.unit,
        display_unit=display_unit(source.unit),
        valid_observations=len(values),
        completeness_percent=round(len(values) / expected_days * 100, 2),
        annual_variability_percent=round(annual_variability, 3) if annual_variability is not None else None,
        trend=analyze_trend(observations),
        source=source,
        annual_series=[
            AnnualObservation(year=observation.timestamp.year, value=round(observation.value, 6))
            for observation in annual_observations
        ],
    )


def _data_gaps(terrain: TerrainResponse | None) -> list[DataGap]:
    gaps = []
    if terrain is None or any(site.status != "READY" for site in terrain.sites):
        gaps.append(DataGap(dataset="Métricas raster NASADEM", impact="El catálogo y las vistas previas están conectados; sin Earthdata Login no se calculan elevación, pendiente ni orientación.", next_action="Configurar EARTHDATA_TOKEN y validar las celdas de NASADEM_HGT.001 y NASADEM_SC.001."))
    return gaps + [
        DataGap(dataset="Red eléctrica y subestaciones", impact="No se estima distancia ni capacidad de conexión.", next_action="Validar servicios oficiales de MINEM y COES."),
        DataGap(dataset="Áreas protegidas y restricciones ambientales", impact="No se emite una conclusión de compatibilidad ambiental.", next_action="Integrar fuentes oficiales con licencia y fecha de actualización."),
        DataGap(dataset="Patrimonio, comunidades y conflictos", impact="No se descartan restricciones sociales o arqueológicas.", next_action="Validar fuentes del Ministerio de Cultura, Defensoría y SENACE."),
        DataGap(dataset="GPM IMERG V07", impact="La precipitación proviene de POWER; IMERG todavía no se usa como producto especializado.", next_action="Configurar Earthdata y verificar producto, unidad y versión."),
    ]


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 1)


async def _extract_power(request: SolarScreeningRequest):
    connector = PowerConnector()
    start = perf_counter()
    datasets = await asyncio.gather(*(
        connector.daily_point_multi(site.latitude, site.longitude, SOLAR_VARIABLES, request.start_date, request.end_date)
        for site in request.sites
    ))
    return datasets, _elapsed_ms(start)


async def _extract_terrain(sites: list[Point]) -> tuple[TerrainResponse | None, str | None, float]:
    """NASADEM enriquece la etapa territorial; su fallo se declara y no invalida el análisis solar."""
    start = perf_counter()
    try:
        terrain = await asyncio.wait_for(NasademConnector().points(sites), timeout=TERRAIN_TIMEOUT_SECONDS)
        return terrain, None, _elapsed_ms(start)
    except NasademConnectorError as exc:
        return None, str(exc), _elapsed_ms(start)
    except TimeoutError:
        return None, f"NASA CMR no respondió en {TERRAIN_TIMEOUT_SECONDS} s.", _elapsed_ms(start)


def _max_separation_km(sites: list[Point]) -> float | None:
    distances = [GEOD.inv(a.longitude, a.latitude, b.longitude, b.latitude)[2] / 1000 for a, b in combinations(sites, 2)]
    return max(distances) if distances else None


async def run_solar_screening(request: SolarScreeningRequest) -> SolarScreeningResponse:
    timings = StageTimings()
    (datasets_by_site, timings.extraction_ms), (terrain, terrain_error, timings.terrain_ms) = await asyncio.gather(
        _extract_power(request), _extract_terrain(request.sites)
    )
    expected_days = (request.end_date - request.start_date).days + 1

    analysis_start = perf_counter()
    summaries_by_site: list[list[VariableSummary]] = []
    for datasets in datasets_by_site:
        summaries_by_site.append([
            _summary(variable, *datasets[variable], expected_days)
            for variable in SOLAR_VARIABLES
        ])

    for variable in SOLAR_VARIABLES:
        summaries = [next(item for item in site if item.variable == variable) for site in summaries_by_site]
        adjusted = benjamini_hochberg([item.trend.p_value for item in summaries])
        for item, adjusted_p in zip(summaries, adjusted, strict=True):
            item.adjusted_p_value = adjusted_p
            item.significant_after_bh = adjusted_p is not None and adjusted_p < item.trend.alpha
    timings.analysis_ms = _elapsed_ms(analysis_start)

    irradiance_means = [next(item for item in summaries if item.variable == "ALLSKY_SFC_SW_DWN").mean for summaries in summaries_by_site]
    ordered_indexes = sorted(range(len(irradiance_means)), key=lambda index: irradiance_means[index], reverse=True)
    positions = {index: position + 1 for position, index in enumerate(ordered_indexes)}
    site_results = []
    finance_start = perf_counter()
    for index, (site, summaries) in enumerate(zip(request.sites, summaries_by_site, strict=True)):
        solar = next(item for item in summaries if item.variable == "ALLSKY_SFC_SW_DWN")
        opportunities = [
            f"Irradiancia histórica media de {solar.mean:.2f} {solar.display_unit} con {solar.completeness_percent:.1f}% de cobertura diaria.",
            f"Posición {positions[index]} de {len(request.sites)} entre las ubicaciones comparadas por irradiancia media.",
        ]
        if solar.significant_after_bh and solar.trend.direction == "increasing":
            opportunities.append("La tendencia de irradiancia es creciente y conserva significancia después del ajuste BH.")
        cautions = [
            "NASA POWER representa una estimación en grilla y no sustituye mediciones en sitio.",
            "El análisis no incluye conexión eléctrica, topografía, predios ni restricciones ambientales o sociales.",
        ]
        if solar.significant_after_bh and solar.trend.direction == "decreasing":
            cautions.append("La irradiancia presenta una tendencia decreciente significativa después del ajuste BH.")
        elif not solar.significant_after_bh:
            cautions.append("No existe evidencia suficiente de una tendencia de irradiancia significativa después del ajuste BH.")
        site_results.append(
            SolarSiteResult(
                location=site,
                relative_solar_position=positions[index],
                relative_position_text=f"{positions[index]} de {len(request.sites)} por irradiancia histórica media",
                variables=summaries,
                finance=calculate_solar_projection(solar.mean, request.assumptions),
                opportunities=opportunities,
                cautions=cautions,
            )
        )

    timings.finance_ms = _elapsed_ms(finance_start)

    ranked = sorted(site_results, key=lambda item: item.relative_solar_position)
    best = ranked[0]
    worst = ranked[-1]
    best_solar = next(item for item in best.variables if item.variable == "ALLSKY_SFC_SW_DWN")
    worst_solar = next(item for item in worst.variables if item.variable == "ALLSKY_SFC_SW_DWN")
    delta = best_solar.mean - worst_solar.mean
    delta_percent = delta / worst_solar.mean * 100 if worst_solar.mean else 0
    findings = [
        f"{best.location.label or 'La primera ubicación'} registra la mayor irradiancia media: {best_solar.mean:.2f} {best_solar.display_unit}.",
        f"La diferencia entre la mayor y menor irradiancia media es {delta:.2f} {best_solar.display_unit} ({delta_percent:.1f}%).",
        "La posición relativa considera únicamente irradiancia histórica; no es una recomendación de inversión ni un score de factibilidad.",
    ]

    labelled = [
        SiteSummaries(label=site.label or f"Sitio {index + 1}", summaries=summaries)
        for index, (site, summaries) in enumerate(zip(request.sites, summaries_by_site, strict=True))
    ]
    trend_findings = collect_trend_findings(labelled)
    gaps = _data_gaps(terrain)
    nasa_questions = answer_nasa_questions(
        labelled,
        trend_findings,
        site_results,
        {item.label: (site.latitude, site.longitude) for item, site in zip(labelled, request.sites, strict=True)},
        pending_gaps=sum(1 for gap in gaps if gap.status == Provenance.UNAVAILABLE),
    )
    pipeline = build_solar_pipeline(
        request, labelled, site_results, trend_findings, terrain, terrain_error, gaps, _max_separation_km(request.sites), timings
    )
    fingerprint = hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:16]
    return SolarScreeningResponse(
        analysis_id=fingerprint,
        generated_at=datetime.now(timezone.utc),
        title="Screening solar comparativo — sur del Perú",
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}",
        pipeline=pipeline,
        nasa_questions=nasa_questions,
        trend_findings=trend_findings,
        sites=site_results,
        terrain=terrain,
        comparative_findings=findings,
        data_gaps=gaps,
        assumptions=request.assumptions,
        disclaimer="Screening preliminar basado en datos NASA y supuestos del usuario. No sustituye estudios de recurso, conexión, ingeniería, impacto ambiental, patrimonio, debida diligencia legal ni factibilidad financiera.",
    )
