"use client";

// La Luna real en 3D: mapa de color de la cámara LROC y relieve del altímetro LOLA de la sonda Lunar Reconnaissance
// Orbiter (NASA Scientific Visualization Studio, «CGI Moon Kit», ID 4720). Se ve como un horizonte curvo abajo, con el sol
// rasante para que los cráteres hagan sombra. Al saltar al cometa la cámara sube y la Luna se aleja.

import { useEffect, useRef } from "react";
import type * as THREE_NS from "three";

const RADIUS = 40;
const DROP = 2.84; // la cima de la Luna queda al 65 % de la altura de la pantalla

export function MoonScene({ leaving }: { leaving: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const leavingRef = useRef(leaving);
  useEffect(() => { leavingRef.current = leaving; }, [leaving]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let disposed = false;
    let cleanup = () => {};
    Promise.all([import("three"), import("./hero-3d")]).then(([T, { buildShip }]) => {
      if (disposed) return;
      let renderer: THREE_NS.WebGLRenderer;
      try { renderer = new T.WebGLRenderer({ canvas, alpha: true, antialias: true }); } catch { return; }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.outputColorSpace = T.SRGBColorSpace;
      const scene = new T.Scene();
      const camera = new T.PerspectiveCamera(35, 1, 0.1, 400);
      camera.position.set(0, 0, 30);
      camera.lookAt(0, 0, 0);
      const resize = () => {
        const w = canvas.clientWidth, h = canvas.clientHeight;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      };
      resize();
      const observer = new ResizeObserver(resize);
      observer.observe(canvas);

      const loader = new T.TextureLoader();
      const color = loader.load("/textures/moon/lroc_color_2k.jpg");
      color.colorSpace = T.SRGBColorSpace;
      color.anisotropy = renderer.capabilities.getMaxAnisotropy();
      const relief = loader.load("/textures/moon/ldem_3_8bit.jpg");
      const material = new T.MeshStandardMaterial({ map: color, bumpMap: relief, bumpScale: 2.2, displacementMap: relief, displacementScale: 0.35, roughness: 1, metalness: 0 });
      const moon = new T.Mesh(new T.SphereGeometry(RADIUS, 256, 128), material);
      moon.position.set(0, -RADIUS - DROP, 0);
      // Mares y cráteres del lado visible hacia arriba.
      moon.rotation.set(1.1, -0.4, 0.15);
      scene.add(moon);
      // Sol rasante desde la izquierda y un poco de luz reflejada por la Tierra.
      const sun = new T.DirectionalLight(0xfff6e8, 3.4);
      sun.position.set(-60, 18, 25);
      scene.add(sun);
      scene.add(new T.AmbientLight(0x9fb4ff, 0.35));

      // Bandera del Perú (rojo, blanco, rojo en franjas verticales) plantada a la izquierda del héroe, ondeando.
      const flagCanvas = document.createElement("canvas");
      flagCanvas.width = 300; flagCanvas.height = 200;
      const fctx = flagCanvas.getContext("2d")!;
      fctx.fillStyle = "#D91023"; fctx.fillRect(0, 0, 300, 200);
      fctx.fillStyle = "#FFFFFF"; fctx.fillRect(100, 0, 100, 200);
      const flagTexture = new T.CanvasTexture(flagCanvas);
      flagTexture.colorSpace = T.SRGBColorSpace;
      const flagGeo = new T.PlaneGeometry(2.1, 1.4, 24, 8);
      const flagBase = (flagGeo.attributes.position as THREE_NS.BufferAttribute).array.slice();
      const flag = new T.Mesh(flagGeo, new T.MeshStandardMaterial({ map: flagTexture, side: T.DoubleSide, roughness: 0.8 }));
      const pole = new T.Mesh(new T.CylinderGeometry(0.04, 0.04, 3.4, 8), new T.MeshStandardMaterial({ color: 0xdddddd, metalness: 0.6, roughness: 0.3 }));
      const flagGroup = new T.Group();
      pole.position.y = 1.7;
      flag.position.set(1.05, 2.65, 0);
      flagGroup.add(pole, flag);
      flagGroup.position.set(-3.4, -DROP - 0.1, 2);
      flagGroup.rotation.y = 0.35;
      scene.add(flagGroup);

      // La nave del héroe, estacionada a la derecha; al despegar sube y vuela hacia la Tierra.
      const ship = buildShip(T);
      ship.scale.setScalar(1.25);
      const parked = new T.Vector3(4.6, -DROP + 0.55, 1.5);
      ship.position.copy(parked);
      ship.rotation.set(0.15, -0.9, 0);
      scene.add(ship);

      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const clock = new T.Clock();
      let lift = 0;
      let frame = 0;
      const tick = () => {
        const dt = Math.min(clock.getDelta(), 0.05);
        if (!reduced) moon.rotation.y += dt * 0.004;
        // Al saltar, la Luna baja y se aleja (la cámara sube).
        lift += ((leavingRef.current ? 1 : 0) - lift) * (reduced ? 1 : dt * 1.2);
        moon.position.y = -RADIUS - DROP - lift * 26;
        flagGroup.position.y = -DROP - 0.1 - lift * 26;
        // La bandera ondea: cada vértice se mueve según su distancia al mástil.
        const pos = flagGeo.attributes.position as THREE_NS.BufferAttribute;
        const time = reduced ? 0 : clock.elapsedTime;
        for (let i = 0; i < pos.count; i += 1) {
          const x = flagBase[i * 3] + 1.05;
          pos.setZ(i, Math.sin(x * 2.6 - time * 4) * 0.12 * (x / 2.1));
        }
        pos.needsUpdate = true;
        flagGeo.computeVertexNormals();
        // Nave: estacionada con los motores suaves; al despegar sube hacia la Tierra, arriba al centro, y se achica.
        if (leavingRef.current) {
          ship.position.lerp(new T.Vector3(0, 7.5, -30), reduced ? 1 : dt * 0.9);
          ship.rotation.x += (-0.9 - ship.rotation.x) * dt * 2;
          ship.rotation.y += (0 - ship.rotation.y) * dt * 2;
        } else {
          ship.position.y = parked.y + Math.sin(clock.elapsedTime * 1.4) * 0.05;
        }
        renderer.render(scene, camera);
        frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
      cleanup = () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
        flagTexture.dispose();
        flagGeo.dispose();
        moon.geometry.dispose();
        material.dispose();
        color.dispose();
        relief.dispose();
        renderer.dispose();
      };
    });
    return () => { disposed = true; cleanup(); };
  }, []);

  return <canvas ref={canvasRef} className="gameMoon3d" aria-hidden />;
}
