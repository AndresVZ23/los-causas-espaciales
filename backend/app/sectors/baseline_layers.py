"""Capas oficiales de la línea base por medio (físico, biológico, sociocultural) y su lectura en palabras de la fuente.

Solo se resumen atributos que la propia fuente publica (nombre, categoría, resolución, enlace); no se infiere nada
que el servicio no diga. Una capa sin intersecciones se informa con su advertencia: cero registros no es cero recurso.
"""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from ..schemas.baseline import BaselineLayer, Component, LayerHighlight
from ..schemas.data_sources import TerritorialSourceResult

COMPONENT_SOURCES: dict[Component, list[str]] = {
    "fisico": ["ana-water-bodies", "ana-hydro-units"],
    "biologico": ["sernanp-anp", "minam-ecosystems", "minam-vegetation-cover", "minam-coastal-lomas", "minam-ramsar"],
    "sociocultural": [
        "cultura-archaeology", "cultura-archaeology-declared", "cultura-ciras", "cultura-das", "cultura-qhapaq-nan",
        "cultura-cultural-landscape", "cultura-world-heritage", "cultura-prior-consultation", "cultura-citizen-records",
    ],
}
MAX_HIGHLIGHTS = 12


def _text(value: Any) -> str:
    return " ".join(str(value).split()) if value not in (None, "") else ""


def _title(value: Any) -> str:
    text = _text(value)
    return text.title() if text.isupper() else text


def _day(value: Any) -> str:
    # ArcGIS publica fechas como milisegundos desde 1970 (UTC).
    if isinstance(value, (int, float)) and value > 10**11:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return _text(value)


def _join(*parts: Any) -> str | None:
    text = " · ".join(part for part in (_text(p) for p in parts) if part)
    return text or None


def _link(value: Any) -> str | None:
    text = _text(value)
    return text if text.startswith("https://") else None


Reader = Callable[[dict[str, Any], int], tuple[str, str | None, str | None]]

READERS: dict[str, Reader] = {
    "cultura-archaeology": lambda a, _: (_text(a.get("nombre")), _join(a.get("clasificac"), _title(a.get("distrito"))), None),
    "cultura-archaeology-declared": lambda a, _: (_text(a.get("nombre_map")), _join(a.get("resolucion"), _day(a.get("fecha_resol"))), None),
    "cultura-ciras": lambda a, _: (f"CIRA {_text(a.get('cira'))}".strip(), _join(a.get("proyecto"), a.get("anio")), _link(a.get("enlace"))),
    "cultura-das": lambda a, _: (_text(a.get("proyecto")), _join(a.get("cod_das_informe") or a.get("cod_das_inicio"), a.get("categoria"),
                                                                  _day(a.get("fecha_informe") or a.get("fecha_inicio"))), _link(a.get("enlace"))),
    "cultura-qhapaq-nan": lambda a, layer: (("Proyección de camino: " if layer == 1 else "") + _text(a.get("tramnomb")),
                                            _join(a.get("stranomb"), a.get("seccnomb")), None),
    "cultura-cultural-landscape": lambda a, _: (_text(a.get("nombre_pc")), _join(a.get("tipo"), a.get("estado_sit")), None),
    "cultura-world-heritage": lambda a, _: (_text(a.get("nombre")), None, None),
    "cultura-prior-consultation": lambda a, _: (f"{_title(a.get('nombdist'))} ({_title(a.get('nombprov'))})", f"Código de tipo {_text(a.get('tipo'))}", None),
    "cultura-citizen-records": lambda a, _: (_text(a.get("nombre_bien")) or "Bien sin nombre", _join("Reporte ciudadano", _day(a.get("fecha"))), None),
    "sernanp-anp": lambda a, _: (_text(a.get("anp_nomb")), _join(a.get("anp_cate"), a.get("anp_suleg")), None),
    "minam-ecosystems": lambda a, _: (_text(a.get("eco_detall")), None, None),
    "minam-vegetation-cover": lambda a, _: (_text(a.get("CobVeg2013")), None, None),
    "minam-coastal-lomas": lambda a, _: (f"Lomas en {_title(a.get('nombdist'))}", _join(_title(a.get("nombprov")), _title(a.get("nombdep"))), None),
    "minam-ramsar": lambda a, _: (_text(a.get("NOMBRE")), _text(a.get("D_LEGAL")) or None, None),
    "ana-water-bodies": lambda a, _: (_text(a.get("NOMBRE_CA")), _join(a.get("CATEGORIA"), a.get("NOMBRE_UH")), None),
    "ana-hydro-units": lambda a, _: (_text(a.get("NOMBRE")), _join(f"código {_text(a.get('CODIGO'))}" if a.get("CODIGO") else "", a.get("NOMB_UH_N3")), None),
}


def _generic(attributes: dict[str, Any], _layer: int) -> tuple[str, str | None, str | None]:
    name = next((_text(v) for k, v in attributes.items() if ("nomb" in k.lower() or "name" in k.lower()) and _text(v)), "")
    return name or "Registro sin nombre publicado", None, None


def _readable(limitations: list[str]) -> list[str]:
    # Un corte de conexión llega sin mensaje («…utilizables: »); se dice qué pasó en vez de dejar la frase colgando.
    if limitations and limitations[0].rstrip().endswith(":"):
        return [f"{limitations[0].rstrip()} el servidor cortó la conexión o no respondió a tiempo; reintente más tarde.", *limitations[1:]]
    return limitations


def summarize_layer(result: TerritorialSourceResult, component: Component) -> BaselineLayer:
    reader = READERS.get(result.source_id, _generic)
    groups: dict[tuple[str, str | None], LayerHighlight] = {}
    for feature in result.features:
        label, detail, link = reader(feature.attributes, feature.layer_id)
        label = label or "Registro sin nombre publicado"
        key = (label, detail)
        if key in groups:
            groups[key].count += 1
        else:
            groups[key] = LayerHighlight(label=label, detail=detail, link=link)
    highlights = sorted(groups.values(), key=lambda item: (-item.count, item.label))[:MAX_HIGHLIGHTS]
    return BaselineLayer(
        source_id=result.source_id, organization=result.organization, dataset=result.dataset, component=component,
        status=result.status, intersection_count=result.intersection_count,
        truncated=any("superó 100 objetos" in note for note in result.limitations),
        highlights=highlights, provenance=result.provenance, downloaded_at=result.downloaded_at,
        source_url=result.source_url, limitations=_readable(result.limitations),
    )
