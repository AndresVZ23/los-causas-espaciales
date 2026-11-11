// Escena de la maqueta en bloques (ADR-047): el terreno en trozos de 25 × 25 celdas, mallas instanciadas para árboles,
// volúmenes, vía y piezas del jugador, y una baliza por hallazgo. Colores planos, sin texturas ni sombras, para que
// corra en equipos modestos. Al poner o quitar un bloque solo se rehacen los trozos afectados.

import {
  AmbientLight, BoxGeometry, BufferAttribute, BufferGeometry, CanvasTexture, Color, DirectionalLight, EdgesGeometry, Fog, HemisphereLight, InstancedMesh,
  LineBasicMaterial, LineSegments, Material, Matrix4, Mesh, MeshBasicMaterial, MeshLambertMaterial, Object3D, PlaneGeometry, Quaternion, Scene, Sprite, SpriteMaterial,
  Texture, Vector3,
} from "three";
import { BUILT, COVER, KIND, PIECES, SLOPE_CLASSES, WATER, cellHash, groundTop, surfaceTop, toScene, type Zone, type ZoneGrid } from "./zone-data";
import type { Target } from "./zone-world";

export const SKY = 0x9fcbe9;
const EARTH = 0x8a6a4a;
const ROCK = 0x74706c;
const ROAD = 0xf1c84b;
const CHANGED = 0x3a4348;
const ROOFS = [0xece4d6, 0xd9c8ac, 0xc98f6b, 0xdfd6c6];
const CHUNK = 25;
/** Alto de la etiqueta de una baliza como fracción de la distancia unitaria a la cámara (≈ 3 % del alto de pantalla). */
const LABEL_HEIGHT = 0.046;

export type BeaconPoint = { id: string; x: number; y: number; z: number };
export type ZoneScene = {
  scene: Scene; beacons: BeaconPoint[]; setSlopeView: (on: boolean) => void; animate: (seconds: number) => void;
  /** Redibuja lo que cambió en esas celdas. */
  refresh: (indices: number[]) => void;
  /** Redibuja todo (después de deshacer los cambios). */
  rebuild: () => void;
  highlight: (target: Target | null) => void; dispose: () => void;
};

function slopeColor(degrees: number): number {
  return (SLOPE_CLASSES.find((item) => degrees >= item.from) ?? SLOPE_CLASSES[SLOPE_CLASSES.length - 1]).color;
}

const palette = new Map<number, Color>();
const tone = (hex: number) => palette.get(hex) ?? palette.set(hex, new Color(hex)).get(hex)!;

