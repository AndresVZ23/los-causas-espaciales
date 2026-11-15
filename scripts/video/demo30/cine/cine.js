// Cinemáticas en 3D del demo de 30 segundos (ADR-051). Son animación hecha para el video, no capturas del juego:
// la Luna de 2045, el salto a 2026, la llegada a la Tierra y cuatro desastres dibujados sobre el relieve real de sus
// lugares (Copernicus DEM GLO-30 y ESA WorldCover, los mismos archivos de las misiones). Los eventos son simulados.
// Cada escena es una función del tiempo: window.draw(escena, segundos) dibuja siempre el mismo cuadro.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { mergeVertices } from "three/addons/utils/BufferGeometryUtils.js";

const W = 1920, H = 1080, REPO = "/repo/";
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById("c"), antialias: true, preserveDrawingBuffer: true, powerPreference: "high-performance" });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 }));
const renderPass = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.5, 0.6, 0.9);
composer.addPass(renderPass);
composer.addPass(bloom);
composer.addPass(new OutputPass());

// --- Utilidades -------------------------------------------------------------------------------------------------------
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * clamp(t);
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
function rng(seed) {
  let s = seed >>> 0;
  return () => { s += 0x6d2b79f5; let t = Math.imul(s ^ (s >>> 15), 1 | s); t ^= t + Math.imul(t ^ (t >>> 7), 61 | t); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function hash2(ix, iy) { let h = Math.imul(ix, 374761393) + Math.imul(iy, 668265263); h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }
function noise2(x, y) {
  const ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy, u = fx * fx * (3 - 2 * fx), v = fy * fy * (3 - 2 * fy);
  const a = hash2(ix, iy), b = hash2(ix + 1, iy), c = hash2(ix, iy + 1), d = hash2(ix + 1, iy + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm2(x, y, octaves = 5) { let s = 0, a = 0.5, f = 1; for (let i = 0; i < octaves; i += 1) { s += a * noise2(x * f, y * f); f *= 2.03; a *= 0.5; } return s; }
const NOISE = `
float hash31(vec3 p){ p = fract(p * 0.1031); p += dot(p, p.yzx + 33.33); return fract((p.x + p.y) * p.z); }
float vnoise(vec3 p){ vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash31(i), hash31(i + vec3(1,0,0)), f.x), mix(hash31(i + vec3(0,1,0)), hash31(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hash31(i + vec3(0,0,1)), hash31(i + vec3(1,0,1)), f.x), mix(hash31(i + vec3(0,1,1)), hash31(i + vec3(1,1,1)), f.x), f.y), f.z); }
float fbm(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 5; i++) { s += a * vnoise(p); p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= 0.5; } return s; }
`;
const textureLoader = new THREE.TextureLoader();
async function texture(url, srgb = true) {
  const t = await textureLoader.loadAsync(REPO + url);
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = 8;
  return t;
}

// --- La Tierra: Blue Marble y Black Marble de NASA, con un parámetro de salud (0 = la de 2045, 1 = la de hoy) ----------
let earthMaps = null;
async function makeEarth(radius) {
  earthMaps ??= { day: await texture("videos/assets/bluemarble.jpg"), night: await texture("videos/assets/blackmarble.jpg"), mask: await texture("frontend/public/textures/earth/landmask-1k.png", false) };
  const uniforms = { dayMap: { value: earthMaps.day }, nightMap: { value: earthMaps.night }, maskMap: { value: earthMaps.mask }, sunDir: { value: V3(1, 0.25, 0.6).normalize() }, health: { value: 1 }, time: { value: 0 } };
  const vertexShader = `varying vec2 vUv; varying vec3 vNw; varying vec3 vPw; varying vec3 vPl;
    void main(){ vUv = uv; vPl = position; vec4 wp = modelMatrix * vec4(position, 1.0); vPw = wp.xyz; vNw = normalize(mat3(modelMatrix) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`;
  const surface = new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader: NOISE + `
    uniform sampler2D dayMap, nightMap, maskMap; uniform vec3 sunDir; uniform float health, time;
    varying vec2 vUv; varying vec3 vNw; varying vec3 vPw; varying vec3 vPl;
    void main(){
      vec3 N = normalize(vNw), V = normalize(cameraPosition - vPw), L = normalize(sunDir), p = normalize(vPl);
      float ndl = dot(N, L), dayF = smoothstep(-0.14, 0.28, ndl);
      vec3 day = texture2D(dayMap, vUv).rgb; float land = texture2D(maskMap, vUv).r;
      float lum = dot(day, vec3(0.299, 0.587, 0.114));
      // La Tierra de 2045: tierra seca y mares turbios, sin verde.
      vec3 sick = mix(vec3(0.085, 0.062, 0.05) + lum * vec3(0.3, 0.19, 0.12), mix(vec3(lum), vec3(0.6, 0.39, 0.21), 0.8) * 0.95, land);
      vec3 base = mix(sick, day * 1.08, health);
      float c = fbm(p * 5.2 + vec3(time * 0.012, 0.0, time * 0.008)) + 0.3 * fbm(p * 15.0 - vec3(0.0, time * 0.01, 0.0));
      c = smoothstep(0.6, 0.84, c);
      base = mix(base, mix(vec3(0.36, 0.25, 0.17), vec3(0.9), health), c * mix(0.8, 0.9, health));
      vec3 lit = base * (0.035 + 1.08 * max(ndl, 0.0));
      float spec = pow(max(dot(N, normalize(L + V)), 0.0), 70.0) * (1.0 - land) * (1.0 - c);
      lit += vec3(1.0, 0.94, 0.82) * spec * 0.7 * health;
      // De noche: luces de ciudad (apagadas en 2045) e incendios (solo en 2045).
      vec3 city = texture2D(nightMap, vUv).rgb;
      float fires = smoothstep(0.7, 0.9, fbm(p * 21.0 + 3.0)) * land * (1.0 - health);
      vec3 night = city * 2.4 * health * (1.0 - c * 0.7) + vec3(1.0, 0.33, 0.05) * fires * 2.2;
      vec3 col = mix(night, lit, dayF) + vec3(1.0, 0.3, 0.05) * fires * 0.5 * dayF;
      float rim = pow(1.0 - max(dot(N, V), 0.0), 3.2);
      col += mix(vec3(1.0, 0.42, 0.13), vec3(0.3, 0.58, 1.0), health) * rim * (0.2 + 0.8 * dayF);
      gl_FragColor = vec4(col, 1.0);
    }` });
  const halo = new THREE.ShaderMaterial({ uniforms: { health: uniforms.health, sunDir: uniforms.sunDir }, side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `varying vec3 vNw; varying vec3 vPw; void main(){ vec4 wp = modelMatrix * vec4(position, 1.0); vPw = wp.xyz; vNw = normalize(mat3(modelMatrix) * normal); gl_Position = projectionMatrix * viewMatrix * wp; }`,
    fragmentShader: `uniform float health; uniform vec3 sunDir; varying vec3 vNw; varying vec3 vPw;
      void main(){ vec3 N = normalize(vNw), V = normalize(cameraPosition - vPw); float a = pow(clamp(-dot(N, V) / 0.42, 0.0, 1.0), 3.0);
        float lit = mix(0.22, 1.0, smoothstep(-0.35, 0.5, dot(N, normalize(sunDir))));
        gl_FragColor = vec4(mix(vec3(1.0, 0.4, 0.12), vec3(0.3, 0.6, 1.0), health) * a * lit * 1.1, 1.0); }` });
  const spin = new THREE.Group();
  spin.add(new THREE.Mesh(new THREE.SphereGeometry(radius, 180, 120), surface));
  const group = new THREE.Group();
  group.add(spin, new THREE.Mesh(new THREE.SphereGeometry(radius * 1.1, 96, 64), halo));
  /** Deja el punto (lat, lon) mirando hacia +Z, con el norte arriba. */
  const face = (lat, lon) => { spin.rotation.set(0, THREE.MathUtils.degToRad(-90 - lon), 0); group.rotation.x = THREE.MathUtils.degToRad(lat); };
  return { group, spin, uniforms, face };
}

function makeStars(count, radius, seed) {
  const random = rng(seed), position = new Float32Array(count * 3), color = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 1) {
    const z = random() * 2 - 1, a = random() * Math.PI * 2, r = Math.sqrt(1 - z * z), b = 0.25 + 1.6 * random() ** 3, warm = random();
    position.set([r * Math.cos(a) * radius, z * radius, r * Math.sin(a) * radius], i * 3);
    color.set([b * (0.85 + 0.15 * warm), b * 0.92, b * (1 - 0.18 * warm)], i * 3);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(color, 3));
  return new THREE.Points(geometry, new THREE.PointsMaterial({ size: 2.1, sizeAttenuation: false, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
}

// --- Carteles que siempre miran a la cámara: humo, polvo de nieve, lodo, lava ------------------------------------------
function makeBillboards(max, additive = false, contrast = 0.45) {
  const geometry = new THREE.InstancedBufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute([-0.5, -0.5, 0, 0.5, -0.5, 0, 0.5, 0.5, 0, -0.5, 0.5, 0], 3));
  geometry.setIndex([0, 1, 2, 0, 2, 3]);
  const center = new THREE.InstancedBufferAttribute(new Float32Array(max * 3), 3), misc = new THREE.InstancedBufferAttribute(new Float32Array(max * 4), 4), color = new THREE.InstancedBufferAttribute(new Float32Array(max * 3), 3);
  geometry.setAttribute("iCenter", center); geometry.setAttribute("iMisc", misc); geometry.setAttribute("iColor", color);
  const material = new THREE.ShaderMaterial({ uniforms: { light: { value: new THREE.Vector2(0.55, 0.83) } }, transparent: true, depthWrite: false, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    vertexShader: `attribute vec3 iCenter; attribute vec4 iMisc; attribute vec3 iColor; varying vec2 vUv; varying float vAlpha, vSeed; varying vec3 vColor;
      void main(){ vUv = position.xy; vAlpha = iMisc.y; vSeed = iMisc.z; vColor = iColor; float c = cos(iMisc.w), s = sin(iMisc.w);
        vec4 mv = modelViewMatrix * vec4(iCenter, 1.0); mv.xy += vec2(position.x * c - position.y * s, position.x * s + position.y * c) * iMisc.x; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: NOISE + `uniform vec2 light; varying vec2 vUv; varying float vAlpha, vSeed; varying vec3 vColor;
      void main(){ float r = length(vUv) * 2.0, n = fbm(vec3(vUv * 3.4 + vSeed * 17.0, vSeed * 5.0)); float a = smoothstep(1.0, 0.2, r + (n - 0.5) * 0.75) * vAlpha;
        if (a < 0.004) discard; float shade = ${additive ? "1.0" : `${(1 - contrast * 0.66).toFixed(3)} + ${contrast.toFixed(3)} * dot(normalize(vUv + 1e-4), light) * smoothstep(0.0, 0.9, r) + ${(contrast * 0.5).toFixed(3)} * (n - 0.5)`};
        gl_FragColor = vec4(vColor * shade, a); }` });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  const eye = V3();
  /** `list`: [x, y, z, tamaño, alfa, semilla, giro, r, g, b] por partícula. Se dibujan de atrás hacia adelante. */
  const fill = (list, camera) => {
    camera.getWorldPosition(eye);
    if (!additive) list.sort((a, b) => ((b[0] - eye.x) ** 2 + (b[1] - eye.y) ** 2 + (b[2] - eye.z) ** 2) - ((a[0] - eye.x) ** 2 + (a[1] - eye.y) ** 2 + (a[2] - eye.z) ** 2));
    const count = Math.min(list.length, max);
    for (let i = 0; i < count; i += 1) { const p = list[i]; center.setXYZ(i, p[0], p[1], p[2]); misc.setXYZW(i, p[3], p[4], p[5], p[6]); color.setXYZ(i, p[7], p[8], p[9]); }
    geometry.instanceCount = count;
    center.needsUpdate = misc.needsUpdate = color.needsUpdate = true;
  };
  return { mesh, fill };
}

// --- La Luna: suelo con cráteres, el viajero y la nave ------------------------------------------------------------------
const MOON_R = 11000;
const moonCraters = (() => {
  const random = rng(2045), list = [];
  for (let i = 0; i < 90; i += 1) {
    const r = 3 + 46 * random() ** 2.4, x = (random() - 0.5) * 1900, z = (random() - 0.5) * 1900 - 150;
    if (Math.hypot(x, z) < r + 9) continue;          // el viajero queda en suelo limpio
    list.push({ x, z, r, depth: r * (0.16 + 0.1 * random()), rim: r * (0.035 + 0.03 * random()) });
  }
  for (let i = 0; i < 260; i += 1) {                    // cráteres chicos cerca de la cámara
    const r = 0.5 + 4.5 * random() ** 2.2, a = random() * Math.PI * 2, d = 4 + 190 * random() ** 0.8, x = Math.cos(a) * d, z = Math.sin(a) * d - 20;
    if (Math.hypot(x - 1.3, z) < r + 2.6 || (Math.abs(x - 2.3) < 2 && z > 2 && z < 11)) continue;
    list.push({ x, z, r, depth: r * (0.14 + 0.1 * random()), rim: r * (0.04 + 0.03 * random()) });
  }
  return list;
})();
function moonHeight(x, z) {
  let h = 7 * (fbm2(x * 0.003 + 3.1, z * 0.003 + 7.7) - 0.5) + 1.5 * (fbm2(x * 0.021, z * 0.021) - 0.5) + 0.34 * (fbm2(x * 0.17, z * 0.17, 3) - 0.5) + 0.07 * (fbm2(x * 1.1, z * 1.1, 2) - 0.5);
  for (const c of moonCraters) {
    const d = Math.hypot(x - c.x, z - c.z) / c.r;
    if (d < 1.7) h += -c.depth * (d < 1 ? (1 - d * d) ** 1.3 : 0) + c.rim * Math.exp(-(((d - 1) / 0.17) ** 2));
  }
  return h - (x * x + z * z) / (2 * MOON_R);
}
function makeMoonGround(size, segments) {
  const geometry = new THREE.PlaneGeometry(size, size, segments, segments);
  geometry.rotateX(-Math.PI / 2);
  const position = geometry.attributes.position, color = new Float32Array(position.count * 3), half = size / 2;
  // Los vértices se juntan hacia el centro: cerca de la cámara hay detalle de centímetros y lejos, de metros.
  const dense = (v) => Math.sign(v) * (Math.abs(v) / half) ** 2.1 * half;
  for (let i = 0; i < position.count; i += 1) {
    const x = dense(position.getX(i)), z = dense(position.getZ(i));
    position.setXYZ(i, x, moonHeight(x, z), z);
    const g = 0.2 + 0.2 * fbm2(x * 0.012 + 40, z * 0.012 + 11) + 0.07 * noise2(x * 0.9, z * 0.9) + 0.05 * noise2(x * 7, z * 7);
    color.set([g, g * 0.985, g * 0.955], i * 3);
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(color, 3));
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, metalness: 0 }));
  mesh.receiveShadow = mesh.castShadow = true;
  return mesh;
}
function makeShip() {
  const ship = new THREE.Group();
  const hull = new THREE.MeshStandardMaterial({ color: 0xa9b1ba, roughness: 0.55, metalness: 0.4 }), dark = new THREE.MeshStandardMaterial({ color: 0x1c2630, roughness: 0.4, metalness: 0.7 });
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.85, 3.4, 10, 20), hull); body.rotation.x = Math.PI / 2;
  const nose = new THREE.Mesh(new THREE.ConeGeometry(0.62, 1.9, 20), dark); nose.rotation.x = -Math.PI / 2; nose.position.z = -3.3;
  const glass = new THREE.Mesh(new THREE.SphereGeometry(0.62, 20, 14, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0x0b1a2c, roughness: 0.08, metalness: 0.9, emissive: 0x16446e, emissiveIntensity: 0.7 }));
  glass.position.set(0, 0.5, -1.1); glass.scale.set(1, 0.75, 1.9);
  ship.add(body, nose, glass);
  for (const side of [-1, 1]) {
    const shape = new THREE.Shape([new THREE.Vector2(0.55, 1.7), new THREE.Vector2(0.55, -2.3), new THREE.Vector2(3.5, -2.55), new THREE.Vector2(3.7, -2.0)]);
    const wing = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.09, bevelEnabled: false }), hull);
    wing.rotation.x = Math.PI / 2; wing.scale.x = side; wing.position.y = -0.12; wing.rotation.y = 0;
    const fin = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.85, 1.0), hull); fin.position.set(side * 0.5, 0.75, 2.0); fin.rotation.z = side * -0.32;
    ship.add(wing, fin);
  }
  const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.78, 0.8, 20, 1, true), dark); nozzle.rotation.x = Math.PI / 2; nozzle.position.z = 2.75;
  const flame = new THREE.Mesh(new THREE.CircleGeometry(0.58, 20), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.9, 1.8, 2.2) })); flame.position.z = 3.1;
  const trail = new THREE.Mesh(new THREE.ConeGeometry(0.55, 1, 20, 1, true), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.3, 0.85, 1.1), transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  trail.rotation.x = Math.PI / 2; trail.position.z = 3.6;
  ship.add(nozzle, flame, trail);
  ship.traverse((o) => { if (o.isMesh && o !== trail && o !== flame) o.castShadow = true; });
  /** Largo de la estela del motor (0 = apagado). */
  const thrust = (k) => { flame.visible = trail.visible = k > 0.01; trail.scale.set(1 + 0.25 * k, Math.max(0.01, 9 * k), 1 + 0.25 * k); trail.position.z = 3.1 + 4.5 * k; };
  return { ship, thrust };
}
let heroAsset = null;
async function makeHero() {
  heroAsset ??= await new GLTFLoader().loadAsync(REPO + "frontend/public/models/heroes/hombre.glb");
  const { clone } = await import("three/addons/utils/SkeletonUtils.js");
  const hero = clone(heroAsset.scene);
  hero.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
  const mixer = new THREE.AnimationMixer(hero);
  mixer.clipAction(heroAsset.animations.find((clip) => clip.name === "Idle") ?? heroAsset.animations[0]).play();
  mixer.setTime(1.2);
  const holder = new THREE.Group();
  holder.add(hero);
  holder.updateMatrixWorld(true);
  let head = null, foot = null;
  hero.traverse((o) => { if (!o.isBone) return; if (/HeadTop_End$/.test(o.name) || (!head && /Head$/.test(o.name))) head = o; if (!foot && /(Left|Right)(ToeBase|Foot)$/.test(o.name)) foot = o; });
  if (head && foot) {
    const tall = head.getWorldPosition(V3()).y - foot.getWorldPosition(V3()).y;
    hero.scale.multiplyScalar(1.8 / Math.max(1e-6, Math.abs(tall)));
    holder.updateMatrixWorld(true);
    hero.position.y -= foot.getWorldPosition(V3()).y - 0.06;
  }
  console.log("cine: viajero", head?.name, foot?.name, hero.scale.x.toFixed(4));
  return { hero: holder, mixer };
}
/** Dirección de la Tierra en el cielo de la Luna (hacia −Z, a la derecha y arriba). */
const EARTH_DIR = V3(0.26, 0.2, -1).normalize();
const MOON_SUN = V3(-0.9, 0.17, -0.06).normalize();
async function moonSet(scene, groundSize, segments) {
  scene.background = new THREE.Color(0x000000);
  scene.add(makeStars(5200, 9000, 7));
  const ground = makeMoonGround(groundSize, segments);
  scene.add(ground);
  // Piedras sueltas, que con la luz rasante dan sombras largas.
  const rockGeometry = mergeVertices(new THREE.IcosahedronGeometry(1, 2).deleteAttribute("uv").deleteAttribute("normal")), rockPosition = rockGeometry.attributes.position;
  for (let i = 0; i < rockPosition.count; i += 1) {
    const x = rockPosition.getX(i), y = rockPosition.getY(i), z = rockPosition.getZ(i), k = 0.66 + 0.62 * fbm2(x * 1.7 + y * 2.3 + 5, z * 1.9 - y * 1.1 + 2, 3);
    rockPosition.setXYZ(i, x * k, y * k * 0.78, z * k);
  }
  rockGeometry.computeVertexNormals();
  const random = rng(404), rocks = new THREE.InstancedMesh(rockGeometry, new THREE.MeshStandardMaterial({ color: 0x6f6b66, roughness: 1 }), 420), dummy = new THREE.Object3D();
  for (let i = 0; i < 420; i += 1) {
    const a = random() * Math.PI * 2, d = 3 + 170 * random() ** 1.5, x = Math.cos(a) * d, z = Math.sin(a) * d - 12, k = 0.08 + 0.9 * random() ** 3;
    dummy.position.set(x, moonHeight(x, z) + k * 0.25, z);
    dummy.scale.set(k * (0.7 + 0.7 * random()), k * (0.5 + 0.5 * random()), k * (0.7 + 0.7 * random()));
    dummy.rotation.set(random() * 3, random() * 3, random() * 3);
    dummy.updateMatrix();
    rocks.setMatrixAt(i, Math.hypot(x - 1.3, z) < 1.8 || (Math.abs(x - 2.3) < 1.6 && z > 1 && z < 11) || (k > 0.5 && d < 14) ? new THREE.Matrix4().makeScale(0, 0, 0) : dummy.matrix);
  }
  rocks.castShadow = rocks.receiveShadow = true;
  scene.add(rocks);
  ground.userData.rocks = rocks;
  const sun = new THREE.DirectionalLight(0xfff3e2, 3.4);
  sun.position.copy(MOON_SUN).multiplyScalar(600);
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  Object.assign(sun.shadow.camera, { left: -230, right: 230, top: 230, bottom: -230, near: 50, far: 1500 });
  sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.35;
  scene.add(sun, sun.target, new THREE.AmbientLight(0x8a5a40, 0.07));
  const earth = await makeEarth(330);
  earth.group.position.copy(EARTH_DIR).multiplyScalar(2700);
  earth.uniforms.sunDir.value.copy(MOON_SUN);
  earth.uniforms.health.value = 0;
  earth.face(8, -62);
  scene.add(earth.group);
  return { ground, sun, earth };
}

const scenes = {};

// Luna, año 2045: el viajero mira la Tierra enferma desde la colonia.
scenes.luna = async () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(31, W / H, 0.1, 20000);
  const { earth } = await moonSet(scene, 1700, 560);
  const { hero, mixer } = await makeHero();
  hero.position.set(1.3, moonHeight(1.3, 0), 0);
  hero.rotation.y = Math.atan2(EARTH_DIR.x, EARTH_DIR.z) + (window.HERO_TURN ?? Math.PI);
  scene.add(hero);
  const { ship, thrust } = makeShip();
  ship.position.set(15, moonHeight(15, -31) + 1.5, -31); ship.rotation.y = -1.05; ship.scale.setScalar(1.25); thrust(0);
  scene.add(ship);
  // La colonia New Horizon al fondo: cúpulas con luz.
  const random = rng(11);
  for (let i = 0; i < 5; i += 1) {
    const r = 7 + random() * 9, x = -70 - random() * 150, z = -150 - random() * 170;
    const dome = new THREE.Mesh(new THREE.SphereGeometry(r, 28, 14, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0xcfd8e2, roughness: 0.35, metalness: 0.55, emissive: 0x2a6f8f, emissiveIntensity: 0.55 }));
    dome.position.set(x, moonHeight(x, z) - 0.6, z); dome.castShadow = true;
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.5, 10, 8), new THREE.MeshBasicMaterial({ color: new THREE.Color(4, 2.6, 1.1) }));
    lamp.position.set(x + r * 0.7, moonHeight(x, z) + 1.6, z + r * 0.75);
    scene.add(dome, lamp);
  }
  const look = V3();
  return { scene, camera, bloom: [0.4, 0.65, 0.9], exposure: 1.0, update(t) {
    const k = smooth(0, 4.6, t);
    camera.position.set(lerp(2.7, 1.9, k), moonHeight(2.3, 7.5) + lerp(1.3, 1.62, k), lerp(8.6, 6.3, k));
    look.set(camera.position.x + 0.12 * 40, camera.position.y + lerp(0.085, 0.11, k) * 40, camera.position.z - 40);
    camera.lookAt(look);
    mixer.setTime(1.2 + t);
    earth.uniforms.time.value = t;
    earth.spin.rotation.y += 0;
  } };
};

// El salto: la nave despega de la Luna, el tiempo retrocede y aparece la Tierra de 2026.
scenes.salto = async () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(36, W / H, 0.1, 30000);
  const { ground, earth } = await moonSet(scene, 3000, 620);
  scene.add(camera);
  const { ship, thrust } = makeShip();
  scene.add(ship);
  // Estelas de estrellas del salto, pegadas a la cámara.
  const random = rng(31), N = 1100, seeds = [], lines = new Float32Array(N * 6), colors = new Float32Array(N * 6);
  for (let i = 0; i < N; i += 1) { const a = random() * Math.PI * 2, r = 5 + 260 * random() ** 0.7; seeds.push([Math.cos(a) * r, Math.sin(a) * r, random(), 0.5 + random()]); }
  const streakGeometry = new THREE.BufferGeometry();
  streakGeometry.setAttribute("position", new THREE.BufferAttribute(lines, 3));
  streakGeometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const streaks = new THREE.LineSegments(streakGeometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  streaks.frustumCulled = false;
  camera.add(streaks);
  const start = V3(15, moonHeight(15, -31) + 1.5, -31), look = V3(), shipPos = V3(), far = V3();
  return { scene, camera, bloom: [0.5, 0.7, 0.86], exposure: 1.0, update(t) {
    const warp = smooth(1.15, 1.75, t) * (1 - smooth(2.75, 3.25, t)), after = t >= 2.75;
    // La nave: acelera hacia la Tierra; después del salto ya planea frente a ella.
    const run = t * t * 26 + t * 6;
    shipPos.copy(start).addScaledVector(EARTH_DIR, run).add(V3(0, 0.25 * t, 0));
    if (after) shipPos.copy(EARTH_DIR).multiplyScalar(1500);
    ship.position.copy(shipPos);
    far.copy(shipPos).addScaledVector(EARTH_DIR, 100);
    ship.lookAt(far); ship.rotateY(Math.PI);
    ship.rotation.z += Math.sin(t * 2.1) * 0.05 + warp * Math.sin(t * 37) * 0.03;
    thrust(after ? 0.45 : 0.35 + 0.65 * smooth(0, 1.1, t));
    ground.visible = ground.userData.rocks.visible = !after;
    // La Tierra: enferma hasta el salto; sana y cerca al salir.
    earth.uniforms.health.value = after ? 1 : 0;
    earth.uniforms.time.value = t;
    earth.group.position.copy(EARTH_DIR).multiplyScalar(after ? 2900 : 2700 + run);
    earth.group.scale.setScalar(after ? 1.3 : 1);
    if (after) { earth.uniforms.sunDir.value.set(-0.55, 0.3, 0.78).normalize(); earth.face(-12, -75); }
    // La cámara va detrás de la nave y se alinea con ella.
    const back = lerp(11, 16, smooth(0, 1.3, t)) - 4 * warp + (after ? 6 * smooth(2.75, 4.0, t) : 0);
    camera.position.copy(shipPos).addScaledVector(EARTH_DIR, -back).add(V3(lerp(3.2, 0.6, smooth(0, 1.4, t)), lerp(1.6, 2.6, smooth(0, 1.4, t)), 0));
    camera.position.x += warp * Math.sin(t * 43) * 0.18; camera.position.y += warp * Math.cos(t * 51) * 0.14;
    look.copy(shipPos).addScaledVector(EARTH_DIR, 60).add(V3(0, after ? 3.5 : 2, 0));
    camera.lookAt(look);
    camera.fov = 36 + 44 * warp; camera.updateProjectionMatrix();
    // Estelas.
    const length = 4 + 520 * warp * warp, travel = t * 900 * (0.15 + warp);
    for (let i = 0; i < N; i += 1) {
      const [x, y, phase, bright] = seeds[i], z = -1400 + ((phase * 1500 + travel) % 1500), b = bright * warp;
      lines.set([x, y, z, x, y, z - length], i * 6);
      colors.set([b * 0.9, b, b * 1.25, b * 0.15, b * 0.3, b * 0.6], i * 6);
    }
    streakGeometry.attributes.position.needsUpdate = streakGeometry.attributes.color.needsUpdate = true;
    streaks.visible = warp > 0.01;
  } };
};

// Llegada a la Tierra de 2026: queda encuadrada donde aparece después el globo real de la aplicación.
scenes.llegada = async () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(30, W / H, 0.1, 5000);
  scene.background = new THREE.Color(0x000000);
  scene.add(makeStars(4200, 3000, 19));
  const earth = await makeEarth(1);
  earth.face(-20, -97);
  earth.uniforms.sunDir.value.set(-0.42, 0.3, 0.86).normalize();
  scene.add(earth.group);
  const tan = Math.tan(THREE.MathUtils.degToRad(15)), look = V3();
  return { scene, camera, bloom: [0.45, 0.6, 0.86], exposure: 1.0, update(t) {
    const k = smooth(0, 2.4, t), d = lerp(8.2, 4.66, k);
    camera.position.set(lerp(1.4, 0, k), lerp(0.5, 0, k), d);
    look.set(-d * (262 / 540) * tan, d * (10 / 540) * tan, 0);
    camera.lookAt(look);
    earth.uniforms.time.value = 6 + t;
    earth.spin.rotation.y = THREE.MathUtils.degToRad(-90 + 97 + lerp(-16, 0, k));
  } };
};

// La Tierra de 2045 sana: cada lugar avisado a tiempo la cura.
scenes.sana = async () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(28, W / H, 0.1, 5000);
  scene.background = new THREE.Color(0x000000);
  scene.add(makeStars(4200, 3000, 23));
  const earth = await makeEarth(1);
  earth.uniforms.sunDir.value.set(-0.62, 0.25, 0.74).normalize();
  scene.add(earth.group);
  return { scene, camera, bloom: [0.5, 0.65, 0.84], exposure: 1.0, update(t) {
    const k = smooth(0, 4, t);
    camera.position.set(0, 0.1, lerp(6.6, 5.9, k));
    camera.lookAt(0, lerp(-0.2, -0.14, k), 0);
    earth.face(-8, -78 + 14 * k);
    earth.uniforms.health.value = smooth(0.35, 2.7, t);
    earth.uniforms.time.value = 3 + t * 1.5;
  } };
};

// --- Relieve real de las misiones -------------------------------------------------------------------------------------
const COVER = { 0: 0xa8a39a, 10: 0x35602d, 20: 0x7d7a40, 30: 0x8fa94c, 40: 0xb9ad5c, 50: 0x9b958c, 60: 0xcdb68b, 70: 0xf1f5f8, 80: 0x2e5f86, 90: 0x50805f, 95: 0x2f5b3c, 100: 0x8e9a6c };
const bytes = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
const NEIGHBORS = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
async function loadTerrain(id, exaggeration) {
  const data = await (await fetch(`${REPO}backend/data/missions/terrain/${id}.json`)).json();
  const n = data.grid, size = data.size_km * 1000, relief = new Uint16Array(bytes(data.relief_dm).buffer), cover = bytes(data.cover);
  const h = new Float32Array(n * n);
  for (let i = 0; i < n * n; i += 1) h[i] = (relief[i] / 10) * exaggeration;
  const tmp = new Float32Array(n * n);                       // una pasada de suavizado: el DEM mide techos y copas
  for (let r = 0; r < n; r += 1) for (let c = 0; c < n; c += 1) {
    let sum = 0, count = 0;
    for (let dr = -1; dr <= 1; dr += 1) for (let dc = -1; dc <= 1; dc += 1) { const rr = r + dr, cc = c + dc; if (rr >= 0 && rr < n && cc >= 0 && cc < n) { sum += h[rr * n + cc]; count += 1; } }
    tmp[r * n + c] = sum / count;
  }
  h.set(tmp);
  const cell = size / (n - 1);
  const xz = (i) => [((i % n) / (n - 1) - 0.5) * size, (Math.floor(i / n) / (n - 1) - 0.5) * size];
  const at = (x, z) => {
    const fc = clamp(x / size + 0.5, 0, 0.9999) * (n - 1), fr = clamp(z / size + 0.5, 0, 0.9999) * (n - 1), c = Math.floor(fc), r = Math.floor(fr), u = fc - c, v = fr - r, i = r * n + c;
    return h[i] * (1 - u) * (1 - v) + h[i + 1] * u * (1 - v) + h[i + n] * (1 - u) * v + h[i + n + 1] * u * v;
  };
  return { id, n, size, cell, h, cover, xz, at };
}
function terrainMesh(T, { snowLine = Infinity, tint = 1 } = {}) {
  const { n, size, h, cover } = T, geometry = new THREE.PlaneGeometry(size, size, n - 1, n - 1);
  geometry.rotateX(-Math.PI / 2);
  const position = geometry.attributes.position, color = new Float32Array(n * n * 3), c = new THREE.Color(), rock = new THREE.Color(0x6b6259), snow = new THREE.Color(0.93, 0.96, 1.0);
  for (let i = 0; i < n * n; i += 1) {
    position.setY(i, h[i]);
    const r = Math.floor(i / n), col = i % n, [x, z] = T.xz(i);
    const dx = (h[r * n + Math.min(n - 1, col + 1)] - h[r * n + Math.max(0, col - 1)]) / (2 * T.cell), dz = (h[Math.min(n - 1, r + 1) * n + col] - h[Math.max(0, r - 1) * n + col]) / (2 * T.cell);
    const slope = Math.hypot(dx, dz), kind = cover[i];
    c.setHex(COVER[kind] ?? COVER[0]).multiplyScalar((0.74 + 0.5 * fbm2(x * 0.006 + 9, z * 0.006 + 4)) * tint);
    if (kind !== 80) c.lerp(rock, smooth(0.5, 1.15, slope) * 0.8);
    if (kind === 70 || h[i] > snowLine) c.lerp(snow, 1 - smooth(0.9, 1.8, slope) * 0.75);
    color.set([c.r, c.g, c.b], i * 3);
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(color, 3));
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.96, metalness: 0 }));
  mesh.receiveShadow = mesh.castShadow = true;
  return mesh;
}
/** Casas como bloques pequeños sobre las celdas urbanas de WorldCover: de lejos se leen como un pueblo. */
function houses(T, max, seed, lift = 0) {
  const random = rng(seed), cells = [];
  for (let i = 0; i < T.n * T.n; i += 1) if (T.cover[i] === 50) cells.push(i);
  const count = Math.min(max, cells.length), mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0.02 }), count);
  const dummy = new THREE.Object3D(), color = new THREE.Color(), palette = [0xd8c7a6, 0xc7b79a, 0xb9a88f, 0xe3d7c4, 0xa9a39a, 0xa8674f, 0xb9906e, 0x9aa3ab, 0xcfc4b4, 0xbdb1a0];
  for (let k = 0; k < count; k += 1) {
    const i = cells[Math.floor(random() * cells.length)], [x0, z0] = T.xz(i), x = x0 + (random() - 0.5) * T.cell, z = z0 + (random() - 0.5) * T.cell, tall = 4 + 5.5 * random() ** 2;
    dummy.position.set(x, T.at(x, z) + tall / 2 - 0.4 + lift, z);
    dummy.scale.set(8 + 7 * random(), tall, 8 + 7 * random());
    dummy.rotation.y = (random() < 0.5 ? 0 : Math.PI / 2) + (random() - 0.5) * 0.08;
    dummy.updateMatrix();
    mesh.setMatrixAt(k, dummy.matrix);
    mesh.setColorAt(k, color.setHex(palette[Math.floor(random() * palette.length)]).multiplyScalar(0.8 + 0.35 * random()));
  }
  mesh.castShadow = mesh.receiveShadow = true;
  return mesh;
}
function sky(scene, top, horizon, sunDir, sunColor, fogDensity, fogColor = horizon) {
  const dome = new THREE.Mesh(new THREE.SphereGeometry(40000, 40, 20), new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { top: { value: new THREE.Color(top) }, horizon: { value: new THREE.Color(horizon) }, sunDir: { value: sunDir.clone().normalize() }, sunColor: { value: sunColor } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform vec3 top, horizon, sunDir, sunColor; varying vec3 vDir;
      void main(){ vec3 d = normalize(vDir); float k = pow(clamp(d.y, 0.0, 1.0), 0.55); vec3 col = mix(horizon, top, k); float s = max(dot(d, sunDir), 0.0);
        col += sunColor * (pow(s, 900.0) * 6.0 + pow(s, 24.0) * 0.35); gl_FragColor = vec4(col, 1.0); }` }));
  dome.renderOrder = -10;
  scene.add(dome);
  scene.fog = new THREE.FogExp2(new THREE.Color(fogColor), fogDensity);
  return dome;
}
function sunLight(scene, dir, color, intensity, reach, ambientSky, ambientGround, ambient) {
  const sun = new THREE.DirectionalLight(color, intensity);
  sun.position.copy(dir).normalize().multiplyScalar(reach * 2);
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  Object.assign(sun.shadow.camera, { left: -reach, right: reach, top: reach, bottom: -reach, near: reach * 0.2, far: reach * 4.5 });
  sun.shadow.bias = -0.0008; sun.shadow.normalBias = reach * 0.0016;
  const hemi = new THREE.HemisphereLight(ambientSky, ambientGround, ambient);
  scene.add(sun, sun.target, hemi);
  return { sun, hemi };
}
/** Camino cuesta abajo desde una celda: siempre al vecino más bajo; sale de los hoyos pequeños. */
function descend(T, start, maxSteps) {
  const { n, h } = T, path = [start], seen = new Set([start]);
  let cur = start, pits = 0;
  for (let step = 0; step < maxSteps; step += 1) {
    const r = Math.floor(cur / n), c = cur % n;
    let best = -1, bestH = h[cur], alt = -1, altH = Infinity;
    for (const [dr, dc] of NEIGHBORS) {
      const rr = r + dr, cc = c + dc;
      if (rr < 1 || cc < 1 || rr >= n - 1 || cc >= n - 1) continue;
      const j = rr * n + cc;
      if (seen.has(j)) continue;
      if (h[j] < bestH) { bestH = h[j]; best = j; }
      if (h[j] < altH) { altH = h[j]; alt = j; }
    }
    if (best < 0) { if (alt < 0 || (pits += 1) > 16) break; best = alt; }
    path.push(best); seen.add(best); cur = best;
  }
  return path;
}
/** Puntos del camino suavizados, con la distancia recorrida en cada uno. */
function pathPoints(T, cells, lift) {
  const raw = cells.map((i) => T.xz(i)), points = [];
  let along = 0;
  for (let k = 0; k < raw.length; k += 1) {
    let x = 0, z = 0, count = 0;
    for (let j = Math.max(0, k - 3); j <= Math.min(raw.length - 1, k + 3); j += 1) { x += raw[j][0]; z += raw[j][1]; count += 1; }
    x /= count; z /= count;
    if (points.length) along += Math.hypot(x - points[points.length - 1].x, z - points[points.length - 1].z);
    points.push({ x, z, y: T.at(x, z) + lift, s: along });
  }
  return { points, length: along, at(s) {
    const d = clamp(s, 0, along); let k = 1;
    while (k < points.length - 1 && points[k].s < d) k += 1;
    const a = points[k - 1], b = points[k], u = (d - a.s) / Math.max(1e-6, b.s - a.s);
    return { x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, z: a.z + (b.z - a.z) * u, dx: b.x - a.x, dz: b.z - a.z };
  } };
}
function rain(count, box, seed, color = 0xbcc8d6, opacity = 0.38) {
  const random = rng(seed), seeds = [], position = new Float32Array(count * 6);
  for (let i = 0; i < count; i += 1) seeds.push([random(), random(), random(), 0.7 + 0.6 * random()]);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
  const mesh = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false, fog: false }));
  mesh.frustumCulled = false;
  const update = (t, center) => {
    for (let i = 0; i < count; i += 1) {
      const [a, b, c, speed] = seeds[i], y = center.y + box.y * (1 - ((b + t * speed * 1.9) % 1)) - box.y * 0.35, x = center.x + (a - 0.5) * box.x, z = center.z + (c - 0.5) * box.z, len = 16 * speed;
      position.set([x, y, z, x + len * 0.16, y - len, z + len * 0.05], i * 6);
    }
    geometry.attributes.position.needsUpdate = true;
  };
  return { mesh, update };
}
const shake = (camera, t, amount) => { camera.position.x += Math.sin(t * 31.7) * amount; camera.position.y += Math.cos(t * 27.3) * amount * 0.8; camera.rotation.z += Math.sin(t * 23.1) * amount * 0.0012; };

