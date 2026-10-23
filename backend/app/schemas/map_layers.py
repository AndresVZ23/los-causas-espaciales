"""Contrato de las capas visuales del mapa (NASA GIBS): solo visualización, nunca entran en el cálculo."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class MapLayer(BaseModel):
    id: str = Field(description="Identificador corto usado por la consola.")
    label: str
    group: str
    description: str
    gibs_id: str
    tile_url: str = Field(description="Plantilla XYZ con {time}, {z}, {y} y {x}; GIBS usa fila (y) antes que columna (x).")
    max_zoom: int = Field(description="Último nivel con teselas; MapLibre amplía ese nivel al acercarse.")
    latest_date: date | None = Field(description="Fecha más reciente publicada; None si no se pudo leer el catálogo.")
    first_date: date | None
    period_days: int | None = Field(description="Paso temporal del producto (1 = diario, 16 = compuesto de 16 días).")
    legend_url: str | None
    source: str = "NASA GIBS (WMTS, EPSG:3857)"
    notice: str | None = Field(default=None, description="Advertencia visible, por ejemplo una serie detenida.")


class MapLayersResponse(BaseModel):
    layers: list[MapLayer]
    capabilities_read_at: datetime | None = Field(description="Hora UTC de la lectura de capacidades de GIBS; None si se usó el respaldo sin fechas.")
    note: str = "Capas visuales: muestran qué se ve en una fecha, no entran en ningún cálculo de la consola."
