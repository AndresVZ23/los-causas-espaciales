"""Verificación de conformidad con el contrato C2.

`envelope_violations` devuelve una lista vacía cuando una respuesta de cualquier sector cumple el contrato.
Cada piloto debe tener una prueba que lo afirme sobre una ejecución real o controlada.
"""

from ..schemas.analysis import Provenance
from ..schemas.screening import (
    NASA_QUESTION_ORDER,
    STAGE_KEYS,
    PipelineStatus,
    QuestionStatus,
    ScreeningEnvelope,
    SubjectKind,
)
from .nasa_questions import INSUFFICIENT

GEOMETRY_BY_KIND = {
    SubjectKind.POINT: {"Point"},
    SubjectKind.SEGMENT: {"LineString", "MultiLineString"},
    SubjectKind.POLYGON: {"Polygon", "MultiPolygon"},
}


def envelope_violations(envelope: ScreeningEnvelope) -> list[str]:
    problems: list[str] = []

    keys = tuple(stage.key for stage in envelope.pipeline)
    if keys != STAGE_KEYS:
        problems.append(f"Etapas fuera del orden canónico: {keys}.")
    for index, stage in enumerate(envelope.pipeline, start=1):
        if stage.step != index:
            problems.append(f"La etapa {stage.key} tiene step={stage.step}; se esperaba {index}.")
        if not stage.evidence:
            problems.append(f"La etapa {stage.key} no informa evidencia.")
        if stage.duration_ms is not None and stage.duration_ms < 0:
            problems.append(f"La etapa {stage.key} informa una duración negativa.")
    export = next((stage for stage in envelope.pipeline if stage.key == "export"), None)
    if export and export.status not in (PipelineStatus.READY, PipelineStatus.COMPLETED):
        problems.append("La exportación debe estar LISTO o COMPLETADO.")

    pending = [gap for gap in envelope.data_gaps if gap.status == Provenance.UNAVAILABLE]
    territorial = next((stage for stage in envelope.pipeline if stage.key == "territorial"), None)
    if pending and territorial and territorial.status == PipelineStatus.COMPLETED:
        problems.append("La etapa territorial no puede estar COMPLETADO con brechas DATA_UNAVAILABLE.")

    question_keys = tuple(question.key for question in envelope.nasa_questions)
    if question_keys != NASA_QUESTION_ORDER:
        problems.append(f"Preguntas NASA fuera de orden o incompletas: {question_keys}.")
    for question in envelope.nasa_questions:
        if not question.stage_steps or any(step < 1 or step > len(STAGE_KEYS) for step in question.stage_steps):
            problems.append(f"La pregunta {question.key} no enlaza etapas válidas.")
        if question.status == QuestionStatus.INSUFFICIENT and question.key != "so_what" and INSUFFICIENT not in question.answer:
            problems.append(f"La pregunta {question.key} declara evidencia insuficiente sin la frase obligatoria.")
        if not question.answer.strip():
            problems.append(f"La pregunta {question.key} no tiene respuesta.")

    labels = [subject.label for subject in envelope.subjects]
    ids = [subject.id for subject in envelope.subjects]
    if len(set(labels)) != len(labels) or len(set(ids)) != len(ids):
        problems.append("Los sujetos de estudio deben tener id y etiqueta únicos.")
    for subject in envelope.subjects:
        geometry_type = subject.geometry.get("type")
        if geometry_type not in GEOMETRY_BY_KIND[subject.kind]:
            problems.append(f"El sujeto {subject.label} es {subject.kind} pero su geometría es {geometry_type}.")
    seen = set()
    for finding in envelope.trend_findings:
        if finding.site not in labels:
            problems.append(f"La tendencia de {finding.variable} cita un sujeto inexistente: {finding.site}.")
        if (finding.site, finding.variable) in seen:
            problems.append(f"Tendencia duplicada para {finding.site} · {finding.variable}.")
        seen.add((finding.site, finding.variable))

    for item in envelope.assumption_items:
        if item.provenance != Provenance.ASSUMPTION:
            problems.append(f"El supuesto {item.key} debe tener procedencia USER_ASSUMPTION.")
    if not envelope.sector_label.strip() or not envelope.disclaimer.strip():
        problems.append("sector_label y disclaimer son obligatorios.")
    return problems
