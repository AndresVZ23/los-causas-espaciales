// Personajes realistas animados (Mixamo, publicados entre los ejemplos oficiales de three.js): «hombre» es Soldier y
// «mujer» es Michelle. Los dos usan el esqueleto estándar de Mixamo, así que las animaciones de Soldier (quieto, caminar
// y correr, grabadas con captura de movimiento) se aplican a los dos. Los archivos se cargan una vez y se clonan.

import type * as THREE_NS from "three";
import type { Gender } from "./game-types";

type Three = typeof THREE_NS;
interface Loaded { scene: THREE_NS.Group; animations: THREE_NS.AnimationClip[] }

const cache = new Map<string, Promise<Loaded>>();

async function load(url: string): Promise<Loaded> {
  if (!cache.has(url)) {
    cache.set(url, import("three/addons/loaders/GLTFLoader.js").then(({ GLTFLoader }) => new GLTFLoader().loadAsync(url)).then((gltf) => ({ scene: gltf.scene, animations: gltf.animations })));
    // Un fallo (por ejemplo, un corte de red) no debe quedar guardado: si no, el modelo no vuelve a pedirse hasta
    // recargar la página y todas las misiones siguientes caen a la vista de mapa.
    cache.get(url)!.catch(() => cache.delete(url));
  }
  return cache.get(url)!;
}

/** Empieza a bajar los dos modelos a la vez, sin esperar: `hombre.glb` hace falta siempre porque trae las animaciones. */
export function preloadHeroModels(): void {
  for (const gender of ["hombre", "mujer"]) void load(`/models/heroes/${gender}.glb`).catch(() => undefined);
}

// Descarte por cámara: una malla con esqueleto no puede usar la esfera de su geometría (los huesos la mueven), y por eso
// antes iba con `frustumCulled = false` y todos los personajes se dibujaban siempre, también los que quedaban a la
// espalda de la cámara. Se mide una vez la esfera del cuerpo ya escalado y se agranda para que cubra correr y bailar.
function fitBounds(object: THREE_NS.Object3D) {
  object.updateMatrixWorld(true);
  object.traverse((node) => {
    const mesh = node as THREE_NS.SkinnedMesh;
    if (!mesh.isSkinnedMesh) return;
    mesh.skeleton.update();
    mesh.computeBoundingSphere();
    if (mesh.boundingSphere) mesh.boundingSphere.radius *= 1.6;
    mesh.frustumCulled = true;
  });
}

export interface HeroRig {
  object: THREE_NS.Object3D;
  /** Avanza la animación (y el traspaso de movimiento, en la mujer). */
  update: (dt: number) => void;
  /** Pasa suavemente a la animación pedida (quieto, caminar o correr). */
  play: (name: "Idle" | "Walk" | "Run") => void;
  /** Hueso por nombre de Mixamo, por ejemplo «RightArm», para poses que no vienen grabadas (saludar, volar). */
  bone: (name: string) => THREE_NS.Bone | undefined;
}

