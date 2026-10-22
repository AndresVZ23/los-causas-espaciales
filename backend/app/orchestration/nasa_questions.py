"""Respuestas deterministas a las preguntas del reto «Be An Earth System Trend Detective!».

Las cuatro preguntas del reto (qué, dónde, cuánto, si es significativo) se responden solo con
tendencias ya calculadas; la quinta (qué significa para invertir) aplica reglas explícitas y declara
lo que todavía no puede cuantificarse. Ninguna función consulta fuentes externas.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ..core.units import display_unit, is_ratio_scale
from ..schemas.analysis import Provenance
from ..schemas.pipeline import (
    NasaQuestionAnswer,
    QuestionStatus,
    SolarSiteResult,
    TrendFinding,
    VariableSummary,
)

INSUFFICIENT = "Evidencia insuficiente para establecer una tendencia estadísticamente significativa."
AUTOCORRELATION_CAUTION = 0.3
IRRADIANCE = "ALLSKY_SFC_SW_DWN"


@dataclass(frozen=True)
class SiteSummaries:
    label: str
    summaries: Sequence[VariableSummary]


def collect_trend_findings(sites: Sequence[SiteSummaries]) -> list[TrendFinding]:
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
                    adjusted_p_value=item.adjusted_p_value if item.adjusted_p_value is not None else trend.p_value,
                    autocorrelation_lag1=trend.autocorrelation_lag1,
                )
            )
    return findings


NBSP = " "  # cifra y unidad no deben separarse al ajustar línea


def _join(items: Sequence[str]) -> str:
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
    return _join(items[:1] + rest)


def _qty(value: float, unit: str, digits: int, signed: bool = True) -> str:
    return f"{value:+.{digits}f}{NBSP}{unit}" if signed else f"{value:.{digits}f}{NBSP}{unit}"


def _millions(value: float) -> str:
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


def _what(findings: list[TrendFinding], sites: Sequence[SiteSummaries], tests: int) -> NasaQuestionAnswer:
    labels = [item.label for site in sites for item in site.summaries]
    changing = list(dict.fromkeys(finding.label for finding in findings))
    stable = [label for label in dict.fromkeys(labels) if label not in changing]
    if not findings:
        return NasaQuestionAnswer(
            key="what", question="What is changing?", question_es="¿Qué está cambiando?", status=QuestionStatus.INSUFFICIENT,
            answer=f"{INSUFFICIENT} Ninguna de las {tests} pruebas conserva significancia tras Benjamini–Hochberg.",
            evidence=[f"Variables analizadas: {_join(stable)}."], provenance=[Provenance.MODEL], stage_steps=[3, 4],
        )
    evidence = [f"{finding.label} · {finding.site} · p ajustado {finding.adjusted_p_value:.4f}" for finding in findings]
    if stable:
        evidence.append(f"Sin evidencia de cambio: {_join([_lower_first(label) for label in stable])}.")
    return NasaQuestionAnswer(
        key="what", question="What is changing?", question_es="¿Qué está cambiando?", status=QuestionStatus.ANSWERED,
        answer=f"{_sentence(changing)}. {len(findings)} de {tests} pruebas conservan significancia tras Benjamini–Hochberg (α = 0.05).",
        evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[3, 4],
    )


def _where(findings: list[TrendFinding], sites: Sequence[SiteSummaries], coordinates: dict[str, tuple[float, float]]) -> NasaQuestionAnswer:
    all_sites = [site.label for site in sites]
    evidence = [f"{label}: {lat:.3f}, {lon:.3f} (WGS84) · celda de grilla NASA POWER, no medición en sitio" for label, (lat, lon) in coordinates.items()]
    if not findings:
        return NasaQuestionAnswer(
            key="where", question="Where is it changing?", question_es="¿Dónde está cambiando?", status=QuestionStatus.INSUFFICIENT,
            answer=f"No se identifica un lugar con cambio significativo entre {_join(all_sites)}.",
            evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[1, 5],
        )
    by_variable: dict[str, list[str]] = {}
    for finding in findings:
        by_variable.setdefault(finding.label, []).append(finding.site)
    parts = []
    for label, places in by_variable.items():
        scope = "en todos los sitios analizados" if set(places) == set(all_sites) else f"solo en {_join(places)}"
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


def _significant(findings: list[TrendFinding], sites: Sequence[SiteSummaries], tests: int, years: int) -> NasaQuestionAnswer:
    raw = sum(1 for site in sites for item in site.summaries if item.trend.significant)
    flagged = [item for item in findings if item.autocorrelation_lag1 is not None and abs(item.autocorrelation_lag1) >= AUTOCORRELATION_CAUTION]
    method = (
        f"Mann–Kendall y pendiente de Sen sobre {years} medias anuales; familia Benjamini–Hochberg = cada variable entre "
        f"{len(sites)} sitios; α = 0.05."
    )
    evidence = [method, f"Significativas antes del ajuste: {raw} de {tests}; después: {len(findings)} de {tests}."]
    if not findings:
        return NasaQuestionAnswer(
            key="significant", question="Is the change statistically significant?", question_es="¿El cambio es estadísticamente significativo?",
            status=QuestionStatus.INSUFFICIENT, answer=INSUFFICIENT, evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[4],
        )
    answer = f"Sí en {len(findings)} de {tests} pruebas tras Benjamini–Hochberg."
    status = QuestionStatus.ANSWERED
    if flagged:
        worst = max(abs(item.autocorrelation_lag1 or 0) for item in flagged)
        answer += (
            f" En {len(flagged)} de ellas la autocorrelación lag-1 llega a {worst:.2f}: Mann–Kendall sin modificar puede "
            "sobrestimar la significancia, por lo que conviene confirmarla con una variante corregida."
        )
        evidence.append(f"Autocorrelación lag-1 ≥ {AUTOCORRELATION_CAUTION}: " + "; ".join(f"{item.label} · {item.site} ({item.autocorrelation_lag1:.2f})" for item in flagged))
        status = QuestionStatus.PARTIAL
    return NasaQuestionAnswer(
        key="significant", question="Is the change statistically significant?", question_es="¿El cambio es estadísticamente significativo?",
        status=status, answer=answer, evidence=evidence, provenance=[Provenance.MODEL], stage_steps=[4],
    )


# Lecturas sectoriales (fotovoltaica) por variable y dirección: explican consecuencias, no las cuantifican.
SOLAR_READINGS: dict[tuple[str, str], str] = {
    ("ALLSKY_SFC_SW_DWN", "decreasing"): "la irradiancia cae: la media histórica sobrestima el recurso futuro y el VAN debe sensibilizarse a la baja",
    ("ALLSKY_SFC_SW_DWN", "increasing"): "la irradiancia sube: la media histórica es conservadora para el recurso",
    ("T2M", "increasing"): "la temperatura sube: aumentan las pérdidas térmicas de los módulos, que el cálculo de energía actual no modela",
    ("T2M", "decreasing"): "la temperatura baja: reduce pérdidas térmicas de los módulos, que el cálculo de energía actual no modela",
    ("WS10M", "decreasing"): "el viento a 10 m disminuye: menor enfriamiento convectivo de los módulos",
    ("WS10M", "increasing"): "el viento a 10 m aumenta: revisar cargas de diseño de estructuras",
    ("PRECTOTCORR", "increasing"): "la precipitación aumenta: revisar drenaje y exposición hidrometeorológica",
    ("PRECTOTCORR", "decreasing"): "la precipitación disminuye: más ensuciamiento de módulos y menos limpieza natural",
}


def _so_what(findings: list[TrendFinding], sites: Sequence[SiteSummaries], results: Sequence[SolarSiteResult], gaps: int) -> NasaQuestionAnswer:
    sentences: list[str] = []
    irradiance_changes = [item for item in findings if item.variable == IRRADIANCE]
    if not irradiance_changes:
        sentences.append(
            "El recurso solar no muestra deriva significativa en ningún sitio: no hay evidencia para castigar la media histórica por tendencia, "
            "lo que no prueba que sea constante."
        )
    by_reading: dict[str, list[str]] = {}
    for finding in findings:
        direction = "increasing" if finding.slope_per_year > 0 else "decreasing"
        reading = SOLAR_READINGS.get((finding.variable, direction))
        if reading:
            by_reading.setdefault(reading, []).append(finding.site)
    for reading, places in by_reading.items():
        sentences.append(f"En {_join(places)}, {reading}.")
    npvs = [result.finance.npv_usd for result in results]
    positive = sum(1 for value in npvs if value >= 0)
    sentences.append(
        f"Con los supuestos del usuario, el VAN es positivo en {positive} de {len(npvs)} sitios "
        f"(de {_millions(min(npvs))} a {_millions(max(npvs))})."
    )
    evidence = [
        "Regla sectorial explícita por variable y dirección de la tendencia; no se cuantifica impacto sin modelo técnico.",
        f"{gaps} capas territoriales siguen pendientes; su ausencia no equivale a riesgo cero.",
        "Screening preliminar: no sustituye estudios de recurso, ingeniería, impacto ambiental ni factibilidad.",
    ]
    return NasaQuestionAnswer(
        key="so_what", question="What do these changes mean for investment decisions?", question_es="¿Qué significan estos cambios para invertir?",
        status=QuestionStatus.PARTIAL, answer=" ".join(sentences), evidence=evidence,
        provenance=[Provenance.MODEL, Provenance.ASSUMPTION, Provenance.UNAVAILABLE], stage_steps=[5, 6, 7],
    )


def answer_nasa_questions(
    sites: Sequence[SiteSummaries],
    findings: list[TrendFinding],
    results: Sequence[SolarSiteResult],
    coordinates: dict[str, tuple[float, float]],
    pending_gaps: int,
) -> list[NasaQuestionAnswer]:
    tests = sum(len(site.summaries) for site in sites)
    years = max((len(item.annual_series) for site in sites for item in site.summaries), default=0)
    return [
        _what(findings, sites, tests),
        _where(findings, sites, coordinates),
        _how_much(findings),
        _significant(findings, sites, tests, years),
        _so_what(findings, sites, results, pending_gaps),
    ]
