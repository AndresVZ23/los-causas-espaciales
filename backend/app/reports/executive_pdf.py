"""Reporte ejecutivo PDF a partir del sobre común C2.

Lee campos de `ScreeningEnvelope`, así que sirve para cualquier sector (solar, vial, inmobiliario). La línea base
(ambiente y patrimonio) agrega su propia sección por área desde `baseline_pdf`. No calcula nada nuevo: presenta
respuestas, tendencias, relieve, pipeline, supuestos y brechas tal como llegaron, con su procedencia y una huella
SHA-256 del contenido para trazabilidad.
"""

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas.analysis import Provenance
from ..schemas.baseline import BaselineScreeningResponse
from ..schemas.screening import ScreeningEnvelope, TrendFinding

FONT_DIR = Path(__file__).parent / "fonts"
SANS, SANS_BOLD, MONO = "PublicSans", "PublicSans-SemiBold", "IBMPlexMono"
# Caracteres sin glifo en las fuentes del sistema de diseño: se escriben en texto en vez de dejar un cuadro vacío.
GLYPH_FALLBACK = {"α": "alfa", "→": "->"}

INK = colors.HexColor("#1d2327")
MUTED = colors.HexColor("#5b6670")
RULE = colors.HexColor("#d5dbe0")
WASH = colors.HexColor("#f3f5f6")
ACCENT = colors.HexColor("#0e7c6e")  # cian del sistema oscurecido para impresión (contraste AA sobre blanco)
STATUS_COLORS = {
    "RESPONDIDA": "#1f7a45", "PARCIAL": "#9a6b00", "EVIDENCIA_INSUFICIENTE": "#5b6670",
    "COMPLETADO": "#1f7a45", "LISTO": "#0e7c6e", "NO_DISPONIBLE": "#b3364a", "ERROR": "#b3364a",
}
STATUS_LABELS = {
    "RESPONDIDA": "Respondida", "PARCIAL": "Con salvedades", "EVIDENCIA_INSUFICIENTE": "Evidencia insuficiente",
    "COMPLETADO": "Completado", "LISTO": "Listo", "NO_DISPONIBLE": "No disponible", "ERROR": "Error",
}
STAGE_STATUS_LABELS = {**STATUS_LABELS, "PARCIAL": "Parcial"}
DISCOVERY_LABELS = {"artefacto_probable": "Artefacto probable", "confirmado": "Confirmado", "sin_respaldo": "Sin respaldo",
                    "coincidencia": "Coincidencia", "contradiccion": "Contradicción"}
PROVENANCE_TEXT = {
    Provenance.REAL: "observación original de la fuente", Provenance.CACHED: "copia validada en caché, con su fecha de descarga",
    Provenance.MODEL: "cálculo derivado con método identificado", Provenance.ASSUMPTION: "supuesto editable del usuario",
    Provenance.DEMO: "ejemplo ilustrativo", Provenance.UNAVAILABLE: "fuente no conectada o información insuficiente",
}
KIND_LABELS = {"point": "Sitio", "segment": "Tramo", "polygon": "Terreno"}

_fonts_ready = False


