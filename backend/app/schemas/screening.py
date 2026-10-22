"""Contrato común de screening por sector (C2, versión 1.0).

Todo sector (solar, vial, inmobiliario) responde con un `ScreeningEnvelope`: el pipeline de nueve etapas,
las preguntas del reto NASA, las tendencias significativas, el relieve, las brechas y los supuestos se leen
igual en todos, de modo que la interfaz, el reporte PDF y el asistente no dependen del sector.
Los campos propios de cada sector se agregan al heredar el sobre. Los cambios son solo aditivos;
un cambio incompatible exige un ADR y subir `contract_version`.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from .analysis import Point, Provenance
from .terrain import TerrainResponse

CONTRACT_VERSION = "1.0"


class Sector(StrEnum):
    CLIMATE = "climate"
    SOLAR = "solar"
    ROAD = "road"
    REAL_ESTATE = "real_estate"


class PipelineStatus(StrEnum):
    COMPLETED = "COMPLETADO"
    PARTIAL = "PARCIAL"
    READY = "LISTO"
    UNAVAILABLE = "NO_DISPONIBLE"
    ERROR = "ERROR"


NasaQuestionKey = Literal["what", "where", "how_much", "significant", "so_what"]
NASA_QUESTION_ORDER: tuple[NasaQuestionKey, ...] = ("what", "where", "how_much", "significant", "so_what")
STAGE_KEYS = ("selection", "configuration", "extraction", "analysis", "territorial", "evaluation", "finance", "results", "export")


class QuestionStatus(StrEnum):
    ANSWERED = "RESPONDIDA"
    PARTIAL = "PARCIAL"
    INSUFFICIENT = "EVIDENCIA_INSUFICIENTE"


class SubjectKind(StrEnum):
    POINT = "point"
    SEGMENT = "segment"
    POLYGON = "polygon"


class StudySubject(BaseModel):
    """Unidad que se analiza y se compara: un sitio, un tramo de corredor o un terreno."""

    id: str
    label: str
    kind: SubjectKind
    geometry: dict[str, Any] = Field(description="Geometría GeoJSON RFC 7946 (WGS84, longitud-latitud).")
    representative_point: Point = Field(description="Punto donde se consultan NASA POWER y NASADEM para este sujeto.")


class AssumptionItem(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    provenance: Provenance = Provenance.ASSUMPTION


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


class AnnualObservation(BaseModel):
    year: int
    value: float


class TrendFinding(BaseModel):
    """Una tendencia que conserva significancia tras Benjamini–Hochberg."""

    site: str = Field(description="Etiqueta del sujeto de estudio (sitio, tramo o terreno).")
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
    annual_series: list[AnnualObservation] = Field(default_factory=list, description="Medias anuales en unidades de presentación; permite graficar sin datos del sector.")


class NasaQuestionAnswer(BaseModel):
    key: NasaQuestionKey
    question: str
    question_es: str
    status: QuestionStatus
    answer: str
    evidence: list[str]
    provenance: list[Provenance]
    stage_steps: list[int]


class DataGap(BaseModel):
    dataset: str
    status: Provenance = Provenance.UNAVAILABLE
    impact: str
    next_action: str


class ScreeningEnvelope(BaseModel):
    contract_version: Literal["1.0"] = CONTRACT_VERSION
    analysis_id: str
    generated_at: datetime
    sector: Sector
    sector_label: str
    title: str
    period: str
    subjects: list[StudySubject] = Field(min_length=1)
    pipeline: list[PipelineStage]
    nasa_questions: list[NasaQuestionAnswer]
    trend_findings: list[TrendFinding]
    terrain: TerrainResponse | None = None
    data_gaps: list[DataGap]
    assumption_items: list[AssumptionItem]
    disclaimer: str
