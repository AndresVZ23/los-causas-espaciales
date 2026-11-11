// Contrato de una «zona para explorar» (ADR-047) y lectura de su cuadrícula. Sin three.js: sirve también a la lista del panel.

export type BeaconKind = "evento" | "amenaza" | "pista_falsa" | "oportunidad" | "infraestructura" | "brecha";
export type ZoneFigure = { label: string; value: string };
export type ZoneBeacon = {
  id: string; kind: BeaconKind; title: string; body: string; figures: ZoneFigure[]; sources: string[]; second_source: string | null;
  look_first: string; latitude: number; longitude: number; placement: string;
};
export type ZonePath = { label: string; coordinates: [number, number][]; source: string };
export type ZoneSource = { name: string; use: string; license: string; url: string };
export type ZoneSummary = { id: string; name: string; country: string; tagline: string; latitude: number; longitude: number; size_km: number; built_at: string };
export type Zone = ZoneSummary & {
  bounds: [number, number, number, number]; grid: number; cell_m: number; vertical_exaggeration: number;
  base_elevation_m: number; min_elevation_m: number; max_elevation_m: number;
  heights_b64: string; cover_b64: string; slope_b64: string;
  beacons: ZoneBeacon[]; paths: ZonePath[]; sources: ZoneSource[]; notes: string[];
};

/**
 * Cuadrícula por filas de norte a sur. `heights`, `cover` y `slope` son el dato y nunca cambian. `road` marca las
 * celdas por donde pasa una vía y `deco` es la altura del adorno de la celda (árbol o volumen). Lo que el jugador
 * cambia va aparte: `dug` son los bloques de terreno que quitó y `placed` las piezas que puso, por celda y de abajo
 * hacia arriba. `solid` es la altura que se pisa: terreno que queda, más adorno, más piezas.
 */
export type ZoneGrid = {
  size: number; heights: Uint16Array; cover: Uint8Array; slope: Uint8Array; road: Uint8Array; deco: Uint8Array; solid: Float32Array;
  dug: Uint8Array; placed: Map<number, number[]>; touched: Set<number>;
  /** Adornos y vía tal como salen del dato, para saber qué celdas cambió el jugador y poder deshacerlo. */
  origin: { deco: Uint8Array; road: Uint8Array };
};

/** Pieza que el jugador puede poner. `height` es lo que ocupa en la columna; `parts` son las cajas que la dibujan. */
export type Piece = { id: string; label: string; brief: string; css: string; height: number; builds: boolean; parts: { size: [number, number, number]; lift: number; color: number }[] };
export const PIECES: Piece[] = [
  { id: "vivienda", label: "Vivienda", brief: "Vivienda", css: "#ece4d6", height: 1, builds: true, parts: [{ size: [0.9, 0.7, 0.9], lift: 0.35, color: 0xece4d6 }, { size: [1, 0.3, 1], lift: 0.85, color: 0xc0694a }] },
  { id: "panel", label: "Panel solar", brief: "Panel", css: "#2b57a8", height: 0.4, builds: true, parts: [{ size: [0.16, 0.3, 0.16], lift: 0.15, color: 0x8a8f94 }, { size: [0.95, 0.1, 0.95], lift: 0.35, color: 0x2b57a8 }] },
  { id: "muro", label: "Muro de defensa", brief: "Muro", css: "#8f9499", height: 1, builds: false, parts: [{ size: [1, 1, 1], lift: 0.5, color: 0x8f9499 }] },
  { id: "arbol", label: "Árbol", brief: "Árbol", css: "#3c8a47", height: 3, builds: false, parts: [{ size: [0.28, 2, 0.28], lift: 1, color: 0x6b4a2e }, { size: [1.06, 1.06, 1.06], lift: 2.5, color: 0x3c8a47 }] },
  { id: "via", label: "Vía", brief: "Vía", css: "#f1c84b", height: 0.15, builds: true, parts: [{ size: [0.95, 0.15, 0.95], lift: 0.075, color: 0xf1c84b }] },
  { id: "relleno", label: "Relleno", brief: "Relleno", css: "#9a7650", height: 1, builds: false, parts: [{ size: [1, 1, 1], lift: 0.5, color: 0x9a7650 }] },
];

