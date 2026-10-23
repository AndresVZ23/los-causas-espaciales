"""Contrato del puntaje multicriterio (común a todos los sectores; campo aditivo `scorecard` del sobre C2)."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from .analysis import Provenance


class Direction(StrEnum):
    HIGHER_IS_BETTER = "mayor_es_mejor"
    LOWER_IS_BETTER = "menor_es_mejor"


class Criterion(BaseModel):
    """Un criterio con su escala de referencia declarada: `worst` puntúa 0 y `best` puntúa 100, con recorte fuera del rango."""

    key: str
    label: str
    unit: str
    direction: Direction
    weight: float = Field(ge=0, le=1)
    worst: float
    best: float
    provenance: Provenance = Field(description="Procedencia del valor medido o estimado del criterio.")
    basis: str = Field(description="De dónde sale el valor y por qué esa escala de referencia.")

    @model_validator(mode="after")
    def check_scale(self):
        if self.worst == self.best:
            raise ValueError(f"La escala de {self.key} necesita extremos distintos.")
        if (self.direction == Direction.HIGHER_IS_BETTER) != (self.best > self.worst):
            raise ValueError(f"La escala de {self.key} contradice su dirección.")
        return self


class SubjectValues(BaseModel):
    subject: str
    values: dict[str, float | None] = Field(description="Valor por criterio; None si el dato no está disponible.")


class ScorecardRequest(BaseModel):
    criteria: list[Criterion] = Field(min_length=1, max_length=20)
    subjects: list[SubjectValues] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def check_weights(self):
        total = sum(item.weight for item in self.criteria)
        if abs(total - 1) > 1e-3:
            raise ValueError(f"Los pesos deben sumar 1 (suman {total:.3f}).")
        keys = [item.key for item in self.criteria]
        if len(set(keys)) != len(keys):
            raise ValueError("Hay criterios repetidos.")
        return self


class CriterionScore(BaseModel):
    key: str
    value: float | None
    score: float | None = Field(description="0–100 en la escala de referencia; None si falta el dato.")
    contribution: float | None = Field(description="Aporte al puntaje total, en puntos, con los pesos renormalizados por cobertura.")


class SubjectScore(BaseModel):
    subject: str
    score: float | None = Field(description="0–100; None si ningún criterio tiene dato.")
    coverage: float = Field(description="Fracción del peso con dato disponible (0–1).")
    rank: int | None
    first_place_share: float = Field(description="Fracción de combinaciones de pesos aleatorias en que el sujeto queda primero.")
    criteria: list[CriterionScore]


class WeightSensitivity(BaseModel):
    """Qué pasa con el primer lugar al bajar y subir a la mitad y al 150 % el peso de un criterio (el resto se renormaliza)."""

    key: str
    leader_at_half: str | None
    leader_at_one_and_half: str | None
    changes_leader: bool


class Scorecard(BaseModel):
    method: str
    criteria: list[Criterion]
    subjects: list[SubjectScore]
    leader: str | None
    margin: float | None = Field(description="Puntos entre el primero y el segundo; None con un solo sujeto con puntaje.")
    tie: bool = Field(description="Empate práctico: margen < 5 puntos o líder primero en menos del 75 % de las combinaciones de pesos.")
    stability_draws: int
    weight_sensitivity: list[WeightSensitivity]
    notes: list[str]
