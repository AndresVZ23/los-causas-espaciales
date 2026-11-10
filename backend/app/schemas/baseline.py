"""Línea base territorial para debida diligencia (módulos 4 y 5): insumos para estudios de impacto ambiental.

Ordena la evidencia como la línea base de un EIA peruano —medio físico, biológico y sociocultural— sin
sustituirla: cada capa conserva su fuente, su fecha y sus límites, y una ausencia de registros no es ausencia
del recurso, del ecosistema ni del patrimonio.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance
from .climate import ExtremeIndexSummary, TerritoryRef
from .pipeline import VariableSummary
from .screening import ScreeningEnvelope

Component = Literal["fisico", "biologico", "sociocultural", "amenazas"]


class BaselineGeometry(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    label: str = Field(min_length=1, max_length=80)
    geometry: dict[str, Any] = Field(description="GeoJSON RFC 7946 (WGS84 longitud-latitud): Polygon, MultiPolygon, LineString o MultiLineString.")


class BaselineRequest(BaseModel):
    sites: list[Point] = Field(default_factory=list, max_length=4, description="Puntos; se estudia un círculo de radio buffer_km.")
    territories: list[TerritoryRef] = Field(default_factory=list, max_length=4)
    geometries: list[BaselineGeometry] = Field(default_factory=list, max_length=4, description="Polígonos o corredores del usuario; las líneas se amplían con buffer_km.")
    buffer_km: float = Field(default=1.0, ge=0.25, le=10)

    @model_validator(mode="after")
    def validate_subjects(self):
        total = len(self.sites) + len(self.territories) + len(self.geometries)
        if not 1 <= total <= 4:
            raise ValueError("Se analizan entre 1 y 4 áreas en total, entre sitios, territorios y geometrías.")
        if len({(item.level, item.ubigeo) for item in self.territories}) != len(self.territories):
            raise ValueError("Hay territorios repetidos.")
        return self


class LayerHighlight(BaseModel):
    """Un registro (o grupo de registros iguales) devuelto por la capa, en palabras de la fuente."""

    label: str
    count: int = 1
    detail: str | None = None
    link: str | None = Field(default=None, description="Documento público citado por la propia fuente (p. ej. el PDF de un DAS).")


class BaselineLayer(BaseModel):
    source_id: str
    organization: str
    dataset: str
    component: Component
    status: Literal["READY", "DATA_UNAVAILABLE"]
    intersection_count: int | None
    truncated: bool = Field(description="La fuente devolvió más de 100 objetos; el conteo no es exhaustivo.")
    highlights: list[LayerHighlight]
    provenance: Provenance
    downloaded_at: datetime | None
    source_url: str
    limitations: list[str]
    stale_note: str | None = Field(default=None, description="La fuente no respondió hoy y se muestra su última copia válida: motivo y fecha de la copia.")


class LandCoverClass(BaseModel):
    code: int
    label: str
    first_percent: float
    last_percent: float


class LandCoverChange(BaseModel):
    product: str = "MCD12Q1 · clasificación IGBP (LC_Type1)"
    first_year: int
    last_year: int
    pixels: int
    changed_percent: float = Field(description="Porcentaje de píxeles cuya clase cambió entre el primer y el último año.")
    classes: list[LandCoverClass]
    provenance: Provenance
    downloaded_at: datetime
    source_url: str
    limitations: list[str]


class LandCoverShare(BaseModel):
    code: int
    label: str
    percent: float


class CoverGroupCheck(BaseModel):
    """Un grupo de cobertura comparable entre MOD44B (fracción por píxel) y WorldCover (clase dominante por píxel)."""

    variable: Literal["VCF_TREE", "VCF_NONTREE", "VCF_BARE"]
    label: str
    modis_percent: float | None = Field(description="MOD44B del mismo año, promedio del área; None si ese año no tiene dato.")
    worldcover_percent: float


class LandCoverCrosscheck(BaseModel):
    """ESA WorldCover (10 m) sobre la misma ventana del análisis MODIS, como fuente independiente de cobertura."""

    source: str
    year: int
    pixels: int
    resolution_m: float
    classes: list[LandCoverShare]
    groups: list[CoverGroupCheck]
    provenance: Provenance
    downloaded_at: datetime
    source_urls: list[str]
    limitations: list[str]


class SubjectBaseline(BaseModel):
    subject: str
    origin: str = Field(description="Cómo se definió el área: sitio con radio, territorio IGN o geometría del usuario.")
    area_km2: float
    study_area: dict[str, Any] = Field(description="Polígono GeoJSON usado para consultar capas y filtrar píxeles.")
    modis_window_km: int | None = None
    modis_pixels: dict[str, int] = Field(default_factory=dict, description="Píxeles MODIS dentro del área, por producto.")
    vegetation: list[VariableSummary] = Field(default_factory=list)
    vegetation_notes: list[str] = Field(default_factory=list)
    land_cover: LandCoverChange | None = None
    land_cover_check: LandCoverCrosscheck | None = Field(default=None, description="Contraste ESA WorldCover; None si no se pudo leer, nunca ceros.")
    climate: list[VariableSummary] = Field(default_factory=list, description="Módulo 3: lluvia anual NASA POWER en el punto representativo.")
    extremes: list[ExtremeIndexSummary] = Field(default_factory=list, description="Módulo 3: índices ETCCDI con contrastes GPM IMERG y CHIRPS.")
    wet_day_p95_mm: float | None = None
    layers: list[BaselineLayer] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class BaselineScreeningResponse(ScreeningEnvelope):
    components: list[Component]
    baselines: list[SubjectBaseline]
    method_notes: list[str]
