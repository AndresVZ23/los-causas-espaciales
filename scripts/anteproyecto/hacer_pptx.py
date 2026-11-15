"""Pone los textos corregidos en el PowerPoint fuente del anteproyecto, conservando el formato de cada párrafo.

    pip install python-pptx
    python scripts/anteproyecto/hacer_pptx.py <entrada.pptx> <salida.pptx>

Cada caja («Texto Objetivos», «Texto Idea principal», «Texto Recursos») tiene párrafos de un solo tramo de texto. Se
clona el primer párrafo de la caja (con sus viñetas, sangrías, fuente y color) una vez por párrafo nuevo y solo se
cambia el texto: así el estilo es exactamente el de la plantilla.
"""
import copy
import sys

from pptx import Presentation

from textos import SECCIONES

NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def main(src, dst):
    deck = Presentation(src)
    slide = deck.slides[0]
    done = set()
    for shape in slide.shapes:
        paragraphs = SECCIONES.get(shape.name)
        if paragraphs is None:
            continue
        body = shape.text_frame._txBody
        existing = body.findall(f"{NS}p")
        template = existing[0]
        runs = template.findall(f"{NS}r")
        if len(runs) != 1:
            raise SystemExit(f"{shape.name}: se esperaba un solo tramo por párrafo y hay {len(runs)}")
        for old in existing:
            body.remove(old)
        for _, text in paragraphs:
            para = copy.deepcopy(template)
            para.find(f"{NS}r").find(f"{NS}t").text = text
            body.append(para)
        done.add(shape.name)
    missing = set(SECCIONES) - done
    if missing:
        raise SystemExit(f"No se encontraron las cajas: {sorted(missing)}")
    deck.save(dst)
    check = Presentation(dst)
    for shape in check.slides[0].shapes:
        if shape.name in SECCIONES:
            texts = [p.text for p in shape.text_frame.paragraphs]
            assert texts == [t for _, t in SECCIONES[shape.name]], shape.name
            print(f"{shape.name}: {len(texts)} párrafos")
    print("escrito:", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