/** `cull`: activa el descarte por cámara (lo pide el mundo 3D, que tiene muchos personajes; el héroe del menú va como estaba). */
export async function loadHeroRig(T: Three, gender: Gender, cull = false): Promise<HeroRig> {
  const [{ clone }, body, moves] = await Promise.all([
    import("three/addons/utils/SkeletonUtils.js"),
    load(`/models/heroes/${gender}.glb`),
    load("/models/heroes/hombre.glb"),
  ]);
  const object = clone(body.scene);
  object.traverse((node) => {
    const mesh = node as THREE_NS.SkinnedMesh;
    if (mesh.isMesh) { mesh.frustumCulled = false; mesh.castShadow = false; } // con `cull`, el descarte se activa al final (`fitBounds`)
  });
  // Los dos modelos vienen a escalas distintas: se llevan a 1,8 unidades de alto con los pies en el suelo.
  // Altura medida entre los huesos de la cabeza y del pie (más fiable que la caja de la malla con piel).
  object.updateMatrixWorld(true);
  const find = (suffix: string) => { let hit: THREE_NS.Object3D | undefined; object.traverse((node) => { if (!hit && node.name.endsWith(suffix)) hit = node; }); return hit; };
  const head = find("HeadTop_End") ?? find("Head");
  const foot = find("LeftToeBase") ?? find("LeftFoot");
  if (head && foot) {
    const top = head.getWorldPosition(new T.Vector3()).y;
    const bottom = foot.getWorldPosition(new T.Vector3()).y;
    const height = (top - bottom) * (head.name.endsWith("HeadTop_End") ? 1 : 1.1);
    if (height > 0) {
      const factor = 1.8 / height;
      object.scale.multiplyScalar(factor);
      object.updateMatrixWorld(true);
      object.position.y -= foot.getWorldPosition(new T.Vector3()).y - 0.05;
    }
  }
  // Todos los personajes deben mirar hacia +Z (como espera el juego). Se mide con la línea de los hombros: mirando a +Z,
  // el hombro derecho queda hacia −X. Si queda hacia +X, el modelo viene de espaldas y se gira media vuelta.
  {
    object.updateMatrixWorld(true);
    let left: THREE_NS.Object3D | undefined, right: THREE_NS.Object3D | undefined;
    object.traverse((node) => { if (!left && /LeftArm$/.test(node.name)) left = node; if (!right && /RightArm$/.test(node.name)) right = node; });
    if (left && right && right.getWorldPosition(new T.Vector3()).x > left.getWorldPosition(new T.Vector3()).x) {
      object.rotation.y += Math.PI;
      object.updateMatrixWorld(true);
    }
  }
  const actions = new Map<string, THREE_NS.AnimationAction>();
  // El hombre se anima directo. La mujer copia en cada cuadro el movimiento de un Soldier invisible, hueso por hueso y en
  // el espacio del mundo: rotación = (Soldier ahora × Soldier en reposo⁻¹) × mujer en reposo. Así no importa que los huesos
  // de cada modelo tengan otra orientación de base; la cadera queda en su sitio porque el juego mueve al personaje.
  const driver = gender === "hombre" ? object : clone(moves.scene);
  driver.updateMatrixWorld(true);
  const mixer = new T.AnimationMixer(driver);
  for (const clip of moves.animations) {
    if (clip.name === "TPose") continue;
    actions.set(clip.name, mixer.clipAction(clip));
  }
  const key = (name: string) => name.replace(/^mixamorig:?/, "");
  const bonesOf = (root: THREE_NS.Object3D) => { const map = new Map<string, THREE_NS.Bone>(); root.traverse((node) => { if ((node as THREE_NS.Bone).isBone) map.set(key(node.name), node as THREE_NS.Bone); }); return map; };
  type Pair = { target: THREE_NS.Bone; source: THREE_NS.Bone; sourceRestInv: THREE_NS.Quaternion; targetRest: THREE_NS.Quaternion };
  const pairs: Pair[] = [];
  const turn = new T.Quaternion();
  const turnInv = new T.Quaternion();
  const yawFixInv = new T.Quaternion();
  if (driver !== object) {
    // Referencia común: los dos archivos traen su propia postura «T». Se mide el reposo de cada uno en esa postura.
    const pose = (root: THREE_NS.Object3D, clips: THREE_NS.AnimationClip[]) => {
      const tpose = clips.find((clip) => clip.name === "TPose");
      if (!tpose) { root.updateMatrixWorld(true); return; }
      const temp = new T.AnimationMixer(root);
      temp.clipAction(tpose).play();
      temp.update(0);
      root.updateMatrixWorld(true);
      temp.stopAllAction();
      temp.uncacheRoot(root);
    };
    // Las animaciones de Soldier vienen giradas respecto de su postura «T»: se mide ese giro en la cadera (Idle frente
    // a TPose) para descontarlo, o la mujer quedaría mirando de lado mientras corre.
    const hipsOf = (root: THREE_NS.Object3D) => { let hit: THREE_NS.Object3D | undefined; root.traverse((node) => { if (!hit && /Hips$/.test(node.name)) hit = node; }); return hit; };
    const idle = moves.animations.find((clip) => clip.name === "Idle");
    const driverHips = hipsOf(driver);
    if (idle && driverHips) {
      const temp = new T.AnimationMixer(driver);
      temp.clipAction(idle).play(); temp.update(0); driver.updateMatrixWorld(true);
      const idleQ = driverHips.getWorldQuaternion(new T.Quaternion());
      temp.stopAllAction(); temp.uncacheRoot(driver);
      pose(driver, moves.animations);
      const tposeQ = driverHips.getWorldQuaternion(new T.Quaternion());
      const f = new T.Vector3(0, 0, 1).applyQuaternion(idleQ.multiply(tposeQ.invert()));
      yawFixInv.setFromAxisAngle(new T.Vector3(0, 1, 0), -Math.atan2(f.x, f.z));
    } else pose(driver, moves.animations);
    pose(object, body.animations);
    const sourceBones = bonesOf(driver);
    const targetBones = bonesOf(object);
    const depth = (node: THREE_NS.Object3D) => { let d = 0; for (let p = node.parent; p; p = p.parent) d += 1; return d; };
    // Cada modelo puede mirar hacia otro lado en su archivo: se mide su frente con la línea de los hombros.
    const facing = (bones: Map<string, THREE_NS.Bone>) => {
      const left = bones.get("LeftArm") ?? bones.get("LeftShoulder"), right = bones.get("RightArm") ?? bones.get("RightShoulder");
      if (!left || !right) return 0;
      const toRight = right.getWorldPosition(new T.Vector3()).sub(left.getWorldPosition(new T.Vector3()));
      return Math.atan2(toRight.z, toRight.x);
    };
    turn.setFromAxisAngle(new T.Vector3(0, 1, 0), facing(sourceBones) - facing(targetBones));
    turnInv.copy(turn).invert();
    for (const [name, target] of [...targetBones.entries()].sort((x, y) => depth(x[1]) - depth(y[1]))) {
      const source = sourceBones.get(name);
      if (!source) continue;
      pairs.push({ target, source, sourceRestInv: source.getWorldQuaternion(new T.Quaternion()).invert(), targetRest: target.getWorldQuaternion(new T.Quaternion()) });
    }
  }
  const world = new T.Quaternion();
  const parentWorld = new T.Quaternion();
  const sourceWorld = new T.Quaternion();
  const tmpPos = new T.Vector3();
  const tmpScale = new T.Vector3();
  // Giro en el mundo ya resuelto de cada hueso. Un cuaternión fijo por hueso: antes se creaba uno nuevo por hueso y por
  // cuadro (unos 65 por personaje), basura que el navegador tenía que recoger en plena partida. Como los pares van de
  // la cadera hacia las puntas, el del padre siempre queda escrito antes de que lo lea el hijo.
  const computed = new Map<THREE_NS.Object3D, THREE_NS.Quaternion>();
  for (const pair of pairs) computed.set(pair.target, new T.Quaternion());
  const base = new T.Quaternion();
  const update = (dt: number) => {
    mixer.update(dt);
    if (!pairs.length) return;
    // Una sola actualización de matrices por cuadro; luego cada hueso se resuelve una vez, de la cadera hacia las puntas.
    driver.updateMatrixWorld(true);
    object.updateMatrixWorld(true);
    // Los reposos se midieron con el modelo suelto (sin padre). En el juego el modelo cuelga del héroe, que gira hacia
    // donde corre: ese giro se aplica aquí. Sin esto, la mujer mantenía siempre el mismo frente en el mundo y parecía
    // correr de espaldas o de lado según la dirección.
    if (object.parent) object.parent.getWorldQuaternion(base); else base.identity();
    for (const pair of pairs) {
      pair.source.matrixWorld.decompose(tmpPos, sourceWorld, tmpScale);
      // Giro del hueso respecto de su reposo, llevado al frente del otro modelo: (giro · Δ · giro⁻¹) · reposo de la mujer.
      world.copy(sourceWorld).premultiply(yawFixInv).multiply(pair.sourceRestInv).premultiply(turnInv).multiply(turn).multiply(pair.targetRest).premultiply(base);
      const parent = pair.target.parent;
      const known = parent ? computed.get(parent) : undefined;
      if (known) parentWorld.copy(known);
      else if (parent) parent.matrixWorld.decompose(tmpPos, parentWorld, tmpScale);
      else parentWorld.identity();
      pair.target.quaternion.copy(parentWorld.invert().multiply(world));
      computed.get(pair.target)!.copy(world);
    }
  };
  let current: THREE_NS.AnimationAction | null = null;
  const play: HeroRig["play"] = (name) => {
    const next = actions.get(name);
    if (!next || next === current) return;
    next.reset().setEffectiveWeight(1).fadeIn(0.25).play();
    current?.fadeOut(0.25);
    current = next;
  };
  play("Idle");
  if (cull) fitBounds(object);
  const bones = new Map<string, THREE_NS.Bone>();
  object.traverse((node) => { if ((node as THREE_NS.Bone).isBone) bones.set(node.name.replace("mixamorig:", "").replace("mixamorig", ""), node as THREE_NS.Bone); });
  return { object, update, play, bone: (name) => bones.get(name) };
}


