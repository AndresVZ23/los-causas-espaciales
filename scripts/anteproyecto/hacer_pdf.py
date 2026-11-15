"""Pone los textos de textos.py en el PDF del anteproyecto: quita el texto de los tres recuadros y escribe el nuevo.

El resto de la hoja (fondo, logo, nombres, etiquetas) no se toca: sigue siendo el PDF que exportó PowerPoint.
Medidas tomadas del original: Arial 10 pt, interlínea 12 pt, 3 pt entre párrafos, viñeta en x=137, texto con viñeta
en x=147, texto corrido en x=137, margen derecho en x=536; el bloque va centrado en vertical en su caja de texto.
Sirve también sobre un PDF ya corregido: siempre borra lo que haya dentro de las tarjetas antes de escribir.

    pip install pymupdf
    python scripts/anteproyecto/hacer_pdf.py <entrada.pdf> <salida.pdf> [--medir]

--medir solo muestra cómo parte cada línea y cuánto margen queda en cada tarjeta (máximo cómodo: 10 líneas).
ARIAL_TTF indica la fuente si no está en la ruta habitual de macOS, Windows o Linux.
"""
import os
import sys
from pathlib import Path

import pymupdf

from textos import IDEA, OBJETIVOS, RECURSOS

ARIAL = next((path for path in [os.environ.get("ARIAL_TTF"), "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf",
                                "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"] if path and Path(path).exists()), None)
if ARIAL is None:
    raise SystemExit("No se encontró Arial: indique su ruta en la variable ARIAL_TTF.")
SIZE, LEADING, GAP = 10.0, 12.0, 3.0
X_BULLET, X_TEXT, X_PLAIN, X_RIGHT = 137.0, 147.0, 137.0, 536.3
BASELINE = 10.05          # de la parte alta del bloque a la primera línea base
BLUE = (0x1D / 255, 0x2C / 255, 0x85 / 255)
BLACK = (0, 0, 0)
# Caja de texto de cada sección en puntos (del PPTX: y, alto) y tarjeta blanca que la contiene (del PDF).
BOXES = [
    ("Objetivos", OBJETIVOS, 349.9, 139.7, (124.9, 344.2, 546.6, 492.5)),
    ("Idea principal", IDEA, 509.8, 139.7, (124.9, 506.0, 546.6, 654.2)),
    ("Recursos", RECURSOS, 668.9, 143.3, (124.9, 667.8, 546.6, 816.1)),
]


def wrap(font, text, width):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if font.text_length(trial, fontsize=SIZE) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def layout(font, paragraphs):
    out = []
    for bullet, text in paragraphs:
        x = X_TEXT if bullet else X_PLAIN
        out.append((bullet, x, wrap(font, text, X_RIGHT - x)))
    return out


def main(src, dst, measure_only=False):
    doc = pymupdf.open(src)
    page = doc[0]
    font = pymupdf.Font(fontfile=ARIAL)
    report = []
    plans = []
    for name, paragraphs, top, height, card in BOXES:
        blocks = layout(font, paragraphs)
        n_lines = sum(len(lines) for _, _, lines in blocks)
        total = n_lines * LEADING + (len(blocks) - 1) * GAP
        start = top + height / 2 - total / 2
        margin_top = start - card[1]
        margin_bottom = card[3] - (start + total)
        report.append((name, n_lines, total, margin_top, margin_bottom, blocks))
        plans.append((blocks, start, card))
    for name, n_lines, total, mt, mb, blocks in report:
        print(f"== {name}: {n_lines} líneas, bloque {total:.0f} pt, margen arriba {mt:.1f} pt, abajo {mb:.1f} pt")
        for bullet, x, lines in blocks:
            for i, line in enumerate(lines):
                w = font.text_length(line, fontsize=SIZE)
                print(f"   {'•' if bullet and i == 0 else ' '} [{w:5.1f}/{X_RIGHT - x:5.1f}] {line}")
    if measure_only:
        return
    # 1. Quitar solo el texto viejo de cada tarjeta (los dibujos y las imágenes se conservan).
    for _, _, card in plans:
        rect = pymupdf.Rect(card[0] + 6, card[1] + 1, card[2] - 1, card[3] - 1)
        page.add_redact_annot(rect, fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE, text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    # 2. Escribir el texto nuevo con la misma fuente, tamaño, color y sangrías.
    blue, black = pymupdf.TextWriter(page.rect, color=BLUE), pymupdf.TextWriter(page.rect, color=BLACK)
    for blocks, start, _ in plans:
        y = start + BASELINE
        for bullet, x, lines in blocks:
            for i, line in enumerate(lines):
                if bullet and i == 0:
                    black.append((X_BULLET, y), "•", font=font, fontsize=SIZE)
                blue.append((x, y), line, font=font, fontsize=SIZE)
                y += LEADING
            y += GAP
    black.write_text(page)
    blue.write_text(page)
    doc.subset_fonts()
    doc.set_metadata({**doc.metadata, "title": "Anteproyecto · Los Causas Espaciales · NASA Space Apps 2026 Moquegua"})
    doc.save(dst, garbage=4, deflate=True)
    print("escrito:", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--medir" in sys.argv)
