from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance, SourceMetadata, TrendResult


class PipelineStatus(StrEnum):
    COMPLETED = "COMPLETADO"
    PARTIAL = "PARCIAL"
    UNAVAILABLE = "NO_DISPONIBLE"
    ERROR = "ERROR"


class SolarAssumptions(BaseModel):
    capacity_mw: float = Field(default=20, gt=0, le=10_000)
    performance_ratio: float = Field(default=0.80, gt=0, le=1)
    initial_capex_usd: float = Field(default=18_000_000, gt=0)
    annual_opex_usd: float = Field(default=360_000, ge=0)
    energy_price_usd_mwh: float = Field(default=55, ge=0)
    mitigation_capex_usd: float = Field(default=0, ge=0)
    discount_rate: float = Field(default=0.10, gt=-1, le=1)
    horizon_years: int = Field(default=20, ge=1, le=50)


class SolarScreeningRequest(BaseModel):
    sites: list[Point] = Field(min_length=2, max_length=4)
    start_date: date
    end_date: date
    assumptions: SolarAssumptions = Field(default_factory=SolarAssumptions)

    @model_validator(mode="after")
    def validate_screening(self):
        if self.end_date <= self.start_date:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial.")
        if (self.end_date - self.start_date).days < 365 * 5:
            raise ValueError("El piloto solar requiere al menos cinco años de observaciones.")
        if self.end_date > date.today():
            raise ValueError("La fecha final no puede estar en el futuro.")
        return self


class PipelineStage(BaseModel):
    step: int
    key: str
    name: str
    status: PipelineStatus
    summary: str
    provenance: list[Provenance]


class VariableSummary(BaseModel):
    variable: str
    label: str
    mean: float
    minimum: float
    maximum: float
    unit: str
    valid_observations: int
    completeness_percent: float
    annual_variability_percent: float | None
    trend: TrendResult
    adjusted_p_value: float | None = None
    significant_after_bh: bool = False
    source: SourceMetadata


class SolarFinancialProjection(BaseModel):
    specific_yield_kwh_kwp_year: float
    annual_energy_mwh: float
    annual_revenue_usd: float
    npv_usd: float
    cash_flows_usd: list[float]
    model_provenance: Provenance = Provenance.MODEL
    assumption_provenance: Provenance = Provenance.ASSUMPTION
    formula: str
    limitations: list[str]


class SolarSiteResult(BaseModel):
    location: Point
    relative_solar_position: int
    relative_position_text: str
    variables: list[VariableSummary]
    finance: SolarFinancialProjection
    opportunities: list[str]
    cautions: list[str]


class DataGap(BaseModel):
    dataset: str
    status: Provenance = Provenance.UNAVAILABLE
    impact: str
    next_action: str


class SolarScreeningResponse(BaseModel):
    analysis_id: str
    generated_at: datetime
    title: str
    sector: str = "Energía solar fotovoltaica"
    period: str
    pipeline: list[PipelineStage]
    sites: list[SolarSiteResult]
    comparative_findings: list[str]
    data_gaps: list[DataGap]
    assumptions: SolarAssumptions
    disclaimer: str