def _register_fonts() -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    for name, file in ((SANS, "PublicSans-Regular.ttf"), (SANS_BOLD, "PublicSans-SemiBold.ttf"), (MONO, "IBMPlexMono-Regular.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
    pdfmetrics.registerFontFamily(SANS, normal=SANS, bold=SANS_BOLD, italic=SANS, boldItalic=SANS_BOLD)
    _fonts_ready = True


def _text(value: object) -> str:
    """Texto seguro para Paragraph: reemplaza glifos ausentes y escapa el marcado."""
    text = str(value)
    for char, replacement in GLYPH_FALLBACK.items():
        text = text.replace(char, replacement)
    return escape(text)


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle("title", fontName=SANS_BOLD, fontSize=19, leading=23, textColor=INK, spaceAfter=3),
        "subtitle": ParagraphStyle("subtitle", fontName=SANS, fontSize=9.5, leading=13, textColor=MUTED),
        "h2": ParagraphStyle("h2", fontName=SANS_BOLD, fontSize=12, leading=15, textColor=INK, spaceBefore=12, spaceAfter=5),
        "h3": ParagraphStyle("h3", fontName=SANS_BOLD, fontSize=9.4, leading=12, textColor=INK, spaceBefore=8, spaceAfter=3),
        "lede": ParagraphStyle("lede", fontName=SANS, fontSize=8.6, leading=12, textColor=MUTED, spaceAfter=6),
        "body": ParagraphStyle("body", fontName=SANS, fontSize=8.8, leading=12.4, textColor=INK),
        "cell": ParagraphStyle("cell", fontName=SANS, fontSize=8.2, leading=11.2, textColor=INK),
        "cellMuted": ParagraphStyle("cellMuted", fontName=SANS, fontSize=7.6, leading=10.2, textColor=MUTED),
        "cellHead": ParagraphStyle("cellHead", fontName=SANS_BOLD, fontSize=7.6, leading=10, textColor=MUTED),
        "mono": ParagraphStyle("mono", fontName=MONO, fontSize=7.4, leading=10, textColor=INK),
        "figure": ParagraphStyle("figure", fontName=SANS_BOLD, fontSize=15, leading=18, textColor=INK),
    }


def fingerprint(envelope: ScreeningEnvelope) -> str:
    payload = json.dumps(envelope.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _status_cell(status: str, styles: dict[str, ParagraphStyle], labels: dict[str, str]) -> Paragraph:
    color = STATUS_COLORS.get(status, "#5b6670")
    return Paragraph(f'<font name="{SANS_BOLD}" color="{color}">{_text(labels.get(status, status))}</font>', styles["cell"])


def _table(rows: list[list], widths: list[float], header: bool = True, zebra: bool = False) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ]
    if header:
        commands += [("LINEBELOW", (0, 0), (-1, 0), 0.8, MUTED)]
    if zebra:
        commands += [("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, WASH])]
    table.setStyle(TableStyle(commands))
    return table


def _fmt(value: float, digits: int = 4) -> str:
    return f"{value:+.{digits}f}"


def _trend_chart(finding: TrendFinding, width: float = 60 * mm, height: float = 25 * mm) -> Drawing:
    """Serie anual y recta de Sen; sin ejes decorativos, con extremos rotulados."""
    drawing = Drawing(width, height)
    points = [(item.year, item.value) for item in finding.annual_series]
    if len(points) < 2:
        drawing.add(String(0, height / 2, "Serie no disponible", fontName=SANS, fontSize=7, fillColor=MUTED))
        return drawing
    left, right, bottom, top = 22, width - 4, 10, height - 4
    years = [p[0] for p in points]
    values = [p[1] for p in points]
    y_min, y_max = min(values), max(values)
    span = (y_max - y_min) or abs(y_max) or 1.0
    y_min, y_max = y_min - span * 0.08, y_max + span * 0.08

    def sx(year: float) -> float:
        return left + (year - years[0]) / max(years[-1] - years[0], 1) * (right - left)

    def sy(value: float) -> float:
        return bottom + (value - y_min) / (y_max - y_min) * (top - bottom)

    drawing.add(Line(left, bottom, right, bottom, strokeColor=RULE, strokeWidth=0.5))
    drawing.add(PolyLine([coord for year, value in points for coord in (sx(year), sy(value))], strokeColor=ACCENT, strokeWidth=1.1))
    for year, value in points:
        drawing.add(Circle(sx(year), sy(value), 0.9, fillColor=ACCENT, strokeColor=None))
    intercept = median(value - finding.slope_per_year * year for year, value in points)
    drawing.add(Line(sx(years[0]), sy(intercept + finding.slope_per_year * years[0]), sx(years[-1]), sy(intercept + finding.slope_per_year * years[-1]),
                     strokeColor=INK, strokeWidth=0.7, strokeDashArray=[2, 1.5]))
    label = dict(fontName=MONO, fontSize=5.8, fillColor=MUTED)
    drawing.add(String(left, 1.5, str(years[0]), **label))
    drawing.add(String(right, 1.5, str(years[-1]), textAnchor="end", **label))
    drawing.add(String(left - 2, sy(max(values)) - 2, f"{max(values):.2f}", textAnchor="end", **label))
    drawing.add(String(left - 2, sy(min(values)) - 2, f"{min(values):.2f}", textAnchor="end", **label))
    return drawing


def _decorate(envelope: ScreeningEnvelope, short_hash: str):
    def draw(canvas, doc):
        canvas.saveState()
        width, height = A4
        left, right = doc.leftMargin + 6, width - doc.rightMargin - 6  # alineado con el contenido del marco
        canvas.setFont(SANS_BOLD, 7.5)
        canvas.setFillColor(INK)
        canvas.drawString(left, height - 12 * mm, "Los Causas Espaciales")
        canvas.setFont(SANS, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(left + 31 * mm, height - 12 * mm, "Reporte ejecutivo de screening")
        canvas.drawRightString(right, height - 12 * mm, _plain(f"{envelope.sector_label} · análisis {envelope.analysis_id}"))
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(left, height - 14 * mm, right, height - 14 * mm)
        canvas.line(left, 13 * mm, right, 13 * mm)
        canvas.setFont(SANS, 6.8)
        basis = "datos NASA y supuestos del usuario" if envelope.assumption_items else "datos NASA, sin supuestos financieros"
        # Patrimonio no usa datos NASA: su alcance se dice aparte y corto, para no montarse sobre la huella.
        scope = ("Identificación preliminar con registros de Cultura; no sustituye el CIRA ni una opinión legal." if envelope.sector == "heritage"
                 else f"Screening preliminar con {basis}; no sustituye factibilidad ni mediciones in situ.")
        canvas.drawString(left, 9 * mm, scope)
        canvas.drawRightString(right, 9 * mm, f"Huella {short_hash} · página {doc.page}")
        canvas.restoreState()
    return draw


def _plain(value: str) -> str:
    for char, replacement in GLYPH_FALLBACK.items():
        value = value.replace(char, replacement)
    return value


def _musd(value: float) -> str:
    return f"{value / 1e6:,.2f} M" if value >= 0 else f"−{abs(value) / 1e6:,.2f} M"


def _factor_value(value: float, unit: str) -> str:
    if unit == "fracción":
        return f"{value * 100:.1f} %"
    if unit.startswith("USD") and abs(value) >= 1e5:
        return f"{value / 1e6:,.2f} M {unit}"
    return f"{value:,.2f} {unit}".strip()


def _sensitivity_section(envelope: ScreeningEnvelope, styles: dict[str, ParagraphStyle], usable: float) -> list:
    items = envelope.financial_sensitivity
    currency = items[0].currency
    out: list = [
        Paragraph("Escenarios y sensibilidad del VAN", styles["h2"]),
        Paragraph(_text(f"VAN en {currency}. El tornado mueve un factor a la vez, con el resto en el caso base; los escenarios los mueven juntos. "
                        "Los rangos son supuestos del usuario, salvo los marcados MODEL_ESTIMATE, que salen de los años observados."), styles["lede"]),
    ]
    keys = [scenario.key for scenario in items[0].scenarios]
    rows = [[Paragraph("Escenario", styles["cellHead"])] + [Paragraph(_text(item.subject), styles["cellHead"]) for item in items]]
    for key in keys:
        label = next(scenario.label for scenario in items[0].scenarios if scenario.key == key)
        npvs = [next(scenario.npv for scenario in item.scenarios if scenario.key == key) for item in items]
        rows.append([Paragraph(f"<b>{_text(label)}</b>", styles["cell"])] + [Paragraph(_text(_musd(value)), styles["mono"]) for value in npvs])
    first = 40 * mm
    out.append(_table(rows, [first] + [(usable - first) / len(items)] * len(items)))
    for key in keys:
        changes = next(scenario.changes for scenario in items[0].scenarios if scenario.key == key)
        if key != "base":
            out.append(Paragraph(_text(f"{key.capitalize()} ({items[0].subject}): " + "; ".join(changes) + "."), styles["cellMuted"]))
    for item in items:
        bar_rows = [[Paragraph(h, styles["cellHead"]) for h in ("Factor", "Rango: desfavorable a favorable", "VAN desfavorable", "VAN favorable", "Origen")]]
        for bar in item.tornado:
            bar_rows.append([
                Paragraph(_text(bar.label), styles["cell"]),
                Paragraph(_text(f"{_factor_value(bar.low_value, bar.unit)} → {_factor_value(bar.high_value, bar.unit)}"), styles["mono"]),
                Paragraph(_text(_musd(bar.npv_at_low)), styles["mono"]), Paragraph(_text(_musd(bar.npv_at_high)), styles["mono"]),
                Paragraph(f"<font name='{MONO}' size='6.5'>{bar.provenance.value}</font>", styles["cellMuted"]),
            ])
        block = [Paragraph(_text(f"{item.subject} · VAN base {_musd(item.base_npv)} {item.currency}"), styles["h3"]),
                 _table(bar_rows, [38 * mm, 52 * mm, 24 * mm, 24 * mm, usable - 138 * mm])]
        block += [Paragraph(_text(f"• {even.note}"), styles["cell"]) for even in item.break_evens]
        out.append(KeepTogether(block))
    return out


def _scorecard_section(envelope: ScreeningEnvelope, styles: dict[str, ParagraphStyle], usable: float) -> list:
    card = envelope.scorecard
    out: list = [
        Paragraph("Puntaje multicriterio", styles["h2"]),
        Paragraph(_text(card.method), styles["lede"]),
    ]
    summary = "; ".join(
        f"{item.subject}: {item.score:.0f}/100 (primero en {item.first_place_share:.0%} de {card.stability_draws} combinaciones de pesos, cobertura {item.coverage:.0%})"
        if item.score is not None else f"{item.subject}: sin datos suficientes"
        for item in card.subjects
    )
    out.append(Paragraph(f"<b>{_text(summary)}.</b>", styles["body"]))
    if card.tie:
        out.append(Paragraph(_text(f"Empate práctico ({card.margin:.1f} punto(s) de diferencia): el puntaje no separa los sujetos; la decisión debe leerse criterio por criterio."), styles["body"]))
    out.append(Spacer(1, 2 * mm))
    head = [Paragraph(h, styles["cellHead"]) for h in ("Criterio", "Peso", "Escala (0 a 100)")] + [Paragraph(_text(item.subject), styles["cellHead"]) for item in card.subjects]
    rows = [head]
    for position, criterion in enumerate(card.criteria):
        cells = [Paragraph(_text(criterion.label), styles["cell"]), Paragraph(f"{criterion.weight * 100:.0f} %", styles["mono"]),
                 Paragraph(_text(f"{_factor_value(criterion.worst, criterion.unit)} a {_factor_value(criterion.best, criterion.unit)}"), styles["mono"])]
        for subject in card.subjects:
            item = subject.criteria[position]
            cells.append(Paragraph(_text("sin dato" if item.score is None else f"{item.score:.0f} pts"), styles["mono"]))
        rows.append(cells)
    fixed = 44 * mm + 16 * mm + 50 * mm
    out.append(_table(rows, [44 * mm, 16 * mm, 50 * mm] + [(usable - fixed) / len(card.subjects)] * len(card.subjects)))
    fragile = [criterion.label.lower() for criterion, item in zip(card.criteria, card.weight_sensitivity, strict=True) if item.changes_leader]
    out.append(Paragraph(_text(
        f"El primer lugar cambia al llevar a la mitad o al 150 % el peso de: {', '.join(fragile)}." if fragile
        else "El primer lugar no cambia al llevar cualquier peso a la mitad o al 150 %."), styles["cellMuted"]))
    out += [Paragraph(_text(note), styles["cellMuted"]) for note in card.notes]
    return out


def render_executive_pdf(envelope: ScreeningEnvelope) -> bytes:
    _register_fonts()
    styles = _styles()
    digest = fingerprint(envelope)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
        title=_plain(f"Reporte ejecutivo · {envelope.title}"), author="Los Causas Espaciales",
        subject=_plain(f"Screening {envelope.sector_label} · {envelope.period}"), creator="Los Causas Espaciales · contrato C2",
    )
    usable = doc.width - 12  # el marco de SimpleDocTemplate tiene 6 pt de margen interno por lado
    story: list = []

    pending = [gap for gap in envelope.data_gaps if gap.status == Provenance.UNAVAILABLE]
    caveats = [stage for stage in envelope.pipeline if stage.status not in ("COMPLETADO", "LISTO")]
    start, _, end = envelope.period.partition("/")
    story += [
        Paragraph(_text(envelope.title), styles["title"]),
        Paragraph(_text(f"{envelope.sector_label} · período {start} a {end} · análisis generado el {envelope.generated_at:%Y-%m-%d %H:%M} UTC"), styles["subtitle"]),
        Spacer(1, 7 * mm),
    ]
    facts = [
        (str(len(envelope.subjects)), "sujetos de estudio"),
        (str(len(envelope.trend_findings)), "tendencias significativas"),
        (str(len(caveats)), "etapas con salvedades"),
        (str(len(pending)), "brechas abiertas"),
    ]
    facts_table = Table([[Paragraph(value, styles["figure"]) for value, _ in facts], [Paragraph(_text(label), styles["cellMuted"]) for _, label in facts]],
                        colWidths=[usable / 4] * 4)
    facts_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, ACCENT), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 2),
    ]))
    story += [facts_table, Spacer(1, 4 * mm)]

    story.append(Paragraph("Las preguntas del reto NASA", styles["h2"]))
    story.append(Paragraph("«Be An Earth System Trend Detective!»: cuatro preguntas del reto y una quinta del producto, respondidas solo con resultados calculados.", styles["lede"]))
    question_rows = [[Paragraph("Pregunta", styles["cellHead"]), Paragraph("Estado", styles["cellHead"]), Paragraph("Respuesta", styles["cellHead"])]]
    for index, question in enumerate(envelope.nasa_questions, start=1):
        question_rows.append([
            Paragraph(f"<b>{index}. {_text(question.question_es)}</b><br/><font color='#5b6670' size='7'>{_text(question.question)}</font>", styles["cell"]),
            _status_cell(question.status, styles, STATUS_LABELS),
            Paragraph(_text(question.answer), styles["cell"]),
        ])
    story.append(_table(question_rows, [44 * mm, 27 * mm, usable - 71 * mm]))

    story.append(Paragraph("Tendencias significativas", styles["h2"]))
    if envelope.trend_findings:
        story.append(Paragraph("Medias anuales (línea continua) y pendiente de Sen (discontinua). Significancia con Mann–Kendall corregido por autocorrelación (Hamed–Rao) y ajuste Benjamini–Hochberg.", styles["lede"]))
        for finding in envelope.trend_findings:
            low, high = finding.confidence_interval or (None, None)
            interval = f" (IC 95 %: {_fmt(low)} a {_fmt(high)})" if low is not None and high is not None else ""
            percent = f", {finding.change_percent_of_mean:+.1f} % de la media" if finding.change_percent_of_mean is not None else ""
            p_mod = finding.p_value_modified if finding.p_value_modified is not None else finding.p_value
            lag = f" · lag-1 sin tendencia {finding.autocorrelation_lag1_detrended:.2f}" if finding.autocorrelation_lag1_detrended is not None else ""
            text = (
                f"<b>{_text(finding.label)} · {_text(finding.site)}</b><br/>"
                f"{_text(_fmt(finding.slope_per_year) + ' ' + finding.unit + '/año' + interval)}<br/>"
                f"Cambio {finding.first_year}–{finding.last_year}: <b>{_text(f'{finding.change_over_period:+.2f} {finding.unit}{percent}')}</b><br/>"
                f"<font name='{MONO}' size='7' color='#5b6670'>p corregido {p_mod:.4f} · p BH {finding.adjusted_p_value:.4f}{_text(lag)}</font>"
            )
            row = Table([[_trend_chart(finding), Paragraph(text, styles["cell"])]], colWidths=[64 * mm, usable - 64 * mm])
            row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                                     ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            story.append(KeepTogether(row))
    else:
        story.append(Paragraph("Evidencia insuficiente para establecer una tendencia estadísticamente significativa en las variables y sujetos analizados.", styles["body"]))

    if envelope.discoveries:
        story.append(Paragraph("Descubrimientos al cruzar fuentes", styles["h2"]))
        story.append(Paragraph("Cada dato se comprueba con fuentes independientes: lo que confirman, lo que contradicen y lo que solo una de ellas ve. "
                               "No son conclusiones; señalan qué mirar primero.", styles["lede"]))
        discovery_rows = [[Paragraph(h, styles["cellHead"]) for h in ("Tipo", "Descubrimiento", "Fuentes")]]
        for item in envelope.discoveries:
            discovery_rows.append([Paragraph(_text(DISCOVERY_LABELS.get(item.kind, item.kind)), styles["cell"]),
                                   Paragraph(f"<b>{_text(item.title)}</b><br/>{_text(item.detail)}", styles["cell"]),
                                   Paragraph(_text(" · ".join(item.sources)), styles["cellMuted"])])
        story.append(_table(discovery_rows, [27 * mm, usable - 71 * mm, 44 * mm]))

    baseline = envelope if isinstance(envelope, BaselineScreeningResponse) else None
    kind_labels = {**KIND_LABELS, "polygon": "Área"} if baseline else KIND_LABELS

    story.append(Paragraph("Sujetos de estudio y relieve", styles["h2"]))
    terrain_by_label = {site.location.label: site for site in (envelope.terrain.sites if envelope.terrain else [])}
    subject_rows = [[Paragraph(h, styles["cellHead"]) for h in ("Sujeto", "Tipo", "Punto representativo (WGS84)", "Elevación", "Pendiente", "Orientación")]]
    for subject in envelope.subjects:
        site = terrain_by_label.get(subject.label)
        point = subject.representative_point
        if site is None:
            relief = ["Sin consulta"] * 3
        elif site.status == "PENDING":
            relief = ["Descargando"] * 3
        else:
            metrics = site.metrics
            relief = [
                f"{metrics.elevation_m:,.0f} m" if metrics.elevation_m is not None else "N/D",
                f"{metrics.slope_degrees:.2f}°" if metrics.slope_degrees is not None else "N/D",
                f"{metrics.aspect_cardinal} · {metrics.aspect_degrees:.0f}°" if metrics.aspect_degrees is not None else "N/D",
            ]
        subject_rows.append([Paragraph(f"<b>{_text(subject.label)}</b>", styles["cell"]), Paragraph(kind_labels.get(subject.kind, subject.kind), styles["cell"]),
                             Paragraph(f"{point.latitude:.4f}, {point.longitude:.4f}", styles["mono"])] + [Paragraph(_text(value), styles["cell"]) for value in relief])
    story.append(_table(subject_rows, [34 * mm, 18 * mm, 42 * mm, 24 * mm, 24 * mm, usable - 142 * mm]))
    if envelope.terrain:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(_text(f"Relieve: {envelope.terrain.dataset}, {envelope.terrain.spatial_resolution}, altura ortométrica respecto al geoide EGM96. No sustituye un levantamiento topográfico."), styles["cellMuted"]))

    if baseline is not None:
        from .baseline_pdf import baseline_sections  # local: baseline_pdf importa este módulo
        story += baseline_sections(baseline, styles, usable)

    story.append(Paragraph("Pipeline de análisis", styles["h2"]))
    stage_rows = [[Paragraph(h, styles["cellHead"]) for h in ("#", "Etapa", "Estado", "Lo que ocurrió")]]
    for item in envelope.pipeline:
        elapsed = "<1" if item.duration_ms is not None and item.duration_ms < 1 else f"{item.duration_ms or 0:,.0f}"
        duration = f" <font name='{MONO}' size='6.8' color='#5b6670'>· {_text(elapsed)} ms</font>" if item.duration_ms is not None else ""
        stage_rows.append([Paragraph(str(item.step), styles["mono"]), Paragraph(f"<b>{_text(item.name)}</b>", styles["cell"]),
                           _status_cell(item.status, styles, STAGE_STATUS_LABELS), Paragraph(_text(item.summary) + duration, styles["cell"])])
    story.append(_table(stage_rows, [7 * mm, 34 * mm, 24 * mm, usable - 65 * mm]))

    if envelope.assumption_items:
        story.append(Paragraph("Supuestos del usuario", styles["h2"]))
        story.append(Paragraph("Todos con procedencia USER_ASSUMPTION: el escenario económico depende de ellos y no de observaciones.", styles["lede"]))
        assumption_rows = [[Paragraph(h, styles["cellHead"]) for h in ("Supuesto", "Valor", "Unidad")]]
        for item in envelope.assumption_items:
            value = f"{item.value * 100:.1f} %" if item.unit == "fracción" else f"{item.value:,.2f}".rstrip("0").rstrip(".")
            assumption_rows.append([Paragraph(_text(item.label), styles["cell"]), Paragraph(value, styles["mono"]),
                                    Paragraph(_text("" if item.unit == "fracción" else item.unit), styles["cellMuted"])])
        story.append(_table(assumption_rows, [70 * mm, 40 * mm, usable - 110 * mm]))

    if envelope.scorecard is not None:
        story += _scorecard_section(envelope, styles, usable)

    if envelope.financial_sensitivity:
        story += _sensitivity_section(envelope, styles, usable)

    if envelope.data_gaps:
        story.append(Paragraph("Brechas antes de invertir", styles["h2"]))
        story.append(Paragraph("Definen el siguiente trabajo; una capa ausente no equivale a riesgo cero.", styles["lede"]))
        gap_rows = [[Paragraph(h, styles["cellHead"]) for h in ("Capa o fuente", "Impacto", "Siguiente acción")]]
        for gap in envelope.data_gaps:
            gap_rows.append([Paragraph(f"<b>{_text(gap.dataset)}</b>", styles["cell"]), Paragraph(_text(gap.impact), styles["cell"]), Paragraph(_text(gap.next_action), styles["cell"])])
        story.append(_table(gap_rows, [44 * mm, (usable - 44 * mm) / 2, (usable - 44 * mm) / 2]))

    story.append(Paragraph("Método, fuentes y trazabilidad", styles["h2"]))
    significant = next((question for question in envelope.nasa_questions if question.key == "significant"), None)
    method = significant.evidence[0] if significant and significant.evidence else "Mann–Kendall corregido y pendiente de Sen sobre medias anuales."
    if baseline is not None:
        from .baseline_pdf import baseline_sources
        sources = baseline_sources(baseline)
    else:
        sources = ["NASA POWER, API Daily Point (https://power.larc.nasa.gov/docs/services/api/), estimaciones en grilla que no sustituyen mediciones en sitio."]
        checks = {check.source for site in getattr(envelope, "sites", []) for index in getattr(site, "extremes", []) for check in index.counterchecks}
        if any(source.startswith("CHIRPS") for source in checks):
            sources.append("CHIRPS v2.0 (Climate Hazards Center, UCSB) servido por NASA SERVIR ClimateSERV (https://climateserv.servirglobal.net/), "
                           "precipitación diaria a 0.05°, como contraste de los extremos.")
        if any(check.source.startswith("ERA5") for site in getattr(envelope, "sites", []) for item in getattr(site, "variables", []) for check in item.counterchecks):
            sources.append("ERA5 (ECMWF) servido por PVGIS 5.3 del JRC de la Comisión Europea (https://re.jrc.ec.europa.eu/api/v5_3/MRcalc), "
                           "temperatura a 2 m e irradiación global horizontal mensuales 2005–2023, como contraste de MERRA-2 y CERES.")
    if envelope.terrain:
        dois = sorted({granule.doi_url for site in envelope.terrain.sites for granule in site.granules})
        sources.append(f"{envelope.terrain.dataset}: {', '.join(dois)}.")
    used = sorted({value for stage in envelope.pipeline for value in stage.provenance} | {value for question in envelope.nasa_questions for value in question.provenance})
    provenance_lines = [f"<font name='{MONO}' size='7'>{value}</font>: {_text(PROVENANCE_TEXT.get(Provenance(value), value))}" for value in used]
    story += [
        Paragraph(f"<b>Método.</b> {_text(method)}", styles["body"]), Spacer(1, 2 * mm),
        Paragraph("<b>Fuentes.</b> " + " ".join(_text(source) for source in sources), styles["body"]), Spacer(1, 2 * mm),
        Paragraph("<b>Procedencia usada en este reporte.</b> " + "; ".join(provenance_lines) + ".", styles["body"]), Spacer(1, 2 * mm),
        Paragraph(f"<b>Alcance.</b> {_text(envelope.disclaimer)}", styles["body"]), Spacer(1, 3 * mm),
        Paragraph(f"Análisis {_text(envelope.analysis_id)} · contrato C2 v{_text(envelope.contract_version)} · reporte generado {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · huella SHA-256 del contenido:", styles["cellMuted"]),
        Paragraph(digest, styles["mono"]),
    ]

    doc.build(story, onFirstPage=_decorate(envelope, digest[:12]), onLaterPages=_decorate(envelope, digest[:12]))
    return buffer.getvalue()
