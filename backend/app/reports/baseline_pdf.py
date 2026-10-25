"""Sección del reporte ejecutivo para la línea base ambiental y patrimonial (módulos 4 y 5).

Presenta, por área de estudio, lo que el sobre común no lleva: los indicadores MODIS con su tendencia, el
cambio de cobertura y las capas oficiales por medio de la línea base, con los registros en palabras de la
fuente y sus enlaces. No calcula nada: transcribe el resultado con su procedencia.
"""

from xml.sax.saxutils import quoteattr

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph

from ..schemas.baseline import BaselineLayer, BaselineScreeningResponse, SubjectBaseline
from .executive_pdf import _table, _text

COMPONENT_LABELS = {"fisico": "Medio físico", "biologico": "Medio biológico", "sociocultural": "Medio sociocultural"}
EVIDENCE_STRONG = 0.01
MAX_HIGHLIGHTS = 6


def _evidence(significant: bool, adjusted: float | None) -> str:
    if not significant or adjusted is None:
        return "Insuficiente"
    return "Fuerte" if adjusted < EVIDENCE_STRONG else "Moderada"


def _signed(value: float, digits: int) -> str:
    return f"{'+' if value > 0 else '−' if value < 0 else ''}{abs(value):.{digits}f}"


def _link(label: str, url: str | None) -> str:
    # El enlace lo publica la propia fuente (p. ej. el PDF de un DAS); solo se aceptan direcciones https.
    if url and url.startswith("https://"):
        return f"<link href={quoteattr(url)} color='#0e7c6e'>{_text(label)}</link>"
    return f"<b>{_text(label)}</b>"


def _vegetation(item: SubjectBaseline, styles: dict[str, ParagraphStyle], usable: float) -> list:
    if not item.vegetation:
        return []
    rows = [[Paragraph(h, styles["cellHead"]) for h in ("Indicador MODIS", "Media", "Pendiente Sen", "Cambio", "p BH", "Evidencia")]]
    for variable in item.vegetation:
        series = variable.annual_series
        years = series[-1].year - series[0].year if len(series) > 1 else 0
        slope = variable.trend.slope_per_year
        percent = variable.unit == "percent_cover"
        change = "N/D" if slope is None else f"{_signed(slope * years, 1)} {'pts' if percent else variable.display_unit}"
        rows.append([
            Paragraph(f"<b>{_text(variable.label)}</b><br/><font size='6.8' color='#5b6670'>{_text(variable.source.dataset)} · {series[0].year}–{series[-1].year}</font>", styles["cell"]),
            Paragraph(_text(f"{variable.mean:.{1 if percent else 3}f} {variable.display_unit}"), styles["mono"]),
            Paragraph(_text("N/D" if slope is None else f"{_signed(slope, 3)}/año"), styles["mono"]),
            Paragraph(_text(change), styles["mono"]),
            Paragraph("N/D" if variable.adjusted_p_value is None else f"{variable.adjusted_p_value:.3f}", styles["mono"]),
            Paragraph(_evidence(variable.significant_after_bh, variable.adjusted_p_value), styles["cell"]),
        ])
    return [_table(rows, [56 * mm, 26 * mm, 26 * mm, 22 * mm, 14 * mm, usable - 144 * mm])]


def _land_cover(item: SubjectBaseline, styles: dict[str, ParagraphStyle], usable: float) -> list:
    cover = item.land_cover
    if cover is None:
        return []
    rows = [[Paragraph(h, styles["cellHead"]) for h in ("Cobertura IGBP (MCD12Q1)", str(cover.first_year), str(cover.last_year))]]
    rows += [[Paragraph(_text(entry.label), styles["cell"]), Paragraph(f"{entry.first_percent:.1f} %", styles["mono"]), Paragraph(f"{entry.last_percent:.1f} %", styles["mono"])]
             for entry in cover.classes[:6]]
    return [
        _table(rows, [usable - 50 * mm, 25 * mm, 25 * mm]),
        Paragraph(_text(f"Cambió de clase el {cover.changed_percent:.1f} % de {cover.pixels} píxeles de 500 m. {cover.limitations[0]}"), styles["cellMuted"]),
    ]