/** Un trozo del terreno: cara superior de cada celda y solo las caras laterales a la vista, bloque por bloque. */
function chunkGeometry(grid: ZoneGrid, row0: number, col0: number): { geometry: BufferGeometry; cover: BufferAttribute; slope: BufferAttribute } {
  const { size } = grid;
  const positions: number[] = [], normals: number[] = [], coverColors: number[] = [], slopeColors: number[] = [], indices: number[] = [];
  const quad = (corners: number[], normal: [number, number, number], a: Color, fa: number, b: Color, fb: number) => {
    const base = positions.length / 3;
    positions.push(...corners);
    for (let vertex = 0; vertex < 4; vertex += 1) {
      normals.push(normal[0], normal[1], normal[2]);
      coverColors.push(a.r * fa, a.g * fa, a.b * fa);
      slopeColors.push(b.r * fb, b.g * fb, b.b * fb);
    }
    indices.push(base, base + 1, base + 2, base, base + 2, base + 3);
  };
  const top = (row: number, col: number) => (row < 0 || col < 0 || row >= size || col >= size ? 0 : groundTop(grid, row * size + col));

  for (let row = row0; row < Math.min(row0 + CHUNK, size); row += 1) {
    for (let col = col0; col < Math.min(col0 + CHUNK, size); col += 1) {
      const index = row * size + col;
      const cover = grid.cover[index];
      const dug = grid.dug[index];
      const y = top(row, col);
      const original = surfaceTop(grid.heights[index], cover);
      const x = col, z = row;
      const tint = 0.9 + 0.2 * cellHash(row, col);
      const natural = tone((COVER[cover] ?? COVER[0]).color);
      // Una celda excavada muestra tierra o roca, y en la vista de pendientes queda en gris: ya no es terreno medido.
      const surface = dug ? tone(dug < 3 ? EARTH : ROCK) : natural;
      const steep = tone(dug ? CHANGED : cover === WATER ? 0x27506e : slopeColor(grid.slope[index]));
      quad([x, y, z, x, y, z + 1, x + 1, y, z + 1, x + 1, y, z], [0, 1, 0], surface, tint, steep, tint);

      const sides: [number, number, [number, number, number], (y0: number, y1: number) => number[]][] = [
        [row, col + 1, [1, 0, 0], (y0, y1) => [x + 1, y0, z + 1, x + 1, y0, z, x + 1, y1, z, x + 1, y1, z + 1]],
        [row, col - 1, [-1, 0, 0], (y0, y1) => [x, y0, z, x, y0, z + 1, x, y1, z + 1, x, y1, z]],
        [row + 1, col, [0, 0, 1], (y0, y1) => [x, y0, z + 1, x + 1, y0, z + 1, x + 1, y1, z + 1, x, y1, z + 1]],
        [row - 1, col, [0, 0, -1], (y0, y1) => [x + 1, y0, z, x, y0, z, x, y1, z, x + 1, y1, z]],
      ];
      for (const [nRow, nCol, normal, corners] of sides) {
        const floor = top(nRow, nCol);
        for (let level = Math.floor(floor); level < y; level += 1) {
          const y0 = Math.max(level, floor), y1 = Math.min(level + 1, y);
          if (y1 - y0 < 0.001) continue;
          const depth = original - y1;
          const crust = depth < 0.99;
          const layer = crust ? natural : tone(depth < 3 ? EARTH : ROCK);
          const shade = (crust ? 0.84 : 0.9) * (0.92 + 0.16 * cellHash(row, col, level + 1));
          quad(corners(y0, y1), normal, layer, shade, crust ? steep : layer, shade * (crust ? 1 : 0.7));
        }
      }
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(new Float32Array(positions), 3));
  geometry.setAttribute("normal", new BufferAttribute(new Float32Array(normals), 3));
  const cover = new BufferAttribute(new Float32Array(coverColors), 3);
  const slope = new BufferAttribute(new Float32Array(slopeColors), 3);
  geometry.setIndex(new BufferAttribute(new Uint32Array(indices), 1));
  geometry.computeBoundingSphere();
  return { geometry, cover, slope };
}

type Box = { x: number; y: number; z: number; sx: number; sy: number; sz: number; color: number; tint: number };

/** Árboles, volúmenes de zona construida y losas de la vía. Son señales de la cobertura, no objetos reales. */
function decorations(grid: ZoneGrid): Box[] {
  const boxes: Box[] = [];
  const { size } = grid;
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      const index = row * size + col;
      const ground = groundTop(grid, index);
      const x = col + 0.5, z = row + 0.5;
      if (grid.road[index]) boxes.push({ x, y: ground + 0.05, z, sx: 0.74, sy: 0.1, sz: 0.74, color: ROAD, tint: 0.94 + 0.12 * cellHash(row, col, 3) });
      const height = grid.deco[index];
      if (!height) continue;
      if (grid.cover[index] === BUILT) {
        boxes.push({ x, y: ground + height / 2, z, sx: 0.86, sy: height, sz: 0.86, color: ROOFS[Math.floor(cellHash(row, col, 5) * ROOFS.length)], tint: 0.95 + 0.1 * cellHash(row, col, 9) });
      } else {
        boxes.push({ x, y: ground + 1, z, sx: 0.28, sy: 2, sz: 0.28, color: 0x6b4a2e, tint: 1 });
        boxes.push({ x, y: ground + 2.5, z, sx: 1.06, sy: 1.06, sz: 1.06, color: grid.cover[index] === 95 ? 0x2f7a5e : 0x3c8a47, tint: 0.85 + 0.3 * cellHash(row, col, 13) });
      }
    }
  }
  return boxes;
}

/** Piezas que puso el jugador, apiladas sobre el terreno y el adorno de su celda. */
function placedBoxes(grid: ZoneGrid): Box[] {
  const boxes: Box[] = [];
  for (const [index, stack] of grid.placed) {
    const row = Math.floor(index / grid.size), col = index % grid.size;
    let base = groundTop(grid, index) + grid.deco[index];
    for (const id of stack) {
      const piece = PIECES[id];
      for (const part of piece.parts) boxes.push({ x: col + 0.5, y: base + part.lift, z: row + 0.5, sx: part.size[0], sy: part.size[1], sz: part.size[2], color: part.color, tint: 1 });
      base += piece.height;
    }
  }
  return boxes;
}

