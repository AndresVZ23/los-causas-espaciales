"""Contracts for area-weighted NASA POWER sampling of user and official geometries."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .analysis import Observation, Point, SourceMetadata

PowerVariable = Literal["T2M", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN", "WS10M"]


class SpatialSamplingRequest(BaseModel):
    subject: dict[str, Any]
    variable: PowerVariable
    start_date: date
    end_date: date
    corridor_buffer_km: float = Field(default=1, gt=0, le=25)

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        if (self.end_date - self.start_date).days > 366 * 30:
            raise ValueError("regional sampling is limited to 30 years per request")
        return self


class SamplingSubject(BaseModel):
    kind: str
    name: str
    origin: str
    geometry_type: str
    area_km2: float | None = None
    corridor_buffer_km: float | None = None


class PowerCellSeries(BaseModel):
    cell_id: str
    center: Point
    bounds: tuple[float, float, float, float]
    overlap_area_km2: float = Field(gt=0)
    weight: float = Field(gt=0, le=1)
    observations: list[Observation]


class SpatialAggregateObservation(BaseModel):
    timestamp: date
    value: float
    dispersion_stddev: float = Field(ge=0)
    minimum: float
    maximum: float
    contributing_cells: int = Field(ge=1)


class SpatialSamplingResponse(BaseModel):
    mode: Literal["POINT", "REGIONAL"]
    subject: SamplingSubject
    variable: PowerVariable
    unit: str
    request_bounds: tuple[float, float, float, float] | None = None
    grid_spacing_degrees: tuple[float, float] | None = None
    spatial_coverage_percent: float
    cells: list[PowerCellSeries]
    aggregate: list[SpatialAggregateObservation]
    source: SourceMetadata
    method: str
    limitations: list[str]
