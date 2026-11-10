import type { IconName } from "./icons";

export type Point = { latitude: number; longitude: number; label: string };
export type Assumptions = {
  capacity_mw: number; performance_ratio: number; initial_capex_usd: number; annual_opex_usd: number; energy_price_usd_mwh: number; mitigation_capex_usd: number; discount_rate: number; horizon_years: number;
  // Rangos de sensibilidad (±); el orden de claves replica el del backend para comparar supuestos vigentes.
  price_sensitivity: number; capex_sensitivity: number; opex_sensitivity: number; performance_ratio_sensitivity: number; discount_rate_sensitivity: number;
};
// Contrato C2 · sensibilidad del VAN (común a todos los sectores con finanzas).
export type SensitivityBar = {
  key: string; label: string; unit: string; base_value: number; low_value: number; high_value: number;
  npv_at_low: number; npv_at_high: number; swing: number; provenance: string; basis: string;
};
export type FinanceScenario = { key: "base" | "adverso" | "favorable"; label: string; npv: number; changes: string[] };
export type BreakEven = { key: string; label: string; unit: string; assumed_value: number; break_even_value: number | null; note: string };
// Contrato C2 · puntaje multicriterio (escala de referencia declarada, pesos, cobertura y estabilidad).
export type Criterion = {
  key: string; label: string; unit: string; direction: "mayor_es_mejor" | "menor_es_mejor"; weight: number;
  worst: number; best: number; provenance: string; basis: string;
};
export type CriterionScore = { key: string; value: number | null; score: number | null; contribution: number | null };
export type SubjectScore = { subject: string; score: number | null; coverage: number; rank: number | null; first_place_share: number; criteria: CriterionScore[] };
export type WeightSensitivity = { key: string; leader_at_half: string | null; leader_at_one_and_half: string | null; changes_leader: boolean };
export type Scorecard = {
  method: string; criteria: Criterion[]; subjects: SubjectScore[]; leader: string | null; margin: number | null; tie: boolean;
  stability_draws: number; weight_sensitivity: WeightSensitivity[]; notes: string[];
};
export type SubjectSensitivity = { subject: string; metric: string; currency: string; base_npv: number; scenarios: FinanceScenario[]; tornado: SensitivityBar[]; break_evens: BreakEven[] };
export type Trend = {
  direction: string; slope_per_year: number | null; p_value: number | null; p_value_modified?: number | null; variance_correction?: number | null;
  confidence_interval: [number, number] | null; significant: boolean;
  autocorrelation_lag1: number | null; autocorrelation_lag1_detrended?: number | null; interpretation: string; limitations: string[];
};
export type SourceMetadata = { dataset: string; version: string; downloaded_at: string; source_url: string; provenance: string; spatial_resolution: string; quality_notes?: string[] };
export type VariableSummary = {
  variable: string; label: string; mean: number; minimum: number; maximum: number; unit: string; display_unit: string;
  valid_observations: number; completeness_percent: number; annual_variability_percent: number | null;
  trend: Trend; adjusted_p_value: number | null; significant_after_bh: boolean;
  annual_series: { year: number; value: number }[]; source: SourceMetadata;
  last_valid_date?: string | null; current_period?: CurrentPeriod | null;
  counterchecks?: ExtremeCountercheck[];
};
export type CurrentPeriod = {
  year: number; through: string; days: number; value: number; baseline_mean: number; baseline_years: string;
  anomaly: number; anomaly_percent: number | null; rank: number; years_compared: number;
};
export type SolarFinance = { specific_yield_kwh_kwp_year: number; annual_energy_mwh: number; annual_revenue_usd: number; npv_usd: number; formula: string; limitations: string[] };
export type SiteResult = { location: Point; relative_solar_position: number; relative_position_text: string; variables: VariableSummary[]; finance: SolarFinance; opportunities: string[]; cautions: string[] };
export type QuestionKey = "what" | "where" | "how_much" | "significant" | "so_what";
export type StageEvidence = { label: string; value: string; provenance: string | null };
export type Stage = { step: number; key: string; name: string; status: string; summary: string; provenance: string[]; evidence?: StageEvidence[]; duration_ms?: number | null; answers?: QuestionKey[] };
export type NasaQuestion = { key: QuestionKey; question: string; question_es: string; status: "RESPONDIDA" | "PARCIAL" | "EVIDENCIA_INSUFICIENTE"; answer: string; evidence: string[]; provenance: string[]; stage_steps: number[] };
export type TrendFinding = { site: string; variable: string; label: string; unit: string; slope_per_year: number; confidence_interval: [number, number] | null; first_year: number; last_year: number; change_over_period: number; change_percent_of_mean: number | null; p_value: number; adjusted_p_value: number; autocorrelation_lag1: number | null };
export type DataGap = { dataset: string; status: string; impact: string; next_action: string };
// Contrato común C2 (ScreeningEnvelope v1.0): campos que todos los sectores comparten.
export type StudySubject = { id: string; label: string; kind: "point" | "segment" | "polygon"; geometry: { type: string; coordinates: unknown }; representative_point: Point };
export type AssumptionItem = { key: string; label: string; value: number; unit: string; provenance: string };
export type ScreeningResult = {
  contract_version?: string; analysis_id: string; generated_at: string; title: string; sector: string; sector_label?: string; period: string;
  subjects?: StudySubject[]; assumption_items?: AssumptionItem[]; financial_sensitivity?: SubjectSensitivity[]; scorecard?: Scorecard | null;
  pipeline: Stage[]; nasa_questions: NasaQuestion[]; trend_findings: TrendFinding[];
  sites: SiteResult[]; terrain: TerrainResult | null;
  comparative_findings: string[]; data_gaps: DataGap[]; assumptions: Assumptions; discoveries?: Discovery[]; disclaimer: string;
  // Validaciones del método contra datos reales (con fecha, fuente y alcance); no son resultados del análisis en curso.
  method_validation?: string[];
};
export type DiscoveryKind = "artefacto_probable" | "confirmado" | "sin_respaldo" | "coincidencia" | "contradiccion";
export type Discovery = { kind: DiscoveryKind; title: string; detail: string; subjects: string[]; sources: string[] };
// Módulo 1 · Inteligencia climática (sector "climate" del contrato C2).
export type ExtremeIndex = {
  variable: string; label: string; description: string; unit: string; display_unit: string;
  mean: number; minimum: number; maximum: number; valid_years: number; discarded_years: number;
  trend: Trend; adjusted_p_value: number | null; significant_after_bh: boolean; annual_series: { year: number; value: number }[];
  atypical_years?: { year: number; value: number; robust_z: number; countercheck_value?: number | null; countercheck_values?: Record<string, number> }[];
  countercheck?: ExtremeCountercheck | null;
  counterchecks?: ExtremeCountercheck[];
};
export type Agreement = "coincide" | "contradice" | "sin_respaldo" | "solo_contraste" | "sin_tendencia";
export type ExtremeCountercheck = {
  source: string; valid_years: number; direction: string; slope_per_year: number | null; adjusted_p_value: number | null;
  significant_after_bh: boolean; agreement: Agreement; annual_series: { year: number; value: number }[];
  period?: string | null; primary_slope_per_year?: number | null;
};
// Territorios oficiales (IGN · COD-AB vía API de Codex) y su análisis por celdas NASA POWER.
export type TerritoryLevel = "department" | "province" | "district";
export type TerritorySummary = {
  level: TerritoryLevel; name: string; ubigeo: string; pcode: string; parent_ubigeo: string | null;
  department: string | null; province: string | null; area_sqkm: number; center: { latitude: number; longitude: number };
};
export type TerritoryPick = { level: TerritoryLevel; ubigeo: string; name: string; context: string; geometry: GeoJSON.Geometry | null };
export type CellTrend = {
  cell_id: string; center: { latitude: number; longitude: number }; bounds: [number, number, number, number]; weight: number;
  variable: string; direction: string; slope_per_year: number | null; p_value: number | null; adjusted_p_value: number | null; significant: boolean; valid_years: number;
};
export type TerritoryInfo = {
  level: TerritoryLevel; ubigeo: string; name: string; area_km2: number; mode: "REGIONAL" | "POINT"; cells: number;
  coverage_percent: number; grid_degrees: [number, number] | null; geometry: GeoJSON.Geometry; source: string;
};
export type ClimateSite = {
  location: Point; variables: VariableSummary[]; extremes: ExtremeIndex[]; wet_day_p95_mm: number | null;
  territory?: TerritoryInfo | null; cell_trends?: CellTrend[];
};
export type ClimateResult = Omit<ScreeningResult, "sites" | "comparative_findings" | "assumptions"> & { sector: "climate"; sites: ClimateSite[]; method_notes: string[] };
// Piloto vial (K2 de Codex · sector "road" del contrato C2).
export type RoadAssumptions = {
  baseline_interruption_days_per_year: number; residual_interruption_fraction: number; cost_per_interruption_day_usd: number;
  mitigation_capex_usd_per_km: number; annual_maintenance_usd_per_km: number; discount_rate: number; horizon_years: number;
  heavy_rain_threshold_mm_day: number; interruption_days_sensitivity: number; cost_per_day_sensitivity: number; capex_sensitivity: number;
  maintenance_sensitivity: number; residual_fraction_sensitivity: number; discount_rate_sensitivity: number;
};
export type RoadSegment = {
  subject_id: string; label: string; representative_point: Point; length_km: number; variables: VariableSummary[];
  heavy_rain_days_per_year: number | null; heavy_rain_years: number;
  spatial_exposure: { cell_count: number; spatial_coverage_percent: number; mean_precipitation_mm_day: number | null; rx1day_mm: number | null; method: string; limitations: string[] } | null;
  terrain_slope_degrees: number | null; territorial_intersections: Record<string, number | null>;
  finance: { baseline_interruption_days_per_year: number; avoided_interruption_days_per_year: number; annual_avoided_cost_usd: number; mitigation_capex_usd: number; npv_usd: number; formula: string; limitations: string[] };
  opportunities: string[]; cautions: string[];
};
// `stale_note`: la fuente no respondió hoy y se muestra su última copia válida (motivo y fecha de la copia).
export type RoadTerritorialSource = { source_id: string; status: string; intersection_count: number | null; provenance: string; downloaded_at?: string | null; limitations: string[]; stale_note?: string | null };
export type RoadResult = Omit<ScreeningResult, "sites" | "comparative_findings" | "assumptions"> & {
  sector: "road"; corridor_source: { name: string; source: string; source_url: string | null; license: string | null; provenance: string; limitations: string[] };
  segments: RoadSegment[]; territorial_evidence: { subject: string; sources: RoadTerritorialSource[] }[]; assumptions: RoadAssumptions;
};
// Piloto inmobiliario (K3 de Codex · sector "real_estate" del contrato C2).
export type RealEstateAssumptions = {
  developable_fraction: number; floor_area_ratio: number; sale_price_usd_m2: number; construction_cost_usd_m2: number; land_cost_usd_m2: number;
  mitigation_cost_usd_m2_land: number; selling_cost_fraction: number; annual_absorption_fraction: number; discount_rate: number; horizon_years: number;
  sale_price_sensitivity: number; construction_cost_sensitivity: number; land_cost_sensitivity: number; mitigation_cost_sensitivity: number;
  absorption_sensitivity: number; discount_rate_sensitivity: number;
};
export type RealEstateSite = {
  subject_id: string; label: string; representative_point: Point; area_km2: number; variables: VariableSummary[];
  spatial_exposure: { mode: string; cell_count: number; spatial_coverage_percent: number; mean_precipitation_mm_day: number | null; rx1day_mm: number | null; p99_precipitation_mm_day: number | null; method: string } | null;
  terrain_slope_degrees: number | null; territorial_intersections: Record<string, number | null>;
  finance: { land_area_m2: number; saleable_floor_area_m2: number; land_acquisition_usd: number; initial_mitigation_usd: number; projected_revenue_usd: number;
    projected_construction_cost_usd: number; sold_fraction_within_horizon: number; npv_usd: number; formula: string; limitations: string[] };
  opportunities: string[]; cautions: string[];
};
export type TerritorialEvidence = { subject: string; sources: RoadTerritorialSource[] };
export type RealEstateResult = Omit<ScreeningResult, "sites" | "comparative_findings" | "assumptions"> & {
  sector: "real_estate"; site_sources: { subject: string; origin: string; dataset: string; license: string | null; provenance: string; limitations: string[] }[];
  sites: RealEstateSite[]; territorial_evidence: TerritorialEvidence[]; assumptions: RealEstateAssumptions;
};
// Línea base territorial (módulos 4 y 5 · sectores "environment" y "heritage" del contrato C2).
export type BaselineComponent = "fisico" | "biologico" | "sociocultural" | "amenazas";
export type LayerHighlight = { label: string; count: number; detail: string | null; link: string | null };
export type BaselineLayer = {
  source_id: string; organization: string; dataset: string; component: BaselineComponent; status: "READY" | "DATA_UNAVAILABLE";
  intersection_count: number | null; truncated: boolean; highlights: LayerHighlight[]; provenance: string; downloaded_at: string | null;
  source_url: string; limitations: string[]; stale_note?: string | null;
};
export type LandCoverChange = {
  product: string; first_year: number; last_year: number; pixels: number; changed_percent: number;
  classes: { code: number; label: string; first_percent: number; last_percent: number }[]; provenance: string; source_url: string; limitations: string[];
};
export type LandCoverCrosscheck = {
  source: string; year: number; pixels: number; resolution_m: number; classes: { code: number; label: string; percent: number }[];
  groups: { variable: string; label: string; modis_percent: number | null; worldcover_percent: number }[];
  provenance: string; downloaded_at: string; source_urls: string[]; limitations: string[];
};
export type SubjectBaseline = {
  subject: string; origin: string; area_km2: number; study_area: GeoJSON.Geometry; modis_window_km: number | null; modis_pixels: Record<string, number>;
  vegetation: VariableSummary[]; vegetation_notes: string[]; land_cover: LandCoverChange | null; land_cover_check?: LandCoverCrosscheck | null;
  layers: BaselineLayer[]; errors: string[];
  climate?: VariableSummary[]; extremes?: ExtremeIndex[]; wet_day_p95_mm?: number | null;
};
export type BaselineResult = Omit<ScreeningResult, "sites" | "comparative_findings" | "assumptions"> & {
  sector: "environment" | "heritage" | "hazards"; components: BaselineComponent[]; baselines: SubjectBaseline[]; method_notes: string[];
};
// Piloto eólico (sector "wind" del contrato C2): forma horaria NASA POWER, nivel del Atlas Eólico Global.
export type WindAssumptions = {
  capacity_mw: number; hub_height_m: number; cut_in_ms: number; rated_ms: number; cut_out_ms: number; losses: number;
  initial_capex_usd: number; annual_opex_usd: number; energy_price_usd_mwh: number; mitigation_capex_usd: number; discount_rate: number; horizon_years: number;
  price_sensitivity: number; capex_sensitivity: number; opex_sensitivity: number; losses_sensitivity: number; discount_rate_sensitivity: number;
};
export type WindResource = {
  years: string; hours: number; mean_speed_10m: number; mean_speed_50m: number; shear_exponent: number; shear_basis: string; hub_height_m: number;
  mean_speed_hub: number; air_density_kg_m3: number; density_basis: string; capacity_factor_gross: number; annual_capacity_factors: { year: number; value: number }[];
  capacity_factor_gross_nasa_level: number; level_source: string; level_factor: number; mean_speed_hub_used: number;
  provenance: string; downloaded_at: string; source_url: string; version: string;
};
export type WindAtlasCheck = {
  source: string; speed_50m: number | null; speed_100m: number | null; speed_hub: number | null; power_speed_50m: number;
  gap_percent_50m: number | null; gap_percent_hub: number | null; capacity_factor_gross_at_atlas: number | null; annual_energy_mwh_at_atlas: number | null;
  provenance: string; downloaded_at: string; urls: string[]; license: string; limitations: string[];
};
export type WindSite = {
  location: Point; relative_position: number; relative_position_text: string; variables: VariableSummary[]; resource: WindResource; atlas_check: WindAtlasCheck | null;
  finance: { capacity_factor_net: number; annual_energy_mwh: number; annual_revenue_usd: number; npv_usd: number; formula: string; limitations: string[] };
  opportunities: string[]; cautions: string[];
};
export type WindResult = Omit<ScreeningResult, "sites" | "assumptions"> & { sector: "wind"; sites: WindSite[]; assumptions: WindAssumptions };
// Piloto hidroeléctrico (sector "hydro" del contrato C2): caudal GloFAS con GEOGLOWS, salto NASADEM con Copernicus.
export type HydroPoint = { latitude: number; longitude: number };
export type HydroSiteInput = { label: string; intake: HydroPoint; powerhouse: HydroPoint; design_flow_m3s: number | null };
export type HydroAssumptions = {
  design_exceedance_percent: number; ecological_flow_fraction: number; min_turbine_flow_fraction: number; efficiency: number; head_loss_fraction: number;
  availability: number; capex_usd_per_mw: number; opex_fraction_of_capex: number; energy_price_usd_mwh: number; mitigation_capex_usd: number;
  discount_rate: number; horizon_years: number; price_sensitivity: number; capex_sensitivity: number; opex_sensitivity: number; discount_rate_sensitivity: number;
};
export type HydroHead = {
  source: string; intake_elevation_m: number; powerhouse_elevation_m: number; gross_head_m: number; second_source: string | null;
  second_gross_head_m: number | null; gap_m: number | null; gap_percent: number | null; conduction_km: number; mean_slope_percent: number;
  provenance: string; limitations: string[];
};
export type HydroResource = {
  period: string; days: number; mean_flow_m3s: number; firm_flow_m3s: number; ecological_flow_m3s: number; design_flow_m3s: number; design_basis: string;
  min_turbine_flow_m3s: number; flow_duration: { exceedance_percent: number; flow_m3s: number }[]; net_head_m: number; capacity_mw: number;
  plant_factor: number; annual_plant_factors: { year: number; value: number }[];
  cell: { latitude: number; longitude: number; distance_km: number; moved: boolean; point_cell_mean_m3s: number | null; used_cell_mean_m3s: number; neighborhood_max_m3s: number; scan_year: number };
  source: string; source_url: string; provenance: string; downloaded_at: string;
};
export type HydroFlowCheck = {
  source: string; river_id: number; nearest_river_id: number; candidates: number; period: string; mean_m3s: number; primary_mean_m3s: number;
  ratio: number | null; gap_percent: number | null; verdict: "coinciden" | "intermedio" | "difieren" | "no_comparable";
  plant_factor_at_second: number | null; annual_energy_mwh_at_second: number | null; provenance: string; downloaded_at: string; source_url: string; limitations: string[];
};
export type HydroSiteResult = {
  location: Point; powerhouse: Point; relative_position: number; relative_position_text: string; variables: VariableSummary[];
  head: HydroHead; resource: HydroResource; flow_check: HydroFlowCheck | null;
  finance: { capacity_mw: number; plant_factor_net: number; annual_energy_mwh: number; initial_capex_usd: number; annual_opex_usd: number; annual_revenue_usd: number; npv_usd: number; formula: string; limitations: string[] };
  opportunities: string[]; cautions: string[];
};
export type HydroResult = Omit<ScreeningResult, "sites" | "assumptions"> & { sector: "hydro"; sites: HydroSiteResult[]; assumptions: HydroAssumptions };
export type AnyResult = ScreeningResult | ClimateResult | RoadResult | RealEstateResult | BaselineResult | WindResult | HydroResult;
export const isWind = (result: AnyResult | null): result is WindResult => result?.sector === "wind";
export const isHydro = (result: AnyResult | null): result is HydroResult => result?.sector === "hydro";
export const isClimate = (result: AnyResult | null): result is ClimateResult => result?.sector === "climate";
export const isRoad = (result: AnyResult | null): result is RoadResult => result?.sector === "road";
export const isRealEstate = (result: AnyResult | null): result is RealEstateResult => result?.sector === "real_estate";
export const isBaseline = (result: AnyResult | null): result is BaselineResult => ["environment", "heritage", "hazards"].includes(result?.sector ?? "");
/** Sujetos con series NASA, cualquiera sea el sector: sitios (solar, clima) o tramos (vial). */
export type SeriesSubject = { location: Point; variables: VariableSummary[]; extremes?: ExtremeIndex[] };
export const seriesSubjects = (result: AnyResult | null): SeriesSubject[] => {
  if (!result) return [];
  if (isRoad(result)) return result.segments.map((segment) => ({ location: { ...segment.representative_point, label: segment.label }, variables: segment.variables }));
  if (isRealEstate(result)) return result.sites.map((site) => ({ location: { ...site.representative_point, label: site.label }, variables: site.variables }));
  // Patrimonio no tiene series: sus registros no son temporales. Ambiente aporta MODIS; Amenazas, lluvia y extremos.
  if (isBaseline(result)) return result.baselines.filter((item) => item.vegetation.length || item.climate?.length).map((item) => {
    const subject = result.subjects?.find((entry) => entry.label === item.subject);
    return {
      location: { latitude: subject?.representative_point.latitude ?? 0, longitude: subject?.representative_point.longitude ?? 0, label: item.subject },
      variables: [...item.vegetation, ...(item.climate ?? [])], extremes: item.extremes ?? [],
    };
  });
  return result.sites;
};
export type TerrainGranule = { short_name: "NASADEM_HGT" | "NASADEM_SC"; version: string; granule_id: string; title: string; tile_id: string; bounding_box: [number, number, number, number]; updated_at: string; data_url: string; preview_url: string | null; doi_url: string; catalogue_url: string; access: string };
export type TerrainSite = { location: Point; status: "READY" | "METADATA_ONLY" | "PARTIAL" | "PENDING"; metrics: { elevation_m: number | null; slope_degrees: number | null; aspect_degrees: number | null; aspect_cardinal: string | null; vertical_datum: string }; granules: TerrainGranule[]; provenance: string; limitations: string[];
  crosscheck?: { source: string; elevation_m: number | null; slope_degrees: number | null; vertical_datum: string; tile_url: string; provenance: string; downloaded_at: string; limitations: string[] } | null };
export type TerrainResult = { generated_at: string; dataset: string; crs: string; spatial_resolution: string; sites: TerrainSite[]; note: string };
// Capas visuales NASA GIBS (GET /api/v1/map/layers): solo visualización, nunca entran en el cálculo.
export type MapLayer = {
  id: string; label: string; group: string; description: string; gibs_id: string; tile_url: string; max_zoom: number;
  latest_date: string | null; first_date: string | null; period_days: number | null; legend_url: string | null; source: string; notice: string | null;
};
export type VisualLayerState = { layer: MapLayer; date: string; opacity: number };
export type Module = { id: string; short: string; name: string; icon: IconName; status: string; ready: boolean; description: string };
