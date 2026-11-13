// Contrato de las misiones del modo jugador (espejo de backend/app/schemas/missions.py).

export type Continent = "Sudamérica" | "Norteamérica" | "Europa" | "Asia" | "África" | "Oceanía" | "Antártida";
export type HeatClass = "calienta" | "enfria" | "sin_evidencia";
export type Direction = "increasing" | "decreasing" | "no_trend";

export interface MissionTrend {
  label: string;
  unit: string | null;
  mean: number | null;
  direction: Direction;
  slope_per_year: number | null;
  confidence_interval: [number, number] | null;
  p_value_adjusted: number | null;
  significant: boolean;
  valid_years: number | null;
  annual_series: { year: number; value: number | null }[];
  second_source: { source: string; agreement: string | null; period: string | null } | null;
}

export interface Mission {
  id: string;
  continent: Continent;
  country: string;
  name: string;
  latitude: number;
  longitude: number;
  context: string;
  not_measured: string;
  scale: "ciudad" | "paisaje";
  hazard?: "huaico" | "avalancha" | "inundacion" | "erupcion" | "calor" | null;
  heat: HeatClass;
  temperature: MissionTrend | null;
  rain: MissionTrend | null;
  sun: MissionTrend | null;
  extremes: { variable: string; label: string; unit: string | null; direction: Direction; slope_per_year: number | null; significant: boolean }[];
  flagged_extremes: { variable: string; label: string; year: number; value: number | null; countercheck_values: Record<string, number | null> }[];
  analysis: {
    analysis_id: string | null;
    generated_at: string | null;
    period: string | null;
    dataset: string | null;
    version: string | null;
    downloaded_at: string | null;
    provenance: string;
    source_url: string | null;
  };
}

export interface MissionsPayload {
  built_at: string;
  method: string;
  missions: Mission[];
}

export type Gender = "mujer" | "hombre";

export interface Hero {
  name: string;
  gender: Gender;
}

/** Dónde está la cámara y qué ve la persona. */
export type Stage = "inicio" | "avatar" | "luna" | "viaje" | "tierra" | "mision";
export type Role = "jugador" | "espectador";

export const CONTINENTS: { id: Continent; center: [number, number]; zoom: number }[] = [
  { id: "Sudamérica", center: [-62, -22], zoom: 2.4 },
  { id: "Norteamérica", center: [-95, 38], zoom: 2.0 },
  { id: "Europa", center: [12, 52], zoom: 2.9 },
  { id: "Asia", center: [80, 30], zoom: 2.2 },
  { id: "África", center: [20, 2], zoom: 2.4 },
  { id: "Oceanía", center: [160, -15], zoom: 2.4 },
  { id: "Antártida", center: [-60, -68], zoom: 2.6 },
];

export const HEAT_LABEL: Record<HeatClass, string> = {
  calienta: "Se calienta",
  enfria: "Se enfría",
  sin_evidencia: "Sin evidencia suficiente",
};

/** Capa visual de NASA GIBS tal como la entrega /api/v1/map/layers (catálogo canónico de la plataforma). */
export interface NasaLayer {
  id: string;
  label: string;
  group: string;
  description: string;
  tile_url: string;
  max_zoom: number;
  latest_date: string | null;
  period_days: number | null;
  legend_url: string | null;
  notice: string | null;
}

/** «Visiones del héroe»: qué capa de NASA ver, con un nombre de juego. El orden es el de la barra. */
export const VISIONS: { id: string; name: string; hint: string }[] = [
  { id: "true-color", name: "Nubes de hoy", hint: "El planeta como lo fotografió el satélite Terra ese día." },
  { id: "sst-anomaly", name: "Mar más caliente", hint: "Rojo: el mar está más caliente que lo normal para esa fecha. Así se ve El Niño." },
  { id: "sst", name: "Temperatura del mar", hint: "Cuán caliente está la superficie del océano." },
  { id: "ndvi", name: "Vegetación", hint: "Verde intenso: mucha vegetación viva. Café: poca o ninguna." },
  { id: "land-temp", name: "Suelo caliente", hint: "Temperatura del suelo de día (no es la del aire)." },
  { id: "fires", name: "Focos de calor", hint: "Puntos donde los satélites detectaron calor intenso: incendios y quemas." },
  { id: "rain", name: "Lluvia", hint: "Dónde llovió y con qué fuerza, según GPM IMERG." },
  { id: "soil-moisture", name: "Suelo seco o húmedo", hint: "Humedad del suelo donde crecen las raíces (SMAP)." },
];
