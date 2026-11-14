// Objetos que el héroe lleva en la mano (o puestos): linterna, radio, botiquín, agua, paraguas y abrigo.
// Cada uno se dibuja en metros reales. La mano la pone `hero-rig` (hueso «RightHand»); la orientación sigue hacia dónde
// mira el héroe, para que la linterna siempre alumbre adelante y el paraguas quede sobre la cabeza.

import type * as THREE_NS from "three";

type Three = typeof import("three");

export type ItemId = "linterna" | "radio" | "botiquin" | "agua" | "paraguas" | "abrigo";

/** Orden fijo: la tecla de cada objeto es su posición (1 = linterna … 6 = abrigo). */
export const ITEMS: { id: ItemId; icon: string; name: string; use: string }[] = [
  { id: "linterna", icon: "🔦", name: "Linterna", use: "alumbra adelante" },
  { id: "radio", icon: "📻", name: "Radio", use: "escucha las noticias" },
  { id: "botiquin", icon: "🩹", name: "Botiquín", use: "+40 de salud (se gasta)" },
  { id: "agua", icon: "💧", name: "Agua", use: "te protege del calor" },
  { id: "paraguas", icon: "☂️", name: "Paraguas", use: "te protege de la lluvia" },
  { id: "abrigo", icon: "🧥", name: "Abrigo", use: "te protege del frío" },
];

export type HandItem = {
  object: THREE_NS.Object3D;
  /** true: va puesto en el cuerpo (abrigo), no en la mano. */
  worn: boolean;
};

const mat = (T: Three, color: number, extra: Partial<THREE_NS.MeshStandardMaterialParameters> = {}) => new T.MeshStandardMaterial({ color, roughness: 0.6, ...extra });