export const WATER = 80;
export const BUILT = 50;
const TREES = new Set([10, 95]);
/** El agua queda un poco por debajo del borde del bloque, como en un juego de bloques. */
export const WATER_DROP = 0.2;

export const COVER: Record<number, { label: string; color: number }> = {
  0: { label: "Sin dato", color: 0x565c62 },
  10: { label: "Árboles", color: 0x3f8f4a },
  20: { label: "Matorral", color: 0x9aa35a },
  30: { label: "Pastizal", color: 0x7fb85a },
  40: { label: "Cultivo", color: 0xbcc94f },
  50: { label: "Zona construida", color: 0xb9aea3 },
  60: { label: "Suelo desnudo", color: 0xcda975 },
  70: { label: "Nieve o hielo", color: 0xf1f5f7 },
  80: { label: "Agua", color: 0x2f7fc4 },
  90: { label: "Humedal", color: 0x4aa39a },
  95: { label: "Manglar", color: 0x2f7a5e },
  100: { label: "Musgo y líquenes", color: 0xa7b08a },
};

export const KIND: Record<BeaconKind, { label: string; color: number; css: string }> = {
  evento: { label: "Evento en curso", color: 0xee7180, css: "#ee7180" },
  amenaza: { label: "Amenaza", color: 0xf0934a, css: "#f0934a" },
  pista_falsa: { label: "Pista falsa", color: 0x74a0ff, css: "#74a0ff" },
  oportunidad: { label: "Oportunidad", color: 0x75e59a, css: "#75e59a" },
  infraestructura: { label: "Infraestructura", color: 0xf1c84b, css: "#f1c84b" },
  brecha: { label: "Lo que falta saber", color: 0xb5bdc4, css: "#b5bdc4" },
};

/** Clases de pendiente de la vista «Pendientes»: de 15° en adelante es la ladera que la plataforma marca como fuerte. */
export const SLOPE_CLASSES = [
  { from: 25, label: "25° o más", color: 0xd9404f },
  { from: 15, label: "15° a 25°", color: 0xf0934a },
  { from: 8, label: "8° a 15°", color: 0xe9c75a },
  { from: 0, label: "Menos de 8°", color: 0x52626a },
];

function bytes(base64: string): Uint8Array {
  const text = atob(base64);
  const out = new Uint8Array(text.length);
  for (let index = 0; index < text.length; index += 1) out[index] = text.charCodeAt(index);
  return out;
}

/** Número estable por celda: decide el matiz de cada bloque y dónde hay árbol o volumen, igual en cada visita. */
export function cellHash(row: number, col: number, salt = 0): number {
  let value = Math.imul(row * 73856093 ^ col * 19349663 ^ salt * 83492791, 2654435761);
  value ^= value >>> 15;
  return ((value >>> 0) % 1000) / 1000;
}

/** Altura del adorno de una celda, en bloques: árbol (3), volumen de zona construida (1 o 2) o nada. */
export function decorationHeight(cover: number, slope: number, row: number, col: number): number {
  const chance = cellHash(row, col, 7);
  if (TREES.has(cover)) return chance < 0.22 && slope < 40 ? 3 : 0;
  if (cover === BUILT) return chance < 0.42 ? (cellHash(row, col, 11) < 0.25 ? 2 : 1) : 0;
  return 0;
}

