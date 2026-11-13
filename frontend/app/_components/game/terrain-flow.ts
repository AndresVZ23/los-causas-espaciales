// Por dónde corre el agua en el relieve del juego (Copernicus DEM GLO-30, ya suavizado y exagerado como se dibuja).
// Método «priority-flood» (Barnes, Lehman y Mulla, 2014): se inunda desde los bordes hacia adentro con una cola de
// prioridad; así se rellenan los hoyos y cada celda queda unida al borde por un camino que nunca sube. Con esa red se
// sabe qué celdas son quebradas (drenan poca área) y cuál es el río principal (drena la mayor parte de la zona).
// Es una aproximación visual para el juego, no un modelo hidrológico de la plataforma.

import type * as THREE_NS from "three";

export type Drainage = {
  n: number;
  /** Celda a la que baja el agua desde cada celda (−1 en el borde). */
  down: Int32Array;
  /** Número de celdas que drenan a cada celda, incluida ella misma. */
  acc: Float32Array;
};

/** Montículo binario mínimo de índices por altura. */
class MinHeap {
  private keys: Float64Array;
  private items: Int32Array;
  size = 0;
  constructor(capacity: number) { this.keys = new Float64Array(capacity); this.items = new Int32Array(capacity); }
  push(item: number, key: number) {
    let i = this.size++;
    this.keys[i] = key; this.items[i] = item;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this.keys[p] <= this.keys[i]) break;
      this.swap(i, p); i = p;
    }
  }
  pop(): number {
    const top = this.items[0];
    this.size -= 1;
    if (this.size > 0) {
      this.keys[0] = this.keys[this.size]; this.items[0] = this.items[this.size];
      let i = 0;
      for (;;) {
        const l = i * 2 + 1, r = l + 1;
        let m = i;
        if (l < this.size && this.keys[l] < this.keys[m]) m = l;
        if (r < this.size && this.keys[r] < this.keys[m]) m = r;
        if (m === i) break;
        this.swap(i, m); i = m;
      }
    }
    return top;
  }
  private swap(a: number, b: number) {
    const k = this.keys[a]; this.keys[a] = this.keys[b]; this.keys[b] = k;
    const t = this.items[a]; this.items[a] = this.items[b]; this.items[b] = t;
  }
}

const NEIGHBORS: [number, number][] = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];

export function drainage(heights: Float32Array, n: number): Drainage {
  const total = n * n;
  const filled = new Float32Array(heights);
  const down = new Int32Array(total).fill(-1);
  const seen = new Uint8Array(total);
  const order = new Int32Array(total);
  const heap = new MinHeap(total);
  for (let r = 0; r < n; r += 1) for (let c = 0; c < n; c += 1) {
    if (r !== 0 && c !== 0 && r !== n - 1 && c !== n - 1) continue;
    const i = r * n + c;
    seen[i] = 1;
    heap.push(i, filled[i]);
  }
  let k = 0;
  while (heap.size) {
    const i = heap.pop();
    order[k++] = i;
    const r = Math.floor(i / n), c = i % n;
    for (const [dr, dc] of NEIGHBORS) {
      const rr = r + dr, cc = c + dc;
      if (rr < 0 || cc < 0 || rr >= n || cc >= n) continue;
      const j = rr * n + cc;
      if (seen[j]) continue;
      seen[j] = 1;
      filled[j] = Math.max(heights[j], filled[i] + 1e-3);
      down[j] = i;
      heap.push(j, filled[j]);
    }
  }
  const acc = new Float32Array(total).fill(1);
  for (let idx = k - 1; idx >= 0; idx -= 1) {
    const i = order[idx];
    if (down[i] >= 0) acc[down[i]] += acc[i];
  }
  return { n, down, acc };
}

/** Camino del agua desde una celda, cuesta abajo, hasta el borde o hasta `maxSteps` celdas. */
export function traceDown(d: Drainage, start: number, maxSteps: number, stop?: (cell: number) => boolean): number[] {
  const path = [start];
  let cur = start;
  for (let s = 0; s < maxSteps; s += 1) {
    const next = d.down[cur];
    if (next < 0) break;
    path.push(next);
    cur = next;
    if (stop?.(next)) break;
  }
  return path;
}

/** Río principal: desde la celda que más drena, aguas arriba por el afluente mayor mientras drene al menos `minAcc`. */
export function mainChannel(d: Drainage, minAcc: number): number[] {
  const { n, down, acc } = d;
  let outlet = 0;
  for (let i = 1; i < n * n; i += 1) if (acc[i] > acc[outlet]) outlet = i;
  const path = [outlet];
  let cur = outlet;
  for (let guard = 0; guard < n * 4; guard += 1) {
    const r = Math.floor(cur / n), c = cur % n;
    let best = -1;
    for (const [dr, dc] of NEIGHBORS) {
      const rr = r + dr, cc = c + dc;
      if (rr < 0 || cc < 0 || rr >= n || cc >= n) continue;
      const j = rr * n + cc;
      if (down[j] === cur && (best < 0 || acc[j] > acc[best])) best = j;
    }
    if (best < 0 || acc[best] < minAcc) break;
    path.push(best);
    cur = best;
  }
  return path.reverse();
}

/** Centro de una celda en metros del mundo del juego (x al este, z al sur, origen en el centro de la zona). */
export function cellXZ(cell: number, n: number, size: number): [number, number] {
  return [((cell % n) / (n - 1) - 0.5) * size, (Math.floor(cell / n) / (n - 1) - 0.5) * size];
}