function label(text: string, accent: string): Sprite {
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d")!;
  const font = "600 40px system-ui, 'Segoe UI', sans-serif";
  context.font = font;
  const short = text.length > 38 ? `${text.slice(0, 37).trimEnd()}…` : text;
  canvas.width = Math.ceil(context.measureText(short).width) + 64;
  canvas.height = 76;
  context.fillStyle = "rgba(8,12,13,.9)";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = accent;
  context.fillRect(0, 0, 12, canvas.height);
  context.font = font;
  context.fillStyle = "#e8eaed";
  context.textBaseline = "middle";
  context.fillText(short, 34, canvas.height / 2 + 2);
  // Tamaño constante en pantalla (unos 30 px de alto): la etiqueta se lee igual de lejos y no tapa la vista de cerca.
  const sprite = new Sprite(new SpriteMaterial({ map: new CanvasTexture(canvas), depthTest: false, fog: false, transparent: true, sizeAttenuation: false }));
  sprite.scale.set((canvas.width / canvas.height) * LABEL_HEIGHT, LABEL_HEIGHT, 1);
  sprite.renderOrder = 5;
  return sprite;
}

export function buildZoneScene(zone: Zone, grid: ZoneGrid, still: boolean): ZoneScene {
  const scene = new Scene();
  scene.background = new Color(SKY);
  scene.fog = new Fog(SKY, 130, 340);
  scene.add(new HemisphereLight(0xffffff, 0x8a7560, 1.5), new AmbientLight(0xffffff, 0.35));
  const sun = new DirectionalLight(0xfff4e0, 1.9);
  sun.position.set(-0.55, 1, -0.35);
  scene.add(sun);
  const table = new Mesh(new PlaneGeometry(1600, 1600), new MeshBasicMaterial({ color: 0x2b3a42 }));
  table.rotation.x = -Math.PI / 2;
  table.position.set(grid.size / 2, -0.02, grid.size / 2);
  scene.add(table);

  // Terreno por trozos.
  const across = Math.ceil(grid.size / CHUNK);
  const ground = new MeshLambertMaterial({ vertexColors: true });
  let slopeView = false;
  const chunks: { mesh: Mesh; cover: BufferAttribute; slope: BufferAttribute }[] = [];
  const drawChunk = (number: number) => {
    const built = chunkGeometry(grid, Math.floor(number / across) * CHUNK, (number % across) * CHUNK);
    built.geometry.setAttribute("color", slopeView ? built.slope : built.cover);
    const previous = chunks[number];
    if (previous) {
      previous.mesh.geometry.dispose();
      previous.mesh.geometry = built.geometry;
      previous.cover = built.cover; previous.slope = built.slope;
    } else {
      const mesh = new Mesh(built.geometry, ground);
      scene.add(mesh);
      chunks[number] = { mesh, cover: built.cover, slope: built.slope };
    }
  };
  for (let number = 0; number < across * across; number += 1) drawChunk(number);

  // Adornos y piezas del jugador: una malla instanciada cada uno, rehecha entera cuando cambia (son pocas cajas).
  const unit = new BoxGeometry(1, 1, 1);
  const flat = new MeshLambertMaterial();
  const matrix = new Matrix4(), upright = new Quaternion(), shade = new Color();
  const boxMesh = (boxes: Box[]): InstancedMesh | null => {
    if (!boxes.length) return null;
    const mesh = new InstancedMesh(unit, flat, boxes.length);
    boxes.forEach((box, index) => {
      matrix.compose(new Vector3(box.x, box.y, box.z), upright, new Vector3(box.sx, box.sy, box.sz));
      mesh.setMatrixAt(index, matrix);
      mesh.setColorAt(index, shade.set(box.color).multiplyScalar(box.tint));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
    return mesh;
  };
  const swap = (current: InstancedMesh | null, boxes: Box[]): InstancedMesh | null => {
    if (current) { scene.remove(current); current.dispose(); }
    const mesh = boxMesh(boxes);
    if (mesh) scene.add(mesh);
    return mesh;
  };
  let decoMesh = swap(null, decorations(grid));
  let placedMesh = swap(null, placedBoxes(grid));

  // Bloque al que apunta el jugador: un marco de aristas y una lámina clara sobre su cara superior. Se dibujan por
  // encima del terreno para que se vean aunque el bloque quede medio tapado.
  const frame = new LineSegments(new EdgesGeometry(new BoxGeometry(1.02, 1.02, 1.02)), new LineBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.9 }));
  const lid = new Mesh(new BoxGeometry(1, 0.04, 1), new MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.32, depthWrite: false, fog: false }));
  frame.visible = lid.visible = false;
  frame.renderOrder = lid.renderOrder = 4;
  scene.add(frame, lid);

  const gems: { mesh: Object3D; base: number; phase: number }[] = [];
  const beacons: BeaconPoint[] = zone.beacons.map((beacon, index) => {
    const { x, z } = toScene(zone, beacon.latitude, beacon.longitude);
    const col = Math.min(grid.size - 1, Math.max(0, Math.floor(x))), row = Math.min(grid.size - 1, Math.max(0, Math.floor(z)));
    const y = grid.solid[row * grid.size + col];
    const kind = KIND[beacon.kind];
    const beam = new Mesh(new BoxGeometry(0.45, 80, 0.45), new MeshBasicMaterial({ color: kind.color, transparent: true, opacity: 0.4, depthWrite: false, fog: false }));
    beam.position.set(col + 0.5, y + 40, row + 0.5);
    const gem = new Mesh(new BoxGeometry(1.1, 1.1, 1.1), new MeshLambertMaterial({ color: kind.color, emissive: kind.color, emissiveIntensity: 0.45 }));
    gem.position.set(col + 0.5, y + 3.8, row + 0.5);
    const tag = label(beacon.title, kind.css);
    tag.position.set(col + 0.5, y + 6.6, row + 0.5);
    scene.add(beam, gem, tag);
    gems.push({ mesh: gem, base: y + 3.8, phase: index * 1.3 });
    return { id: beacon.id, x: col + 0.5, y, z: row + 0.5 };
  });

  return {
    scene, beacons,
    setSlopeView: (on) => {
      slopeView = on;
      for (const chunk of chunks) chunk.mesh.geometry.setAttribute("color", on ? chunk.slope : chunk.cover);
    },
    animate: (seconds) => {
      if (still) return;
      for (const gem of gems) {
        gem.mesh.rotation.y = seconds * 0.9 + gem.phase;
        // El bloque sube y baja a saltos, como los marcadores del globo.
        gem.mesh.position.y = gem.base + Math.round((0.5 + 0.5 * Math.sin(seconds * 1.6 + gem.phase)) * 4) * 0.12;
      }
    },
    refresh: (indices) => {
      // La cara lateral de una celda depende de su vecina: se rehacen también los trozos de las cuatro vecinas.
      const dirty = new Set<number>();
      for (const index of indices) {
        const row = Math.floor(index / grid.size), col = index % grid.size;
        for (const [r, c] of [[row, col], [row - 1, col], [row + 1, col], [row, col - 1], [row, col + 1]]) {
          if (r >= 0 && c >= 0 && r < grid.size && c < grid.size) dirty.add(Math.floor(r / CHUNK) * across + Math.floor(c / CHUNK));
        }
      }
      dirty.forEach(drawChunk);
      decoMesh = swap(decoMesh, decorations(grid));
      placedMesh = swap(placedMesh, placedBoxes(grid));
    },
    rebuild: () => {
      for (let number = 0; number < across * across; number += 1) drawChunk(number);
      decoMesh = swap(decoMesh, decorations(grid));
      placedMesh = swap(placedMesh, placedBoxes(grid));
    },
    highlight: (target) => {
      frame.visible = lid.visible = Boolean(target);
      if (!target) return;
      const top = grid.solid[target.index];
      const x = (target.index % grid.size) + 0.5, z = Math.floor(target.index / grid.size) + 0.5;
      frame.position.set(x, Math.max(0.5, top - 0.5), z);
      lid.position.set(x, top + 0.03, z);
    },
    dispose: () => {
      scene.traverse((object) => {
        const item = object as Mesh & { material?: Material | Material[] };
        item.geometry?.dispose();
        for (const material of Array.isArray(item.material) ? item.material : item.material ? [item.material] : []) {
          (material as Material & { map?: Texture | null }).map?.dispose();
          material.dispose();
        }
        if ((object as InstancedMesh).isInstancedMesh) (object as InstancedMesh).dispose();
      });
    },
  };
}
