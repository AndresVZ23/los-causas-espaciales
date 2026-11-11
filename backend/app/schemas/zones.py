"""Contrato de las «zonas para explorar»: una maqueta en bloques de un lugar real, con lo que la plataforma sabe de él."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

BeaconKind = Literal["evento", "amenaza", "pista_falsa", "oportunidad", "infraestructura", "brecha"]


class ZoneFigure(BaseModel):
    label: str
    value: str


class ZoneBeacon(BaseModel):
    """Un punto de la maqueta donde la plataforma tiene algo que decir, con su cifra, sus fuentes y qué mirar primero."""

    id: str
    kind: BeaconKind
    title: str
    body: str
    figures: list[ZoneFigure] = Field(default_factory=list)
    sources: list[str]
    second_source: str | None = Field(default=None, description="Qué dice la segunda fuente independiente, si la hay.")
    look_first: str = Field(description="Qué conviene mirar o estudiar primero; no es una orden de qué construir.")
    latitude: float
    longitude: float
    placement: str = Field(description="Por qué la baliza está en ese punto de la maqueta.")


class ZonePath(BaseModel):
    label: str
    coordinates: list[tuple[float, float]] = Field(description="Longitud y latitud, en orden.")
    source: str


class ZoneSource(BaseModel):
    name: str
    use: str
    license: str
    url: str


class ZoneSummary(BaseModel):
    id: str
    name: str
    country: str
    tagline: str
    latitude: float
    longitude: float
    size_km: float
    built_at: datetime


class Zone(ZoneSummary):
    bounds: tuple[float, float, float, float] = Field(description="Oeste, sur, este, norte (WGS84).")
    grid: int = Field(description="Celdas por lado; las matrices van por filas de norte a sur.")
    cell_m: float
    vertical_exaggeration: float
    base_elevation_m: float = Field(description="Elevación real del bloque cero.")
    min_elevation_m: float
    max_elevation_m: float
    heights_b64: str = Field(description="Altura de cada columna en bloques (uint16 little-endian, base64).")
    cover_b64: str = Field(description="Clase ESA WorldCover de cada celda (uint8, base64); 0 = sin dato.")
    slope_b64: str = Field(description="Pendiente real en grados enteros (uint8, base64), antes de exagerar el relieve.")
    beacons: list[ZoneBeacon]
    paths: list[ZonePath] = Field(default_factory=list)
    sources: list[ZoneSource]
    notes: list[str]
