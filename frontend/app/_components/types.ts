import type { IconName } from "./icons";

export type Point = { latitude: number; longitude: number; label: string };
export type Assumptions = { capacity_mw: number; performance_ratio: number; initial_capex_usd: number; annual_opex_usd: number; energy_price_usd_mwh: number; mitigation_capex_usd: number; discount_rate: number; horizon_years: number };
export type Trend = {
  direction: string; slope_per_year: number | null; p_value: number | null; p_value_modified?: number | null; variance_correction?: number | null;
  confidence_interval: [number, number] | null; significant: boolean;
  autocorrelation_lag1: number | null; autocorrelation_lag1_detrended?: number | null; interpretation: string; limitations: string[];
};
export type SourceMetadata = { dataset: string; version: string; downloaded_at: string; source_url: string; provenance: string; spatial_resolution: string };
export type VariableSummary = {
  variable: string; label: string; mean: number; minimum: number; maximum: number; unit: string; display_unit: string;
  valid_observations: number; completeness_percent: number; annual_variability_percent: number | null;
  trend: Trend; adjusted_p_value: number | null; significant_after_bh: boolean;
  annual_series: { year: number; value: number }[]; source: SourceMetadata;
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
  subjects?: StudySubject[]; assumption_items?: AssumptionItem[];
  pipeline: Stage[]; nasa_questions: NasaQuestion[]; trend_findings: TrendFinding[];
  sites: SiteResult[]; terrain: TerrainResult | null;
  comparative_findings: string[]; data_gaps: DataGap[]; assumptions: Assumptions; disclaimer: string;
};
export type TerrainGranule = { short_name: "NASADEM_HGT" | "NASADEM_SC"; version: string; granule_id: string; title: string; tile_id: string; bounding_box: [number, number, number, number]; updated_at: string; data_url: string; preview_url: string | null; doi_url: string; catalogue_url: string; access: string };
export type TerrainSite = { location: Point; status: "READY" | "METADATA_ONLY" | "PARTIAL" | "PENDING"; metrics: { elevation_m: number | null; slope_degrees: number | null; aspect_degrees: number | null; aspect_cardinal: string | null; vertical_datum: string }; granules: TerrainGranule[]; provenance: string; limitations: string[] };
export type TerrainResult = { generated_at: string; dataset: string; crs: string; spatial_resolution: string; sites: TerrainSite[]; note: string };
export type Module = { id: string; short: string; name: string; icon: IconName; status: string; ready: boolean; description: string };
