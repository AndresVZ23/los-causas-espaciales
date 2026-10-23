"""Typed contract for the backend-only K2 road-corridor screening pilot."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance
from .pipeline import VariableSummary
from .screening import ScreeningEnvelope, Sector


class RoadAssumptions(BaseModel):
    """Commercial and disruption inputs supplied by the user, never inferred from NASA."""

    baseline_interruption_days_per_year: float = Field(default=5, ge=0, le=365)
    residual_interruption_fraction: float = Field(default=0.40, ge=0, le=1)
    cost_per_interruption_day_usd: float = Field(default=200_000, ge=0)
    mitigation_capex_usd_per_km: float = Field(default=120_000, gt=0)
    annual_maintenance_usd_per_km: float = Field(default=3_000, ge=0)
    discount_rate: float = Field(default=0.10, gt=-1, le=1)
    horizon_years: int = Field(default=15, ge=1, le=50)
    heavy_rain_threshold_mm_day: float = Field(default=20, gt=0, le=500)
    interruption_days_sensitivity: float = Field(default=0.40, ge=0, lt=1)
    cost_per_day_sensitivity: float = Field(default=0.30, ge=0, lt=1)
    capex_sensitivity: float = Field(default=0.25, ge=0, lt=1)
    maintenance_sensitivity: float = Field(default=0.25, ge=0, lt=1)
    residual_fraction_sensitivity: float = Field(default=0.15, ge=0, le=1)
    discount_rate_sensitivity: float = Field(default=0.02, ge=0, lt=0.5)


class RoadSegmentInput(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    geometry: dict[str, Any]
    expected_interruption_days_per_year: float | None = Field(
        default=None,
        ge=0,
        le=365,
        description="Optional user override; absence uses the common road assumption.",
    )
    mitigation_capex_usd: float | None = Field(
        default=None,
        gt=0,
        description="Optional user override; absence uses segment length × common CAPEX per km.",
    )


class RoadScreeningRequest(BaseModel):
    segments: list[RoadSegmentInput] | None = Field(
        default=None,
        description="One to twelve WGS84 LineStrings. None selects the public Moquegua–Ilo pilot snapshot.",
    )
    start_date: date
    end_date: date
    corridor_buffer_km: float = Field(default=1, gt=0, le=25)
    include_territorial_layers: bool = True
    assumptions: RoadAssumptions = Field(default_factory=RoadAssumptions)

    @model_validator(mode="after")
    def validate_screening(self):
        if self.end_date <= self.start_date:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial.")
        if (self.end_date - self.start_date).days < 365 * 5:
            raise ValueError("El piloto vial requiere al menos cinco años de observaciones.")
        if self.end_date > date.today():
            raise ValueError("La fecha final no puede estar en el futuro.")
        if self.segments is not None:
            if not 1 <= len(self.segments) <= 12:
                raise ValueError("El piloto vial admite entre uno y doce tramos.")
            ids = [item.id for item in self.segments]
            labels = [item.label for item in self.segments]
            if len(ids) != len(set(ids)) or len(labels) != len(set(labels)):
                raise ValueError("Los tramos deben tener id y etiqueta únicos.")
        return self


class RoadCorridorSource(BaseModel):
    name: str
    source: str
    source_url: str | None = None
    license: str | None = None
    retrieved_at: datetime | None = None
    provenance: Provenance
    limitations: list[str]


class RoadCellMetric(BaseModel):
    cell_id: str
    center: Point
    weight: float
    mean_precipitation_mm_day: float | None
    rx1day_mm: float | None


class RoadSpatialExposure(BaseModel):
    period: str
    unit: str
    cell_count: int
    spatial_coverage_percent: float
    mean_precipitation_mm_day: float | None
    rx1day_mm: float | None
    cells: list[RoadCellMetric]
    provenance: Provenance
    source_url: str
    method: str
    limitations: list[str]


class RoadTerritorialSourceSummary(BaseModel):
    source_id: str
    status: str
    intersection_count: int | None
    provenance: Provenance
    downloaded_at: datetime | None
    limitations: list[str]


class RoadTerritorialEvidence(BaseModel):
    subject: str
    sources: list[RoadTerritorialSourceSummary]


class RoadFinancialProjection(BaseModel):
    baseline_interruption_days_per_year: float
    residual_interruption_days_per_year: float
    avoided_interruption_days_per_year: float
    cost_per_interruption_day_usd: float
    annual_avoided_cost_usd: float
    mitigation_capex_usd: float
    annual_maintenance_usd: float
    npv_usd: float
    cash_flows_usd: list[float]
    model_provenance: Provenance = Provenance.MODEL
    assumption_provenance: Provenance = Provenance.ASSUMPTION
    formula: str
    limitations: list[str]


class RoadSegmentResult(BaseModel):
    subject_id: str
    label: str
    representative_point: Point
    length_km: float
    variables: list[VariableSummary]
    heavy_rain_days_per_year: float | None
    heavy_rain_years: int
    spatial_exposure: RoadSpatialExposure | None
    terrain_slope_degrees: float | None
    territorial_intersections: dict[str, int | None]
    finance: RoadFinancialProjection
    opportunities: list[str]
    cautions: list[str]


class RoadScreeningResponse(ScreeningEnvelope):
    sector: Sector = Sector.ROAD
    sector_label: str = "Infraestructura vial"
    corridor_source: RoadCorridorSource
    segments: list[RoadSegmentResult]
    territorial_evidence: list[RoadTerritorialEvidence]
    assumptions: RoadAssumptions