export function buildHandItem(T: Three, id: ItemId): HandItem {
  const g = new T.Group();
  if (id === "linterna") {
    // Cuerpo amarillo, cabeza negra y lente encendido apuntando hacia adelante (+Z), con su haz de luz.
    const body = new T.Mesh(new T.CylinderGeometry(0.035, 0.035, 0.2, 14), mat(T, 0xffc21a)); body.rotation.x = Math.PI / 2; g.add(body);
    const head = new T.Mesh(new T.CylinderGeometry(0.055, 0.04, 0.07, 16), mat(T, 0x1d1d1f)); head.rotation.x = Math.PI / 2; head.position.z = 0.13; g.add(head);
    const lens = new T.Mesh(new T.CircleGeometry(0.05, 16), new T.MeshBasicMaterial({ color: 0xfff6d0 })); lens.position.z = 0.166; g.add(lens);
    const light = new T.SpotLight(0xfff1c8, 70, 45, 0.42, 0.45, 1.2); light.position.z = 0.17; g.add(light);
    const target = new T.Object3D(); target.position.set(0, -1.2, 10); g.add(target); light.target = target;
    // Haz visible también de día: un cono suave que sale del lente.
    const beam = new T.Mesh(new T.ConeGeometry(0.9, 6, 24, 1, true), new T.MeshBasicMaterial({ color: 0xfff1c8, transparent: true, opacity: 0.17, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide }));
    beam.rotation.x = -Math.PI / 2 - 0.12; beam.position.set(0, -0.36, 3.15); g.add(beam);
  } else if (id === "radio") {
    const box = new T.Mesh(new T.BoxGeometry(0.2, 0.12, 0.07), mat(T, 0x2b2f33)); g.add(box);
    const grill = new T.Mesh(new T.CircleGeometry(0.035, 16), mat(T, 0x8a8f94)); grill.position.set(-0.05, 0, 0.036); g.add(grill);
    const dial = new T.Mesh(new T.PlaneGeometry(0.07, 0.03), new T.MeshBasicMaterial({ color: 0xffb21a })); dial.position.set(0.05, 0.02, 0.036); g.add(dial);
    const antenna = new T.Mesh(new T.CylinderGeometry(0.004, 0.004, 0.32), mat(T, 0xc9cdd1, { metalness: 0.8 })); antenna.position.set(0.08, 0.2, 0); antenna.rotation.z = -0.3; g.add(antenna);
  } else if (id === "botiquin") {
    const box = new T.Mesh(new T.BoxGeometry(0.24, 0.17, 0.08), mat(T, 0xf6f6f6)); g.add(box);
    for (const z of [0.041, -0.041]) {
      const v = new T.Mesh(new T.PlaneGeometry(0.035, 0.11), new T.MeshBasicMaterial({ color: 0xe5262f, side: T.DoubleSide })); v.position.z = z; g.add(v);
      const h = new T.Mesh(new T.PlaneGeometry(0.11, 0.035), new T.MeshBasicMaterial({ color: 0xe5262f, side: T.DoubleSide })); h.position.z = z; g.add(h);
    }
    const handle = new T.Mesh(new T.TorusGeometry(0.035, 0.008, 6, 12, Math.PI), mat(T, 0x333333)); handle.position.y = 0.085; g.add(handle);
  } else if (id === "agua") {
    const bottle = new T.Mesh(new T.CylinderGeometry(0.035, 0.035, 0.2, 16), new T.MeshStandardMaterial({ color: 0x8fd3ff, roughness: 0.1, transparent: true, opacity: 0.75 })); g.add(bottle);
    const label = new T.Mesh(new T.CylinderGeometry(0.036, 0.036, 0.06, 16, 1, true), mat(T, 0x2b8fd6)); g.add(label);
    const cap = new T.Mesh(new T.CylinderGeometry(0.018, 0.02, 0.03, 12), mat(T, 0x1f6fb2)); cap.position.y = 0.115; g.add(cap);
  } else if (id === "paraguas") {
    // Bastón desde la mano y la tela abierta sobre la cabeza, en gajos rojos y amarillos.
    const stick = new T.Mesh(new T.CylinderGeometry(0.012, 0.012, 1.05), mat(T, 0x3b2a1e)); stick.position.y = 0.5; g.add(stick);
    const handle = new T.Mesh(new T.TorusGeometry(0.05, 0.012, 6, 12, Math.PI), mat(T, 0x3b2a1e)); handle.rotation.z = Math.PI; handle.position.set(0.05, -0.02, 0); g.add(handle);
    for (let i = 0; i < 8; i += 1) {
      const gore = new T.Mesh(new T.ConeGeometry(0.8, 0.32, 3, 1, true, (i / 8) * Math.PI * 2, Math.PI / 4), new T.MeshStandardMaterial({ color: i % 2 ? 0xffc21a : 0xe5262f, roughness: 0.7, side: T.DoubleSide }));
      gore.position.y = 1.08; g.add(gore);
    }
  } else {
    // Abrigo: un poncho andino con franjas, puesto sobre el torso.
    const c = document.createElement("canvas"); c.width = 64; c.height = 64;
    const x = c.getContext("2d")!;
    ["#8a3c2a", "#e5262f", "#ffc21a", "#2b8fd6", "#8a3c2a", "#5ee08a", "#8a3c2a"].forEach((color, i) => { x.fillStyle = color; x.fillRect(0, i * 9.2, 64, i % 2 ? 4 : 9.2); });
    const tex = new T.CanvasTexture(c); tex.colorSpace = T.SRGBColorSpace;
    const poncho = new T.Mesh(new T.CylinderGeometry(0.17, 0.4, 0.62, 20, 1, true), new T.MeshStandardMaterial({ map: tex, roughness: 0.95, side: T.DoubleSide })); poncho.position.y = -0.2; g.add(poncho);
    const collar = new T.Mesh(new T.TorusGeometry(0.13, 0.04, 8, 18), mat(T, 0x8a3c2a, { roughness: 1 })); collar.rotation.x = Math.PI / 2; collar.position.y = 0.11; g.add(collar);
  }
  g.traverse((o) => { (o as THREE_NS.Mesh).castShadow = true; });
  // Los objetos pequeños se agrandan un poco (como en los videojuegos) para que se note qué lleva en la mano.
  if (id !== "paraguas" && id !== "abrigo") g.scale.setScalar(1.7);
  return { object: g, worn: id === "abrigo" };
}

/** Libera geometrías, materiales y la textura de lienzo del poncho al guardar el objeto. */
export function disposeHandItem(item: HandItem) {
  item.object.traverse((o) => {
    const mesh = o as THREE_NS.Mesh;
    mesh.geometry?.dispose();
    const m = mesh.material as THREE_NS.Material | THREE_NS.Material[] | undefined;
    // Liberar el material no libera su textura: el poncho crea una de lienzo cada vez que se saca el abrigo.
    for (const x of Array.isArray(m) ? m : m ? [m] : []) { (x as THREE_NS.MeshStandardMaterial).map?.dispose(); x.dispose(); }
  });
}
