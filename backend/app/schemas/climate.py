"""Contratos del módulo de inteligencia climática (sector `climate` del sobre C2)."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, TrendResult
from .pipeline import VariableSummary
from .screening import AnnualObservation, ScreeningEnvelope, Sector


class AtypicalYear(BaseModel):
    """Valor anual marcado para revisión por su z robusto; sigue dentro del análisis."""

    year: int
    value: float
    robust_z: float
    countercheck_value: float | None = Field(default=None, description="Mismo índice y año según la fuente de contraste (GPM IMERG).")


class Agreement(StrEnum):
    COINCIDE = "coincide"           # ambas fuentes significativas, misma dirección
    CONTRADICE = "contradice"       # ambas significativas, direcciones opuestas
    SIN_RESPALDO = "sin_respaldo"   # solo la fuente principal es significativa
    SOLO_CONTRASTE = "solo_contraste"
    SIN_TENDENCIA = "sin_tendencia"


class ExtremeCountercheck(BaseModel):
    """El mismo índice ETCCDI calculado con una segunda fuente independiente y su acuerdo con la principal."""

    source: str
    valid_years: int
    direction: str
    slope_per_year: float | None
    adjusted_p_value: float | None
    significant_after_bh: bool
    agreement: Agreement
    annual_series: list[AnnualObservation]


class ExtremeIndexSummary(BaseModel):
    """Índice ETCCDI anual de un sujeto. Comparte los nombres de campo de `VariableSummary` para reutilizar el análisis común."""

    variable: str = Field(description="Código ETCCDI: RX1DAY, RX5DAY, R95P, PRCPTOT, R10MM o CDD.")
    label: str
    description: str
    unit: str
    display_unit: str
    mean: float
    minimum: float
    maximum: float
    valid_years: int
    discarded_years: int = Field(description="Años excluidos por tener menos de 90 % de días válidos.")
    trend: TrendResult
    adjusted_p_value: float | None = None
    significant_after_bh: bool = False
    annual_series: list[AnnualObservation]
    atypical_years: list[AtypicalYear] = Field(default_factory=list, description="Años con z robusto > 10, para contrastar con estaciones.")
    countercheck: ExtremeCountercheck | None = None


class ClimateSiteResult(BaseModel):
    location: Point
    variables: list[VariableSummary]
    extremes: list[ExtremeIndexSummary]
    wet_day_p95_mm: float | None = Field(description="Percentil 95 de los días húmedos del período, umbral de R95P.")


class ClimateScreeningRequest(BaseModel):
    sites: list[Point] = Field(min_length=1, max_length=4)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_date <= self.start_date:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial.")
        if (self.end_date - self.start_date).days < 365 * 10:
            raise ValueError("El análisis de extremos requiere al menos diez años de observaciones diarias.")
        if self.end_date > date.today():
            raise ValueError("La fecha final no puede estar en el futuro.")
        return self


class ClimateScreeningResponse(ScreeningEnvelope):
    """Sobre común C2 + resultados propios del módulo climático."""

    sector: Sector = Sector.CLIMATE
    sector_label: str = "Inteligencia climática"
    sites: list[ClimateSiteResult]
    method_notes: list[str]
