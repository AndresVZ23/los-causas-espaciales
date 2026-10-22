from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance, SourceMetadata, TrendResult
from .terrain import TerrainResponse


class PipelineStatus(StrEnum):
    COMPLETED = "COMPLETADO"
    PARTIAL = "PARCIAL"
    READY = "LISTO"
    UNAVAILABLE = "NO_DISPONIBLE"
    ERROR = "ERROR"


NasaQuestionKey = Literal["what", "where", "how_much", "significant", "so_what"]


class QuestionStatus(StrEnum):
    ANSWERED = "RESPONDIDA"
    PARTIAL = "PARCIAL"
    INSUFFICIENT = "EVIDENCIA_INSUFICIENTE"


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


class StageEvidence(BaseModel):
    label: str
    value: str
    provenance: Provenance | None = None


class PipelineStage(BaseModel):
    step: int
    key: str
    name: str
    status: PipelineStatus
    summary: str
    provenance: list[Provenance]
    evidence: list[StageEvidence] = Field(default_factory=list)
    duration_ms: float | None = Field(default=None, description="Tiempo medido en el servidor; None si la etapa no ejecuta cálculo propio.")
    answers: list[NasaQuestionKey] = Field(default_factory=list, description="Preguntas del reto NASA que esta etapa sustenta.")


class TrendFinding(BaseModel):
    """Una tendencia que conserva significancia tras Benjamini–Hochberg."""

    site: str
    variable: str
    label: str
    unit: str
    slope_per_year: float
    confidence_interval: tuple[float, float] | None
    first_year: int
    last_year: int
    change_over_period: float
    change_percent_of_mean: float | None = Field(description="None en escalas de intervalo, como la temperatura en °C.")
    p_value: float
    p_value_modified: float | None = None
    adjusted_p_value: float
    variance_correction: float | None = None
    autocorrelation_lag1: float | None
    autocorrelation_lag1_detrended: float | None = None


class NasaQuestionAnswer(BaseModel):
    key: NasaQuestionKey
    question: str
    question_es: str
    status: QuestionStatus
    answer: str
    evidence: list[str]
    provenance: list[Provenance]
    stage_steps: list[int]


class AnnualObservation(BaseModel):
    year: int
    value: float


class VariableSummary(BaseModel):
    variable: str
    label: str
    mean: float
    minimum: float
    maximum: float
    unit: str
    display_unit: str
    valid_observations: int
    completeness_percent: float
    annual_variability_percent: float | None
    trend: TrendResult
    adjusted_p_value: float | None = None
    significant_after_bh: bool = False
    source: SourceMetadata
    annual_series: list[AnnualObservation]


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
    nasa_questions: list[NasaQuestionAnswer] = Field(default_factory=list)
    trend_findings: list[TrendFinding] = Field(default_factory=list)
    sites: list[SolarSiteResult]
    terrain: TerrainResponse | None = None
    comparative_findings: list[str]
    data_gaps: list[DataGap]
    assumptions: SolarAssumptions
    disclaimer: str
