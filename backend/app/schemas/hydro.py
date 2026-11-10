"""Contrato del piloto hidroeléctrico de pasada: sobre común C2 + caudal (GloFAS con GEOGLOWS), salto (NASADEM con
Copernicus), energía y finanzas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance
from .pipeline import AnnualObservation, VariableSummary
from .screening import ScreeningEnvelope, Sector

FlowVerdict = Literal["coinciden", "intermedio", "difieren", "no_comparable"]


class HydroSite(BaseModel):
    """Un aprovechamiento: la toma sobre el río y la casa de máquinas aguas abajo."""

    label: str = Field(min_length=1, max_length=120)
    intake: Point = Field(description="Toma (bocatoma) sobre el río; aquí se lee el caudal.")
    powerhouse: Point = Field(description="Casa de máquinas; el salto es la diferencia de elevación con la toma.")
    design_flow_m3s: float | None = Field(default=None, gt=0, le=10_000, description="Caudal de diseño propio del sitio; si se declara, manda sobre la excedencia.")


class HydroAssumptions(BaseModel):
    design_exceedance_percent: float = Field(default=30, ge=5, le=95, description="El caudal de diseño es el aprovechable excedido este % del tiempo.")
    ecological_flow_fraction: float = Field(default=0.10, ge=0, le=0.5, description="Fracción del caudal medio que se deja siempre en el río.")
    min_turbine_flow_fraction: float = Field(default=0.20, ge=0, le=0.9, description="Mínimo técnico como fracción del caudal de diseño.")
    efficiency: float = Field(default=0.87, gt=0.3, le=0.95, description="Turbina, generador y transformador.")
    head_loss_fraction: float = Field(default=0.05, ge=0, lt=0.5, description="Pérdidas de carga en la conducción.")
    availability: float = Field(default=0.95, gt=0.3, le=1, description="Disponibilidad por mantenimiento y salidas.")
    capex_usd_per_mw: float = Field(default=2_500_000, gt=0)
    opex_fraction_of_capex: float = Field(default=0.025, ge=0, le=0.2)
    energy_price_usd_mwh: float = Field(default=55, ge=0)
    mitigation_capex_usd: float = Field(default=0, ge=0)
    discount_rate: float = Field(default=0.10, gt=-1, le=1)
    horizon_years: int = Field(default=30, ge=1, le=50)
    price_sensitivity: float = Field(default=0.20, ge=0, lt=1, description="Variación relativa del precio (±).")
    capex_sensitivity: float = Field(default=0.20, ge=0, lt=1, description="Variación relativa del CAPEX por MW (±).")
    opex_sensitivity: float = Field(default=0.20, ge=0, lt=1, description="Variación relativa del OPEX (±).")
    discount_rate_sensitivity: float = Field(default=0.02, ge=0, lt=0.5, description="Variación absoluta de la tasa de descuento (±).")


class HydroScreeningRequest(BaseModel):
    sites: list[HydroSite] = Field(min_length=1, max_length=4)
    start_date: date
    end_date: date
    assumptions: HydroAssumptions = Field(default_factory=HydroAssumptions)

    @model_validator(mode="after")
    def validate_screening(self):
        if self.end_date <= self.start_date:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial.")
        if (self.end_date - self.start_date).days < 365 * 5:
            raise ValueError("El piloto hidroeléctrico requiere al menos cinco años de caudal.")
        if self.end_date > date.today():
            raise ValueError("La fecha final no puede estar en el futuro.")
        labels = [site.label.strip() for site in self.sites]
        if len(set(labels)) != len(labels):
            raise ValueError("Cada sitio necesita un nombre distinto.")
        return self


class FlowDurationPoint(BaseModel):
    exceedance_percent: float
    flow_m3s: float


class HydroFlowCell(BaseModel):
    """La celda de GloFAS que se usó y por qué (regla del cauce)."""

    latitude: float
    longitude: float
    distance_km: float = Field(description="Del punto de la toma al centro de la celda usada.")
    moved: bool = Field(description="True si el cauce del modelo no pasa por la celda de la toma y se usó una vecina.")
    point_cell_mean_m3s: float | None
    used_cell_mean_m3s: float
    neighborhood_max_m3s: float
    scan_year: int


class HydroHead(BaseModel):
    """Salto bruto entre la toma y la casa de máquinas, con el modelo de elevación usado y el de contraste."""

    source: str
    intake_elevation_m: float
    powerhouse_elevation_m: float
    gross_head_m: float
    second_source: str | None = None
    second_gross_head_m: float | None = None
    gap_m: float | None = Field(default=None, description="Salto del contraste − salto usado.")
    gap_percent: float | None = None
    conduction_km: float = Field(description="Distancia geodésica entre toma y casa de máquinas: longitud mínima de la conducción.")
    mean_slope_percent: float
    provenance: Provenance
    limitations: list[str]


class HydroResource(BaseModel):
    """Recurso hídrico en la toma (GloFAS) y la central de pasada que resulta con los supuestos del usuario."""

    period: str = Field(description="Años completos usados en la curva de duración y la energía.")
    days: int
    mean_flow_m3s: float
    firm_flow_m3s: float = Field(description="Caudal del río excedido el 95 % del tiempo.")
    ecological_flow_m3s: float
    design_flow_m3s: float
    design_basis: str
    min_turbine_flow_m3s: float
    flow_duration: list[FlowDurationPoint] = Field(description="Curva de duración del caudal del río, sin descontar el ecológico.")
    net_head_m: float
    capacity_mw: float
    plant_factor: float = Field(description="Caudal turbinado medio ÷ caudal de diseño, antes de la disponibilidad.")
    annual_plant_factors: list[AnnualObservation]
    cell: HydroFlowCell
    source: str
    source_url: str
    provenance: Provenance
    downloaded_at: datetime


class HydroFlowCheck(BaseModel):
    """El caudal medio según la segunda fuente (GEOGLOWS) frente a GloFAS, en los años comunes."""

    source: str
    river_id: int
    nearest_river_id: int
    candidates: int = Field(description="Tramos de río distintos evaluados alrededor de la toma.")
    period: str
    mean_m3s: float
    primary_mean_m3s: float
    ratio: float | None = Field(description="Segunda fuente ÷ GloFAS.")
    gap_percent: float | None
    verdict: FlowVerdict
    plant_factor_at_second: float | None = Field(description="Factor de planta si el caudal fuera el de la segunda fuente; None si no es comparable.")
    annual_energy_mwh_at_second: float | None
    provenance: Provenance
    downloaded_at: datetime
    source_url: str
    limitations: list[str]


class HydroFinancialProjection(BaseModel):
    capacity_mw: float
    plant_factor_net: float
    annual_energy_mwh: float
    initial_capex_usd: float
    annual_opex_usd: float
    annual_revenue_usd: float
    npv_usd: float
    cash_flows_usd: list[float]
    model_provenance: Provenance = Provenance.MODEL
    assumption_provenance: Provenance = Provenance.ASSUMPTION
    formula: str
    limitations: list[str]


class HydroSiteResult(BaseModel):
    location: Point = Field(description="La toma, con el nombre del sitio: es su punto representativo.")
    powerhouse: Point
    relative_position: int
    relative_position_text: str
    variables: list[VariableSummary]
    head: HydroHead
    resource: HydroResource
    flow_check: HydroFlowCheck | None = Field(default=None, description="None si la segunda fuente no respondió; nunca ceros.")
    finance: HydroFinancialProjection
    opportunities: list[str]
    cautions: list[str]


class HydroScreeningResponse(ScreeningEnvelope):
    """Sobre común C2 + campos propios del piloto hidroeléctrico."""

    sector: Sector = Sector.HYDRO
    sector_label: str = "Energía hidroeléctrica"
    sites: list[HydroSiteResult]
    comparative_findings: list[str]
    assumptions: HydroAssumptions
