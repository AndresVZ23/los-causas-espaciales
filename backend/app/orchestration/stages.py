"""Construcción del pipeline de nueve etapas a partir de lo que realmente ocurrió en la ejecución.

Cada estado se deriva de hechos medidos (cobertura, procedencia, pruebas, capas disponibles); ninguna
etapa se declara completada por defecto.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from ..core.units import display_unit
from ..schemas.analysis import Provenance
from ..schemas.pipeline import (
    DataGap,
    PipelineStage,
    PipelineStatus,
    SolarScreeningRequest,
    SolarSiteResult,
    StageEvidence,
    TrendFinding,
)
from ..schemas.terrain import TerrainResponse
from .nasa_questions import SiteSummaries

COMPLETENESS_THRESHOLD = 95.0


@dataclass
class StageTimings:
    extraction_ms: float | None = None
    terrain_ms: float | None = None
    analysis_ms: float | None = None
    finance_ms: float | None = None
    extra: dict[str, float] = field(default_factory=dict)


def _unique(values: Sequence[Provenance]) -> list[Provenance]:
    return list(dict.fromkeys(values))


def _money(value: float) -> str:
    return f"USD {value:,.0f}"


def build_solar_pipeline(
    request: SolarScreeningRequest,
    sites: Sequence[SiteSummaries],
    results: Sequence[SolarSiteResult],
    findings: Sequence[TrendFinding],
    terrain: TerrainResponse | None,
    terrain_error: str | None,
    gaps: Sequence[DataGap],
    separation_km: float | None,
    timings: StageTimings,
) -> list[PipelineStage]:
    summaries = [item for site in sites for item in site.summaries]
    source_provenance = _unique([item.source.provenance for item in summaries])
    tests = len(summaries)
    years = max((len(item.annual_series) for item in summaries), default=0)

    selection_evidence = [StageEvidence(label=site.label or f"Sitio {index + 1}", value=f"{site.latitude:.3f}, {site.longitude:.3f}") for index, site in enumerate(request.sites)]
    if separation_km is not None:
        selection_evidence.append(StageEvidence(label="Separación geodésica", value=f"{separation_km:,.1f} km (WGS84)"))

    variables = list(dict.fromkeys(item.variable for item in summaries))
    configuration_evidence = [
        StageEvidence(label="Sector", value="Solar fotovoltaico"),
        StageEvidence(label="Variables NASA POWER", value=", ".join(variables)),
        StageEvidence(label="Período", value=f"{request.start_date.isoformat()} a {request.end_date.isoformat()} · {years} años"),
        StageEvidence(label="Significancia", value="α = 0.05 · BH por variable entre sitios"),
        StageEvidence(label="Supuestos financieros", value=f"{request.assumptions.capacity_mw:g} MW · tasa {request.assumptions.discount_rate:.0%} · {request.assumptions.horizon_years} años", provenance=Provenance.ASSUMPTION),
    ]

    observations = sum(item.valid_observations for item in summaries)
    min_completeness = min((item.completeness_percent for item in summaries), default=0.0)
    downloads = sorted(item.source.downloaded_at for item in summaries)
    cached = sum(1 for item in summaries if item.source.provenance == Provenance.CACHED)
    extraction_status = PipelineStatus.COMPLETED if min_completeness >= COMPLETENESS_THRESHOLD else PipelineStatus.PARTIAL
    extraction_evidence = [
        StageEvidence(label="Observaciones diarias válidas", value=f"{observations:,}"),
        StageEvidence(label="Cobertura mínima", value=f"{min_completeness:.1f} %"),
        StageEvidence(label="Series desde caché", value=f"{cached} de {tests}", provenance=Provenance.CACHED if cached else Provenance.REAL),
    ]
    if downloads:
        extraction_evidence.append(StageEvidence(label="Descarga NASA (UTC)", value=downloads[0].strftime("%Y-%m-%d %H:%M") if downloads[0] == downloads[-1] else f"{downloads[0]:%Y-%m-%d} a {downloads[-1]:%Y-%m-%d}"))
    extraction_summary = (
        f"NASA POWER entregó {observations:,} observaciones diarias para {len(variables)} variables en {len(sites)} sitios."
        if extraction_status == PipelineStatus.COMPLETED
        else f"La cobertura mínima es {min_completeness:.1f} %, inferior al umbral de {COMPLETENESS_THRESHOLD:.0f} %; revise los faltantes antes de interpretar."
    )

    raw_significant = sum(1 for item in summaries if item.trend.significant)
    insufficient = sum(1 for item in summaries if item.trend.direction == "insufficient_evidence")
    autocorrelated = sum(1 for item in summaries if item.trend.autocorrelation_lag1 is not None and abs(item.trend.autocorrelation_lag1) >= 0.3)
    analysis_status = PipelineStatus.COMPLETED if insufficient == 0 else PipelineStatus.PARTIAL
    analysis_evidence = [
        StageEvidence(label="Pruebas Mann–Kendall", value=f"{tests} ({len(variables)} variables × {len(sites)} sitios)"),
        StageEvidence(label="Significativas antes de BH", value=f"{raw_significant} de {tests}"),
        StageEvidence(label="Significativas tras BH", value=f"{len(findings)} de {tests}"),
        StageEvidence(label="Autocorrelación lag-1 ≥ 0.3", value=f"{autocorrelated} series"),
    ]
    if insufficient:
        analysis_evidence.append(StageEvidence(label="Series con menos de 5 años", value=str(insufficient), provenance=Provenance.UNAVAILABLE))
    places_by_label: dict[str, list[str]] = {}
    for item in findings:
        places_by_label.setdefault(item.label[0].lower() + item.label[1:], []).append(item.site)
    changing = "; ".join(f"{label} en {' y '.join(places)}" for label, places in places_by_label.items())
    analysis_summary = (
        f"Mann–Kendall y Sen sobre {years} medias anuales; cambian con significancia: {changing}."
        if findings
        else "Mann–Kendall y Sen sobre medias anuales; ninguna tendencia conserva significancia tras BH."
    )

    pending = [gap for gap in gaps if gap.status == Provenance.UNAVAILABLE]
    territorial_evidence: list[StageEvidence] = []
    territorial_provenance: list[Provenance] = [Provenance.MODEL]
    if terrain is not None:
        located = sum(1 for site in terrain.sites if site.granules)
        ready = sum(1 for site in terrain.sites if site.status == "READY")
        tiles = ", ".join(dict.fromkeys(granule.tile_id for site in terrain.sites for granule in site.granules))
        territorial_evidence.append(StageEvidence(label="Gránulos NASADEM localizados", value=f"{located} de {len(terrain.sites)} sitios · {tiles}", provenance=Provenance.REAL))
        territorial_evidence.append(StageEvidence(label="Elevación y pendiente calculadas", value=f"{ready} de {len(terrain.sites)} sitios", provenance=Provenance.REAL if ready else Provenance.UNAVAILABLE))
        territorial_provenance += _unique([site.provenance for site in terrain.sites])
        terrain_sentence = f"NASADEM localizó {located} de {len(terrain.sites)} sitios y calculó métricas en {ready}."
    else:
        territorial_evidence.append(StageEvidence(label="NASADEM", value=terrain_error or "No consultado", provenance=Provenance.UNAVAILABLE))
        terrain_sentence = "NASADEM no respondió; el relieve queda sin evaluar."
    territorial_evidence.append(StageEvidence(label="Capas pendientes", value=", ".join(gap.dataset for gap in pending) or "Ninguna", provenance=Provenance.UNAVAILABLE if pending else None))
    terrain_ready = terrain is not None and all(site.status == "READY" for site in terrain.sites)
    territorial_status = PipelineStatus.COMPLETED if terrain_ready and not pending else PipelineStatus.PARTIAL
    if pending:
        territorial_provenance.append(Provenance.UNAVAILABLE)

    ranked = sorted(results, key=lambda item: item.relative_solar_position)
    irradiance = [next(v for v in item.variables if v.variable == "ALLSKY_SFC_SW_DWN") for item in ranked]
    unit = display_unit(irradiance[0].unit) if irradiance else ""
    delta = irradiance[0].mean - irradiance[-1].mean if irradiance else 0.0
    evaluation_evidence = [StageEvidence(label=f"{index + 1}.º {item.location.label}", value=f"{solar.mean:.3f} {unit}") for index, (item, solar) in enumerate(zip(ranked, irradiance, strict=True))]
    evaluation_evidence.append(StageEvidence(label="Criterio", value="Irradiancia histórica media; sin score compuesto"))

    npvs = [item.finance.npv_usd for item in results]
    finance_evidence = [StageEvidence(label=item.location.label or "Sitio", value=f"{_money(item.finance.npv_usd)} · {item.finance.annual_energy_mwh:,.0f} MWh/año", provenance=Provenance.MODEL) for item in results]
    finance_evidence.append(StageEvidence(label="Fórmula", value="Energía = MW × irradiancia × 365 × PR; VAN a tasa del usuario"))

    all_provenance = _unique(source_provenance + [Provenance.MODEL, Provenance.ASSUMPTION] + ([Provenance.UNAVAILABLE] if pending else []))
    return [
        PipelineStage(step=1, key="selection", name="Selección", status=PipelineStatus.COMPLETED, summary=f"{len(request.sites)} ubicaciones WGS84 validadas.", provenance=[Provenance.ASSUMPTION], evidence=selection_evidence, answers=["where"]),
        PipelineStage(step=2, key="configuration", name="Configuración", status=PipelineStatus.COMPLETED, summary=f"Sector solar, {len(variables)} variables NASA, {years} años y supuestos financieros explícitos.", provenance=[Provenance.ASSUMPTION], evidence=configuration_evidence),
        PipelineStage(step=3, key="extraction", name="Extracción", status=extraction_status, summary=extraction_summary, provenance=source_provenance, evidence=extraction_evidence, duration_ms=timings.extraction_ms, answers=["what"]),
        PipelineStage(step=4, key="analysis", name="Análisis", status=analysis_status, summary=analysis_summary, provenance=[Provenance.MODEL], evidence=analysis_evidence, duration_ms=timings.analysis_ms, answers=["what", "how_much", "significant"]),
        PipelineStage(step=5, key="territorial", name="Inteligencia territorial", status=territorial_status, summary=f"{terrain_sentence} {len(pending)} capas oficiales siguen pendientes y no se interpretan como riesgo cero.", provenance=_unique(territorial_provenance), evidence=territorial_evidence, duration_ms=timings.terrain_ms, answers=["where", "so_what"]),
        PipelineStage(step=6, key="evaluation", name="Evaluación", status=PipelineStatus.COMPLETED, summary=f"Orden relativo por irradiancia; diferencia entre extremos de {delta:.3f} {unit}.", provenance=_unique(source_provenance + [Provenance.MODEL]), evidence=evaluation_evidence, answers=["so_what"]),
        PipelineStage(step=7, key="finance", name="Impacto económico", status=PipelineStatus.COMPLETED, summary=f"VAN positivo en {sum(1 for value in npvs if value >= 0)} de {len(npvs)} sitios con los supuestos del usuario.", provenance=[Provenance.MODEL, Provenance.ASSUMPTION], evidence=finance_evidence, duration_ms=timings.finance_ms, answers=["so_what"]),
        PipelineStage(step=8, key="results", name="Resultados", status=PipelineStatus.COMPLETED, summary=f"Respuestas a las preguntas NASA, {len(findings)} tendencias significativas y {len(pending)} brechas documentadas.", provenance=all_provenance, evidence=[StageEvidence(label="Tendencias significativas", value=str(len(findings))), StageEvidence(label="Brechas para debida diligencia", value=str(len(pending)), provenance=Provenance.UNAVAILABLE if pending else None)]),
        PipelineStage(step=9, key="export", name="Exportación", status=PipelineStatus.READY, summary="Reporte JSON reproducible disponible; se marca completado al descargarlo. El PDF ejecutivo sigue pendiente.", provenance=all_provenance, evidence=[StageEvidence(label="Formato", value="JSON con identificador, período, supuestos, procedencia y métodos"), StageEvidence(label="PDF ejecutivo", value="Pendiente", provenance=Provenance.UNAVAILABLE)]),
    ]
