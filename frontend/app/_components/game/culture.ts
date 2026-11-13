// Identidad cultural de cada lugar: elementos 3D propios del país o la región (hechos con figuras simples, diseño
// propio) y colores típicos de sus casas. Son ambientación del juego, no datos medidos.

import type * as THREE_NS from "three";

type Three = typeof THREE_NS;
type Builder = (T: Three) => THREE_NS.Object3D;

const mat = (T: Three, color: number, extra: Partial<THREE_NS.MeshStandardMaterialParameters> = {}) => new T.MeshStandardMaterial({ color, roughness: 0.8, ...extra });
const finish = (g: THREE_NS.Object3D) => { g.traverse((o) => { (o as THREE_NS.Mesh).castShadow = true; (o as THREE_NS.Mesh).receiveShadow = true; }); return g; };

const windmill: Builder = (T) => {
  const g = new T.Group();
  const tower = new T.Mesh(new T.CylinderGeometry(2.2, 3.2, 12, 8), mat(T, 0x8a5a3c)); tower.position.y = 6; g.add(tower);
  const cap = new T.Mesh(new T.ConeGeometry(2.8, 3, 8), mat(T, 0x3b3b3b)); cap.position.y = 13.5; g.add(cap);
  const blades = new T.Group(); blades.position.set(0, 11.5, 3.2); blades.name = "spin";
  for (let i = 0; i < 4; i += 1) { const b = new T.Mesh(new T.BoxGeometry(1.3, 9, 0.15), mat(T, 0xf2ead8)); b.position.y = 4.5; const arm = new T.Group(); arm.rotation.z = (i * Math.PI) / 2; arm.add(b); blades.add(arm); }
  g.add(blades);
  return finish(g);
};
const torii: Builder = (T) => {
  const g = new T.Group(), red = mat(T, 0xd62d20), black = mat(T, 0x1b1b1b);
  for (const x of [-4, 4]) { const p = new T.Mesh(new T.CylinderGeometry(0.45, 0.5, 9, 12), red); p.position.set(x, 4.5, 0); g.add(p); }
  const top = new T.Mesh(new T.BoxGeometry(12, 0.8, 1), black); top.position.y = 9.4; g.add(top);
  const beam = new T.Mesh(new T.BoxGeometry(10.5, 0.6, 0.7), red); beam.position.y = 7.6; g.add(beam);
  return finish(g);
};
const gondola: Builder = (T) => {
  const g = new T.Group();
  const hull = new T.Mesh(new T.CapsuleGeometry(0.7, 7, 4, 10), mat(T, 0x111111, { roughness: 0.3 })); hull.rotation.x = Math.PI / 2; hull.scale.set(1, 1, 0.35); hull.position.y = 0.3; g.add(hull);
  const prow = new T.Mesh(new T.BoxGeometry(0.15, 1.4, 0.6), mat(T, 0xc9a54a)); prow.position.set(0, 1, 4); g.add(prow);
  return finish(g);
};
const archBridge: Builder = (T) => {
  const g = new T.Group();
  const arch = new T.Mesh(new T.TorusGeometry(7, 1.2, 8, 24, Math.PI), mat(T, 0xe9dcc4)); g.add(arch);
  const deck = new T.Mesh(new T.BoxGeometry(16, 0.8, 5), mat(T, 0xe9dcc4)); deck.position.y = 6.6; g.add(deck);
  g.rotation.y = Math.PI / 2;
  return finish(g);
};
const llama: Builder = (T) => {
  const g = new T.Group(), wool = mat(T, 0xf3ece0), legs = mat(T, 0xd9cdb8);
  const body = new T.Mesh(new T.CapsuleGeometry(0.45, 1, 4, 10), wool); body.rotation.z = Math.PI / 2; body.position.y = 1.3; g.add(body);
  const neck = new T.Mesh(new T.CapsuleGeometry(0.2, 0.9, 4, 8), wool); neck.position.set(0.75, 2.1, 0); g.add(neck);
  const head = new T.Mesh(new T.CapsuleGeometry(0.17, 0.25, 4, 8), wool); head.rotation.z = Math.PI / 2; head.position.set(0.95, 2.65, 0); g.add(head);
  for (const x of [-0.5, 0.5]) for (const z of [-0.25, 0.25]) { const l = new T.Mesh(new T.CylinderGeometry(0.08, 0.08, 1, 6), legs); l.position.set(x, 0.5, z); g.add(l); }
  const tassel = new T.Mesh(new T.SphereGeometry(0.12, 6, 6), mat(T, 0xe5262f)); tassel.position.set(0.95, 2.95, 0.12); g.add(tassel);
  return finish(g);
};
const mototaxi: Builder = (T) => {
  const g = new T.Group();
  const cab = new T.Mesh(new T.BoxGeometry(1.6, 1.5, 2), mat(T, 0xe5262f)); cab.position.y = 1.3; g.add(cab);
  const roof = new T.Mesh(new T.BoxGeometry(1.8, 0.1, 2.4), mat(T, 0x1b1b1b)); roof.position.y = 2.15; g.add(roof);
  for (const [x, z] of [[-0.8, -0.7], [0.8, -0.7], [0, 1.3]]) { const w = new T.Mesh(new T.CylinderGeometry(0.4, 0.4, 0.2, 14), mat(T, 0x1b1b1b)); w.rotation.z = Math.PI / 2; w.position.set(x, 0.4, z); g.add(w); }
  return finish(g);
};
const papelPicado: Builder = (T) => {
  const g = new T.Group(), colors = [0xff3d7f, 0xffb21a, 0x2bb3e0, 0x5ee08a, 0xb36bff];
  for (const x of [-9, 9]) { const p = new T.Mesh(new T.CylinderGeometry(0.15, 0.15, 7, 6), mat(T, 0x8a6a45)); p.position.set(x, 3.5, 0); g.add(p); }
  for (let i = 0; i < 12; i += 1) {
    const flag = new T.Mesh(new T.PlaneGeometry(1.2, 1.4), new T.MeshStandardMaterial({ color: colors[i % colors.length], side: T.DoubleSide }));
    const x = -8.2 + i * 1.5; flag.position.set(x, 6.2 - Math.sin((i / 11) * Math.PI) * 1.2, 0); g.add(flag);
  }
  return finish(g);
};
const steppedPyramid: Builder = (T) => {
  const g = new T.Group();
  for (let i = 0; i < 5; i += 1) { const s = new T.Mesh(new T.BoxGeometry(22 - i * 4, 2.6, 22 - i * 4), mat(T, 0xb7a17e)); s.position.y = 1.3 + i * 2.6; g.add(s); }
  const temple = new T.Mesh(new T.BoxGeometry(4, 3, 4), mat(T, 0x9a7f5a)); temple.position.y = 14.5; g.add(temple);
  return finish(g);
};
const chalet: Builder = (T) => {
  const g = new T.Group();
  const base = new T.Mesh(new T.BoxGeometry(8, 3, 7), mat(T, 0xf2ece0)); base.position.y = 1.5; g.add(base);
  const wood = new T.Mesh(new T.BoxGeometry(8.2, 3, 7.2), mat(T, 0x7a4a2a)); wood.position.y = 4.5; g.add(wood);
  const roof = new T.Mesh(new T.ConeGeometry(6.6, 3.4, 4), mat(T, 0x4a2e1e)); roof.rotation.y = Math.PI / 4; roof.scale.set(1, 1, 0.85); roof.position.y = 7.7; g.add(roof);
  return finish(g);
};
const lighthouse: Builder = (T) => {
  const g = new T.Group();
  const tower = new T.Mesh(new T.CylinderGeometry(1.6, 2.6, 18, 12), mat(T, 0xf2ece0)); tower.position.y = 9; g.add(tower);
  for (const y of [5, 11]) { const band = new T.Mesh(new T.CylinderGeometry(2.3 - y * 0.03, 2.4 - y * 0.03, 1.4, 12), mat(T, 0xc9393b)); band.position.y = y; g.add(band); }
  const lamp = new T.Mesh(new T.SphereGeometry(1.3, 12, 10), new T.MeshStandardMaterial({ color: 0xfff1a8, emissive: 0xffd23a, emissiveIntensity: 1.2 })); lamp.position.y = 19; g.add(lamp);
  return finish(g);
};
const acacia: Builder = (T) => {
  const g = new T.Group();
  const trunk = new T.Mesh(new T.CylinderGeometry(0.25, 0.4, 5, 6), mat(T, 0x5a4030)); trunk.position.y = 2.5; g.add(trunk);
  const crown = new T.Mesh(new T.CylinderGeometry(4.5, 3.5, 1.2, 10), mat(T, 0x5f7f2f, { flatShading: true })); crown.position.y = 5.5; g.add(crown);
  return finish(g);
};
const penguin: Builder = (T) => {
  const g = new T.Group();
  const body = new T.Mesh(new T.CapsuleGeometry(0.32, 0.55, 4, 10), mat(T, 0x1b1b1b)); body.position.y = 0.6; g.add(body);
  const belly = new T.Mesh(new T.SphereGeometry(0.28, 10, 8), mat(T, 0xffffff)); belly.scale.set(0.9, 1.3, 0.6); belly.position.set(0, 0.55, 0.18); g.add(belly);
  const beak = new T.Mesh(new T.ConeGeometry(0.07, 0.2, 6), mat(T, 0xffa21a)); beak.rotation.x = Math.PI / 2; beak.position.set(0, 1.0, 0.32); g.add(beak);
  return finish(g);
};
const researchBase: Builder = (T) => {
  const g = new T.Group();
  for (const [x, z] of [[0, 0], [9, 2], [-8, 3]]) { const hut = new T.Mesh(new T.BoxGeometry(7, 3.2, 4.5), mat(T, 0xd62d20)); hut.position.set(x, 1.8, z); g.add(hut); const roof = new T.Mesh(new T.BoxGeometry(7.4, 0.4, 4.9), mat(T, 0xf2f2f2)); roof.position.set(x, 3.6, z); g.add(roof); }
  const antenna = new T.Mesh(new T.CylinderGeometry(0.1, 0.1, 9, 6), mat(T, 0xcccccc)); antenna.position.set(4, 4.5, -3); g.add(antenna);
  return finish(g);
};
const fortWall: Builder = (T) => {
  const g = new T.Group();
  const wall = new T.Mesh(new T.BoxGeometry(40, 7, 3), mat(T, 0xc9b08a)); wall.position.y = 3.5; g.add(wall);
  for (const x of [-20, 20]) { const turret = new T.Mesh(new T.CylinderGeometry(2, 2.2, 9, 10), mat(T, 0xc9b08a)); turret.position.set(x, 4.5, 0); g.add(turret); const dome = new T.Mesh(new T.SphereGeometry(2, 10, 8, 0, Math.PI * 2, 0, Math.PI / 2), mat(T, 0xa58a62)); dome.position.set(x, 9, 0); g.add(dome); }
  return finish(g);
};
const riverBoat: Builder = (T) => {
  const g = new T.Group();
  const hull = new T.Mesh(new T.BoxGeometry(4, 1.4, 14), mat(T, 0xf2f2f2)); hull.position.y = 0.7; g.add(hull);
  const deck = new T.Mesh(new T.BoxGeometry(3.6, 2.2, 10), mat(T, 0x2b7fd6)); deck.position.y = 2.5; g.add(deck);
  const roof = new T.Mesh(new T.BoxGeometry(4, 0.3, 11), mat(T, 0xf2f2f2)); roof.position.y = 3.8; g.add(roof);
  return finish(g);
};
const outrigger: Builder = (T) => {
  const g = new T.Group();
  const hull = new T.Mesh(new T.CapsuleGeometry(0.4, 5, 4, 8), mat(T, 0x8a5a3c)); hull.rotation.x = Math.PI / 2; hull.position.y = 0.35; g.add(hull);
  const float = new T.Mesh(new T.CapsuleGeometry(0.2, 3.5, 4, 8), mat(T, 0x8a5a3c)); float.rotation.x = Math.PI / 2; float.position.set(2, 0.25, 0); g.add(float);
  for (const z of [-1, 1]) { const bar = new T.Mesh(new T.CylinderGeometry(0.05, 0.05, 2.2, 6), mat(T, 0x5a4030)); bar.rotation.z = Math.PI / 2; bar.position.set(1, 0.5, z); g.add(bar); }
  return finish(g);
};
export const volcanoPlume: Builder = (T) => {
  const g = new T.Group();
  for (let i = 0; i < 14; i += 1) {
    const puff = new T.Mesh(new T.SphereGeometry(18 + i * 4, 10, 8), new T.MeshStandardMaterial({ color: i < 3 ? 0x4a3f3a : 0x8d8580, transparent: true, opacity: 0.55 - i * 0.025, roughness: 1, depthWrite: false }));
    puff.position.set(Math.sin(i * 0.7) * i * 3, i * 22, Math.cos(i) * i * 2); puff.name = "plume"; g.add(puff);
  }
  const glow = new T.PointLight(0xff5a1a, 400, 300); glow.position.y = 5; g.add(glow);
  return g;
};

