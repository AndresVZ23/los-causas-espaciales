"use client";

// Nave y superhéroe en 3D (three.js, modelos hechos con figuras simples, sin archivos externos). Se dibujan en un lienzo
// transparente encima del mapa, en el píxel que calcula MapLibre, con luz de sol y una ligera inclinación como la cámara.
// three.js se carga solo al entrar a una misión. Si el equipo no puede iniciar WebGL, `onUnavailable` avisa y se usan las figuras 2D.

import { useEffect, useRef } from "react";
import type * as THREE_NS from "three";
import type { Gender } from "./game-types";

export interface Scene3DState {
  hero: { x: number; y: number } | null;
  ship: { x: number; y: number } | null;
  phase: "off" | "descenso" | "vuelo" | "aterriza" | "suelo";
  running: boolean;
  /** Rumbo del héroe en radianes: 0 hacia la cámara (sur), π alejándose (norte), π/2 hacia el este. */
  heading: number;
  gender: Gender;
  showHero: boolean;
}

export type Three = typeof THREE_NS;

export function buildShip(T: Three) {
  const ship = new T.Group();
  const hull = new T.MeshStandardMaterial({ color: 0x9aa8c4, metalness: 0.25, roughness: 0.45 });
  const dark = new T.MeshStandardMaterial({ color: 0x46516e, metalness: 0.2, roughness: 0.55 });
  const gold = new T.MeshStandardMaterial({ color: 0xe2bb55, metalness: 0.3, roughness: 0.35 });
  const glass = new T.MeshStandardMaterial({ color: 0x7fd6ff, metalness: 0.2, roughness: 0.05, transparent: true, opacity: 0.8, emissive: 0x0b3b55 });
  const glow = new T.MeshBasicMaterial({ color: 0x8ff0ff });
  // Fuselaje: cono alargado con la punta hacia adelante (-Z, alejándose de la cámara).
  const body = new T.Mesh(new T.CylinderGeometry(0.18, 0.5, 2.6, 18), hull);
  body.rotation.x = -Math.PI / 2;
  ship.add(body);
  const cockpit = new T.Mesh(new T.SphereGeometry(0.32, 20, 14, 0, Math.PI * 2, 0, Math.PI / 2), glass);
  cockpit.position.set(0, 0.32, -0.25);
  cockpit.scale.set(0.9, 0.7, 1.6);
  ship.add(cockpit);
  // Alas en flecha, con borde dorado.
  const wingShape = new T.Shape();
  wingShape.moveTo(0, 0); wingShape.lineTo(1.9, 0.9); wingShape.lineTo(1.9, 1.25); wingShape.lineTo(0, 1.05); wingShape.closePath();
  const wingGeo = new T.ExtrudeGeometry(wingShape, { depth: 0.07, bevelEnabled: false });
  for (const side of [1, -1]) {
    const wing = new T.Mesh(wingGeo, dark);
    wing.rotation.x = -Math.PI / 2;
    wing.scale.x = side;
    wing.position.set(0.25 * side, -0.05, 0.75);
    ship.add(wing);
    const tip = new T.Mesh(new T.BoxGeometry(0.08, 0.45, 0.5), gold);
    tip.position.set(2.1 * side, 0.15, -0.05);
    ship.add(tip);
    const engine = new T.Mesh(new T.CylinderGeometry(0.17, 0.2, 0.7, 14), dark);
    engine.rotation.x = Math.PI / 2;
    engine.position.set(0.42 * side, -0.05, 1.25);
    ship.add(engine);
    const flame = new T.Mesh(new T.CircleGeometry(0.15, 16), glow);
    flame.position.set(0.42 * side, -0.05, 1.61);
    flame.name = "flame";
    ship.add(flame);
    const leg = new T.Mesh(new T.CylinderGeometry(0.03, 0.03, 0.5, 6), gold);
    leg.position.set(0.7 * side, -0.35, 0.4);
    leg.name = "leg";
    ship.add(leg);
  }
  const fin = new T.Mesh(new T.BoxGeometry(0.06, 0.55, 0.6), gold);
  fin.position.set(0, 0.35, 1.0);
  ship.add(fin);
  return ship;
}

