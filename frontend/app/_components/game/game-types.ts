// Contrato de las misiones del modo jugador (espejo de backend/app/schemas/missions.py).

export type Continent = "Sudamérica" | "Norteamérica" | "Europa" | "Asia" | "África" | "Oceanía" | "Antártida";
export type HeatClass = "calienta" | "enfria" | "sin_evidencia";
export type Direction = "increasing" | "decreasing" | "no_trend";
/**
 * Qué dice la segunda fuente (ERA5) de la tendencia de temperatura que clasifica al lugar. Lo calcula el backend:
 * «confirmada» = las dos fuentes son significativas y van en el mismo sentido; «contradicha» = van en sentidos opuestos;
 * «una_fuente» = solo NASA POWER la ve; «sin_segunda_fuente» = no hubo contraste. Es null si el lugar no tiene evidencia.
 */
export type HeatSupport = "confirmada" | "contradicha" | "una_fuente" | "sin_segunda_fuente";
/** Año atípico de un índice de lluvia. `probable_artifact` aplica la regla de la plataforma (ADR-036), no una del juego. */
export interface FlaggedExtreme {
  variable: string;
  label: string;
  /** Unidad del índice: «mm» o «días». La calcula el backend; nunca se asume «mm por día». */
  unit?: string | null;
  year: number;
  value: number | null;
  countercheck_values: Record<string, number | null>;
  /** Verdadero solo si el índice está en mm, hay contraste y el reanálisis supera al menos cinco veces a cada producto satelital. */
  probable_artifact?: boolean;
}

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

export interface AirTrend extends MissionTrend {
  /** Producto y procedencia del dato (p. ej. «NASA POWER · AOD_55 · CERES SYN1deg»). */
  dataset: string;
  provenance: string;
  source_url: string;
  downloaded_at: string | null;
  /** Aclaración corta que acompaña la cifra. */
  note?: string | null;
}

export interface Mission {
  id: string;
  continent: Continent;
  country: string;
  name: string;
  latitude: number;
  longitude: number;
  context: string;
  /** Fuentes externas que respaldan el texto de contexto (puede venir vacío: entonces es texto del equipo sin fuente enlazada). */
  context_sources?: { title: string; url: string }[];
  not_measured: string;
  scale: "ciudad" | "paisaje";
  hazard?: "huaico" | "avalancha" | "inundacion" | "erupcion" | "calor" | "aire" | null;
  heat: HeatClass;
  /** Respaldo de la segunda fuente a la clase de `heat`; null si `heat` es «sin_evidencia». */
  heat_support?: HeatSupport | null;
  temperature: MissionTrend | null;
  rain: MissionTrend | null;
  sun: MissionTrend | null;
  /**
   * Aerosoles en la columna de aire (AOD a 550 nm de NASA POWER), solo en misiones de aire. Se prueba aparte de las
   * variables de clima (familia de una prueba, alfa 0,05). Null o ausente si la misión no es de aire.
   */
  air?: AirTrend | null;
  extremes: { variable: string; label: string; unit: string | null; direction: Direction; slope_per_year: number | null; significant: boolean }[];
  flagged_extremes: FlaggedExtreme[];
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