/** Colibrí de Nazca: dibujo de líneas claras sobre la pampa (contorno simplificado, diseño propio). */
export function nazcaHummingbird(T: Three): THREE_NS.Object3D {
  const pts: [number, number][] = [
    [0, 40], [4, 30], [6, 18], [20, 26], [44, 20], [22, 10], [8, 6], [6, -6], [14, -22], [8, -24], [3, -12], [0, -40],
    [-3, -12], [-8, -24], [-14, -22], [-6, -6], [-8, 6], [-22, 10], [-44, 20], [-20, 26], [-6, 18], [-4, 30], [0, 40],
  ];
  const shape = new T.Shape();
  pts.forEach(([x, y], i) => (i ? shape.lineTo(x, y) : shape.moveTo(x, y)));
  const outline = new T.Group();
  const line = new T.Line(new T.BufferGeometry().setFromPoints(pts.map(([x, y]) => new T.Vector3(x, 0.4, -y))), new T.LineBasicMaterial({ color: 0xfaf3e3 }));
  outline.add(line);
  // Trazo ancho: tiras finas a lo largo del contorno para que se vea desde el aire.
  for (let i = 0; i < pts.length - 1; i += 1) {
    const [x1, y1] = pts[i], [x2, y2] = pts[i + 1];
    const len = Math.hypot(x2 - x1, y2 - y1);
    const strip = new T.Mesh(new T.PlaneGeometry(1.2, len), new T.MeshBasicMaterial({ color: 0xf6ead0 }));
    strip.rotation.x = -Math.PI / 2;
    strip.rotation.z = -Math.atan2(x2 - x1, y2 - y1);
    strip.position.set((x1 + x2) / 2, 0.3, -(y1 + y2) / 2);
    outline.add(strip);
  }
  outline.scale.setScalar(1.6);
  return outline;
}