export function buildHero(T: Three, gender: Gender) {
  const hero = new T.Group();
  const suit = new T.MeshStandardMaterial({ color: 0x2c6fd1, roughness: 0.55, metalness: 0.1 });
  const cape = new T.MeshStandardMaterial({ color: 0xc8323f, roughness: 0.7, side: T.DoubleSide });
  const skin = new T.MeshStandardMaterial({ color: 0xe0a77a, roughness: 0.8 });
  const gold = new T.MeshStandardMaterial({ color: 0xf1c84b, metalness: 0.2, roughness: 0.4 });
  const hair = new T.MeshStandardMaterial({ color: 0x3a2418, roughness: 0.9 });
  const mask = new T.MeshStandardMaterial({ color: 0xc8323f, roughness: 0.5 });
  const emblem = new T.MeshStandardMaterial({ color: 0x38d9c3, emissive: 0x0d4a42, roughness: 0.4 });
  const torso = new T.Mesh(new T.CapsuleGeometry(0.28, 0.55, 6, 14), suit);
  torso.position.y = 1.15;
  hero.add(torso);
  const belt = new T.Mesh(new T.CylinderGeometry(0.29, 0.29, 0.08, 16), gold);
  belt.position.y = 0.88;
  hero.add(belt);
  const badge = new T.Mesh(new T.CircleGeometry(0.11, 16), emblem);
  badge.position.set(0, 1.25, 0.285);
  hero.add(badge);
  const head = new T.Mesh(new T.SphereGeometry(0.24, 18, 14), skin);
  head.position.y = 1.78;
  hero.add(head);
  const band = new T.Mesh(new T.TorusGeometry(0.235, 0.045, 8, 24), mask);
  band.position.set(0, 1.8, 0);
  band.rotation.x = Math.PI / 2;
  hero.add(band);
  const cap = new T.Mesh(new T.SphereGeometry(0.255, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2.1), hair);
  cap.position.y = 1.8;
  hero.add(cap);
  if (gender === "mujer") {
    const long = new T.Mesh(new T.CapsuleGeometry(0.2, 0.35, 4, 10), hair);
    long.position.set(0, 1.55, -0.14);
    hero.add(long);
  }
  const capeMesh = new T.Mesh(new T.PlaneGeometry(0.7, 1.1, 1, 6), cape);
  capeMesh.position.set(0, 1.0, -0.3);
  capeMesh.rotation.x = 0.12;
  capeMesh.name = "cape";
  hero.add(capeMesh);
  const limb = (x: number, y: number, len: number, material: THREE_NS.Material, name: string) => {
    const pivot = new T.Group();
    pivot.position.set(x, y, 0);
    const mesh = new T.Mesh(new T.CapsuleGeometry(0.09, len, 4, 10), material);
    mesh.position.y = -len / 2 - 0.06;
    pivot.add(mesh);
    pivot.name = name;
    hero.add(pivot);
    return pivot;
  };
  limb(-0.38, 1.42, 0.5, suit, "armL");
  limb(0.38, 1.42, 0.5, suit, "armR");
  const legL = limb(-0.14, 0.82, 0.55, suit, "legL");
  const legR = limb(0.14, 0.82, 0.55, suit, "legR");
  for (const leg of [legL, legR]) {
    const boot = new T.Mesh(new T.BoxGeometry(0.17, 0.14, 0.26), gold);
    boot.position.set(0, -0.72, 0.04);
    leg.add(boot);
  }
  return hero;
}