// Erupción en el volcán Taal (Filipinas): columna de ceniza y bombas de lava al atardecer.
scenes.erupcion = async () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(38, W / H, 1, 90000), T = await loadTerrain("taal", 2.2);
  const sunDir = V3(-0.75, 0.14, -0.64);
  sky(scene, 0x060918, 0x8a3d2a, sunDir, new THREE.Color(1.0, 0.5, 0.22), 0.00011, 0x241a20);
  sunLight(scene, sunDir, 0xffc8a2, 1.6, T.size * 0.75, 0x3b4266, 0x1a1210, 0.55);
  scene.add(terrainMesh(T, { tint: 0.62 }));
  const water = new THREE.Mesh(new THREE.PlaneGeometry(60000, 60000), new THREE.MeshStandardMaterial({ color: 0x14283c, roughness: 0.14, metalness: 0.7 }));
  water.rotation.x = -Math.PI / 2; water.position.y = 1.2;
  scene.add(water);
  let vent = 0;
  for (let i = 0; i < T.n * T.n; i += 1) { const r = Math.floor(i / T.n), c = i % T.n; if (r > 20 && c > 20 && r < T.n - 20 && c < T.n - 20 && T.h[i] > T.h[vent]) vent = i; }
  const [vx, vz] = T.xz(vent), vy = T.h[vent];
  const glow = new THREE.PointLight(0xff5a1a, 1.5e6, 5000, 1.6); glow.position.set(vx, vy + 60, vz);
  scene.add(glow);
  const smoke = makeBillboards(950, false, 0.7), fire = makeBillboards(520, true);
  scene.add(smoke.mesh, fire.mesh);
  const random = rng(77), puffs = [], bombs = [], flows = [];
  for (let i = 0; i < 900; i += 1) puffs.push([random(), random() * Math.PI * 2, Math.sqrt(random()), random(), random()]);
  for (let i = 0; i < 300; i += 1) { const a = random() * Math.PI * 2, out = 30 + 95 * random(); bombs.push([random(), Math.cos(a) * out, 150 + 150 * random(), Math.sin(a) * out, random()]); }
  for (let k = 0; k < 3; k += 1) { const p = pathPoints(T, descend(T, vent + (k - 1) * 3 + (k % 2 ? T.n * 3 : -T.n * 3), 90), 4); for (let i = 0; i < 70; i += 1) flows.push([p, random(), random()]); }
  const look = V3();
  return { scene, camera, bloom: [0.62, 0.7, 0.8], exposure: 1.0, update(t) {
    const smokeList = [], fireList = [], cycle = 8;
    for (const [phase, angle, spread, seed, size] of puffs) {
      const age = ((phase + t / cycle) % 1) * cycle, u = age / cycle, rise = 700 * u ** 0.58 * (0.75 + 0.5 * size), r = (12 + 210 * u) * spread;
      const hot = (1 - smooth(0, 0.1, u)) * 0.9, g = 0.012 + 0.03 * seed + 0.045 * u;
      smokeList.push([vx + Math.cos(angle + u * 1.3) * r + 430 * u * u, vy + 16 + rise, vz + Math.sin(angle + u * 1.3) * r - 150 * u * u, 70 + 340 * u ** 0.75, smooth(0, 0.035, u) * (1 - u) ** 0.5 * 0.96, seed, angle + t * 0.1,
        g + 1.1 * hot, g + 0.34 * hot, g + 0.08 * hot]);
    }
    for (const [phase, bx, by, bz, seed] of bombs) {
      const age = ((phase + t / 2.9) % 1) * 2.9, y = vy + 15 + by * age - 46 * age * age;
      if (y < vy - 150) continue;
      const k = 1 - age / 2.9;
      fireList.push([vx + bx * age, y, vz + bz * age, 9 + 20 * seed, 0.9 * k, seed, 0, 3.2, 1.0 * k + 0.22, 0.1]);
    }
    for (const [p, phase, seed] of flows) { const s2 = ((phase + t * 0.035) % 1) * Math.min(p.length, 900), q = p.at(s2); fireList.push([q.x + (seed - 0.5) * 26, q.y + 3, q.z + (seed - 0.5) * 26, 18 + 24 * seed, 0.5, seed, 0, 2.8, 0.75, 0.07]); }
    fireList.push([vx, vy + 30, vz, 230, 0.4 + 0.08 * Math.sin(t * 19), 0.3, 0, 2.4, 0.7, 0.14]);
    glow.intensity = 1.5e6 * (0.8 + 0.25 * Math.sin(t * 23) + 0.12 * Math.sin(t * 61));
    const k = smooth(0, 2.2, t);
    camera.position.set(vx + lerp(1750, 1500, k), 0, vz + lerp(1350, 1600, k));
    camera.position.y = Math.max(T.at(camera.position.x, camera.position.z), 1.2) + lerp(80, 120, k);
    look.set(vx + 120, vy + lerp(300, 380, k), vz - 30);
    camera.lookAt(look);
    shake(camera, t, 1.6);
    smoke.fill(smokeList, camera); fire.fill(fireList, camera);
  } };
};

