"""Contrato de las misiones del «modo jugador»: lugares del mundo con su análisis climático real, ya construido."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Continent = Literal["Sudamérica", "Norteamérica", "Europa", "Asia", "África", "Oceanía", "Antártida"]
HeatClass = Literal["calienta", "enfria", "sin_evidencia"]
Direction = Literal["increasing", "decreasing", "no_trend"]


class YearValue(BaseModel):
    year: int
    value: float | None


class SecondSource(BaseModel):
    source: str
    agreement: str | None = Field(default=None, description="Regla de la plataforma: coincide, sin_tendencia, solo_contraste, etc.")
    period: str | None = None


class MissionTrend(BaseModel):
    """Tendencia de una variable de NASA POWER en el lugar, tal como la devolvió /projects/climate-screening."""

    label: str
    unit: str | None
    mean: float | None
    direction: Direction
    slope_per_year: float | None
    confidence_interval: tuple[float, float] | None = None
    p_value_adjusted: float | None
    significant: bool = Field(description="Significativa tras Benjamini–Hochberg entre las variables del lugar.")
    valid_years: int | None
    annual_series: list[YearValue] = Field(default_factory=list)
    second_source: SecondSource | None = None


class MissionExtreme(BaseModel):
    variable: str
    label: str
    unit: str | None
    direction: Direction
    slope_per_year: float | None
    significant: bool


class FlaggedExtreme(BaseModel):
    """Un año atípico de lluvia extrema que los productos satelitales contrastan (posible artefacto)."""

    variable: str
    label: str
    year: int
    value: float | None
    countercheck_values: dict[str, float | None] = Field(default_factory=dict)


class MissionAnalysis(BaseModel):
    analysis_id: str | None
    generated_at: datetime | None
    period: str | None
    dataset: str | None
    version: str | None
    downloaded_at: datetime | None
    provenance: Literal["REAL_DATA", "CACHED_DATA", "MODEL_ESTIMATE", "USER_ASSUMPTION", "ILLUSTRATIVE_DEMO", "DATA_UNAVAILABLE"]
    source_url: str | None


class Mission(BaseModel):
    id: str
    continent: Continent
    country: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    context: str = Field(description="Contexto cualitativo del lugar. No es un dato de la plataforma y no lleva cifras.")
    not_measured: str = Field(description="Lo que la plataforma no mide en este lugar: una brecha declarada, nunca un cero.")
    scale: Literal["ciudad", "paisaje"] = Field(default="ciudad", description="Ciudad: se baja a nivel de calle con edificios; paisaje: vista amplia.")
    hazard: Literal["huaico", "avalancha", "inundacion", "erupcion", "calor"] | None = Field(default=None, description="Peligro principal del juego (evento simulado inspirado en el riesgo real del lugar).")
    heat: HeatClass
    temperature: MissionTrend | None
    rain: MissionTrend | None
    sun: MissionTrend | None
    extremes: list[MissionExtreme] = Field(default_factory=list)
    flagged_extremes: list[FlaggedExtreme] = Field(default_factory=list)
    analysis: MissionAnalysis


class MissionsResponse(BaseModel):
    built_at: datetime
    method: str
    missions: list[Mission]
