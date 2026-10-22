"""Constructores de las nueve etapas del pipeline a partir de lo que realmente ocurrió en la ejecución.

Cada estado se deriva de hechos medidos (cobertura, procedencia, pruebas, capas disponibles); ninguna etapa
se declara completada por defecto. Las etapas 1–5, 8 y 9 son comunes a todos los sectores; cada sector
construye su etapa 6 (evaluación) y 7 (impacto económico) y las une con `assemble_pipeline`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ..schemas.analysis import Provenance
from ..schemas.pipeline import VariableSummary
from ..schemas.screening import STAGE_KEYS, DataGap, NasaQuestionKey, PipelineStage, PipelineStatus, StageEvidence, StudySubject, TrendFinding
from ..schemas.terrain import TerrainResponse
from .nasa_questions import SubjectSummaries

COMPLETENESS_THRESHOLD = 95.0
STAGE_NAMES = {
    "selection": "Selección", "configuration": "Configuración", "extraction": "Extracción", "analysis": "Análisis",
    "territorial": "Inteligencia territorial", "evaluation": "Evaluación", "finance": "Impacto económico",
    "results": "Resultados", "export": "Exportación",
}


@dataclass
class StageTimings:
    extraction_ms: float | None = None
    terrain_ms: float | None = None
    analysis_ms: float | None = None
    finance_ms: float | None = None


def unique(values: Sequence[Provenance]) -> list[Provenance]:
    return list(dict.fromkeys(values))


def stage(key: str, status: PipelineStatus, summary: str, provenance: Sequence[Provenance], evidence: Sequence[StageEvidence],
          duration_ms: float | None = None, answers: Sequence[NasaQuestionKey] = ()) -> PipelineStage:
    """Crea una etapa con el número y nombre canónicos de su clave."""
    return PipelineStage(
        step=STAGE_KEYS.index(key) + 1, key=key, name=STAGE_NAMES[key], status=status, summary=summary,
        provenance=unique(provenance), evidence=list(evidence), duration_ms=duration_ms, answers=list(answers),
    )


def _all_summaries(subjects: Sequence[SubjectSummaries]) -> list[VariableSummary]:
    return [item for subject in subjects for item in subject.summaries]


def selection_stage(subjects: Sequence[StudySubject], separation_km: float | None) -> PipelineStage:
    kinds = {"point": "ubicaciones", "segment": "tramos", "polygon": "polígonos"}
    noun = kinds.get(subjects[0].kind, "sujetos") if len({s.kind for s in subjects}) == 1 else "sujetos"
    evidence = [StageEvidence(label=s.label, value=f"{s.representative_point.latitude:.3f}, {s.representative_point.longitude:.3f}") for s in subjects]
    if separation_km is not None:
        evidence.append(StageEvidence(label="Separación geodésica máxima", value=f"{separation_km:,.1f} km (WGS84)"))
    return stage("selection", PipelineStatus.COMPLETED, f"{len(subjects)} {noun} WGS84 validados.", [Provenance.ASSUMPTION], evidence, answers=["where"])


def configuration_stage(sector_label: str, variables: Sequence[str], start: date, end: date, years: int,
                        assumption_summary: str) -> PipelineStage:
    evidence = [
        StageEvidence(label="Sector", value=sector_label),
        StageEvidence(label="Variables NASA POWER", value=", ".join(variables)),
        StageEvidence(label="Período", value=f"{start.isoformat()} a {end.isoformat()} · {years} años"),
        StageEvidence(label="Significancia", value="α = 0.05 · Hamed–Rao · BH por variable entre sujetos"),
        StageEvidence(label="Supuestos", value=assumption_summary, provenance=Provenance.ASSUMPTION),
    ]
    return stage("configuration", PipelineStatus.COMPLETED, f"{sector_label}, {len(variables)} variables NASA, {years} años y supuestos explícitos.",
                 [Provenance.ASSUMPTION], evidence)


def extraction_stage(subjects: Sequence[SubjectSummaries], duration_ms: float | None) -> PipelineStage:
    summaries = _all_summaries(subjects)
    variables = list(dict.fromkeys(item.variable for item in summaries))
    observations = sum(item.valid_observations for item in summaries)
    min_completeness = min((item.completeness_percent for item in summaries), default=0.0)
    downloads = sorted(item.source.downloaded_at for item in summaries)
    cached = sum(1 for item in summaries if item.source.provenance == Provenance.CACHED)
    status = PipelineStatus.COMPLETED if min_completeness >= COMPLETENESS_THRESHOLD else PipelineStatus.PARTIAL
    evidence = [
        StageEvidence(label="Observaciones diarias válidas", value=f"{observations:,}"),
        StageEvidence(label="Cobertura mínima", value=f"{min_completeness:.1f} %"),
        StageEvidence(label="Series desde caché", value=f"{cached} de {len(summaries)}", provenance=Provenance.CACHED if cached else Provenance.REAL),
    ]
    if downloads:
        evidence.append(StageEvidence(label="Descarga NASA (UTC)", value=downloads[0].strftime("%Y-%m-%d %H:%M") if downloads[0] == downloads[-1] else f"{downloads[0]:%Y-%m-%d} a {downloads[-1]:%Y-%m-%d}"))
    # Cada producto se publica con su propia latencia: se informa la fecha más antigua entre sujetos, por variable.
    through: dict[str, object] = {}
    for item in summaries:
        if item.last_valid_date and (item.variable not in through or item.last_valid_date < through[item.variable]):
            through[item.variable] = item.last_valid_date
    if through:
        by_date: dict[object, list[str]] = {}
        for variable, last in through.items():
            by_date.setdefault(last, []).append(variable)
        evidence.append(StageEvidence(label="Último dato publicado", value=" · ".join(f"{', '.join(names)}: {last:%Y-%m-%d}" for last, names in sorted(by_date.items(), reverse=True))))
    corrected = sum(1 for item in summaries if any("se dividió por 24" in note for note in item.source.quality_notes))
    verified = sum(1 for item in summaries if any("verificada" in note for note in item.source.quality_notes))
    unverifiable = sum(1 for item in summaries if any("no verificable" in note for note in item.source.quality_notes))
    if corrected or verified or unverifiable:
        parts = [f"corregida en {corrected}" if corrected else "", f"verificada en {verified}" if verified else "", f"no verificable en {unverifiable}" if unverifiable else ""]
        evidence.append(StageEvidence(label="Escala de precipitación NASA", value=" · ".join(p for p in parts if p) + " series", provenance=Provenance.MODEL))
    partial = sorted({item.current_period.year for item in summaries if item.current_period})
    if partial:
        evidence.append(StageEvidence(label="Año en curso", value=f"{', '.join(map(str, partial))} fuera de la tendencia; comparado con la misma ventana de años completos"))
    summary = (
        f"NASA POWER entregó {observations:,} observaciones diarias para {len(variables)} variables en {len(subjects)} sujetos."
        if status == PipelineStatus.COMPLETED
        else f"La cobertura mínima es {min_completeness:.1f} %, inferior al umbral de {COMPLETENESS_THRESHOLD:.0f} %; revise los faltantes antes de interpretar."
    )
    return stage("extraction", status, summary, unique([item.source.provenance for item in summaries]), evidence, duration_ms, ["what"])


def analysis_stage(subjects: Sequence[SubjectSummaries], findings: Sequence[TrendFinding], duration_ms: float | None) -> PipelineStage:
    summaries = _all_summaries(subjects)
    tests = len(summaries)
    variables = list(dict.fromkeys(item.variable for item in summaries))
    years = max((len(item.annual_series) for item in summaries), default=0)
    raw_significant = sum(1 for item in summaries if item.trend.significant)
    insufficient = sum(1 for item in summaries if item.trend.direction == "insufficient_evidence")
    corrected = sum(1 for item in summaries if (item.trend.variance_correction or 1) != 1)
    detrended = [abs(item.trend.autocorrelation_lag1_detrended) for item in summaries if item.trend.autocorrelation_lag1_detrended is not None]
    evidence = [
        StageEvidence(label="Pruebas Mann–Kendall (Hamed–Rao)", value=f"{tests} ({len(variables)} variables × {len(subjects)} sujetos)"),
        StageEvidence(label="Significativas antes de BH", value=f"{raw_significant} de {tests}"),
        StageEvidence(label="Significativas tras BH", value=f"{len(findings)} de {tests}"),
        StageEvidence(label="Varianza corregida por autocorrelación", value=f"{corrected} de {tests} series"),
    ]
    if detrended:
        evidence.append(StageEvidence(label="Lag-1 máx. de rangos sin tendencia", value=f"{max(detrended):.2f}"))
    if insufficient:
        evidence.append(StageEvidence(label="Series con menos de 5 años", value=str(insufficient), provenance=Provenance.UNAVAILABLE))
    places_by_label: dict[str, list[str]] = {}
    for item in findings:
        places_by_label.setdefault(item.label[0].lower() + item.label[1:], []).append(item.site)
    changing = "; ".join(f"{label} en {' y '.join(places)}" for label, places in places_by_label.items())
    summary = (
        f"Mann–Kendall corregido (Hamed–Rao) y Sen sobre {years} medias anuales; cambian con significancia: {changing}."
        if findings
        else "Mann–Kendall corregido (Hamed–Rao) y Sen sobre medias anuales; ninguna tendencia conserva significancia tras BH."
    )
    status = PipelineStatus.COMPLETED if insufficient == 0 else PipelineStatus.PARTIAL
    return stage("analysis", status, summary, [Provenance.MODEL], evidence, duration_ms, ["what", "how_much", "significant"])


def territorial_stage(terrain: TerrainResponse | None, terrain_error: str | None, gaps: Sequence[DataGap], duration_ms: float | None) -> PipelineStage:
    pending = [gap for gap in gaps if gap.status == Provenance.UNAVAILABLE]
    evidence: list[StageEvidence] = []
    provenance: list[Provenance] = [Provenance.MODEL]
    if terrain is not None:
        located = sum(1 for site in terrain.sites if site.granules)
        ready = sum(1 for site in terrain.sites if site.status == "READY")
        # PENDING (acordado con Codex): la tesela se está descargando en segundo plano; no es una falla.
        downloading = sum(1 for site in terrain.sites if site.status == "PENDING")
        tiles = ", ".join(dict.fromkeys(granule.tile_id for site in terrain.sites for granule in site.granules))
        evidence.append(StageEvidence(label="Gránulos NASADEM localizados", value=f"{located} de {len(terrain.sites)} · {tiles}", provenance=Provenance.REAL))
        evidence.append(StageEvidence(label="Elevación y pendiente calculadas", value=f"{ready} de {len(terrain.sites)}", provenance=Provenance.REAL if ready else Provenance.UNAVAILABLE))
        if downloading:
            evidence.append(StageEvidence(label="Teselas descargándose", value=f"{downloading} · vuelva a ejecutar en unos minutos", provenance=Provenance.UNAVAILABLE))
        provenance += [site.provenance for site in terrain.sites]
        terrain_sentence = f"NASADEM localizó {located} de {len(terrain.sites)} sujetos y calculó métricas en {ready}."
        if downloading:
            terrain_sentence += f" {downloading} tesela(s) se descargan en segundo plano."
    else:
        evidence.append(StageEvidence(label="NASADEM", value=terrain_error or "No consultado", provenance=Provenance.UNAVAILABLE))
        terrain_sentence = "NASADEM no respondió; el relieve queda sin evaluar."
    evidence.append(StageEvidence(label="Capas pendientes", value=", ".join(gap.dataset for gap in pending) or "Ninguna", provenance=Provenance.UNAVAILABLE if pending else None))
    terrain_ready = terrain is not None and all(site.status == "READY" for site in terrain.sites)
    if pending:
        provenance.append(Provenance.UNAVAILABLE)
    status = PipelineStatus.COMPLETED if terrain_ready and not pending else PipelineStatus.PARTIAL
    summary = f"{terrain_sentence} {len(pending)} capas oficiales siguen pendientes y no se interpretan como riesgo cero."
    return stage("territorial", status, summary, provenance, evidence, duration_ms, ["where", "so_what"])


def results_stage(findings: Sequence[TrendFinding], gaps: Sequence[DataGap], provenance: Sequence[Provenance]) -> PipelineStage:
    pending = sum(1 for gap in gaps if gap.status == Provenance.UNAVAILABLE)
    evidence = [
        StageEvidence(label="Tendencias significativas", value=str(len(findings))),
        StageEvidence(label="Brechas para debida diligencia", value=str(pending), provenance=Provenance.UNAVAILABLE if pending else None),
    ]
    return stage("results", PipelineStatus.COMPLETED, f"Respuestas a las preguntas NASA, {len(findings)} tendencias significativas y {pending} brechas documentadas.",
                 provenance, evidence)


def export_stage(provenance: Sequence[Provenance]) -> PipelineStage:
    evidence = [
        StageEvidence(label="Formato", value="JSON con identificador, período, supuestos, procedencia y métodos"),
        StageEvidence(label="PDF ejecutivo", value="Preguntas NASA, tendencias, relieve, pipeline, supuestos, brechas y huella SHA-256"),
    ]
    return stage("export", PipelineStatus.READY, "Reporte JSON y PDF ejecutivo disponibles; la etapa se marca completada al descargar uno de ellos.",
                 provenance, evidence)


def assemble_pipeline(stages: Sequence[PipelineStage]) -> list[PipelineStage]:
    """Ordena y valida que estén exactamente las nueve etapas canónicas."""
    ordered = sorted(stages, key=lambda item: item.step)
    keys = tuple(item.key for item in ordered)
    if keys != STAGE_KEYS:
        raise ValueError(f"El pipeline debe tener las nueve etapas canónicas {STAGE_KEYS}; recibido {keys}.")
    return ordered
