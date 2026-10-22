"""Respuestas deterministas a las preguntas del reto «Be An Earth System Trend Detective!».

Las cuatro preguntas del reto (qué, dónde, cuánto, si es significativo) se responden solo con
tendencias ya calculadas; la quinta (qué significa para invertir) aplica reglas explícitas y declara
lo que todavía no puede cuantificarse. Ninguna función consulta fuentes externas.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from ..core.units import display_unit, is_ratio_scale
from ..schemas.analysis import Provenance
from ..schemas.pipeline import VariableSummary
from ..schemas.screening import NasaQuestionAnswer, QuestionStatus, TrendFinding

INSUFFICIENT = "Evidencia insuficiente para establecer una tendencia estadísticamente significativa."
AUTOCORRELATION_CAUTION = 0.3


@dataclass(frozen=True)
class SubjectSummaries:
    """Resúmenes de variables de un sujeto de estudio (sitio, tramo o terreno)."""

    label: str
    summaries: Sequence[VariableSummary]


def collect_trend_findings(sites: Sequence[SubjectSummaries]) -> list[TrendFinding]:
    findings: list[TrendFinding] = []
    for site in sites:
        for item in site.summaries:
            trend = item.trend
            if not item.significant_after_bh or trend.slope_per_year is None or trend.p_value is None or not item.annual_series:
                continue
            first, last = item.annual_series[0].year, item.annual_series[-1].year
            change = trend.slope_per_year * (last - first)
            percent = change / abs(item.mean) * 100 if is_ratio_scale(item.unit) and abs(item.mean) > 1e-12 else None
            findings.append(
                TrendFinding(
                    site=site.label,
                    variable=item.variable,
                    label=item.label,
                    unit=display_unit(item.unit),
                    slope_per_year=trend.slope_per_year,
                    confidence_interval=trend.confidence_interval,
                    first_year=first,
                    last_year=last,
                    change_over_period=change,
                    change_percent_of_mean=percent,
                    p_value=trend.p_value,
                    p_value_modified=trend.p_value_modified,
                    adjusted_p_value=item.adjusted_p_value if item.adjusted_p_value is not None else trend.p_value,
                    variance_correction=trend.variance_correction,
                    autocorrelation_lag1=trend.autocorrelation_lag1,
                    autocorrelation_lag1_detrended=trend.autocorrelation_lag1_detrended,
                    annual_series=item.annual_series,
                )
            )
    return findings


NBSP = " "  # cifra y unidad no deben separarse al ajustar línea


def join_es(items: Sequence[str]) -> str:
    items = list(dict.fromkeys(items))
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} y {items[-1]}"


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _sentence(items: Sequence[str], separator: str = ", ") -> str:
    """Primera etiqueta con mayúscula inicial y el resto en minúscula, como en una frase."""
    items = list(dict.fromkeys(items))
    rest = [_lower_first(item) for item in items[1:]]
    if separator != ", ":
        return separator.join(items[:1] + rest)
    return join_es(items[:1] + rest)


def _qty(value: float, unit: str, digits: int, signed: bool = True) -> str:
    return f"{value:+.{digits}f}{NBSP}{unit}" if signed else f"{value:.{digits}f}{NBSP}{unit}"


def millions_usd(value: float) -> str:
    return f"{'−' if value < 0 else ''}USD{NBSP}{abs(value) / 1e6:.2f}{NBSP}M"


def _magnitude(finding: TrendFinding) -> str:
    interval = ""
    if finding.confidence_interval:
        low, high = finding.confidence_interval
        interval = f" (IC 95 %: {low:+.4f} a {high:+.4f})"
    percent = f", {finding.change_percent_of_mean:+.1f}{NBSP}% de la media" if finding.change_percent_of_mean is not None else ""
    return (
        f"{finding.label} en {finding.site}: {_qty(finding.slope_per_year, finding.unit + '/año', 4)}{interval}; "
        f"{_qty(finding.change_over_period, finding.unit, 2)} entre {finding.first_year} y {finding.last_year}{percent}."
    )


def _what(findings: list[TrendFinding], sites: Sequence[SubjectSummaries], tests: int) -> NasaQuestionAnswer:
    labels = [item.label for site in sites for item in site.summaries]
    changing = list(dict.fromkeys(finding.label for finding in findings))
    stable = [label for label in dict.fromkeys(labels) if label not in changing]
    if not findings:
        return NasaQuestionAnswer(
            key="what", question="What is changing?", question_es="¿Qué está cambiando?", status=QuestionStatus.INSUFFICIENT,
            answer=f"{INSUFFICIENT} Ninguna de las {tests} pruebas conserva significancia tras Benjamini–Hochberg.",
            evidence=[f"Variables analizadas: {join_es(stable)}."], provenance=[Provenance.MODEL], stage_steps=[3, 4],
        )
    evidence = [f"{finding.label} · {finding.site} · p ajustado {finding.adjusted_p_value:.4f}" for finding in findings]
    if stable:
        evidence.append(f"Sin evidencia de cambio: {join_es([_lower_first(label) for label in stable])}.")
    return NasaQuestionAnswer(
        key="what", question="What is changing?", question_es="¿Qué está cambiando?", status=QuestionStatus.ANSWERED,
        answer=f"{_sentence(changing)}. {len(findings)} de {tests} pruebas conservan significancia tras Benjamini–Hochberg (α = 0.05).",
        evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[3, 4],
    )


def _where(findings: list[TrendFinding], sites: Sequence[SubjectSummaries], coordinates: dict[str, tuple[float, float]]) -> NasaQuestionAnswer:
    all_sites = [site.label for site in sites]
    evidence = [f"{label}: {lat:.3f}, {lon:.3f} (WGS84) · celda de grilla NASA POWER, no medición en sitio" for label, (lat, lon) in coordinates.items()]
    if not findings:
        return NasaQuestionAnswer(
            key="where", question="Where is it changing?", question_es="¿Dónde está cambiando?", status=QuestionStatus.INSUFFICIENT,
            answer=f"{INSUFFICIENT} No se identifica un lugar con cambio significativo entre {join_es(all_sites)}.",
            evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[1, 5],
        )
    by_variable: dict[str, list[str]] = {}
    for finding in findings:
        by_variable.setdefault(finding.label, []).append(finding.site)
    parts = []
    for label, places in by_variable.items():
        scope = "en todos los sitios analizados" if set(places) == set(all_sites) else f"solo en {join_es(places)}"
        parts.append(f"{label}: {scope}")
    return NasaQuestionAnswer(
        key="where", question="Where is it changing?", question_es="¿Dónde está cambiando?", status=QuestionStatus.ANSWERED,
        answer=_sentence(parts, separator="; ") + ".", evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[1, 5],
    )


def _how_much(findings: list[TrendFinding]) -> NasaQuestionAnswer:
    if not findings:
        return NasaQuestionAnswer(
            key="how_much", question="How much is it changing?", question_es="¿Cuánto está cambiando?", status=QuestionStatus.INSUFFICIENT,
            answer=f"{INSUFFICIENT} No se informa magnitud sin una tendencia significativa.",
            evidence=[], provenance=[Provenance.MODEL], stage_steps=[4],
        )
    lead = max(findings, key=lambda item: abs(item.change_over_period))
    answer = (
        f"{lead.label} en {lead.site}: {_qty(lead.change_over_period, lead.unit, 2)} entre {lead.first_year} y {lead.last_year} "
        f"({_qty(lead.slope_per_year, lead.unit + '/año', 4)}, pendiente de Sen)."
    )
    return NasaQuestionAnswer(
        key="how_much", question="How much is it changing?", question_es="¿Cuánto está cambiando?", status=QuestionStatus.ANSWERED,
        answer=answer, evidence=[_magnitude(finding) for finding in findings], provenance=[Provenance.MODEL], stage_steps=[4],
    )


def _significant(findings: list[TrendFinding], sites: Sequence[SubjectSummaries], tests: int, years: int) -> NasaQuestionAnswer:
    raw = sum(1 for site in sites for item in site.summaries if item.trend.significant)
    method = (
        f"Mann–Kendall con varianza corregida por autocorrelación (Hamed y Rao, 1998) y pendiente de Sen sobre {years} medias anuales; "
        f"familia Benjamini–Hochberg = cada variable entre {len(sites)} sitios; α = 0.05."
    )
    evidence = [method, f"Significativas antes del ajuste BH: {raw} de {tests}; después: {len(findings)} de {tests}."]
    if not findings:
        return NasaQuestionAnswer(
            key="significant", question="Is the change statistically significant?", question_es="¿El cambio es estadísticamente significativo?",
            status=QuestionStatus.INSUFFICIENT, answer=INSUFFICIENT, evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[4],
        )
    answer = f"Sí en {len(findings)} de {tests} pruebas, con Mann–Kendall corregido por autocorrelación y ajuste Benjamini–Hochberg."
    status = QuestionStatus.ANSWERED
    corrected = [item for item in findings if (item.variance_correction or 1) > 1]
    raw_high = [item for item in findings if abs(item.autocorrelation_lag1 or 0) >= AUTOCORRELATION_CAUTION]
    if corrected:
        answer += f" En {len(corrected)} de ellas la autocorrelación sin tendencia era significativa y la varianza se corrigió; aun así conservan significancia."
    elif raw_high:
        worst_raw = max(abs(item.autocorrelation_lag1 or 0) for item in raw_high)
        worst_detrended = max(abs(item.autocorrelation_lag1_detrended or 0) for item in raw_high)
        answer += (
            f" La autocorrelación bruta (hasta {worst_raw:.2f}) proviene de la propia tendencia: sin ella, la de los rangos es "
            f"{worst_detrended:.2f} o menor y la corrección no altera la varianza."
        )
    evidence.extend(
        f"{item.label} · {item.site}: p clásico {item.p_value:.4f}, p corregido {item.p_value_modified if item.p_value_modified is not None else item.p_value:.4f}, "
        f"p BH {item.adjusted_p_value:.4f}, factor de varianza {item.variance_correction if item.variance_correction is not None else 1:.3f}, "
        f"lag-1 bruto {item.autocorrelation_lag1 if item.autocorrelation_lag1 is not None else float('nan'):.2f} / sin tendencia "
        f"{item.autocorrelation_lag1_detrended if item.autocorrelation_lag1_detrended is not None else float('nan'):.2f}"
        for item in findings
    )
    if years < 10:
        answer += f" La serie tiene {years} años, con potencia estadística baja."
        status = QuestionStatus.PARTIAL
    return NasaQuestionAnswer(
        key="significant", question="Is the change statistically significant?", question_es="¿El cambio es estadísticamente significativo?",
        status=status, answer=answer, evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[4],
    )


@dataclass(frozen=True)
class SectorLens:
    """Cómo lee un sector las tendencias para la quinta pregunta; lo define cada módulo sectorial.

    readings: consecuencia sectorial por (variable, "increasing" | "decreasing"); explica, no cuantifica.
    stable_notes: frase para una variable clave que no cambia con significancia en ningún sujeto.
    economics: frase ya calculada por el sector con su escenario económico (VAN, interrupciones, etc.).
    """

    readings: Mapping[tuple[str, str], str]
    stable_notes: Mapping[str, str] = field(default_factory=dict)
    economics: str | None = None


def _so_what(findings: list[TrendFinding], lens: SectorLens, gaps: int) -> NasaQuestionAnswer:
    changing = {finding.variable for finding in findings}
    sentences = [note for variable, note in lens.stable_notes.items() if variable not in changing]
    by_reading: dict[str, list[str]] = {}
    for finding in findings:
        direction = "increasing" if finding.slope_per_year > 0 else "decreasing"
        reading = lens.readings.get((finding.variable, direction))
        if reading:
            by_reading.setdefault(reading, []).append(finding.site)
    for reading, places in by_reading.items():
        sentences.append(f"En {join_es(places)}, {reading}.")
    if lens.economics:
        sentences.append(lens.economics)
    evidence = [
        "Regla sectorial explícita por variable y dirección de la tendencia; no se cuantifica impacto sin modelo técnico.",
        f"{gaps} capas territoriales siguen pendientes; su ausencia no equivale a riesgo cero.",
        "Screening preliminar: no sustituye estudios de recurso, ingeniería, impacto ambiental ni factibilidad.",
    ]
    return NasaQuestionAnswer(
        key="so_what", question="What do these changes mean for investment decisions?", question_es="¿Qué significan estos cambios para invertir?",
        status=QuestionStatus.PARTIAL, answer=" ".join(sentences) or INSUFFICIENT, evidence=evidence,
        provenance=[Provenance.MODEL, Provenance.ASSUMPTION, Provenance.UNAVAILABLE], stage_steps=[5, 6, 7],
    )


def answer_nasa_questions(
    subjects: Sequence[SubjectSummaries],
    findings: list[TrendFinding],
    coordinates: dict[str, tuple[float, float]],
    pending_gaps: int,
    lens: SectorLens,
) -> list[NasaQuestionAnswer]:
    tests = sum(len(subject.summaries) for subject in subjects)
    years = max((len(item.annual_series) for subject in subjects for item in subject.summaries), default=0)
    return [
        _what(findings, subjects, tests),
        _where(findings, subjects, coordinates),
        _how_much(findings),
        _significant(findings, subjects, tests, years),
        _so_what(findings, lens, pending_gaps),
    ]

