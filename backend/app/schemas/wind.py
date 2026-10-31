"""Contrato del piloto eólico: sobre común C2 + recurso horario, contraste con el Atlas Eólico Global y finanzas."""

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from .analysis import Point, Provenance
from .pipeline import AnnualObservation, VariableSummary
from .screening import ScreeningEnvelope, Sector


class WindAssumptions(BaseModel):
    capacity_mw: float = Field(default=50, gt=0, le=10_000)
    hub_height_m: float = Field(default=100, ge=40, le=200, description="Altura del buje; el viento de 50 m se lleva a esta altura.")
    cut_in_ms: float = Field(default=3.0, gt=0, le=10, description="Velocidad de arranque de la curva de potencia genérica.")
    rated_ms: float = Field(default=12.0, gt=0, le=25, description="Velocidad nominal: desde aquí la turbina entrega su potencia nominal.")
    cut_out_ms: float = Field(default=25.0, gt=0, le=40, description="Velocidad de parada por seguridad.")
    losses: float = Field(default=0.15, ge=0, lt=0.6, description="Pérdidas totales (estela, disponibilidad, eléctricas) como fracción.")
    initial_capex_usd: float = Field(default=65_000_000, gt=0)
    annual_opex_usd: float = Field(default=1_750_000, ge=0)
    energy_price_usd_mwh: float = Field(default=55, ge=0)
    mitigation_capex_usd: float = Field(default=0, ge=0)
    discount_rate: float = Field(default=0.10, gt=-1, le=1)
    horizon_years: int = Field(default=25, ge=1, le=50)
    price_sensitivity: float = Field(default=0.20, ge=0, lt=1, description="Variación relativa del precio (±).")
    capex_sensitivity: float = Field(default=0.20, ge=0, lt=1, description="Variación relativa del CAPEX inicial (±).")
    opex_sensitivity: float = Field(default=0.20, ge=0, lt=1, description="Variación relativa del OPEX anual (±).")
    losses_sensitivity: float = Field(default=0.05, ge=0, lt=0.5, description="Variación absoluta de las pérdidas (±).")
    discount_rate_sensitivity: float = Field(default=0.02, ge=0, lt=0.5, description="Variación absoluta de la tasa de descuento (±).")

    @model_validator(mode="after")
    def validate_curve(self):
        if not self.cut_in_ms < self.rated_ms < self.cut_out_ms:
            raise ValueError("La curva de potencia exige arranque < nominal < parada.")
        return self


class WindScreeningRequest(BaseModel):
    sites: list[Point] = Field(min_length=2, max_length=4)
    start_date: date
    end_date: date
    assumptions: WindAssumptions = Field(default_factory=WindAssumptions)

    @model_validator(mode="after")
    def validate_screening(self):
        if self.end_date <= self.start_date:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial.")
        if (self.end_date - self.start_date).days < 365 * 5:
            raise ValueError("El piloto eólico requiere al menos cinco años de observaciones.")
        if self.end_date > date.today():
            raise ValueError("La fecha final no puede estar en el futuro.")
        return self


class WindResource(BaseModel):
    """Recurso eólico desde la serie horaria de NASA POWER (MERRA-2), llevado a la altura del buje.

    La forma horaria, la variación interanual y la tendencia son de NASA POWER. El nivel medio se toma del Atlas
    Eólico Global cuando responde (`level_source`): la celda de MERRA-2 no resuelve la aceleración local del viento.
    """

    years: str = Field(description="Años completos de la serie horaria usada para la energía.")
    hours: int
    mean_speed_10m: float
    mean_speed_50m: float
    shear_exponent: float = Field(description="Exponente de la ley potencial entre 10 y 50 m.")
    shear_basis: str
    hub_height_m: float
    mean_speed_hub: float
    air_density_kg_m3: float
    density_basis: str
    capacity_factor_gross: float = Field(description="Factor de planta antes de pérdidas, fracción, con el nivel de `level_source`.")
    annual_capacity_factors: list[AnnualObservation] = Field(description="Factor de planta bruto de cada año, fracción, con el mismo nivel.")
    capacity_factor_gross_nasa_level: float = Field(description="Factor de planta bruto con el nivel propio de NASA POWER, sin escalar.")
    level_source: str = Field(default="NASA POWER (MERRA-2)", description="Fuente del nivel medio del viento usado en la energía.")
    level_factor: float = Field(default=1.0, description="Razón aplicada a cada hora de MERRA-2 para llevarla al nivel de `level_source`.")
    mean_speed_hub_used: float = Field(description="Viento medio al buje con ese nivel.")
    provenance: Provenance
    downloaded_at: datetime
    source_url: str
    version: str


class WindAtlasCheck(BaseModel):
    """El mismo punto en el Atlas Eólico Global: nivel de largo plazo a 250 m frente a la celda de MERRA-2."""

    source: str
    speed_50m: float | None
    speed_100m: float | None
    speed_hub: float | None = Field(description="Atlas llevado a la altura del buje con su propia cizalladura 50–100 m.")
    power_speed_50m: float
    gap_percent_50m: float | None = Field(description="(atlas − NASA POWER) / NASA POWER × 100 a 50 m.")
    gap_percent_hub: float | None
    capacity_factor_gross_at_atlas: float | None = Field(description="Factor de planta si la serie horaria tuviera el nivel del atlas.")
    annual_energy_mwh_at_atlas: float | None
    provenance: Provenance
    downloaded_at: datetime
    urls: list[str]
    license: str
    limitations: list[str]


class WindFinancialProjection(BaseModel):
    capacity_factor_net: float
    annual_energy_mwh: float
    annual_revenue_usd: float
    npv_usd: float
    cash_flows_usd: list[float]
    model_provenance: Provenance = Provenance.MODEL
    assumption_provenance: Provenance = Provenance.ASSUMPTION
    formula: str
    limitations: list[str]


class WindSiteResult(BaseModel):
    location: Point
    relative_position: int
    relative_position_text: str
    variables: list[VariableSummary]
    resource: WindResource
    atlas_check: WindAtlasCheck | None = None
    finance: WindFinancialProjection
    opportunities: list[str]
    cautions: list[str]


class WindScreeningResponse(ScreeningEnvelope):
    """Sobre común C2 + campos propios del piloto eólico."""

    sector: Sector = Sector.WIND
    sector_label: str = "Energía eólica"
    sites: list[WindSiteResult]
    comparative_findings: list[str]
    assumptions: WindAssumptions