export interface CultureKit {
  /** Elementos para repartir cerca de la nave y los objetivos. */
  props: { build: Builder; count: number; onWater?: boolean; spin?: boolean }[];
  /** Colores de muros de las casas, típicos de la región. */
  walls?: number[];
  roofs?: number[];
  /** Columna de humo en la cumbre (volcanes). */
  plume?: boolean;
  /** Geoglifo de Nazca en la pampa. */
  geoglyph?: boolean;
  /** Bandera: franjas simples y exactas (solo países donde se puede dibujar sin escudo). */
  flag?: string;
}

const ANDEAN = { walls: [0xc98f5a, 0xb97a48, 0xd9a876, 0xe6c49a], roofs: [0xa4482f, 0x8a3c2a, 0x6b5a4e] };
const CARIBBEAN = { walls: [0xf6c4d0, 0x9fd8e8, 0xf8e08a, 0xb9e3a8, 0xf3b27a, 0xd7c2f2], roofs: [0x8a3c2a, 0xa4482f, 0xeeeeee] };
const MEDITERRANEAN = { walls: [0xf6f2ea, 0xf1e6cf, 0xe9d8b0], roofs: [0xb5653d, 0xa4482f] };
const NORDIC = { walls: [0xc9393b, 0x2b6fd1, 0xf2c94c, 0x3c9a5a, 0xf2f2f2], roofs: [0x2b2b2b, 0x4a4a4a] };
const DUTCH = { walls: [0x8a3c2a, 0x7a3426, 0x9a4a32], roofs: [0x2b2b2b, 0x3b3b3b] };

