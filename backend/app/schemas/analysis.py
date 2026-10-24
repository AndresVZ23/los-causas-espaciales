from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Provenance(StrEnum):
    REAL = "REAL_DATA"
    CACHED = "CACHED_DATA"
    MODEL = "MODEL_ESTIMATE"
    ASSUMPTION = "USER_ASSUMPTION"
    DEMO = "ILLUSTRATIVE_DEMO"
    UNAVAILABLE = "DATA_UNAVAILABLE"


class Point(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: str | None = Field(default=None, max_length=120)


class AnalysisRequest(BaseModel):
    location: Point
    variable: Literal["T2M", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN", "WS10M"] = "T2M"
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def dates_are_valid(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if (self.end_date - self.start_date).days < 365 * 3:
            raise ValueError("at least three years are required for trend analysis")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        return self


class Observation(BaseModel):
    timestamp: date
    value: float


class TrendResult(BaseModel):
    method: str
    direction: Literal["increasing", "decreasing", "no_trend", "insufficient_evidence"]
    slope_per_year: float | None
    p_value: float | None = Field(description="Mann-Kendall clásico (Kendall tau); se conserva para trazabilidad.")
    p_value_modified: float | None = Field(default=None, description="Mann-Kendall con varianza corregida de Hamed y Rao (1998); gobierna la significancia.")
    variance_correction: float | None = Field(default=None, description="Factor n/n* aplicado a Var(S); 1 si no hay autocorrelación significativa sin tendencia.")
    confidence_interval: tuple[float, float] | None
    significant: bool
    alpha: float = 0.05
    valid_observations: int
    autocorrelation_lag1: float | None = Field(default=None, description="Lag-1 de los valores brutos; incluye el efecto de la propia tendencia.")
    autocorrelation_lag1_detrended: float | None = Field(default=None, description="Lag-1 de los rangos sin tendencia, usado por la corrección.")
    interpretation: str
    limitations: list[str]


class SourceMetadata(BaseModel):
    source_id: str
    dataset: str
    version: str
    variable: str
    unit: str
    temporal_resolution: str
    spatial_resolution: str
    downloaded_at: datetime
    source_url: str
    provenance: Provenance
    quality_notes: list[str] = Field(default_factory=list, description="Verificaciones o correcciones aplicadas a la respuesta del proveedor.")


class AnalysisResponse(BaseModel):
    analysis_id: str
    location: Point
    period: str
    observations: list[Observation]
    trend: TrendResult
    source: SourceMetadata


class FinanceRequest(BaseModel):
    initial_capex: float = Field(gt=0)
    annual_revenue: float = Field(ge=0)
    annual_opex: float = Field(ge=0)
    mitigation_capex: float = Field(default=0, ge=0)
    annual_interruption_cost: float = Field(default=0, ge=0)
    discount_rate: float = Field(gt=-1, le=1)
    horizon_years: int = Field(ge=1, le=100)


class FinanceResponse(BaseModel):
    npv: float
    cash_flows: list[float]
    provenance: Provenance = Provenance.ASSUMPTION
    note: str


class GeometryRequest(BaseModel):
    geometry: dict[str, Any]


class GeometryResponse(BaseModel):
    geometry_type: Literal["Point", "LineString", "Polygon", "MultiPolygon"]
    centroid: Point
    bounding_box: tuple[float, float, float, float]
    length_km: float | None = None
    area_km2: float | None = None
    vertex_count: int
    provenance: Provenance = Provenance.MODEL
    method: str
    limitations: list[str]


class ComparisonRequest(BaseModel):
    sites: list[Point] = Field(min_length=2, max_length=5)
    variable: Literal["T2M", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN", "WS10M"] = "T2M"
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def comparison_is_valid(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if (self.end_date - self.start_date).days < 365 * 3:
            raise ValueError("at least three years are required for comparison")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        return self


class SiteComparisonResult(BaseModel):
    analysis_id: str
    location: Point
    mean: float
    minimum: float
    maximum: float
    valid_observations: int
    completeness_percent: float
    trend: TrendResult
    adjusted_p_value: float | None = None
    significant_after_bh: bool = False
    provenance: Provenance


class ComparisonResponse(BaseModel):
    variable: str
    unit: str
    period: str
    sites: list[SiteComparisonResult]
    note: str