// Avalancha en el Huascarán (Perú): la nube de nieve baja por la ladera real, vista desde el valle.
scenes.avalancha = async () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(34, W / H, 2, 160000), T = await loadTerrain("huascaran", 1.25);
  const sunDir = V3(0.62, 0.5, 0.6);
  sky(scene, 0x103c8a, 0x9cc4ee, sunDir, new THREE.Color(1.0, 0.96, 0.88), 0.000016);
  sunLight(scene, sunDir, 0xfff4e2, 3.3, T.size * 0.75, 0x8fb6ff, 0x4c4741, 0.85);
  let top = 0; for (let i = 0; i < T.n * T.n; i += 1) if (T.h[i] > T.h[top]) top = i;
  scene.add(terrainMesh(T, { snowLine: T.h[top] * 0.46 }));
  const p = pathPoints(T, descend(T, top, 170), 10), reach = Math.min(p.length, 4600);
  const cloud = makeBillboards(1700, false, 0.2);
  scene.add(cloud.mesh);
  const random = rng(5), puffs = [];
  for (let i = 0; i < 1600; i += 1) puffs.push([random() ** 2.1, random() - 0.5, random(), random(), random() * Math.PI * 2]);
  // Mirador fijo: valle abajo, a un costado del camino de la avalancha.
  const a = p.at(reach * 0.2), b = p.at(reach * 0.85), len = Math.hypot(b.x - a.x, b.z - a.z) || 1, dx = (b.x - a.x) / len, dz = (b.z - a.z) / len;
  const eye = V3(b.x + dx * 2100 - dz * 900, 0, b.z + dz * 2100 + dx * 900), look = V3();
  eye.y = Math.max(T.at(eye.x, eye.z), b.y) + 320;
  return { scene, camera, bloom: [0.22, 0.5, 0.97], exposure: 0.86, update(t) {
    const front = reach * lerp(0.2, 0.66, smooth(-0.5, 2.7, t)), list = [], trail = 1500;
    for (const [u, side, lift, seed, turn] of puffs) {
      const s2 = front - u * trail;
      if (s2 < 0) continue;
      const q = p.at(s2), l = Math.hypot(q.dx, q.dz) || 1, nx = -q.dz / l, nz = q.dx / l, spread = 150 + 330 * u ** 0.7, boil = 0.5 + 0.5 * Math.sin(t * 5 + seed * 40), shade = 0.94 + 0.16 * seed;
      list.push([q.x + nx * side * spread, q.y + 20 + (90 + 260 * u ** 0.6) * lift + 40 * boil * (1 - u), q.z + nz * side * spread, 170 + 300 * u ** 0.6 + 80 * boil * (1 - u), (0.97 - 0.6 * u) * smooth(0, 0.05, 1 - u + 0.05), seed, turn + t * 0.5,
        shade * 0.96, shade * 0.98, shade * 1.02]);
    }
    const k = smooth(0, 2.6, t), f = p.at(front);
    camera.position.copy(eye).add(V3(-dx * 260 * k, 30 * k, -dz * 260 * k));
    look.set(lerp(a.x, f.x, 0.75), lerp(a.y, f.y, 0.75) + 120, lerp(a.z, f.z, 0.75));
    camera.lookAt(look);
    shake(camera, t, 1.8);
    cloud.fill(list, camera);
  } };
};