export const CULTURE: Record<string, CultureKit> = {
  nazca: { props: [{ build: llama, count: 3 }], geoglyph: true, flag: "peru" },
  poopo: { props: [{ build: llama, count: 5 }], ...ANDEAN, flag: "bolivia" },
  huascaran: { props: [{ build: llama, count: 5 }], ...ANDEAN, flag: "peru" },
  chosica: { props: [{ build: llama, count: 2 }, { build: mototaxi, count: 3 }], ...ANDEAN, flag: "peru" },
  piura: { props: [{ build: mototaxi, count: 5 }], ...ANDEAN, flag: "peru" },
  mocoa: { props: [{ build: mototaxi, count: 2 }], ...CARIBBEAN, flag: "colombia" },
  guayaquil: { props: [{ build: riverBoat, count: 2, onWater: true }], ...CARIBBEAN, flag: "ecuador" },
  manaos: { props: [{ build: riverBoat, count: 4, onWater: true }], ...CARIBBEAN },
  "porto-alegre": { props: [{ build: riverBoat, count: 2, onWater: true }], ...CARIBBEAN },
  "san-juan": { props: [{ build: fortWall, count: 1 }], ...CARIBBEAN },
  "puerto-principe": { props: [], ...CARIBBEAN },
  choluteca: { props: [{ build: mototaxi, count: 2 }], ...CARIBBEAN },
  cdmx: { props: [{ build: papelPicado, count: 4 }, { build: steppedPyramid, count: 1 }], ...CARIBBEAN },
  popocatepetl: { props: [{ build: papelPicado, count: 2 }], plume: true },
  venecia: { props: [{ build: gondola, count: 6, onWater: true }, { build: archBridge, count: 1 }], ...MEDITERRANEAN, flag: "italia" },
  etna: { props: [], plume: true, flag: "italia" },
  sevilla: { props: [], ...MEDITERRANEAN, flag: "espana" },
  valencia: { props: [], ...MEDITERRANEAN, flag: "espana" },
  atenas: { props: [], ...MEDITERRANEAN, flag: "grecia" },
  rotterdam: { props: [{ build: windmill, count: 4, spin: true }], ...DUTCH, flag: "paisesbajos" },
  ahr: { props: [{ build: chalet, count: 3 }], flag: "alemania" },
  aletsch: { props: [{ build: chalet, count: 4 }], flag: "suiza" },
  chamonix: { props: [{ build: chalet, count: 5 }], flag: "francia" },
  svalbard: { props: [], ...NORDIC, flag: "noruega" },
  ilulissat: { props: [], ...NORDIC },
  yellowknife: { props: [], ...NORDIC },
  sendai: { props: [{ build: torii, count: 2 }], flag: "japon" },
  yakarta: { props: [], ...CARIBBEAN, flag: "indonesia" },
  merapi: { props: [], plume: true, flag: "indonesia" },
  daca: { props: [{ build: riverBoat, count: 3, onWater: true }], flag: "banglades" },
  taal: { props: [], plume: true },
  kilauea: { props: [], plume: true },
  villarrica: { props: [{ build: chalet, count: 2 }], plume: true },
  alejandria: { props: [{ build: lighthouse, count: 1 }], ...MEDITERRANEAN },
  turkana: { props: [{ build: acacia, count: 10 }] },
  mogadiscio: { props: [{ build: acacia, count: 6 }], flag: "somalia" },
  ambovombe: { props: [{ build: acacia, count: 6 }], flag: "madagascar" },
  niamey: { props: [{ build: acacia, count: 8 }], flag: "niger" },
  funafuti: { props: [{ build: outrigger, count: 4, onWater: true }] },
  "rey-jorge": { props: [{ build: penguin, count: 14 }, { build: researchBase, count: 1 }], flag: "peru" },
  thwaites: { props: [{ build: penguin, count: 10 }] },
};

