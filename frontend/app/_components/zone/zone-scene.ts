// Escena de la maqueta en bloques (ADR-047): una sola malla para el terreno, mallas instanciadas para árboles, volúmenes
// y vía, y una baliza por hallazgo. Colores planos, sin texturas ni sombras, para que corra en equipos modestos.

import {
  AmbientLight, BoxGeometry, BufferAttribute, BufferGeometry, CanvasTexture, Color, DirectionalLight, Fog, HemisphereLight, InstancedMesh, Material, Matrix4,
  Mesh, MeshBasicMaterial, MeshLambertMaterial, Object3D, PlaneGeometry, Quaternion, Scene, Sprite, SpriteMaterial, Texture, Vector3,
} from "three";
import { BUILT, COVER, KIND, SLOPE_CLASSES, WATER, cellHash, surfaceTop, toScene, type Zone, type ZoneGrid } from "./zone-data";

export const SKY = 0x9fcbe9;
const EARTH = 0x8a6a4a;
const ROCK = 0x74706c;
const ROAD = 0xf1c84b;
const ROOFS = [0xece4d6, 0xd9c8ac, 0xc98f6b, 0xdfd6c6];
/** Alto de la etiqueta de una baliza como fracción de la distancia unitaria a la cámara (≈ 3 % del alto de pantalla). */
const LABEL_HEIGHT = 0.046;

export type BeaconPoint = { id: string; x: number; y: number; z: number };
export type ZoneScene = { scene: Scene; beacons: BeaconPoint[]; setSlopeView: (on: boolean) => void; animate: (seconds: number) => void; dispose: () => void };

function slopeColor(degrees: number): number {
  return (SLOPE_CLASSES.find((item) => degrees >= item.from) ?? SLOPE_CLASSES[SLOPE_CLASSES.length - 1]).color;
}

/** Terreno: cara superior de cada celda y solo las caras laterales que quedan a la vista, bloque por bloque. */
function terrain(grid: ZoneGrid): { geometry: BufferGeometry; cover: BufferAttribute; slope: BufferAttribute } {
  const { size } = grid;
  const positions: number[] = [], normals: number[] = [], coverColors: number[] = [], slopeColors: number[] = [], indices: number[] = [];
  const cache = new Map<number, Color>();
  const color = (hex: number) => cache.get(hex) ?? cache.set(hex, new Color(hex)).get(hex)!;
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
  const top = (row: number, col: number) => (row < 0 || col < 0 || row >= size || col >= size ? 0 : surfaceTop(grid.heights[row * size + col], grid.cover[row * size + col]));

  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      const index = row * size + col;
      const cover = grid.cover[index];
      const y = top(row, col);
      const x = col, z = row;
      const tint = 0.9 + 0.2 * cellHash(row, col);
      const surface = color((COVER[cover] ?? COVER[0]).color);
      const steep = color(cover === WATER ? 0x27506e : slopeColor(grid.slope[index]));
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
          const depth = y - y1;
          const layer = depth < 0.99 ? surface : color(depth < 3 ? EARTH : ROCK);
          const shade = (depth < 0.99 ? 0.84 : 0.9) * (0.92 + 0.16 * cellHash(row, col, level + 1));
          quad(corners(y0, y1), normal, layer, shade, depth < 0.99 ? steep : layer, shade * (depth < 0.99 ? 1 : 0.7));
        }
      }
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(new Float32Array(positions), 3));
  geometry.setAttribute("normal", new BufferAttribute(new Float32Array(normals), 3));
  const cover = new BufferAttribute(new Float32Array(coverColors), 3);
  const slope = new BufferAttribute(new Float32Array(slopeColors), 3);
  geometry.setAttribute("color", cover);
  geometry.setIndex(new BufferAttribute(new Uint32Array(indices), 1));
  geometry.computeBoundingSphere();
  return { geometry, cover, slope };
}

type Piece = { x: number; y: number; z: number; sx: number; sy: number; sz: number; color: number; tint: number };

function instanced(pieces: Piece[]): InstancedMesh | null {
  if (!pieces.length) return null;
  const mesh = new InstancedMesh(new BoxGeometry(1, 1, 1), new MeshLambertMaterial(), pieces.length);
  const matrix = new Matrix4(), still = new Quaternion(), tone = new Color();
  pieces.forEach((piece, index) => {
    matrix.compose(new Vector3(piece.x, piece.y, piece.z), still, new Vector3(piece.sx, piece.sy, piece.sz));
    mesh.setMatrixAt(index, matrix);
    mesh.setColorAt(index, tone.set(piece.color).multiplyScalar(piece.tint));
  });
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  mesh.computeBoundingSphere();
  return mesh;
}

/** Árboles, volúmenes de zona construida y losas de la vía. Son señales de la cobertura, no objetos reales. */
function decorations(grid: ZoneGrid): Piece[] {
  const pieces: Piece[] = [];
  const { size } = grid;
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      const index = row * size + col;
      const ground = surfaceTop(grid.heights[index], grid.cover[index]);
      const x = col + 0.5, z = row + 0.5;
      if (grid.road[index]) pieces.push({ x, y: ground + 0.05, z, sx: 0.74, sy: 0.1, sz: 0.74, color: ROAD, tint: 0.94 + 0.12 * cellHash(row, col, 3) });
      const height = grid.deco[index];
      if (!height) continue;
      if (grid.cover[index] === BUILT) {
        pieces.push({ x, y: ground + height / 2, z, sx: 0.86, sy: height, sz: 0.86, color: ROOFS[Math.floor(cellHash(row, col, 5) * ROOFS.length)], tint: 0.95 + 0.1 * cellHash(row, col, 9) });
      } else {
        pieces.push({ x, y: ground + 1, z, sx: 0.28, sy: 2, sz: 0.28, color: 0x6b4a2e, tint: 1 });
        pieces.push({ x, y: ground + 2.5, z, sx: 1.06, sy: 1.06, sz: 1.06, color: grid.cover[index] === 95 ? 0x2f7a5e : 0x3c8a47, tint: 0.85 + 0.3 * cellHash(row, col, 13) });
      }
    }
  }
  return pieces;
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

  const ground = terrain(grid);
  scene.add(new Mesh(ground.geometry, new MeshLambertMaterial({ vertexColors: true })));
  const table = new Mesh(new PlaneGeometry(1600, 1600), new MeshBasicMaterial({ color: 0x2b3a42 }));
  table.rotation.x = -Math.PI / 2;
  table.position.set(grid.size / 2, -0.02, grid.size / 2);
  scene.add(table);
  const pieces = instanced(decorations(grid));
  if (pieces) scene.add(pieces);

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
    setSlopeView: (on) => { ground.geometry.setAttribute("color", on ? ground.slope : ground.cover); },
    animate: (seconds) => {
      if (still) return;
      for (const gem of gems) {
        gem.mesh.rotation.y = seconds * 0.9 + gem.phase;
        // El bloque sube y baja a saltos, como los marcadores del globo.
        gem.mesh.position.y = gem.base + Math.round((0.5 + 0.5 * Math.sin(seconds * 1.6 + gem.phase)) * 4) * 0.12;
      }
    },
    dispose: () => {
      scene.traverse((object) => {
        const item = object as Mesh & { material?: Material | Material[] };
        item.geometry?.dispose();
        for (const material of Array.isArray(item.material) ? item.material : item.material ? [item.material] : []) {
          (material as Material & { map?: Texture | null }).map?.dispose();
          material.dispose();
        }
      });
    },
  };
}
