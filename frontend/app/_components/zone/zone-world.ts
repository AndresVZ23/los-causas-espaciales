// Lo que el jugador hace en la maqueta: apuntar a un bloque, quitarlo o poner una pieza encima. Sin three.js.
// El dato (relieve, cobertura, pendiente) nunca cambia: lo puesto y lo quitado se guardan aparte y se pueden deshacer.

import { BUILT, COVER, PIECES, WATER, refreshSolid, type Piece, type ZoneGrid } from "./zone-data";

/** Alcance del jugador, en bloques, y tope de piezas apiladas en una celda. */
export const REACH = 7;
export const MAX_STACK = 12;

/** Bloque al que apunta el jugador: `index` es la celda que se quita; `placeIndex`, la celda donde caería una pieza. */
export type Target = { index: number; placeIndex: number };

/** Primer bloque sólido en la línea de la mirada, recorriendo la cuadrícula celda por celda (Amanatides y Woo). */
export function raycast(grid: ZoneGrid, origin: [number, number, number], direction: [number, number, number], reach = REACH): Target | null {
  const { size } = grid;
  const cell = origin.map(Math.floor);
  const step = direction.map((value) => (value > 0 ? 1 : -1));
  const delta = direction.map((value) => (value !== 0 ? Math.abs(1 / value) : Infinity));
  const next = direction.map((value, axis) => (value !== 0 ? (value > 0 ? cell[axis] + 1 - origin[axis] : origin[axis] - cell[axis]) / Math.abs(value) : Infinity));
  let previous = -1;
  for (let travelled = 0; travelled <= reach;) {
    const [x, y, z] = cell;
    if (y < 0) return null;
    const inside = x >= 0 && z >= 0 && x < size && z < size;
    const index = inside ? z * size + x : -1;
    if (inside && y < grid.solid[index]) return { index, placeIndex: previous >= 0 ? previous : index };
    previous = index;
    const axis = next[0] < next[1] && next[0] < next[2] ? 0 : next[1] < next[2] ? 1 : 2;
    cell[axis] += step[axis];
    travelled = next[axis];
    next[axis] += delta[axis];
  }
  return null;
}

/** Quita lo de más arriba de una celda: pieza puesta, adorno, vía o un bloque de terreno. Devuelve qué quitó. */
export function breakTop(grid: ZoneGrid, index: number): string | null {
  const stack = grid.placed.get(index);
  let removed: string | null = null;
  if (stack?.length) {
    removed = PIECES[stack.pop()!].label.toLowerCase();
    if (!stack.length) grid.placed.delete(index);
  } else if (grid.deco[index]) {
    removed = grid.cover[index] === BUILT ? "volumen de zona construida" : "árbol";
    grid.deco[index] = 0;
  } else if (grid.road[index]) {
    removed = "losa de la vía";
    grid.road[index] = 0;
  } else if (grid.cover[index] !== WATER && grid.heights[index] - grid.dug[index] > 0) {
    removed = "bloque de terreno";
    grid.dug[index] += 1;
  }
  if (!removed) return null;
  settle(grid, index);
  return removed;
}

/** Tras un cambio: recalcula la altura que se pisa y anota la celda como cambiada, o la borra si volvió a su estado original. */
function settle(grid: ZoneGrid, index: number): void {
  refreshSolid(grid, index);
  const same = !grid.dug[index] && !grid.placed.has(index) && grid.deco[index] === grid.origin.deco[index] && grid.road[index] === grid.origin.road[index];
  if (same) grid.touched.delete(index); else grid.touched.add(index);
}

/** Pone una pieza encima de una celda. Falso si la columna ya está en el tope. */
export function placePiece(grid: ZoneGrid, index: number, piece: number): boolean {
  const stack = grid.placed.get(index) ?? [];
  if (stack.length >= MAX_STACK) return false;
  stack.push(piece);
  grid.placed.set(index, stack);
  settle(grid, index);
  return true;
}

/** Deshace todo lo que el jugador cambió y vuelve a la maqueta construida con el dato. */
export function restore(grid: ZoneGrid): void {
  const changed = [...grid.touched];
  grid.deco.set(grid.origin.deco);
  grid.road.set(grid.origin.road);
  grid.dug.fill(0);
  grid.placed.clear();
  grid.touched.clear();
  for (const index of changed) refreshSolid(grid, index);
}

/**
 * Lectura rápida de la celda donde se puso una pieza, con la pendiente real y la cobertura del dato. Usa el mismo
 * umbral de 15° que la plataforma. No es un estudio: dice qué conviene mirar primero.
 */
export function assess(grid: ZoneGrid, index: number, piece: Piece): string {
  const slope = grid.slope[index];
  const cover = grid.cover[index];
  const where = `pendiente real ${slope}°, ${(COVER[cover] ?? COVER[0]).label.toLowerCase()}`;
  if (cover === WATER) return `${piece.label} sobre agua: WorldCover clasifica esta celda como agua permanente.`;
  if (cover === 0) return `${piece.label} en una celda sin dato de cobertura (${where}).`;
  if (!piece.builds) return `${piece.label} (${where}).`;
  if (slope >= 25) return `${piece.label} en ladera muy fuerte (${where}). Primero, estabilidad de taludes.`;
  if (slope >= 15) return `${piece.label} en ladera fuerte (${where}): supera el umbral de 15° de la plataforma. Primero, topografía de detalle.`;
  if (slope >= 8) return `${piece.label} en pendiente moderada (${where}): encarece la obra.`;
  if (piece.id === "panel" && [20, 30, 60].includes(cover)) return `${piece.label} en terreno llano y sin árboles (${where}): candidato para estudiar con el módulo Energía.`;
  return `${piece.label} en terreno llano (${where}): aquí el relieve no es el freno.`;
}