/** Bandera dibujada en un lienzo: solo diseños de franjas, cruces o figuras simples que se pueden dibujar exactos. */
export function drawFlag(code: string): HTMLCanvasElement | null {
  const c = document.createElement("canvas"); c.width = 300; c.height = 200;
  const x = c.getContext("2d")!;
  const v = (...cols: string[]) => cols.forEach((col, i) => { x.fillStyle = col; x.fillRect((300 / cols.length) * i, 0, 300 / cols.length + 1, 200); });
  const h = (...cols: string[]) => cols.forEach((col, i) => { x.fillStyle = col; x.fillRect(0, (200 / cols.length) * i, 300, 200 / cols.length + 1); });
  const nordic = (bg: string, cross: string, inner?: string) => { x.fillStyle = bg; x.fillRect(0, 0, 300, 200); x.fillStyle = cross; x.fillRect(80, 0, 50, 200); x.fillRect(0, 75, 300, 50); if (inner) { x.fillStyle = inner; x.fillRect(93, 0, 24, 200); x.fillRect(0, 88, 300, 24); } };
  const star = (cx: number, cy: number, r: number, col: string) => { x.fillStyle = col; x.beginPath(); for (let i = 0; i < 10; i += 1) { const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.4 : r; x.lineTo(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr); } x.fill(); };
  switch (code) {
    case "peru": v("#D91023", "#FFFFFF", "#D91023"); break;
    case "bolivia": h("#D52B1E", "#F9E300", "#007934"); break;
    case "colombia": x.fillStyle = "#FCD116"; x.fillRect(0, 0, 300, 100); x.fillStyle = "#003893"; x.fillRect(0, 100, 300, 50); x.fillStyle = "#CE1126"; x.fillRect(0, 150, 300, 50); break;
    case "ecuador": x.fillStyle = "#FFDD00"; x.fillRect(0, 0, 300, 100); x.fillStyle = "#034EA2"; x.fillRect(0, 100, 300, 50); x.fillStyle = "#ED1C24"; x.fillRect(0, 150, 300, 50); break;
    case "italia": v("#009246", "#FFFFFF", "#CE2B37"); break;
    case "francia": v("#002395", "#FFFFFF", "#ED2939"); break;
    case "alemania": h("#000000", "#DD0000", "#FFCE00"); break;
    case "paisesbajos": h("#AE1C28", "#FFFFFF", "#21468B"); break;
    case "espana": x.fillStyle = "#AA151B"; x.fillRect(0, 0, 300, 200); x.fillStyle = "#F1BF00"; x.fillRect(0, 50, 300, 100); break;
    case "grecia": for (let i = 0; i < 9; i += 1) { x.fillStyle = i % 2 ? "#FFFFFF" : "#0D5EAF"; x.fillRect(0, (200 / 9) * i, 300, 200 / 9 + 1); } x.fillStyle = "#0D5EAF"; x.fillRect(0, 0, 111, 111); x.fillStyle = "#FFFFFF"; x.fillRect(44, 0, 22, 111); x.fillRect(0, 44, 111, 22); break;
    case "suiza": x.fillStyle = "#DA291C"; x.fillRect(0, 0, 300, 200); x.fillStyle = "#FFFFFF"; x.fillRect(132, 50, 36, 100); x.fillRect(100, 82, 100, 36); break;
    case "noruega": nordic("#BA0C2F", "#FFFFFF", "#00205B"); break;
    case "japon": x.fillStyle = "#FFFFFF"; x.fillRect(0, 0, 300, 200); x.fillStyle = "#BC002D"; x.beginPath(); x.arc(150, 100, 60, 0, Math.PI * 2); x.fill(); break;
    case "banglades": x.fillStyle = "#006A4E"; x.fillRect(0, 0, 300, 200); x.fillStyle = "#F42A41"; x.beginPath(); x.arc(135, 100, 60, 0, Math.PI * 2); x.fill(); break;
    case "indonesia": h("#CE1126", "#FFFFFF"); break;
    case "somalia": x.fillStyle = "#4189DD"; x.fillRect(0, 0, 300, 200); star(150, 100, 50, "#FFFFFF"); break;
    case "madagascar": x.fillStyle = "#FFFFFF"; x.fillRect(0, 0, 100, 200); x.fillStyle = "#FC3D32"; x.fillRect(100, 0, 200, 100); x.fillStyle = "#007E3A"; x.fillRect(100, 100, 200, 100); break;
    case "niger": h("#E05206", "#FFFFFF", "#0DB02B"); x.fillStyle = "#E05206"; x.beginPath(); x.arc(150, 100, 22, 0, Math.PI * 2); x.fill(); break;
    default: return null;
  }
  return c;
}
