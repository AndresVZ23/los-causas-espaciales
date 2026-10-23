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
  comparative_findings: string[]; data_gaps: DataGap[]; assumptions: Assumptions; disclaimer: string;
};
// Módulo 1 · Inteligencia climática (sector "climate" del contrato C2).
export type ExtremeIndex = {
  variable: string; label: string; description: string; unit: string; display_unit: string;
  mean: number; minimum: number; maximum: number; valid_years: number; discarded_years: number;
  trend: Trend; adjusted_p_value: number | null; significant_after_bh: boolean; annual_series: { year: number; value: number }[];
  atypical_years?: { year: number; value: number; robust_z: number; countercheck_value?: number | null }[];
  countercheck?: ExtremeCountercheck | null;
};
export type Agreement = "coincide" | "contradice" | "sin_respaldo" | "solo_contraste" | "sin_tendencia";
export type ExtremeCountercheck = {
  source: string; valid_years: number; direction: string; slope_per_year: number | null; adjusted_p_value: number | null;
  significant_after_bh: boolean; agreement: Agreement; annual_series: { year: number; value: number }[];
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
export type RoadTerritorialSource = { source_id: string; status: string; intersection_count: number | null; provenance: string; limitations: string[] };
export type RoadResult = Omit<ScreeningResult, "sites" | "comparative_findings" | "assumptions"> & {
  sector: "road"; corridor_source: { name: string; source: string; source_url: string | null; license: string | null; provenance: string; limitations: string[] };
  segments: RoadSegment[]; territorial_evidence: { subject: string; sources: RoadTerritorialSource[] }[]; assumptions: RoadAssumptions;
};
export type AnyResult = ScreeningResult | ClimateResult | RoadResult;
export const isClimate = (result: AnyResult | null): result is ClimateResult => result?.sector === "climate";
export const isRoad = (result: AnyResult | null): result is RoadResult => result?.sector === "road";
/** Sujetos con series NASA, cualquiera sea el sector: sitios (solar, clima) o tramos (vial). */
export type SeriesSubject = { location: Point; variables: VariableSummary[]; extremes?: ExtremeIndex[] };
export const seriesSubjects = (result: AnyResult | null): SeriesSubject[] => {
  if (!result) return [];
  if (isRoad(result)) return result.segments.map((segment) => ({ location: { ...segment.representative_point, label: segment.label }, variables: segment.variables }));
  return result.sites;
};
export type TerrainGranule = { short_name: "NASADEM_HGT" | "NASADEM_SC"; version: string; granule_id: string; title: string; tile_id: string; bounding_box: [number, number, number, number]; updated_at: string; data_url: string; preview_url: string | null; doi_url: string; catalogue_url: string; access: string };
export type TerrainSite = { location: Point; status: "READY" | "METADATA_ONLY" | "PARTIAL" | "PENDING"; metrics: { elevation_m: number | null; slope_degrees: number | null; aspect_degrees: number | null; aspect_cardinal: string | null; vertical_datum: string }; granules: TerrainGranule[]; provenance: string; limitations: string[] };
export type TerrainResult = { generated_at: string; dataset: string; crs: string; spatial_resolution: string; sites: TerrainSite[]; note: string };
// Capas visuales NASA GIBS (GET /api/v1/map/layers): solo visualización, nunca entran en el cálculo.
export type MapLayer = {
  id: string; label: string; group: string; description: string; gibs_id: string; tile_url: string; max_zoom: number;
  latest_date: string | null; first_date: string | null; period_days: number | null; legend_url: string | null; source: string; notice: string | null;
};
export type VisualLayerState = { layer: MapLayer; date: string; opacity: number };
export type Module = { id: string; short: string; name: string; icon: IconName; status: string; ready: boolean; description: string };
