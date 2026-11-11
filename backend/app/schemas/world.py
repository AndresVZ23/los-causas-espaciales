"""Contratos del alcance global: alertas activas en el mundo y búsqueda de lugares."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .analysis import Provenance

AlertKind = Literal["cyclone", "flood", "drought", "earthquake", "volcano", "wildfire", "storm", "landslide", "other"]
AlertLevel = Literal["red", "orange", "green", "none"]


class WorldAlert(BaseModel):
    """Un evento natural publicado por su fuente. El nivel es el de GDACS; EONET no publica niveles."""

    id: str
    source: Literal["GDACS", "NASA EONET"]
    kind: AlertKind
    kind_label: str
    level: AlertLevel
    title: str
    place: str
    started: date
    updated: date
    current: bool = Field(description="La fuente lo marca como vigente; EONET solo lista eventos abiertos.")
    latitude: float
    longitude: float
    severity: str | None = Field(default=None, description="Magnitud en palabras de la fuente.")
    url: str
    also_seen_by: list[str] = Field(default_factory=list, description="Otra fuente que publica un evento del mismo tipo, cerca y en las mismas fechas.")
    in_peru: bool = False


class WorldSource(BaseModel):
    name: str
    organization: str
    url: str
    provenance: Provenance
    downloaded_at: datetime | None
    note: str


class WorldAlertsResponse(BaseModel):
    generated_at: datetime
    window_days: int
    alerts: list[WorldAlert]
    sources: list[WorldSource]
    method: list[str]
    disclaimer: str


class Place(BaseModel):
    name: str
    detail: str = Field(description="Región y país, en palabras del geocodificador.")
    country_code: str | None
    latitude: float
    longitude: float
    population: int | None = None


class PlaceSearchResponse(BaseModel):
    query: str
    places: list[Place]
    source: str
    provenance: Provenance
    downloaded_at: datetime
    note: str
