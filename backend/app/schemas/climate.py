"""Contratos del módulo de inteligencia climática (sector `climate` del sobre C2)."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, TrendResult
from .territory import TerritoryLevel
# Acuerdo y contraste viven en pipeline.py (también los usan las variables anuales); se reexportan aquí.
from .pipeline import Agreement, ExtremeCountercheck, VariableSummary  # noqa: F401
from .screening import AnnualObservation, ScreeningEnvelope, Sector


class AtypicalYear(BaseModel):
    """Valor anual marcado para revisión por su z robusto; sigue dentro del análisis."""

    year: int
    value: float
    robust_z: float
    countercheck_value: float | None = Field(default=None, description="Mismo índice y año según la fuente de contraste (GPM IMERG).")
    countercheck_values: dict[str, float] = Field(default_factory=dict, description="Mismo índice y año en cada fuente de contraste (IMERG, CHIRPS…).")


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
    countercheck: ExtremeCountercheck | None = Field(default=None, description="Primer contraste (GPM IMERG); se conserva por compatibilidad.")
    counterchecks: list[ExtremeCountercheck] = Field(default_factory=list, description="Todos los contrastes independientes (IMERG, CHIRPS…).")


class CellTrend(BaseModel):
    """Tendencia de una variable en una celda NASA POWER del territorio (Hamed–Rao + BH entre celdas)."""

    cell_id: str
    center: Point
    bounds: tuple[float, float, float, float] = Field(description="Oeste, sur, este, norte de la celda (WGS84).")
    weight: float = Field(description="Peso por área de intersección con el territorio.")
    variable: str
    direction: str
    slope_per_year: float | None
    p_value: float | None
    adjusted_p_value: float | None
    significant: bool
    valid_years: int


class TerritoryInfo(BaseModel):
    level: TerritoryLevel
    ubigeo: str
    name: str
    area_km2: float
    mode: Literal["REGIONAL", "POINT"] = Field(description="POINT: el territorio es menor que una celda y se analiza como punto.")
    cells: int
    coverage_percent: float
    grid_degrees: tuple[float, float] | None
    geometry: dict[str, Any] = Field(description="Límite simplificado del IGN (referencia web, no catastral).")
    source: str = "IGN · COD-AB Perú vía OCHA/HDX (CC BY-IGO); trazos de 2015"


class ClimateSiteResult(BaseModel):
    location: Point
    variables: list[VariableSummary]
    extremes: list[ExtremeIndexSummary]
    wet_day_p95_mm: float | None = Field(description="Percentil 95 de los días húmedos del período, umbral de R95P.")
    territory: TerritoryInfo | None = None
    cell_trends: list[CellTrend] = Field(default_factory=list)


class TerritoryRef(BaseModel):
    level: TerritoryLevel
    ubigeo: str = Field(pattern=r"^\d{2}(\d{2})?(\d{2})?$")


class ClimateScreeningRequest(BaseModel):
    sites: list[Point] = Field(default_factory=list, max_length=4)
    territories: list[TerritoryRef] = Field(default_factory=list, max_length=4)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_period(self):
        if not 1 <= len(self.sites) + len(self.territories) <= 4:
            raise ValueError("Se analizan entre 1 y 4 sujetos en total, entre sitios y territorios.")
        if len({(item.level, item.ubigeo) for item in self.territories}) != len(self.territories):
            raise ValueError("Hay territorios repetidos.")
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