// Huaico en Chosica (Perú): el lodo baja por una quebrada real hacia el pueblo, bajo la lluvia.
scenes.huaico = async () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(40, W / H, 1, 60000), T = await loadTerrain("chosica", 1.35);
  const sunDir = V3(-0.5, 0.5, 0.7);
  sky(scene, 0x1c222a, 0x626a74, sunDir, new THREE.Color(0.22, 0.22, 0.23), 0.00024);
  const { hemi } = sunLight(scene, sunDir, 0xcfd6e0, 1.2, T.size * 0.75, 0x8f9aa8, 0x4a4037, 0.95);
  scene.add(terrainMesh(T, { tint: 0.74 }), houses(T, 4200, 3));
  // Quebrada: entre varios puntos altos, la que baja más y termina junto a las casas.
  const random = rng(9), n = T.n;
  let best = null;
  for (let k = 0; k < 500; k += 1) {
    const start = Math.floor(n * (0.08 + 0.84 * random())) * n + Math.floor(n * (0.08 + 0.84 * random()));
    const cells = descend(T, start, 150), end = cells[cells.length - 1];
    if (cells.length < 45) continue;
    let town = 0;
    for (const j of cells.slice(-22)) { const r = Math.floor(j / n), c = j % n; for (let dr = -3; dr <= 3; dr += 1) for (let dc = -3; dc <= 3; dc += 1) { const q = (r + dr) * n + c + dc; if (q >= 0 && q < n * n && T.cover[q] === 50) town += 1; } }
    const score = (T.h[start] - T.h[end]) * (0.3 + Math.min(1, town / 300)) * Math.min(1, cells.length / 80);
    if (!best || score > best.score) best = { cells, score };
  }
  const p = pathPoints(T, best.cells, 2.6), pts = p.points, m = pts.length, widthAt = (s2) => lerp(13, 58, s2 / p.length);
  // Cinta de lodo: angosta arriba, ancha al llegar al pueblo.
  const position = new Float32Array(m * 6), index = [];
  for (let k = 0; k < m; k += 1) {
    const a = pts[Math.max(0, k - 1)], b = pts[Math.min(m - 1, k + 1)], len = Math.hypot(b.x - a.x, b.z - a.z) || 1, nx = -(b.z - a.z) / len, nz = (b.x - a.x) / len, w = widthAt(pts[k].s);
    for (const side of [-1, 1]) { const x = pts[k].x + nx * w * side, z = pts[k].z + nz * w * side; position.set([x, Math.max(pts[k].y, T.at(x, z) + 1.6), z], (k * 2 + (side > 0 ? 1 : 0)) * 3); }
    if (k < m - 1) index.push(k * 2, k * 2 + 2, k * 2 + 1, k * 2 + 1, k * 2 + 2, k * 2 + 3);
  }
  const mudGeometry = new THREE.BufferGeometry();
  mudGeometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
  mudGeometry.setIndex(index);
  mudGeometry.computeVertexNormals();
  const mud = new THREE.Mesh(mudGeometry, new THREE.MeshStandardMaterial({ color: 0x2b1b11, roughness: 0.22, metalness: 0.2, side: THREE.DoubleSide }));
  mud.receiveShadow = true;
  scene.add(mud);
  const splash = makeBillboards(1500, false, 0.6), drops = rain(5200, V3(2200, 1000, 2200), 4, 0xbcc8d6, 0.3);
  scene.add(splash.mesh, drops.mesh);
  const puffs = [], body = [];
  for (let i = 0; i < 620; i += 1) puffs.push([random() ** 1.4, random() - 0.5, random(), random(), random() * Math.PI * 2]);
  for (let i = 0; i < 820; i += 1) body.push([random(), random() - 0.5, random(), random() * Math.PI * 2]);
  const look = V3(), end = pts[m - 1], tail = pts[Math.max(0, m - 30)], dl = Math.hypot(end.x - tail.x, end.z - tail.z) || 1, dx = (end.x - tail.x) / dl, dz = (end.z - tail.z) / dl;
  return { scene, camera, bloom: [0.2, 0.5, 0.95], exposure: 1.0, update(t) {
    const front = p.length * lerp(0.45, 0.98, smooth(-0.3, 2.5, t)), q = p.at(front);
    let k = 1; while (k < m - 1 && pts[k].s < front) k += 1;
    mudGeometry.setDrawRange(0, Math.max(0, k - 1) * 6);
    const list = [];
    for (const [phase, side, seed, turn] of body) {                 // lodo que corre por el cauce
      const s2 = ((phase + t * 0.22) % 1) * front, a = p.at(s2), w = widthAt(s2), len = Math.hypot(a.dx, a.dz) || 1, g = 0.7 + 0.5 * seed;
      list.push([a.x + (-a.dz / len) * side * w * 1.5, a.y + 3.5, a.z + (a.dx / len) * side * w * 1.5, 18 + 32 * seed, 0.7, seed, turn + t * 2, 0.12 * g, 0.078 * g, 0.048 * g]);
    }
    for (const [u, side, lift, seed, turn] of puffs) {              // el frente: lodo, piedras y polvo
      const s2 = front - u * 520; if (s2 < 0) continue;
      const a = p.at(s2), w = widthAt(s2), len = Math.hypot(a.dx, a.dz) || 1, g = 0.7 + 0.5 * seed;
      list.push([a.x + (-a.dz / len) * side * w * 2.2, a.y + 4 + 30 * lift * (1 - u) ** 2, a.z + (a.dx / len) * side * w * 2.2, 30 + 62 * (1 - u) * (0.45 + seed), 0.92 * (1 - u) ** 0.6, seed, turn + t, 0.15 * g, 0.098 * g, 0.06 * g]);
    }
    const flash = Math.max(0, 1 - Math.abs(t - 0.95) / 0.07) + 0.6 * Math.max(0, 1 - Math.abs(t - 1.12) / 0.05);
    hemi.intensity = 0.95 + 5 * flash;
    const pull = lerp(1.0, 0.7, smooth(0, 2.5, t));
    camera.position.set(end.x + dx * 470 * pull - dz * 210, 0, end.z + dz * 470 * pull + dx * 210);
    camera.position.y = T.at(camera.position.x, camera.position.z) + 150 * pull + 70;
    look.set(lerp(q.x, end.x, 0.3), lerp(q.y, end.y, 0.3) + 25, lerp(q.z, end.z, 0.3));
    camera.lookAt(look);
    shake(camera, t, 1.3);
    drops.update(t, look);
    splash.fill(list, camera);
  } };
};