/** Bailarina con su propio baile de captura de movimiento (SambaDance de Michelle), sin traspaso de animaciones. */
export async function loadDancer(T: Three): Promise<{ object: THREE_NS.Object3D; update: (dt: number) => void }> {
  const [{ clone }, body] = await Promise.all([import("three/addons/utils/SkeletonUtils.js"), load("/models/heroes/mujer.glb")]);
  const object = clone(body.scene);
  object.traverse((node) => { const mesh = node as THREE_NS.SkinnedMesh; if (mesh.isMesh) mesh.frustumCulled = false; });
  object.updateMatrixWorld(true);
  let head: THREE_NS.Object3D | undefined, foot: THREE_NS.Object3D | undefined;
  object.traverse((node) => { if (!head && node.name.endsWith("HeadTop_End")) head = node; if (!foot && node.name.endsWith("LeftToeBase")) foot = node; });
  if (head && foot) {
    const height = head.getWorldPosition(new T.Vector3()).y - foot.getWorldPosition(new T.Vector3()).y;
    if (height > 0) { object.scale.multiplyScalar(1.75 / height); object.updateMatrixWorld(true); object.position.y -= foot.getWorldPosition(new T.Vector3()).y - 0.05; }
  }
  const mixer = new T.AnimationMixer(object);
  const dance = body.animations.find((clip) => clip.name === "SambaDance");
  if (dance) mixer.clipAction(dance).play();
  fitBounds(object);
  return { object, update: (dt) => mixer.update(dt) };
}
