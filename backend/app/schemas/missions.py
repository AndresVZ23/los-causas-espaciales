"""Contrato de las misiones del «modo jugador»: lugares del mundo con su análisis climático real, ya construido."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..missions import rules

Continent = Literal["Sudamérica", "Norteamérica", "Europa", "Asia", "África", "Oceanía", "Antártida"]
HeatClass = Literal["calienta", "enfria", "sin_evidencia"]
HeatSupport = Literal["confirmada", "contradicha", "una_fuente", "sin_segunda_fuente"]
Direction = Literal["increasing", "decreasing", "no_trend"]


class YearValue(BaseModel):
    year: int
    value: float | None


class SecondSource(BaseModel):
    source: str
    agreement: str | None = Field(default=None, description=(
        "Código de la plataforma (schemas/pipeline.py), en los años comunes de las dos fuentes: coincide = ambas significativas y en el "
        "mismo sentido; contradice = ambas significativas y en sentidos opuestos; sin_respaldo = solo la principal (NASA POWER) es "
        "significativa; solo_contraste = solo la segunda fuente lo es; sin_tendencia = ninguna de las dos."))
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


class AirTrend(MissionTrend):
    """Aerosoles en la columna de aire sobre la celda de NASA POWER (AOD_55, adimensional). No es la calidad del aire a nivel de calle."""

    dataset: str = Field(description="Producto y fuente, p. ej. «NASA POWER · AOD_55 (fuente CERES SYN1deg)».")
    provenance: Literal["REAL_DATA", "CACHED_DATA", "MODEL_ESTIMATE", "USER_ASSUMPTION", "ILLUSTRATIVE_DEMO", "DATA_UNAVAILABLE"]
    source_url: str = Field(pattern=r"^https?://\S+$")
    downloaded_at: datetime | None = None
    note: str | None = None


class MissionExtreme(BaseModel):
    variable: str
    label: str
    unit: str | None
    direction: Direction
    slope_per_year: float | None
    significant: bool


class FlaggedExtreme(BaseModel):
    """Un año atípico de un índice de lluvia con el valor del mismo año en los productos de contraste.

    Que esté marcado no lo vuelve un artefacto: varios corresponden a eventos reales que el satélite también registró.
    Solo `probable_artifact` lo dice, con la regla de la plataforma. `unit` y `probable_artifact` los calcula `Mission`
    al validar, a partir de los valores crudos; lo que traiga el archivo en esos dos campos se descarta.
    """

    variable: str
    label: str
    unit: str | None = Field(default=None, description="Unidad del índice («mm» o «días»), tomada de `extremes` de la misma misión. None si el índice no está en esa lista.")
    year: int
    value: float | None
    countercheck_values: dict[str, float | None] = Field(default_factory=dict)
    probable_artifact: bool = Field(default=False, description=(
        "Regla de ADR-036, la misma de rainfall_discoveries: el índice está en mm, hay valores de contraste y el reanálisis supera "
        "al menos ARTIFACT_RATIO veces a cada producto de contraste."))


class ContextSource(BaseModel):
    """Fuente externa que respalda el texto de contexto de una misión."""

    title: str = Field(min_length=1)
    url: str = Field(pattern=r"^https?://\S+$")


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
    context: str = Field(description="Texto de referencia escrito por el equipo; la plataforma no lo mide. Sus fuentes externas van en `context_sources`.")
    context_sources: list[ContextSource] = Field(default_factory=list, description="Fuentes externas del texto de contexto. Vacía: texto del equipo sin fuente enlazada.")
    not_measured: str = Field(description="Lo que la plataforma no mide en este lugar: una brecha declarada, nunca un cero.")
    scale: Literal["ciudad", "paisaje"] = Field(default="ciudad", description="Ciudad: se baja a nivel de calle con edificios; paisaje: vista amplia.")
    hazard: Literal["huaico", "avalancha", "inundacion", "erupcion", "calor", "aire"] | None = Field(default=None, description=(
        "Peligro principal del juego (evento simulado inspirado en el riesgo real del lugar). «aire»: calidad del aire; el mundo 3D no "
        "simula un evento y el reto es la contaminación cotidiana (ADR-050)."))
    heat: HeatClass
    heat_support: HeatSupport | None = Field(default=None, description=(
        "Respaldo de la segunda fuente a la clase de `heat`, según `temperature.second_source.agreement`: coincide → confirmada; "
        "contradice → contradicha; sin segunda fuente → sin_segunda_fuente; cualquier otro código → una_fuente. None si `heat` es sin_evidencia."))
    temperature: MissionTrend | None
    rain: MissionTrend | None
    sun: MissionTrend | None
    air: AirTrend | None = Field(default=None, description=(
        "Solo en misiones de aire: aerosoles en la columna (AOD a 550 nm) de NASA POWER. Se prueba aparte de las variables de clima "
        "(familia de una prueba, alfa 0,05), así no cambia la significancia de temperatura, lluvia ni sol."))
    extremes: list[MissionExtreme] = Field(default_factory=list)
    flagged_extremes: list[FlaggedExtreme] = Field(default_factory=list)
    analysis: MissionAnalysis

    @model_validator(mode="after")
    def _derive_from_raw_values(self) -> "Mission":
        # Estos tres campos se calculan siempre aquí, también si el archivo ya los trae: así el JSON construido antes de
        # que existieran sirve sin reconstruir y ningún archivo puede contradecir la regla de la plataforma.
        units = {item.variable: item.unit for item in self.extremes}
        for flag in self.flagged_extremes:
            flag.unit = units.get(flag.variable)
            flag.probable_artifact = rules.is_probable_artifact(flag.unit, flag.value, flag.countercheck_values)
        second = self.temperature.second_source if self.temperature else None
        self.heat_support = rules.heat_support(self.heat, second.agreement if second else None)
        return self


class MissionTerrain(BaseModel):
    """Terreno 3D de una misión tal como lo escribe scripts/missions/build_terrain.py. Valida el archivo; la ruta lo sirve sin cambios."""

    id: str
    size_km: float = Field(gt=0)
    grid: int = Field(gt=0, description="Celdas por lado.")
    cell_m: float = Field(gt=0)
    bounds: tuple[float, float, float, float] = Field(description="Oeste, sur, este, norte (WGS84).")
    base_elevation_m: float
    max_elevation_m: float
    relief_dm: str = Field(description="Base64 de grid × grid enteros uint16 little-endian: decímetros sobre el punto más bajo.")
    cover: str = Field(description="Base64 de grid × grid bytes: clase de ESA WorldCover; 0 = sin cobertura.")
    cover_share: dict[int, float]
    missing_cells: int = Field(ge=0, description="Celdas sin elevación en la fuente: se declaran, no se dan por cero.")
    sea_assumed: bool = Field(description="Suposición visual declarada: celdas sin cobertura y a nivel del mar pintadas como agua.")
    dem_tiles: list[str]
    dem_missing: list[str]
    cover_tiles: list[str]
    cover_missing: list[str]
    sources: list[dict[str, str]] = Field(min_length=1)
    built_at: datetime

    @model_validator(mode="after")
    def _grids_match_declared_size(self) -> "MissionTerrain":
        # Un archivo truncado o de otra grilla se rechaza aquí en vez de llegar al navegador como un terreno deforme.
        # Largo en base64 de n bytes: 4 × ⌈n / 3⌉; no hace falta decodificar.
        cells = self.grid * self.grid
        for name, text, size in (("relief_dm", self.relief_dm, cells * 2), ("cover", self.cover, cells)):
            if len(text) != 4 * ((size + 2) // 3):
                raise ValueError(f"{name} no corresponde a una grilla de {self.grid} × {self.grid}")
        return self


class MissionsResponse(BaseModel):
    built_at: datetime = Field(description=(
        "Última vez que el guion escribió el archivo con análisis nuevos. No es la fecha de cada análisis: esa es "
        "`analysis.generated_at` de cada misión, y las que se conservan de una construcción anterior mantienen la suya."))
    method: str
    missions: list[Mission]
