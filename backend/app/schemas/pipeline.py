from datetime import date

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance, SourceMetadata, TrendResult
# Los modelos comunes viven en el contrato C2; se reexportan aquí por compatibilidad de importaciones.
from .screening import (  # noqa: F401
    AnnualObservation,
    DataGap,
    NasaQuestionAnswer,
    NasaQuestionKey,
    PipelineStage,
    PipelineStatus,
    QuestionStatus,
    ScreeningEnvelope,
    Sector,
    StageEvidence,
    TrendFinding,
)


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


class CurrentPeriod(BaseModel):
    """El año en curso (incompleto) comparado con la misma ventana del calendario en los años completos."""

    year: int
    through: date = Field(description="Último día publicado por la fuente.")
    days: int
    value: float = Field(description="Media diaria del año en curso hasta `through`.")
    baseline_mean: float = Field(description="Media de la misma ventana (1 de enero a `through`) en los años completos.")
    baseline_years: str
    anomaly: float
    anomaly_percent: float | None = Field(description="None en escalas de intervalo, como la temperatura en °C.")
    rank: int = Field(description="Posición del año en curso entre todos los años de la ventana, de mayor a menor.")
    years_compared: int


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
    last_valid_date: date | None = Field(default=None, description="Último día con dato publicado por la fuente (latencia del proveedor).")
    current_period: CurrentPeriod | None = None


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


class SolarScreeningResponse(ScreeningEnvelope):
    """Sobre común C2 + campos propios del piloto solar."""

    sector: Sector = Sector.SOLAR
    sector_label: str = "Energía solar fotovoltaica"
    sites: list[SolarSiteResult]
    comparative_findings: list[str]
    assumptions: SolarAssumptions
