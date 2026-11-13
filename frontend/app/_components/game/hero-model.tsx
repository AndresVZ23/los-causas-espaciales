"use client";

// El superhéroe en 3D para las pantallas fuera de la misión: elegir figura, la Luna y el viaje en cometa.
// Es el mismo modelo de la misión (buildHero), con su propia cámara y luz. three.js se carga al montarse.

import { useEffect, useRef, useState } from "react";
import type * as THREE_NS from "three";
import type { Gender } from "./game-types";
import { HeroAvatar } from "./hero-avatar";

type Pose = "idle" | "wave" | "fly";

export function HeroModel({ gender, size, pose = "idle", label }: { gender: Gender; size: number; pose?: Pose; label?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let disposed = false;
    let cleanup = () => {};
    Promise.all([import("three"), import("./hero-rig")]).then(async ([T, { loadHeroRig }]) => {
      const rig = await loadHeroRig(T, gender);
      if (disposed) return;
      let renderer: THREE_NS.WebGLRenderer;
      try { renderer = new T.WebGLRenderer({ canvas, alpha: true, antialias: true }); } catch { setFailed(true); return; }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.outputColorSpace = T.SRGBColorSpace;
      renderer.setSize(size, size * 1.25, false);
      const scene = new T.Scene();
      const camera = new T.PerspectiveCamera(30, 1 / 1.25, 0.1, 50);
      camera.position.set(0, 1.25, 5.2);
      camera.lookAt(0, 1.05, 0);
      scene.add(new T.HemisphereLight(0xeef5ff, 0x9a8466, 1.6));
      scene.add(new T.AmbientLight(0xffffff, 0.35));
      const sun = new T.DirectionalLight(0xfff0d8, 2.4);
      sun.position.set(-3, 5, 4);
      scene.add(sun);
      const rim = new T.DirectionalLight(0x8fd8ff, 1.2);
      rim.position.set(3, 2, -3);
      scene.add(rim);
      if (disposed) return;
      const hero = new T.Group();
      hero.add(rig.object);
      scene.add(hero);
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const clock = new T.Clock();
      let frame = 0;
      const tick = () => {
        const delta = clock.getDelta();
        const t = reduced ? 0.6 : clock.elapsedTime;
        rig.update(reduced ? 0 : Math.min(delta, 0.05));
        hero.rotation.y = pose === "fly" ? -0.6 : Math.sin(t * 0.5) * 0.5;
        // Volar: el cuerpo casi horizontal sobre el cometa; saludar: el brazo derecho arriba (poses no grabadas).
        hero.rotation.x = pose === "fly" ? -1.1 : 0;
        hero.position.y = pose === "fly" ? 0.9 + Math.sin(t * 3) * 0.05 : 0;
        const arm = rig.bone("RightArm");
        if (arm && pose === "wave") { arm.rotation.z = -1.9 + Math.sin(t * 6) * 0.25; }
        if (arm && pose === "fly") { arm.rotation.x = -2.6; }
        renderer.render(scene, camera);
        if (!reduced) frame = requestAnimationFrame(tick);
      };
      tick();
      cleanup = () => {
        cancelAnimationFrame(frame);
        scene.traverse((object) => {
          const mesh = object as THREE_NS.Mesh;
          mesh.geometry?.dispose();
          const material = mesh.material as THREE_NS.Material | THREE_NS.Material[] | undefined;
          (Array.isArray(material) ? material : material ? [material] : []).forEach((item) => item.dispose());
        });
        renderer.dispose();
      };
    }).catch(() => setFailed(true));
    return () => { disposed = true; cleanup(); };
  }, [gender, size, pose]);

  if (failed) return <HeroAvatar gender={gender} size={size * 0.8} title={label} />;
  return <canvas ref={canvasRef} className="heroModel" style={{ width: size, height: size * 1.25 }} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} />;
}
