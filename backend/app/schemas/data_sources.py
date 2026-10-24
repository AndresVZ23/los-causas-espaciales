"""Typed contracts for AppEEARS, Peruvian territorial layers, and COES labels."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance


DataStatus = Literal["READY", "PENDING", "FAILED", "DATA_UNAVAILABLE"]


class AppEEARSDateRange(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        return self


class AppEEARSPointTaskRequest(AppEEARSDateRange):
    task_name: str = Field(min_length=3, max_length=120)
    points: list[Point] = Field(min_length=1, max_length=25)


class AppEEARSAreaTaskRequest(AppEEARSDateRange):
    task_name: str = Field(min_length=3, max_length=120)
    geometry: dict[str, Any]


class AppEEARSTaskResponse(BaseModel):
    task_id: str | None = None
    status: DataStatus
    provider_status: str | None = None
    task_type: Literal["point", "area"] | None = None
    submitted_at: datetime | None = None
    checked_at: datetime
    products: list[str] = Field(default_factory=lambda: ["MOD13Q1.061", "MOD44W.061"])
    layers: list[str] = Field(default_factory=list)
    provenance: Provenance
    source_url: str
    limitations: list[str] = Field(default_factory=list)


class AppEEARSBundleFile(BaseModel):
    file_id: str
    file_name: str
    file_size: int = Field(ge=0)
    file_type: str
    sha256: str


class AppEEARSBundleResponse(BaseModel):
    task_id: str
    status: Literal["READY"] = "READY"
    files: list[AppEEARSBundleFile]
    checked_at: datetime
    provenance: Provenance
    source_url: str
    limitations: list[str] = Field(default_factory=list)


class TerritorialQueryRequest(BaseModel):
    geometry: dict[str, Any]
    source_ids: list[str] | None = Field(default=None, max_length=12)


class TerritorialFeature(BaseModel):
    layer_id: int
    layer_name: str
    attributes: dict[str, Any]


class TerritorialSourceResult(BaseModel):
    source_id: str
    organization: str
    dataset: str
    status: Literal["READY", "DATA_UNAVAILABLE"]
    intersection_count: int | None = None
    features: list[TerritorialFeature] = Field(default_factory=list)
    provenance: Provenance
    downloaded_at: datetime | None = None
    source_url: str
    crs: str
    coverage: str
    scale_or_resolution: str
    license: str
    limitations: list[str]


class TerritorialQueryResponse(BaseModel):
    generated_at: datetime
    geometry_type: Literal["Point", "LineString", "Polygon", "MultiPolygon"]
    crs: str = "EPSG:4326; longitude/latitude"
    sources: list[TerritorialSourceResult]
    note: str


class COESMonthlyRequest(BaseModel):
    start_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

    @model_validator(mode="after")
    def validate_months(self):
        start = date.fromisoformat(f"{self.start_month}-01")
        end = date.fromisoformat(f"{self.end_month}-01")
        current = date.today().replace(day=1)
        if end < start:
            raise ValueError("end_month must be on or after start_month")
        if end >= current:
            raise ValueError("COES only exposes closed months through this endpoint")
        distance = (end.year - start.year) * 12 + end.month - start.month
        if distance > 23:
            raise ValueError("at most 24 months can be requested")
        return self


class COESMonthlyObservation(BaseModel):
    month: str
    generation_mwh: float | None
    days_expected: int
    days_observed: int
    completeness_percent: float
    capacity_factor_percent: float | None = None
    provenance: Provenance
    downloaded_at: datetime


class COESCapacityReference(BaseModel):
    status: Literal["READY", "DATA_UNAVAILABLE"]
    provider_name: str | None = None
    installed_capacity_mw: float | None = None
    effective_capacity_mw: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    source_url: str
    provenance: Provenance
    limitations: list[str] = Field(default_factory=list)


class COESPlantSeries(BaseModel):
    plant: str
    companies: list[str]
    generation_type: str
    status: Literal["READY", "PARTIAL", "DATA_UNAVAILABLE"]
    capacity_reference: COESCapacityReference
    observations: list[COESMonthlyObservation]
    limitations: list[str]


class COESMonthlyResponse(BaseModel):
    generated_at: datetime
    source_id: str = "in-coes"
    dataset: str = "COES-SINAC · Producción diaria por central · Medidores"
    unit: str = "MWh"
    temporal_resolution: str = "monthly aggregation of daily metered generation"
    provenance: Provenance = Provenance.REAL
    source_url: str
    downloaded_at: datetime
    plants: list[COESPlantSeries]
    license: str
    methodology: str
    limitations: list[str]
