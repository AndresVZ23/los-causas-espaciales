"""Typed contract for the backend-only K3 real-estate screening pilot."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance
from .pipeline import VariableSummary
from .screening import ScreeningEnvelope, Sector
from .territory import TerritoryLevel


class RealEstateAssumptions(BaseModel):
    """Commercial inputs supplied by the user; none are inferred from NASA or public layers."""

    developable_fraction: float = Field(default=0.55, gt=0, le=1)
    floor_area_ratio: float = Field(default=1.0, gt=0, le=10)
    sale_price_usd_m2: float = Field(default=850, gt=0)
    construction_cost_usd_m2: float = Field(default=480, ge=0)
    land_cost_usd_m2: float = Field(default=90, ge=0)
    mitigation_cost_usd_m2_land: float = Field(default=12, ge=0)
    selling_cost_fraction: float = Field(default=0.05, ge=0, lt=1)
    annual_absorption_fraction: float = Field(default=0.25, gt=0, le=1)
    discount_rate: float = Field(default=0.12, gt=-1, le=1)
    horizon_years: int = Field(default=8, ge=1, le=30)
    sale_price_sensitivity: float = Field(default=0.20, ge=0, lt=1)
    construction_cost_sensitivity: float = Field(default=0.20, ge=0, lt=1)
    land_cost_sensitivity: float = Field(default=0.25, ge=0, lt=1)
    mitigation_cost_sensitivity: float = Field(default=0.30, ge=0, lt=1)
    absorption_sensitivity: float = Field(default=0.10, ge=0, lt=1)
    discount_rate_sensitivity: float = Field(default=0.02, ge=0, lt=0.5)


class RealEstateTerritoryReference(BaseModel):
    level: TerritoryLevel
    ubigeo: str = Field(pattern=r"^\d{2}(\d{2})?(\d{2})?$")


class RealEstateSiteInput(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    geometry: dict[str, Any] | None = None
    territory: RealEstateTerritoryReference | None = None

    @model_validator(mode="after")
    def exactly_one_geometry_source(self):
        if (self.geometry is None) == (self.territory is None):
            raise ValueError("Cada terreno requiere geometry o territory, pero no ambos.")
        return self


class RealEstateScreeningRequest(BaseModel):
    sites: list[RealEstateSiteInput] = Field(min_length=1, max_length=12)
    start_date: date
    end_date: date
    include_territorial_layers: bool = True
    assumptions: RealEstateAssumptions = Field(default_factory=RealEstateAssumptions)

    @model_validator(mode="after")
    def validate_screening(self):
        if self.end_date <= self.start_date:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial.")
        if (self.end_date - self.start_date).days < 365 * 5:
            raise ValueError("El piloto inmobiliario requiere al menos cinco años de observaciones.")
        if self.end_date > date.today():
            raise ValueError("La fecha final no puede estar en el futuro.")
        ids = [item.id for item in self.sites]
        labels = [item.label for item in self.sites]
        if len(ids) != len(set(ids)) or len(labels) != len(set(labels)):
            raise ValueError("Los terrenos deben tener id y etiqueta únicos.")
        return self


class RealEstateSiteSource(BaseModel):
    subject: str
    origin: str
    dataset: str
    source_url: str | None = None
    license: str | None = None
    source_created: date | None = None
    provenance: Provenance
    limitations: list[str]


class RealEstateCellMetric(BaseModel):
    cell_id: str
    center: Point
    weight: float
    mean_precipitation_mm_day: float | None
    rx1day_mm: float | None


class RealEstateSpatialExposure(BaseModel):
    period: str
    unit: str
    mode: str
    cell_count: int
    spatial_coverage_percent: float
    mean_precipitation_mm_day: float | None
    rx1day_mm: float | None
    p99_precipitation_mm_day: float | None
    cells: list[RealEstateCellMetric]
    provenance: Provenance
    source_url: str
    method: str
    limitations: list[str]


class RealEstateTerritorialSourceSummary(BaseModel):
    source_id: str
    status: str
    intersection_count: int | None
    provenance: Provenance
    downloaded_at: datetime | None
    limitations: list[str]
    stale_note: str | None = None   # la fuente no respondió hoy: se muestra su última copia válida (motivo y fecha)


class RealEstateTerritorialEvidence(BaseModel):
    subject: str
    sources: list[RealEstateTerritorialSourceSummary]


class RealEstateFinancialProjection(BaseModel):
    land_area_m2: float
    developable_area_m2: float
    saleable_floor_area_m2: float
    land_acquisition_usd: float
    initial_mitigation_usd: float
    projected_revenue_usd: float
    projected_construction_cost_usd: float
    projected_selling_cost_usd: float
    sold_fraction_within_horizon: float
    npv_usd: float
    cash_flows_usd: list[float]
    model_provenance: Provenance = Provenance.MODEL
    assumption_provenance: Provenance = Provenance.ASSUMPTION
    formula: str
    limitations: list[str]


class RealEstateSiteResult(BaseModel):
    subject_id: str
    label: str
    representative_point: Point
    area_km2: float
    variables: list[VariableSummary]
    spatial_exposure: RealEstateSpatialExposure | None
    terrain_slope_degrees: float | None
    territorial_intersections: dict[str, int | None]
    finance: RealEstateFinancialProjection
    opportunities: list[str]
    cautions: list[str]


class RealEstateScreeningResponse(ScreeningEnvelope):
    sector: Sector = Sector.REAL_ESTATE
    sector_label: str = "Desarrollo inmobiliario"
    site_sources: list[RealEstateSiteSource]
    sites: list[RealEstateSiteResult]
    territorial_evidence: list[RealEstateTerritorialEvidence]
    assumptions: RealEstateAssumptions