/** Suaviza el zigzag de las celdas y reparte puntos cada `step` metros. */
export function smoothPath(points: [number, number][], step: number): [number, number][] {
  if (points.length < 3) return points;
  const soft = points.map((_, i) => {
    let sx = 0, sz = 0, count = 0;
    for (let k = Math.max(0, i - 2); k <= Math.min(points.length - 1, i + 2); k += 1) { sx += points[k][0]; sz += points[k][1]; count += 1; }
    return [sx / count, sz / count] as [number, number];
  });
  soft[0] = points[0]; soft[soft.length - 1] = points[points.length - 1];
  const out: [number, number][] = [soft[0]];
  let carry = 0;
  for (let i = 1; i < soft.length; i += 1) {
    const [ax, az] = soft[i - 1], [bx, bz] = soft[i];
    const len = Math.hypot(bx - ax, bz - az);
    let t = step - carry;
    while (t <= len) { out.push([ax + ((bx - ax) * t) / len, az + ((bz - az) * t) / len]); t += step; }
    carry = len - (t - step);
  }
  return out;
}

/** Distancia horizontal mínima de un punto a los primeros `upTo` puntos de un camino. */
export function distanceToPath(path: [number, number][], x: number, z: number, upTo = path.length): { dist: number; index: number } {
  let dist = Infinity, index = 0;
  for (let i = 0; i < Math.min(upTo, path.length); i += 1) {
    const d = Math.hypot(path[i][0] - x, path[i][1] - z);
    if (d < dist) { dist = d; index = i; }
  }
  return { dist, index };
}

/**
 * Cinta que sigue un camino sobre el terreno (lodo de un huaico, nieve de una avalancha o el agua de un río).
 * La superficie queda casi plana de lado a lado: llena el fondo del cauce y apenas moja las laderas.
 * Se revela por tramos con `geometry.setDrawRange(0, tramos * quadsPerSegment * 6)`.
 */
export function buildRibbon(T: typeof import("three"), path: [number, number][], widthAt: (k: number) => number, groundAt: (x: number, z: number) => number, depth: number, material: THREE_NS.Material) {
  const cols = 7;
  const m = path.length;
  const positions = new Float32Array(m * cols * 3);
  const uvs = new Float32Array(m * cols * 2);
  let along = 0;
  for (let k = 0; k < m; k += 1) {
    const [px, pz] = path[k];
    const [ax, az] = path[Math.max(k - 1, 0)], [bx, bz] = path[Math.min(k + 1, m - 1)];
    const tl = Math.hypot(bx - ax, bz - az) || 1;
    const nx = -(bz - az) / tl, nz = (bx - ax) / tl;
    if (k > 0) along += Math.hypot(px - path[k - 1][0], pz - path[k - 1][1]);
    const w = widthAt(k);
    const surface = groundAt(px, pz) + depth;
    for (let j = 0; j < cols; j += 1) {
      const s = (j / (cols - 1) - 0.5) * 2;
      const x = px + nx * s * w * 0.5, z = pz + nz * s * w * 0.5;
      const y = Math.max(surface - Math.abs(s) * depth * 0.6, groundAt(x, z) + 0.12);
      positions.set([x, y, z], (k * cols + j) * 3);
      uvs.set([j / (cols - 1), along / 14], (k * cols + j) * 2);
    }
  }
  const index: number[] = [];
  for (let k = 0; k < m - 1; k += 1) for (let j = 0; j < cols - 1; j += 1) {
    const a = k * cols + j, b = a + 1, c = a + cols, d = c + 1;
    index.push(a, c, b, b, c, d);
  }
  const geometry = new T.BufferGeometry();
  geometry.setAttribute("position", new T.BufferAttribute(positions, 3));
  geometry.setAttribute("uv", new T.BufferAttribute(uvs, 2));
  geometry.setIndex(index);
  geometry.computeVertexNormals();
  // Visible por ambas caras: según hacia dónde gire el cauce, los triángulos quedan mirando arriba o abajo.
  material.side = T.DoubleSide;
  const mesh = new T.Mesh(geometry, material);
  mesh.receiveShadow = true;
  mesh.frustumCulled = false;
  return { mesh, quadsPerSegment: cols - 1 };
}

/** Textura de flujo: vetas a lo largo del cauce que, al desplazarse, hacen ver que el lodo o el agua corren. */
export function flowTexture(T: typeof import("three"), base: [number, number, number], streak: [number, number, number], foam: boolean) {
  const c = document.createElement("canvas");
  c.width = 64; c.height = 256;
  const x = c.getContext("2d")!;
  x.fillStyle = `rgb(${base.join(",")})`;
  x.fillRect(0, 0, 64, 256);
  let seed = 7;
  const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  for (let i = 0; i < 140; i += 1) {
    const k = 0.6 + rand() * 0.8;
    x.fillStyle = `rgba(${streak.map((v) => Math.min(255, Math.round(v * k))).join(",")},${0.25 + rand() * 0.35})`;
    x.fillRect(rand() * 64, rand() * 256, 1 + rand() * 3, 10 + rand() * 50);
  }
  if (foam) for (let i = 0; i < 60; i += 1) { x.fillStyle = `rgba(235,225,205,${0.15 + rand() * 0.3})`; x.beginPath(); x.arc(rand() * 64, rand() * 256, 0.8 + rand() * 1.8, 0, Math.PI * 2); x.fill(); }
  const texture = new T.CanvasTexture(c);
  texture.wrapS = texture.wrapT = T.RepeatWrapping;
  texture.colorSpace = T.SRGBColorSpace;
  return texture;
}