def _layer_cell(layer: BaselineLayer, styles: dict[str, ParagraphStyle]) -> Paragraph:
    if layer.status != "READY":
        return Paragraph(_text(layer.limitations[0] if layer.limitations else "El servicio no respondió."), styles["cellMuted"])
    if not layer.highlights:
        return Paragraph("Sin registros devueltos; no prueba ausencia.", styles["cellMuted"])
    lines = []
    for highlight in layer.highlights[:MAX_HIGHLIGHTS]:
        count = f" ×{highlight.count}" if highlight.count > 1 else ""
        detail = f" <font size='6.8' color='#5b6670'>· {_text(highlight.detail)}</font>" if highlight.detail else ""
        lines.append(f"{_link(highlight.label, highlight.link)}{count}{detail}")
    hidden = len(layer.highlights) - MAX_HIGHLIGHTS
    if hidden > 0:
        lines.append(f"<font size='6.8' color='#5b6670'>y {hidden} grupo(s) más en el JSON exportado</font>")
    return Paragraph("<br/>".join(lines), styles["cell"])


def _layers(item: SubjectBaseline, components: list[str], styles: dict[str, ParagraphStyle], usable: float) -> list:
    out: list = []
    for component in components:
        layers = [layer for layer in item.layers if layer.component == component]
        if not layers:
            continue
        rows = [[Paragraph(_text(COMPONENT_LABELS.get(component, component)), styles["cellHead"]), Paragraph("Registros", styles["cellHead"]),
                 Paragraph("Lo que registra la fuente", styles["cellHead"])]]
        for layer in layers:
            count = "No disponible" if layer.status != "READY" or layer.intersection_count is None else f"{layer.intersection_count}{'+' if layer.truncated else ''}"
            rows.append([
                Paragraph(f"<b>{_text(layer.dataset)}</b><br/><font size='6.8' color='#5b6670'>{_text(layer.organization)}</font>", styles["cell"]),
                Paragraph(_text(count), styles["mono"]),
                _layer_cell(layer, styles),
            ])
        out.append(_table(rows, [58 * mm, 20 * mm, usable - 78 * mm]))
    return out


def baseline_sections(result: BaselineScreeningResponse, styles: dict[str, ParagraphStyle], usable: float) -> list:
    environment = result.sector == "environment"
    story: list = [
        Paragraph("Línea base por área de estudio", styles["h2"]),
        Paragraph(_text(
            "Indicadores satelitales indirectos (MODIS) y capas oficiales ordenados como la línea base de un EIA. "
            "Una capa sin registros no prueba ausencia; una capa que no respondió se informa como no disponible."
            if environment else
            "Registros del Ministerio de Cultura en palabras de la fuente. Cero registros no prueba ausencia de patrimonio; "
            "nada de esto es opinión legal ni sustituye el CIRA."), styles["lede"]),
    ]
    for item in result.baselines:
        window = f" · ventana MODIS ±{item.modis_window_km} km · {item.modis_pixels.get('MOD44B', 0)} píxeles de 250 m" if item.modis_window_km else ""
        head = [
            Paragraph(_text(f"{item.subject} · {item.area_km2:,.2f} km²"), styles["h3"]),
            Paragraph(_text(f"{item.origin}{window}"), styles["cellMuted"]),
        ]
        blocks = _vegetation(item, styles, usable) + _land_cover(item, styles, usable)
        blocks += [Paragraph(_text(note), styles["cellMuted"]) for note in [*item.vegetation_notes, *item.errors]]
        blocks += _layers(item, result.components, styles, usable)
        # El encabezado del área viaja con su primer bloque: no queda huérfano al pie de una página.
        story.append(KeepTogether(head + blocks[:1]))
        story += blocks[1:]
    if result.method_notes:
        story.append(Paragraph("Método de la línea base", styles["h3"]))
        story += [Paragraph(_text(f"{index}. {note}"), styles["cell"]) for index, note in enumerate(result.method_notes, start=1)]
    return story


def baseline_sources(result: BaselineScreeningResponse) -> list[str]:
    """Fuentes para el pie del reporte: las que de verdad se consultaron, no NASA POWER."""
    organizations = sorted({layer.organization for item in result.baselines for layer in item.layers})
    sources = []
    if any(item.vegetation or item.land_cover for item in result.baselines):
        sources.append("NASA ORNL DAAC · MODIS Web Service (https://modis.ornl.gov/rst/api/v1/): MOD44B, MOD17A3HGF y MCD12Q1, productos anuales.")
    if organizations:
        sources.append(f"Capas oficiales consultadas por intersección espacial: {', '.join(organizations)}.")
    return sources
