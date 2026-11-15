// Estado del planeta y regla de los regresos de TERRA 2045 (ADR-050). Funciones puras: no hay DOM ni React aquí.
//
// Es GAMIFICACIÓN declarada: el porcentaje mide el avance del jugador, no el ambiente real. Nada de lo que se calcula
// aquí sale de un dato medido; las cifras de cada lugar siguen en mission-logic.ts.
//
// Reglas (pedido de Andrés, 14-nov):
// - Misiones fundamentales: al menos un lugar a salvo por cada peligro de FUNDAMENTAL.
// - Si la salud llega a cero, o si el jugador lo pide, Génesis lo devuelve a 2045 («regreso»).
// - Hay MAX_RETURNS regresos. Con un lugar a salvo nuevo desde el regreso anterior, hay energía para volver a 2026;
//   sin mejora, final perdedor. Al agotar los regresos sin completar lo fundamental, final intermedio.
// - Con lo fundamental completo, el regreso final da el final bueno (no gasta un regreso).

import type { Mission } from "./game-types";
import type { Outcome } from "./story";

export type FundamentalHazard = "huaico" | "inundacion" | "calor" | "erupcion" | "avalancha";

/** Peligros que exige el final bueno, con el nombre que ve el jugador. El orden es el de la lista en pantalla. */
export const FUNDAMENTAL: { id: FundamentalHazard; label: string; icon: string }[] = [
  { id: "huaico", label: "Huaico", icon: "🟤" },
  { id: "inundacion", label: "Inundación", icon: "🌊" },
  { id: "calor", label: "Calor y sequía", icon: "🔥" },
  { id: "erupcion", label: "Erupción", icon: "🌋" },
  { id: "avalancha", label: "Avalancha", icon: "❄️" },
];

export const MAX_RETURNS = 3;
export const PLANET_NOTICE = "Estado del planeta: es el avance del juego, no una medición del ambiente.";

/** Puntos de un lugar a salvo: base más la calidad del plan (0 a 4, decisions.ts). */
const PLACE_BASE = 6;
/** Puntos por cada peligro fundamental cubierto. */
const TYPE_BONUS = 8;

export type PlanetTier = 0 | 1 | 2 | 3 | 4;
export const TIERS: { from: number; label: string; future: string }[] = [
  { from: 0, label: "Crítico", future: "La Tierra sigue casi destruida." },
  { from: 21, label: "Deteriorado", future: "La Tierra todavía enfrenta problemas graves." },
  { from: 41, label: "En recuperación", future: "La Tierra empieza a recuperarse en algunas regiones." },
  { from: 61, label: "Saludable", future: "La Tierra se recupera en buena parte del planeta." },
  { from: 81, label: "En equilibrio", future: "La Tierra vuelve a estar en equilibrio." },
];

export interface Progress {
  /** Hoja del cuaderno de cada lugar jugado. */
  story: Record<string, Outcome>;
  /** Calidad del mejor plan confirmado en cada lugar (0 a 4). */
  plans: Record<string, number>;
}

export interface Returns {
  /** Regresos ya usados (0 a MAX_RETURNS). */
  used: number;
  /** Lugares a salvo al momento del último regreso (o 0 al empezar). */
  savedAtLast: number;
}

export const NO_RETURNS: Returns = { used: 0, savedAtLast: 0 };

export function savedIds(story: Record<string, Outcome>): string[] {
  return Object.keys(story).filter((id) => story[id] === "salvado");
}

/** Peligros fundamentales con al menos un lugar a salvo. Los lugares sin peligro fundamental (aire, «lo que falta saber») no cuentan aquí. */
export function coveredHazards(missions: Mission[], story: Record<string, Outcome>): Set<FundamentalHazard> {
  const byId = new Map(missions.map((item) => [item.id, item]));
  const covered = new Set<FundamentalHazard>();
  for (const id of savedIds(story)) {
    const hazard = byId.get(id)?.hazard;
    if (hazard && FUNDAMENTAL.some((item) => item.id === hazard)) covered.add(hazard as FundamentalHazard);
  }
  return covered;
}

export function missingHazards(missions: Mission[], story: Record<string, Outcome>): typeof FUNDAMENTAL {
  const covered = coveredHazards(missions, story);
  return FUNDAMENTAL.filter((item) => !covered.has(item.id));
}

export function fundamentalsDone(missions: Mission[], story: Record<string, Outcome>): boolean {
  return missingHazards(missions, story).length === 0;
}

/** Porcentaje del planeta (0 a 100): peligros cubiertos más los puntos de cada lugar a salvo. */
export function planetPercent(missions: Mission[], progress: Progress): number {
  const known = new Set(missions.map((item) => item.id));
  const places = savedIds(progress.story).filter((id) => known.has(id));
  const points = places.reduce((sum, id) => sum + PLACE_BASE + clampQuality(progress.plans[id]), 0);
  return Math.min(100, coveredHazards(missions, progress.story).size * TYPE_BONUS + points);
}

function clampQuality(value: number | undefined): number {
  return value == null || !Number.isFinite(value) ? 0 : Math.max(0, Math.min(4, Math.round(value)));
}

export function planetTier(percent: number): PlanetTier {
  let tier = 0;
  TIERS.forEach((item, index) => { if (percent >= item.from) tier = index; });
  return tier as PlanetTier;
}

export type ReturnCause = "emergencia" | "voluntario";
export type Ending = "bueno" | "intermedio" | "perdedor";
/** Lo que pasa después de un regreso: volver a 2026 o un final. */
export type ReturnVerdict = { kind: "volver"; used: number; savedAtLast: number } | { kind: "final"; ending: Ending };

/**
 * Regla del regreso. `saved` es el total de lugares a salvo ahora. El regreso con lo fundamental completo es el final
 * bueno y no gasta un regreso; si no, se gasta uno y se mira si hubo mejora desde el anterior.
 */
export function judgeReturn(returns: Returns, saved: number, fundamentals: boolean): ReturnVerdict {
  if (fundamentals) return { kind: "final", ending: "bueno" };
  const used = Math.min(MAX_RETURNS, returns.used + 1);
  const improved = saved > returns.savedAtLast;
  if (!improved) return { kind: "final", ending: "perdedor" };
  if (used >= MAX_RETURNS) return { kind: "final", ending: "intermedio" };
  return { kind: "volver", used, savedAtLast: saved };
}

/** Lugares a salvo nuevos desde el último regreso: lo que decide si hay energía para volver. */
export function newSince(returns: Returns, saved: number): number {
  return Math.max(0, saved - returns.savedAtLast);
}
