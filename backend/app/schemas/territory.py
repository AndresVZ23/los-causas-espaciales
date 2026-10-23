"""Typed API contracts for Peru's reference administrative territories."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from .analysis import Point, Provenance

TerritoryLevel = Literal["department", "province", "district"]


class TerritorySourceMetadata(BaseModel):
    dataset: str
    source_organization: str
    publisher: str
    source_url: str
    source_sha256: str
    license: str
    source_created: date
    reviewed: date
    crs: str
    provenance: Provenance = Provenance.REAL
    warnings: list[str]


class TerritorySummary(BaseModel):
    level: TerritoryLevel
    name: str
    ubigeo: str = Field(pattern=r"^\d{2}(\d{2})?(\d{2})?$")
    pcode: str
    parent_ubigeo: str | None = None
    department: str | None = None
    province: str | None = None
    area_sqkm: float = Field(gt=0)
    center: Point


class TerritorySearchResponse(BaseModel):
    query: str
    count: int
    results: list[TerritorySummary]
    source: TerritorySourceMetadata


class TerritoryHierarchyResponse(BaseModel):
    parent: TerritorySummary | None = None
    children_level: TerritoryLevel
    count: int
    children: list[TerritorySummary]
    source: TerritorySourceMetadata


class TerritoryGeometryResponse(BaseModel):
    territory: TerritorySummary
    feature: dict[str, Any]
    crs: str
    geometry_role: Literal["web_reference_simplified"] = "web_reference_simplified"
    maximum_simplification_tolerance_metres: float
    maximum_level_area_change_percent: float
    source: TerritorySourceMetadata
    limitations: list[str]
