"""Contratos para consultar relieve NASADEM con procedencia verificable."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .analysis import Point, Provenance


class TerrainRequest(BaseModel):
    sites: list[Point] = Field(min_length=1, max_length=5)


class TerrainGranule(BaseModel):
    short_name: Literal["NASADEM_HGT", "NASADEM_SC"]
    version: str = "001"
    granule_id: str
    title: str
    tile_id: str
    bounding_box: tuple[float, float, float, float]
    updated_at: datetime
    data_url: str
    preview_url: str | None
    doi_url: str
    catalogue_url: str
    access: Literal["EARTHDATA_LOGIN_REQUIRED"] = "EARTHDATA_LOGIN_REQUIRED"


class TerrainMetrics(BaseModel):
    elevation_m: float | None = None
    slope_degrees: float | None = None
    aspect_degrees: float | None = None
    aspect_cardinal: str | None = None
    vertical_datum: str = "EGM96 geoid"


class TerrainCrosscheck(BaseModel):
    """El mismo punto en un modelo de elevación independiente de NASADEM (Copernicus GLO-30, TanDEM-X)."""

    source: str
    elevation_m: float | None
    slope_degrees: float | None = Field(description="Pendiente de Horn sobre la ventana 3 × 3 alrededor del punto.")
    vertical_datum: str = "EGM2008 geoid"
    tile_url: str
    provenance: Provenance
    downloaded_at: datetime
    limitations: list[str] = Field(default_factory=list)


class TerrainSiteResult(BaseModel):
    location: Point
    status: Literal["READY", "PENDING", "METADATA_ONLY", "PARTIAL"]
    metrics: TerrainMetrics
    granules: list[TerrainGranule]
    provenance: Provenance
    limitations: list[str]
    crosscheck: TerrainCrosscheck | None = Field(default=None, description="Contraste con Copernicus GLO-30; None si no se pudo leer, nunca ceros.")


class TerrainResponse(BaseModel):
    generated_at: datetime
    dataset: str = "NASADEM V001"
    crs: str = "EPSG:4326; longitude/latitude"
    spatial_resolution: str = "1 arc-second (~30 m at the equator)"
    sites: list[TerrainSiteResult]
    note: str
