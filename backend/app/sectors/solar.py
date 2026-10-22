import asyncio
import hashlib
import json
from datetime import datetime, timezone
from statistics import fmean, pstdev

from ..connectors.nasa.power import PowerConnector, PowerConnectorError
from ..finance.engine import calculate_npv
from ..schemas.analysis import FinanceRequest, Provenance
from ..schemas.pipeline import (
    AnnualObservation,
    DataGap,
    PipelineStage,
    PipelineStatus,
    SolarAssumptions,
    SolarFinancialProjection,
    SolarScreeningRequest,
    SolarScreeningResponse,
    SolarSiteResult,
    VariableSummary,
)
from ..statistics.multiple_testing import benjamini_hochberg
from ..statistics.trends import analyze_trend, annual_means

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


def _data_gaps() -> list[DataGap]:
    return [
        DataGap(dataset="Métricas raster NASADEM", impact="El catálogo y las vistas previas están conectados; sin Earthdata Login no se calculan elevación, pendiente ni orientación.", next_action="Configurar EARTHDATA_TOKEN y validar las celdas de NASADEM_HGT.001 y NASADEM_SC.001."),
        DataGap(dataset="Red eléctrica y subestaciones", impact="No se estima distancia ni capacidad de conexión.", next_action="Validar servicios oficiales de MINEM y COES."),
        DataGap(dataset="Áreas protegidas y restricciones ambientales", impact="No se emite una conclusión de compatibilidad ambiental.", next_action="Integrar fuentes oficiales con licencia y fecha de actualización."),
        DataGap(dataset="Patrimonio, comunidades y conflictos", impact="No se descartan restricciones sociales o arqueológicas.", next_action="Validar fuentes del Ministerio de Cultura, Defensoría y SENACE."),
        DataGap(dataset="GPM IMERG V07", impact="La precipitación proviene de POWER; IMERG todavía no se usa como producto especializado.", next_action="Configurar Earthdata y verificar producto, unidad y versión."),
    ]


async def run_solar_screening(request: SolarScreeningRequest) -> SolarScreeningResponse:
    connector = PowerConnector()
    tasks = [
        connector.daily_point_multi(site.latitude, site.longitude, SOLAR_VARIABLES, request.start_date, request.end_date)
        for site in request.sites
    ]
    datasets_by_site = await asyncio.gather(*tasks)
    expected_days = (request.end_date - request.start_date).days + 1

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

    irradiance_means = [next(item for item in summaries if item.variable == "ALLSKY_SFC_SW_DWN").mean for summaries in summaries_by_site]
    ordered_indexes = sorted(range(len(irradiance_means)), key=lambda index: irradiance_means[index], reverse=True)
    positions = {index: position + 1 for position, index in enumerate(ordered_indexes)}
    site_results = []
    for index, (site, summaries) in enumerate(zip(request.sites, summaries_by_site, strict=True)):
        solar = next(item for item in summaries if item.variable == "ALLSKY_SFC_SW_DWN")
        opportunities = [
            f"Irradiancia histórica media de {solar.mean:.2f} {solar.unit} con {solar.completeness_percent:.1f}% de cobertura diaria.",
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

    ranked = sorted(site_results, key=lambda item: item.relative_solar_position)
    best = ranked[0]
    worst = ranked[-1]
    best_solar = next(item for item in best.variables if item.variable == "ALLSKY_SFC_SW_DWN")
    worst_solar = next(item for item in worst.variables if item.variable == "ALLSKY_SFC_SW_DWN")
    delta = best_solar.mean - worst_solar.mean
    delta_percent = delta / worst_solar.mean * 100 if worst_solar.mean else 0
    findings = [
        f"{best.location.label or 'La primera ubicación'} registra la mayor irradiancia media: {best_solar.mean:.2f} {best_solar.unit}.",
        f"La diferencia entre la mayor y menor irradiancia media es {delta:.2f} {best_solar.unit} ({delta_percent:.1f}%).",
        "La posición relativa considera únicamente irradiancia histórica; no es una recomendación de inversión ni un score de factibilidad.",
    ]

    provenance = []
    for summaries in summaries_by_site:
        for item in summaries:
            if item.source.provenance not in provenance:
                provenance.append(item.source.provenance)
    fingerprint = hashlib.sha256(json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:16]
    pipeline = [
        PipelineStage(step=1, key="selection", name="Selección", status=PipelineStatus.COMPLETED, summary=f"{len(request.sites)} ubicaciones WGS84 validadas.", provenance=[Provenance.ASSUMPTION]),
        PipelineStage(step=2, key="configuration", name="Configuración", status=PipelineStatus.COMPLETED, summary="Sector solar, cuatro variables NASA, período y supuestos financieros definidos.", provenance=[Provenance.ASSUMPTION]),
        PipelineStage(step=3, key="extraction", name="Extracción", status=PipelineStatus.COMPLETED, summary="NASA POWER consultado con una solicitud multiparámetro por ubicación y caché de 24 horas.", provenance=provenance),
        PipelineStage(step=4, key="analysis", name="Análisis", status=PipelineStatus.COMPLETED, summary="Medias, variabilidad, Mann-Kendall, Sen, autocorrelación y ajuste BH calculados.", provenance=[Provenance.MODEL]),
        PipelineStage(step=5, key="territorial", name="Inteligencia territorial", status=PipelineStatus.PARTIAL, summary="Ubicaciones validadas; NASADEM se consulta por un flujo separado y la red, ambiente y restricciones oficiales siguen pendientes.", provenance=[Provenance.MODEL, Provenance.UNAVAILABLE]),
        PipelineStage(step=6, key="evaluation", name="Evaluación", status=PipelineStatus.COMPLETED, summary="Comparación relativa por evidencia observada, sin score arbitrario.", provenance=provenance + [Provenance.MODEL]),
        PipelineStage(step=7, key="finance", name="Impacto económico", status=PipelineStatus.COMPLETED, summary="Producción y VAN calculados con irradiancia NASA y supuestos explícitos del usuario.", provenance=[Provenance.MODEL, Provenance.ASSUMPTION]),
        PipelineStage(step=8, key="results", name="Resultados", status=PipelineStatus.COMPLETED, summary="Hallazgos, cautelas, brechas y próximos estudios reunidos en un resultado reproducible.", provenance=provenance + [Provenance.MODEL, Provenance.ASSUMPTION, Provenance.UNAVAILABLE]),
        PipelineStage(step=9, key="export", name="Exportación", status=PipelineStatus.COMPLETED, summary="El resultado estructurado puede descargarse como reporte JSON.", provenance=provenance + [Provenance.MODEL, Provenance.ASSUMPTION, Provenance.UNAVAILABLE]),
    ]
    return SolarScreeningResponse(
        analysis_id=fingerprint,
        generated_at=datetime.now(timezone.utc),
        title="Screening solar comparativo — sur del Perú",
        period=f"{request.start_date.isoformat()}/{request.end_date.isoformat()}",
        pipeline=pipeline,
        sites=site_results,
        comparative_findings=findings,
        data_gaps=_data_gaps(),
        assumptions=request.assumptions,
        disclaimer="Screening preliminar basado en datos NASA y supuestos del usuario. No sustituye estudios de recurso, conexión, ingeniería, impacto ambiental, patrimonio, debida diligencia legal ni factibilidad financiera.",
    )