// Inundación en Piura (Perú): el agua sube desde el río y cubre las calles.
scenes.inundacion = async () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(38, W / H, 1, 120000), T = await loadTerrain("piura", 2.4);
  const sunDir = V3(0.55, 0.13, -0.82);
  const dome = sky(scene, 0x2a323d, 0xb98a62, sunDir, new THREE.Color(0.5, 0.3, 0.16), 0.00017, 0x7d766e);
  sunLight(scene, sunDir, 0xffd3a6, 1.7, T.size * 0.75, 0x8e99a8, 0x55493c, 0.8);
  // El agua refleja el cielo: se toma el cielo como entorno.
  const skyScene = new THREE.Scene();
  skyScene.add(dome.clone());
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(skyScene, 0, 1, 90000).texture;
  const ground = terrainMesh(T, { tint: 0.9 }), town = houses(T, 6500, 6);
  ground.material.envMapIntensity = town.material.envMapIntensity = 0.3;
  scene.add(ground, town);
  // Ondas: mapa de normales hecho con ruido, repetido en espejo para que no se note la costura.
  const size = 256, data = new Uint8Array(size * size * 4), hgt = (x, y) => fbm2(x * 0.045, y * 0.045, 4) + 0.35 * fbm2(x * 0.19, y * 0.19, 2);
  for (let y = 0; y < size; y += 1) for (let x = 0; x < size; x += 1) {
    const nx = (hgt(x - 1, y) - hgt(x + 1, y)) * 3.2, ny = (hgt(x, y - 1) - hgt(x, y + 1)) * 3.2, l = Math.hypot(nx, ny, 1);
    data.set([(nx / l * 0.5 + 0.5) * 255, (ny / l * 0.5 + 0.5) * 255, (1 / l * 0.5 + 0.5) * 255, 255], (y * size + x) * 4);
  }
  const ripples = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  ripples.wrapS = ripples.wrapT = THREE.MirroredRepeatWrapping; ripples.repeat.set(260, 260); ripples.magFilter = THREE.LinearFilter; ripples.minFilter = THREE.LinearMipmapLinearFilter; ripples.generateMipmaps = true; ripples.anisotropy = 8; ripples.needsUpdate = true;
  const water = new THREE.Mesh(new THREE.PlaneGeometry(90000, 90000), new THREE.MeshStandardMaterial({ color: 0x4a3a2b, roughness: 0.16, metalness: 0.35, normalMap: ripples, normalScale: new THREE.Vector2(0.35, 0.35), envMapIntensity: 2.2, transparent: true, opacity: 0.96 }));
  water.rotation.x = -Math.PI / 2;
  scene.add(water);
  // Niveles: el del río (mediana de las celdas de agua) y uno que ya cubre buena parte de las calles.
  const wet = [], built = [];
  let cx = 0, cz = 0;
  for (let i = 0; i < T.n * T.n; i += 1) { if (T.cover[i] === 80) wet.push(T.h[i]); if (T.cover[i] === 50) { built.push(T.h[i]); const [x, z] = T.xz(i); cx += x; cz += z; } }
  wet.sort((a, b) => a - b); built.sort((a, b) => a - b);
  cx /= Math.max(1, built.length); cz /= Math.max(1, built.length);
  const low = built[Math.floor(built.length * 0.3)] + 0.6, high = built[Math.floor(built.length * 0.82)] + 3.0;
  const drops = rain(5200, V3(1800, 700, 1800), 8, 0xd2dbe6, 0.3), look = V3();
  scene.add(drops.mesh);
  return { scene, camera, bloom: [0.18, 0.5, 0.97], exposure: 0.95, update(t) {
    water.position.y = lerp(low, high, smooth(-0.4, 2.5, t)) + 0.12 * Math.sin(t * 2.4);
    ripples.offset.set(t * 0.6, t * 0.35);
    const k = smooth(0, 2.4, t);
    camera.position.set(cx + lerp(-420, -330, k), 0, cz + lerp(560, 430, k));
    camera.position.y = Math.max(T.at(camera.position.x, camera.position.z), water.position.y) + lerp(46, 34, k);
    look.set(cx + 130, T.at(cx, cz) + 6, cz - 260);
    camera.lookAt(look);
    drops.update(t, look);
  } };
};

// --- Dibujo ------------------------------------------------------------------------------------------------------------
const ready = {};
window.draw = async (name, t) => {
  if (!scenes[name]) throw new Error(`No existe la escena «${name}».`);
  ready[name] ??= await scenes[name]();
  const s = ready[name];
  s.update(t);
  renderPass.scene = s.scene;
  renderPass.camera = s.camera;
  [bloom.strength, bloom.radius, bloom.threshold] = s.bloom;
  renderer.toneMappingExposure = s.exposure;
  composer.render();
  return true;
};
window.sceneNames = Object.keys(scenes);
console.log("cine: listo", window.sceneNames.join(", "));