export function decodeGrid(zone: Zone): ZoneGrid {
  const size = zone.grid;
  const raw = bytes(zone.heights_b64);
  const view = new DataView(raw.buffer);
  const heights = new Uint16Array(size * size);
  for (let index = 0; index < heights.length; index += 1) heights[index] = view.getUint16(index * 2, true);
  const cover = bytes(zone.cover_b64);
  const slope = bytes(zone.slope_b64);
  if (raw.length !== size * size * 2 || cover.length !== size * size || slope.length !== size * size) throw new Error("La cuadrícula de la zona no coincide con su tamaño.");
  // Celdas de vía: cada tramo se recorre en pasos de un cuarto de celda para no dejar huecos en diagonal.
  const road = new Uint8Array(size * size);
  for (const path of zone.paths) {
    for (let index = 1; index < path.coordinates.length; index += 1) {
      const from = toScene(zone, path.coordinates[index - 1][1], path.coordinates[index - 1][0]);
      const to = toScene(zone, path.coordinates[index][1], path.coordinates[index][0]);
      const steps = Math.max(1, Math.ceil(Math.hypot(to.x - from.x, to.z - from.z) * 4));
      for (let step = 0; step <= steps; step += 1) {
        const x = from.x + ((to.x - from.x) * step) / steps;
        const z = from.z + ((to.z - from.z) * step) / steps;
        if (x >= 0 && x < size && z >= 0 && z < size) road[Math.floor(z) * size + Math.floor(x)] = 1;
      }
    }
  }
  const deco = new Uint8Array(size * size);
  const solid = new Float32Array(size * size);
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      const index = row * size + col;
      deco[index] = road[index] ? 0 : decorationHeight(cover[index], slope[index], row, col);
      solid[index] = surfaceTop(heights[index], cover[index]) + deco[index];
    }
  }
  return { size, heights, cover, slope, road, deco, solid, dug: new Uint8Array(size * size), placed: new Map(), touched: new Set(), origin: { deco: deco.slice(), road: road.slice() } };
}

/** Cara superior del terreno que queda en una celda, descontado lo que el jugador quitó. */
export function groundTop(grid: ZoneGrid, index: number): number {
  return surfaceTop(grid.heights[index] - grid.dug[index], grid.dug[index] ? 0 : grid.cover[index]);
}

/** Recalcula la altura que se pisa en una celda después de un cambio del jugador. */
export function refreshSolid(grid: ZoneGrid, index: number): void {
  const pieces = grid.placed.get(index) ?? [];
  grid.solid[index] = groundTop(grid, index) + grid.deco[index] + pieces.reduce((sum, piece) => sum + PIECES[piece].height, 0);
}

/** Cara superior de una celda en unidades de la escena (un bloque = una unidad; el bloque cero también se dibuja). */
export function surfaceTop(height: number, cover: number): number {
  return height + 1 - (cover === WATER ? WATER_DROP : 0);
}

/** Posición en la escena de un punto geográfico: x hacia el este, z hacia el sur. */
export function toScene(zone: Zone, latitude: number, longitude: number): { x: number; z: number } {
  const [west, south, east, north] = zone.bounds;
  return { x: ((longitude - west) / (east - west)) * zone.grid, z: ((north - latitude) / (north - south)) * zone.grid };
}

export function cellIndex(grid: ZoneGrid, x: number, z: number): number {
  const col = Math.min(grid.size - 1, Math.max(0, Math.floor(x)));
  const row = Math.min(grid.size - 1, Math.max(0, Math.floor(z)));
  return row * grid.size + col;
}

/** Elevación real de una celda en metros: deshace la exageración vertical declarada. */
export function realElevation(zone: Zone, height: number): number {
  return zone.base_elevation_m + (height * zone.cell_m) / zone.vertical_exaggeration;
}

const COMPASS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
/** Rumbo de la mirada: con giro cero la cámara mira al norte y el giro positivo va hacia el oeste. */
export function heading(yaw: number): string {
  const degrees = (((-yaw * 180) / Math.PI) % 360 + 360) % 360;
  return COMPASS[Math.round(degrees / 45) % 8];
}