export function Hero3D({ state, onUnavailable }: { state: Scene3DState; onUnavailable: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);
  const genderKey = state.gender;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let disposed = false;
    let frame = 0;
    let cleanup = () => {};
    import("three").then((T) => {
      if (disposed) return;
      let renderer: THREE_NS.WebGLRenderer;
      try {
        renderer = new T.WebGLRenderer({ canvas, alpha: true, antialias: true });
      } catch {
        onUnavailable();
        return;
      }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.outputColorSpace = T.SRGBColorSpace;
      const scene = new T.Scene();
      // Cámara ortográfica en píxeles: (x, -y) de pantalla. La inclinación de los modelos imita la de la cámara del mapa.
      const camera = new T.OrthographicCamera(0, 1, 0, -1, -2000, 2000);
      const resize = () => {
        const w = canvas.clientWidth, h = canvas.clientHeight;
        renderer.setSize(w, h, false);
        camera.right = w; camera.bottom = -h; camera.updateProjectionMatrix();
      };
      resize();
      const observer = new ResizeObserver(resize);
      observer.observe(canvas);
      scene.add(new T.HemisphereLight(0xeef5ff, 0x9a8466, 1.6));
      scene.add(new T.AmbientLight(0xffffff, 0.35));
      const sun = new T.DirectionalLight(0xfff0d8, 2.2);
      sun.position.set(-300, 500, 400);
      scene.add(sun);

      const ship = buildShip(T);
      const shipRoot = new T.Group();
      shipRoot.add(ship);
      scene.add(shipRoot);
      // Personaje realista animado (Mixamo). Mientras carga se muestra la figura simple; si falla, se queda la figura simple.
      let hero: THREE_NS.Object3D = buildHero(T, stateRef.current.gender);
      let rig: import("./hero-rig").HeroRig | null = null;
      const heroRoot = new T.Group();
      heroRoot.add(hero);
      scene.add(heroRoot);
      import("./hero-rig").then(({ loadHeroRig }) => loadHeroRig(T, stateRef.current.gender)).then((loaded) => {
        if (disposed) return;
        heroRoot.remove(hero);
        rig = loaded;
        hero = new T.Group();
        // Los modelos de Mixamo miden ~1,8 unidades y miran hacia +Z, como la figura simple.
        hero.add(loaded.object);
        heroRoot.add(hero);
      }).catch(() => { /* se queda la figura simple */ });
      const named = (group: THREE_NS.Object3D, name: string) => group.children.filter((child) => child.name === name);
      // En una vista desde arriba las personas se ven erguidas: apenas se inclinan hacia la cámara para mostrar la cabeza.
      const tilt = 0.32;
      let landingStart = 0;
      let exitStart = 0;
      let lastPhase = "";
      let heading = 0;
      const clock = new T.Clock();

      const tick = () => {
        const delta = clock.getDelta();
        const t = clock.elapsedTime;
        const s = stateRef.current;
        if (s.phase !== lastPhase) {
          if (s.phase === "aterriza") landingStart = t;
          if (s.phase === "suelo") exitStart = t;
          lastPhase = s.phase;
        }
        // Nave
        shipRoot.visible = !!s.ship && s.phase !== "off";
        if (s.ship) {
          const flying = s.phase === "descenso" || s.phase === "vuelo";
          const land = s.phase === "aterriza" ? Math.min((t - landingStart) / 1.6, 1) : s.phase === "suelo" ? 1 : 0;
          const base = Math.min(46, canvas.clientWidth / 24);
          const size = flying ? base : base * (1 - 0.26 * land);
          const lift = flying ? 22 + Math.sin(t * 2.2) * 5 : (1 - land) * 120;
          shipRoot.position.set(s.ship.x, -s.ship.y + lift, 0);
          shipRoot.scale.setScalar(size);
          shipRoot.rotation.x = tilt;
          ship.rotation.set(0, 0, flying ? Math.sin(t * 1.3) * 0.06 : 0);
          for (const flame of named(ship, "flame")) flame.scale.setScalar(s.phase === "suelo" ? 0.4 : 0.85 + Math.random() * 0.35);
          for (const leg of named(ship, "leg")) leg.visible = land > 0.6;
        }
        // Héroe: sale de la nave al aterrizar, corre balanceando brazos y piernas, y gira hacia donde va.
        heroRoot.visible = s.showHero && !!s.hero && s.phase === "suelo";
        if (s.hero && heroRoot.visible) {
          const out = Math.min((t - exitStart) / 0.9, 1);
          const from = s.ship ?? s.hero;
          const x = from.x + (s.hero.x - from.x) * out;
          const y = from.y + (s.hero.y - from.y) * out;
          heroRoot.position.set(x, -y + (!rig && s.running ? Math.abs(Math.sin(t * 12)) * 4 : 0), 400);
          heroRoot.scale.setScalar(Math.min(46, canvas.clientWidth / 22) * (0.4 + 0.6 * out));
          heading += (((s.heading - heading + Math.PI * 3) % (Math.PI * 2)) - Math.PI) * 0.2;
          // La inclinación va en el grupo exterior (la cámara) y el giro en el interior (el héroe).
          heroRoot.rotation.x = tilt;
          hero.rotation.set(0, heading, 0);
          if (rig) rig.play(s.running ? "Run" : "Idle");
          const swing = s.running ? Math.sin(t * 12) * 0.7 : Math.sin(t * 2) * 0.05;
          for (const [name, sign] of [["legL", 1], ["legR", -1], ["armL", -1], ["armR", 1]] as const) {
            for (const part of named(hero, name)) part.rotation.x = swing * sign;
          }
          for (const capeMesh of named(hero, "cape")) capeMesh.rotation.x = 0.12 + (s.running ? 0.45 + Math.sin(t * 9) * 0.08 : Math.sin(t * 1.5) * 0.05);
        }
        rig?.update(Math.min(delta, 0.05));
        renderer.render(scene, camera);
        frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
      cleanup = () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
        scene.traverse((object) => {
          const mesh = object as THREE_NS.Mesh;
          mesh.geometry?.dispose();
          const material = mesh.material as THREE_NS.Material | THREE_NS.Material[] | undefined;
          (Array.isArray(material) ? material : material ? [material] : []).forEach((item) => item.dispose());
        });
        renderer.dispose();
      };
    }).catch(() => onUnavailable());
    return () => { disposed = true; cleanup(); };
    // El modelo del héroe depende de la figura elegida; lo demás se lee en cada cuadro desde stateRef.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genderKey]);

  return <canvas ref={canvasRef} className="game3d" aria-hidden />;
}
