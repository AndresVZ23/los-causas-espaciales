"""Cómo se declara una capa oficial que no respondió hoy y se muestra desde su última copia válida (ADR-044).

El conector entrega la copia con su fecha original y el motivo (`stale_note`). Aquí se convierte en una brecha con
procedencia `CACHED_DATA`: el dato se usa, pero quien decide debe saber que no se pudo volver a verificar.
"""

from ..connectors.peru.territory import LAYERS
from ..schemas.analysis import Provenance
from ..schemas.screening import DataGap

SUFFIX = "última copia válida"


def stale_gap(source_id: str, note: str, *, dataset: str | None = None, organization: str | None = None) -> DataGap:
    layer = LAYERS.get(source_id)
    name = dataset or (layer.dataset if layer else source_id)
    owner = organization or (layer.organization if layer else "la entidad")
    return DataGap(
        dataset=f"{name} · {SUFFIX}", status=Provenance.CACHED, impact=note,
        next_action=f"Volver a consultar cuando el servicio de {owner} responda. Si ahora exige credenciales, gestionarlas con la entidad; "
                    "mientras tanto, confirmar la vigencia de la copia antes de decidir.",
    )
