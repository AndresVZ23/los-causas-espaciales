"use client";

// Mundo 3D de una misión, diseñado con datos reales (ADR-048, opción A): relieve Copernicus DEM GLO-30 y cobertura
// ESA WorldCover 2021 del lugar, construidos por scripts/missions/build_terrain.py. El terreno es continuo (no bloques);
// árboles, arbustos y rocas se reparten solo donde WorldCover dice bosque, matorral o suelo desnudo. Cielo con sol y nubes,
// agua con reflejo, la nave que aterriza y el héroe animado que corre en tercera persona hasta los vecinos del pueblo.
// Si el terreno no llega o WebGL falla, `onUnavailable` vuelve a la vista de mapa.

import { useCallback, useEffect, useRef, useState } from "react";
import type * as THREE_NS from "three";
import type { Gender, Hero, Mission } from "./game-types";
import type { Checkpoint } from "./mission-logic";
import { CULTURE, drawFlag, nazcaHummingbird, volcanoPlume } from "./culture";
import { ITEMS, buildHandItem, disposeHandItem, type HandItem, type ItemId } from "./hand-items";
import { NINO_CHATS, NINO_COUNTRY, NINO_FACTS, PLAIN_CHATS, ninoCredit } from "./nino-2026";
import { buildRibbon, cellXZ, distanceToPath, drainage, flowTexture, mainChannel, smoothPath, traceDown } from "./terrain-flow";

interface Terrain {
  id: string; size_km: number; grid: number; cell_m: number;
  base_elevation_m: number; max_elevation_m: number;
  relief_dm: string; cover: string; sea_assumed: boolean;
}

// Colores naturales por clase de ESA WorldCover (y sin dato).
const COVER_COLOR: Record<number, number> = {
  0: 0xa8a39a, 10: 0x35602d, 20: 0x7d7a40, 30: 0x8fa94c, 40: 0xb9ad5c, 50: 0x9b958c,
  60: 0xcdb68b, 70: 0xf1f5f8, 80: 0x2e5f86, 90: 0x50805f, 95: 0x2f5b3c, 100: 0x8e9a6c,
};
const ROCK = 0x7d6f63;
// Lanzador de ayuda: qué lanza el héroe según el peligro de cada vecino.
const TOOL: Record<string, { icon: string; name: string; color: number }> = {
  temp: { icon: "💧", name: "agua fresca", color: 0x7fd8ff },
  lluvia: { icon: "🧱", name: "sacos de arena", color: 0xe0c27a },
  agua: { icon: "🌱", name: "semillas", color: 0x8be07a },
  sol: { icon: "🔭", name: "medidor del aire", color: 0xffe08a },
  brecha: { icon: "📡", name: "un sensor", color: 0xc9a8ff },
};
// Contaminadores: el mensaje es una recomendación general de salud, no un dato medido de la misión.
const POLLUTER: Checkpoint = { id: "contaminador", title: "Contaminación", quest: "Quema de basura", icon: "🛑", ask: "¡Quemo la basura y listo, así es más rápido!", message: "", tone: "alerta", bearing: 0 };
const DOG: Checkpoint = { id: "perro", title: "Perrito herido", quest: "Perrito herido", icon: "🐶", ask: "Auuu… (está herido y tiembla)", message: "", tone: "alerta", bearing: 0 };
const POLLUTER_DONE: Checkpoint = { ...POLLUTER, ask: "Está bien, dejo de quemarla…", message: "¡Gracias! Quemar basura llena el aire de humo y partículas que dañan los pulmones. Sepárala y recíclala: así cuidas a tu pueblo." };
const toolFor = (item: Checkpoint) => (item.id === "lluvia" && item.title === "Agua" ? TOOL.agua : TOOL[item.id] ?? TOOL.brecha);

// Calles recreadas: cada tantas celdas urbanas va una calle (la cuadrícula es del juego, no el trazado real).
const STREET_EVERY = 6;
const COVER_NAME: Record<number, string> = {
  0: "Sin dato", 10: "Bosque", 20: "Matorral", 30: "Pasto", 40: "Cultivo", 50: "Ciudad", 60: "Suelo desnudo o arena",
  70: "Nieve o hielo", 80: "Agua", 90: "Humedal", 95: "Manglar", 100: "Musgo y líquenes",
};

function decode(b64: string, kind: "u16" | "u8"): Uint16Array | Uint8Array {
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return kind === "u16" ? new Uint16Array(bytes.buffer) : bytes;
}

type Three = typeof import("three");
/** Camioneta de rescate: cabina, tolva, faros y cuatro ruedas (las ruedas giran al avanzar). */
function buildTruck(T: Three) {
  const g = new T.Group();
  const paint = new T.MeshStandardMaterial({ color: 0xf2f2ee, roughness: 0.5, metalness: 0.2 });
  const stripe = new T.MeshStandardMaterial({ color: 0xff6a1a, roughness: 0.6 });
  const glass = new T.MeshStandardMaterial({ color: 0x24394d, roughness: 0.1, metalness: 0.5 });
  const tire = new T.MeshStandardMaterial({ color: 0x1b1b1b, roughness: 0.9 });
  const body = new T.Mesh(new T.BoxGeometry(2.2, 0.9, 5.2), paint); body.position.y = 1.0; g.add(body);
  const cab = new T.Mesh(new T.BoxGeometry(2.0, 0.95, 2.0), paint); cab.position.set(0, 1.9, 0.9); g.add(cab);
  const window = new T.Mesh(new T.BoxGeometry(1.9, 0.6, 0.05), glass); window.position.set(0, 2.0, 1.92); g.add(window);
  const band = new T.Mesh(new T.BoxGeometry(2.22, 0.22, 5.22), stripe); band.position.y = 1.15; g.add(band);
  const siren = new T.Mesh(new T.BoxGeometry(0.9, 0.18, 0.3), new T.MeshBasicMaterial({ color: 0xff3030 })); siren.position.set(0, 2.45, 0.9); siren.name = "siren"; g.add(siren);
  for (const [x, z] of [[-1.05, 1.7], [1.05, 1.7], [-1.05, -1.7], [1.05, -1.7]]) {
    const wheel = new T.Mesh(new T.CylinderGeometry(0.48, 0.48, 0.4, 18), tire);
    wheel.rotation.z = Math.PI / 2; wheel.position.set(x, 0.5, z); wheel.name = "wheel"; g.add(wheel);
  }
  g.traverse((o) => { (o as import("three").Mesh).castShadow = true; });
  return g;
}
/** Moto: cuadro, asiento, manubrio y dos ruedas. */
function buildMoto(T: Three) {
  const g = new T.Group();
  const paint = new T.MeshStandardMaterial({ color: 0xd8262f, roughness: 0.4, metalness: 0.4 });
  const dark = new T.MeshStandardMaterial({ color: 0x1b1b1b, roughness: 0.9 });
  const frame = new T.Mesh(new T.BoxGeometry(0.35, 0.45, 1.6), paint); frame.position.y = 0.85; g.add(frame);
  const seat = new T.Mesh(new T.BoxGeometry(0.4, 0.15, 0.7), dark); seat.position.set(0, 1.15, -0.2); g.add(seat);
  const bar = new T.Mesh(new T.CylinderGeometry(0.04, 0.04, 0.8, 8), dark); bar.rotation.z = Math.PI / 2; bar.position.set(0, 1.3, 0.75); g.add(bar);
  for (const z of [0.8, -0.8]) {
    const wheel = new T.Mesh(new T.CylinderGeometry(0.42, 0.42, 0.18, 18), dark);
    wheel.rotation.z = Math.PI / 2; wheel.position.set(0, 0.42, z); wheel.name = "wheel"; g.add(wheel);
  }
  g.traverse((o) => { (o as import("three").Mesh).castShadow = true; });
  return g;
}
/** Bote de rescate inflable con motor fuera de borda. */
function buildBoat(T: Three) {
  const g = new T.Group();
  const hull = new T.Mesh(new T.CapsuleGeometry(1.1, 3.4, 6, 14), new T.MeshStandardMaterial({ color: 0xff6a1a, roughness: 0.6 }));
  hull.rotation.x = Math.PI / 2; hull.scale.set(1, 1, 0.45); hull.position.y = 0.35; g.add(hull);
  const floor = new T.Mesh(new T.BoxGeometry(1.6, 0.1, 3.6), new T.MeshStandardMaterial({ color: 0x2b2b2b })); floor.position.y = 0.55; g.add(floor);
  const motor = new T.Mesh(new T.BoxGeometry(0.5, 0.8, 0.5), new T.MeshStandardMaterial({ color: 0x1b1b1b })); motor.position.set(0, 0.8, -2.1); g.add(motor);
  g.traverse((o) => { (o as import("three").Mesh).castShadow = true; });
  return g;
}


/** Casa familiar con puerta visible, para los lugares sin ciudad. */
function buildFamilyHouse(T: Three) {
  const g = new T.Group();
  const walls = new T.Mesh(new T.BoxGeometry(9, 4.5, 8), new T.MeshStandardMaterial({ color: 0xf1e3c8, roughness: 0.85 })); walls.position.y = 2.25; g.add(walls);
  const roof = new T.Mesh(new T.ConeGeometry(7.2, 3.2, 4), new T.MeshStandardMaterial({ color: 0xa4482f, roughness: 0.8, flatShading: true })); roof.rotation.y = Math.PI / 4; roof.position.y = 6.1; g.add(roof);
  const door = new T.Mesh(new T.BoxGeometry(1.6, 2.6, 0.2), new T.MeshStandardMaterial({ color: 0x6b3f22 })); door.position.set(0, 1.3, 4.05); g.add(door);
  for (const x of [-2.8, 2.8]) { const win = new T.Mesh(new T.BoxGeometry(1.4, 1.2, 0.1), new T.MeshStandardMaterial({ color: 0x9fd0ff, emissive: 0x332200 })); win.position.set(x, 2.6, 4.05); g.add(win); }
  g.traverse((o) => { (o as import("three").Mesh).castShadow = true; (o as import("three").Mesh).receiveShadow = true; });
  return g;
}
/** Interior de una casa: sala con sofá, mesa, cuadros, ventanas y un televisor con el noticiero del aviso. */
function buildInterior(T: Three, night: boolean, news: string) {
  const g = new T.Group();
  const W = 16, D = 12, H = 4.2;
  const room = new T.Mesh(new T.BoxGeometry(W, H, D), new T.MeshStandardMaterial({ color: 0xf3e9d8, side: T.BackSide, roughness: 0.9 })); room.position.y = H / 2; g.add(room);
  const floor = new T.Mesh(new T.PlaneGeometry(W, D), new T.MeshStandardMaterial({ color: 0x9a6a42, roughness: 0.7 })); floor.rotation.x = -Math.PI / 2; floor.position.y = 0.01; g.add(floor);
  const rug = new T.Mesh(new T.PlaneGeometry(5, 3.5), new T.MeshStandardMaterial({ color: 0xc8323f, roughness: 1 })); rug.rotation.x = -Math.PI / 2; rug.position.set(-2, 0.02, 1); g.add(rug);
  const sofaMat = new T.MeshStandardMaterial({ color: 0x2b6fd1, roughness: 0.9 });
  const seat = new T.Mesh(new T.BoxGeometry(4, 0.6, 1.4), sofaMat); seat.position.set(-2, 0.5, 3.8); g.add(seat);
  const back = new T.Mesh(new T.BoxGeometry(4, 1.1, 0.4), sofaMat); back.position.set(-2, 1.1, 4.5); g.add(back);
  const tvStand = new T.Mesh(new T.BoxGeometry(3, 0.8, 0.8), new T.MeshStandardMaterial({ color: 0x3b2a1e })); tvStand.position.set(-2, 0.4, -5.4); g.add(tvStand);
  const c = document.createElement("canvas"); c.width = 512; c.height = 288;
  const x = c.getContext("2d")!;
  const tvTexture = new T.CanvasTexture(c);
  tvTexture.colorSpace = T.SRGBColorSpace;
  // El noticiero se puede cambiar: en el Perú pasa las noticias de El Niño con su fuente.
  const setNews = (text: string, credit: string | null) => {
    x.fillStyle = "#0b2a5a"; x.fillRect(0, 0, 512, 288); x.fillStyle = "#e5262f"; x.fillRect(0, 222, 512, 66);
    x.fillStyle = "#fff"; x.font = "bold 28px sans-serif"; x.fillText("NOTICIAS · ÚLTIMA HORA", 24, 48); x.font = "21px sans-serif";
    text.match(/.{1,40}(\s|$)/g)?.slice(0, 5).forEach((line, i) => x.fillText(line.trim(), 24, 88 + i * 27));
    if (credit) { x.font = "italic 15px sans-serif"; x.fillStyle = "#cfe0ff"; x.fillText(`Fuente: ${credit}`.slice(0, 62), 24, 214); }
    x.fillStyle = "#fff"; x.font = "bold 24px sans-serif"; x.fillText("⚠ Prepara tu mochila de emergencia", 24, 264);
    tvTexture.needsUpdate = true;
  };
  setNews(news, null);
  const tv = new T.Mesh(new T.PlaneGeometry(3.4, 1.9), new T.MeshBasicMaterial({ map: tvTexture })); tv.position.set(-2, 2, -5.95); g.add(tv);
  const table = new T.Mesh(new T.BoxGeometry(3, 0.15, 1.8), new T.MeshStandardMaterial({ color: 0x8a5a3c })); table.position.set(4.5, 1, 0); g.add(table);
  for (const [cx, cz] of [[3.2, 1.3], [5.8, 1.3], [3.2, -1.3], [5.8, -1.3]]) { const chair = new T.Mesh(new T.BoxGeometry(0.7, 0.9, 0.7), new T.MeshStandardMaterial({ color: 0x6b3f22 })); chair.position.set(cx, 0.45, cz); g.add(chair); }
  const frameColors = [0xffb21a, 0x5ee08a, 0x2bb3e0];
  frameColors.forEach((col, i) => { const frame = new T.Mesh(new T.PlaneGeometry(1.2, 0.9), new T.MeshStandardMaterial({ color: col })); frame.position.set(-6 + i * 1.8, 2.6, 5.95); frame.rotation.y = Math.PI; g.add(frame); });
  for (const z of [-2.5, 2.5]) { const win = new T.Mesh(new T.PlaneGeometry(2.2, 1.6), new T.MeshBasicMaterial({ color: night ? 0x0b1430 : 0xbfe4ff })); win.position.set(7.95, 2.4, z); win.rotation.y = -Math.PI / 2; g.add(win); }
  const door = new T.Mesh(new T.PlaneGeometry(1.6, 2.6), new T.MeshStandardMaterial({ color: 0x6b3f22 })); door.position.set(-7.95, 1.3, 0); door.rotation.y = Math.PI / 2; g.add(door);
  const lamp = new T.PointLight(0xffe2b0, 40, 30); lamp.position.set(0, 3.8, 0); g.add(lamp);
  const lamp2 = new T.PointLight(0xffe2b0, 25, 20); lamp2.position.set(4.5, 3.5, 0); g.add(lamp2);
  return { group: g, exit: new T.Vector3(-6.8, 0, 0), half: { w: W / 2 - 0.6, d: D / 2 - 0.6 }, setNews };
}

/** Sala de la casa de la fiesta: guirnaldas, bola de espejos, luces que giran, parlantes y una mesa con torta. */
function buildPartyRoom(T: Three) {
  const g = new T.Group();
  const W = 18, D = 14, H = 4.6;
  const room = new T.Mesh(new T.BoxGeometry(W, H, D), new T.MeshStandardMaterial({ color: 0xf2dcb8, side: T.BackSide, roughness: 0.9 })); room.position.y = H / 2; g.add(room);
  const floor = new T.Mesh(new T.PlaneGeometry(W, D), new T.MeshStandardMaterial({ color: 0x7a4e30, roughness: 0.45, metalness: 0.05 })); floor.rotation.x = -Math.PI / 2; floor.position.y = 0.01; g.add(floor);
  // Pista de baile: baldosas de colores cálidos en el centro.
  const tileColors = [0xe5262f, 0xffb21a, 0x2bb3e0, 0x5ee08a];
  const tiles: THREE_NS.Mesh[] = [];
  for (let i = 0; i < 4; i += 1) for (let j = 0; j < 4; j += 1) {
    const tile = new T.Mesh(new T.PlaneGeometry(1.45, 1.45), new T.MeshStandardMaterial({ color: tileColors[(i + j) % 4], emissive: tileColors[(i + j) % 4], emissiveIntensity: 0.15, roughness: 0.4 }));
    tile.rotation.x = -Math.PI / 2; tile.position.set(-2.25 + i * 1.5, 0.02, -2.25 + j * 1.5); g.add(tile); tiles.push(tile);
  }
  const ball = new T.Mesh(new T.IcosahedronGeometry(0.55, 2), new T.MeshStandardMaterial({ color: 0xffffff, metalness: 1, roughness: 0.15, flatShading: true }));
  ball.position.set(0, H - 0.9, 0); g.add(ball);
  const string = new T.Mesh(new T.CylinderGeometry(0.02, 0.02, 0.4), new T.MeshBasicMaterial({ color: 0x333333 })); string.position.set(0, H - 0.2, 0); g.add(string);
  const spots = [0xffa040, 0xff5a5a, 0x40c8ff].map((color) => { const light = new T.PointLight(color, 30, 16); light.position.set(0, 3.2, 0); g.add(light); return light; });
  const warm = new T.PointLight(0xffe2b0, 18, 30); warm.position.set(5, 3.8, 3); g.add(warm);
  const bulbs: THREE_NS.Mesh[] = [];
  for (let side = 0; side < 2; side += 1) for (let i = 0; i < 18; i += 1) {
    const bulb = new T.Mesh(new T.SphereGeometry(0.1, 8, 6), new T.MeshBasicMaterial({ color: [0xff3d7f, 0xffd23a, 0x2bb3e0, 0x5ee08a][i % 4] }));
    bulb.position.set(-8.4 + i * (16.8 / 17), H - 0.5 - Math.sin((i / 17) * Math.PI) * 0.5, side ? 6.7 : -6.7); g.add(bulb); bulbs.push(bulb);
  }
  const c = document.createElement("canvas"); c.width = 512; c.height = 96;
  const x = c.getContext("2d")!; x.fillStyle = "#e5262f"; x.fillRect(0, 0, 512, 96); x.fillStyle = "#fff"; x.font = "bold 44px sans-serif"; x.textAlign = "center"; x.textBaseline = "middle"; x.fillText("¡Feliz cumpleaños, abuela! 🎂", 256, 50);
  const bannerTex = new T.CanvasTexture(c); bannerTex.colorSpace = T.SRGBColorSpace;
  const banner = new T.Mesh(new T.PlaneGeometry(7, 1.3), new T.MeshBasicMaterial({ map: bannerTex })); banner.position.set(0, 3.2, -6.95); g.add(banner);
  const table = new T.Mesh(new T.BoxGeometry(4, 0.15, 1.6), new T.MeshStandardMaterial({ color: 0x8a5a3c })); table.position.set(5.5, 1, 4.5); g.add(table);
  const cake = new T.Mesh(new T.CylinderGeometry(0.5, 0.5, 0.45, 20), new T.MeshStandardMaterial({ color: 0xf6d6e0 })); cake.position.set(5.5, 1.3, 4.5); g.add(cake);
  for (let i = 0; i < 5; i += 1) { const candle = new T.Mesh(new T.CylinderGeometry(0.03, 0.03, 0.22), new T.MeshBasicMaterial({ color: 0xffd23a })); candle.position.set(5.3 + i * 0.1, 1.64, 4.5); g.add(candle); }
  for (const sx of [-7.6, 7.6]) {
    const speaker = new T.Mesh(new T.BoxGeometry(1, 1.8, 0.9), new T.MeshStandardMaterial({ color: 0x1d1d1f, roughness: 0.5 })); speaker.position.set(sx, 0.9, -6); g.add(speaker);
    const cone = new T.Mesh(new T.CircleGeometry(0.32, 20), new T.MeshStandardMaterial({ color: 0x444448 })); cone.position.set(sx, 1.1, -5.54); g.add(cone);
  }
  const door = new T.Mesh(new T.PlaneGeometry(1.6, 2.6), new T.MeshStandardMaterial({ color: 0x6b3f22 })); door.position.set(-8.95, 1.3, 0); door.rotation.y = Math.PI / 2; g.add(door);
  return { group: g, exit: new T.Vector3(-7.8, 0, 0), half: { w: W / 2 - 0.6, d: D / 2 - 0.6 }, ball, spots, bulbs, tiles };
}

/** Centro de reciclaje: el refugio donde los contaminadores aprenden a hacer las cosas bien. */
function buildRefuge(T: Three) {
  const g = new T.Group();
  const base = new T.Mesh(new T.BoxGeometry(12, 4, 9), new T.MeshStandardMaterial({ color: 0xe9efe2, roughness: 0.8 })); base.position.y = 2; g.add(base);
  const roof = new T.Mesh(new T.ConeGeometry(8.6, 3.2, 4), new T.MeshStandardMaterial({ color: 0x2f8a4c, roughness: 0.7, flatShading: true }));
  roof.rotation.y = Math.PI / 4; roof.scale.set(1, 1, 0.75); roof.position.y = 5.6; g.add(roof);
  const c = document.createElement("canvas"); c.width = 512; c.height = 128;
  const x = c.getContext("2d")!; x.fillStyle = "#2f8a4c"; x.fillRect(0, 0, 512, 128); x.fillStyle = "#fff"; x.font = "bold 54px sans-serif"; x.textAlign = "center"; x.textBaseline = "middle"; x.fillText("♻ Centro de reciclaje", 256, 66);
  const sign = new T.Mesh(new T.PlaneGeometry(9, 2.2), new T.MeshBasicMaterial({ map: new T.CanvasTexture(c) })); sign.position.set(0, 3, 4.55); g.add(sign);
  g.traverse((o) => { (o as import("three").Mesh).castShadow = true; (o as import("three").Mesh).receiveShadow = true; });
  return g;
}

// Eventos extremos del juego: simulados, inspirados en los riesgos reales del lugar. Las lecciones son recomendaciones
// habituales de defensa civil, no datos de la plataforma.
type EventKind = "huaico" | "avalancha" | "inundacion" | "erupcion" | "calor";
const EVENT_DETECT: Record<EventKind, string> = {
  huaico: "Lluvia intensa de GPM IMERG (NASA), laderas empinadas del relieve Copernicus y la susceptibilidad a deslizamientos de NASA.",
  avalancha: "Nieve y hielo de ESA WorldCover y MODIS (NASA) en laderas empinadas del relieve Copernicus.",
  inundacion: "Lluvia de GPM IMERG (NASA), caudal de ríos GloFAS (Copernicus) y zonas bajas del relieve.",
  erupcion: "Focos de calor de VIIRS y MODIS (NASA) y alertas en vivo de GDACS cruzadas con NASA EONET.",
  calor: "Temperatura de la superficie de MODIS (capa «Suelo caliente») y la tendencia de NASA POWER.",
};
const EVENT_INFO: Record<EventKind, { title: string; icon: string; order: string; lesson: string[] }> = {
  huaico: { title: "AVISO DE HUAICO", icon: "🟤", order: "Se esperan lluvias fuertes en la sierra: puede bajar un huaico por la quebrada. Lleva a la gente a la zona alta segura.",
    lesson: ["Aléjate de quebradas, cauces y riberas cuando llueve fuerte.", "Sube a zonas altas y firmes; nunca cruces un huaico.", "Ten lista una mochila de emergencia y una ruta de evacuación."] },
  avalancha: { title: "AVISO DE AVALANCHA", icon: "❄️", order: "Riesgo alto de avalancha en la ladera. Lleva a la gente hacia un costado, a la zona segura.",
    lesson: ["Muévete hacia un costado de la avalancha, nunca cuesta abajo.", "Si te alcanza, agárrate a una roca o árbol y protege tu cara para respirar.", "Antes de ir a la montaña, revisa el aviso de riesgo de avalanchas."] },
  inundacion: { title: "AVISO DE INUNDACIÓN", icon: "🌊", order: "El río está creciendo y el agua puede entrar a las calles. Lleva a la gente a la zona alta segura.",
    lesson: ["Sube a un lugar alto y espera allí.", "No camines ni manejes por agua en movimiento: 30 cm pueden arrastrar un auto.", "Desconecta la electricidad si el agua entra a tu casa."] },
  erupcion: { title: "AVISO DE ERUPCIÓN", icon: "🌋", order: "El volcán aumentó su actividad: puede caer ceniza y roca. Evacúa a la gente hacia la zona segura.",
    lesson: ["Sigue las rutas de evacuación y las indicaciones de las autoridades.", "Cubre nariz y boca con una mascarilla o tela húmeda por la ceniza.", "Protege tu cabeza y aléjate de los valles por donde bajan los flujos."] },
  calor: { title: "AVISO DE OLA DE CALOR", icon: "🔥", order: "Se espera calor extremo en las próximas horas. Lleva a la gente al punto de sombra e hidratación.",
    lesson: ["Busca sombra y toma agua aunque no tengas sed.", "Evita el sol fuerte del mediodía y la actividad intensa.", "Cuida a niños, personas mayores y mascotas: se afectan más rápido."] },
};

/** Perrito: cuerpo, cabeza con hocico, orejas, cuatro patas que se mueven y una cola que se mueve. */
function buildDog(T: Three) {
  const g = new T.Group();
  const fur = new T.MeshStandardMaterial({ color: 0xe0b07a, roughness: 0.95 });
  const light = new T.MeshStandardMaterial({ color: 0xfff4e6, roughness: 0.95 });
  const dark = new T.MeshStandardMaterial({ color: 0x2a1d14, roughness: 0.6 });
  const pink = new T.MeshStandardMaterial({ color: 0xff8fa3, roughness: 0.7 });
  // Cachorro: cuerpo corto y redondo, cabeza grande, orejas caídas, patitas cortas.
  const body = new T.Mesh(new T.CapsuleGeometry(0.26, 0.32, 6, 12), fur); body.rotation.x = Math.PI / 2; body.position.y = 0.42; g.add(body);
  const belly = new T.Mesh(new T.SphereGeometry(0.22, 12, 10), light); belly.position.set(0, 0.36, 0.12); g.add(belly);
  const head = new T.Group(); head.position.set(0, 0.78, 0.3); head.name = "head"; g.add(head);
  head.add(new T.Mesh(new T.SphereGeometry(0.3, 16, 14), fur));
  const muzzle = new T.Mesh(new T.SphereGeometry(0.14, 12, 10), light); muzzle.scale.set(1.2, 0.85, 1); muzzle.position.set(0, -0.08, 0.24); head.add(muzzle);
  const nose = new T.Mesh(new T.SphereGeometry(0.05, 10, 8), dark); nose.position.set(0, -0.02, 0.38); head.add(nose);
  const tongue = new T.Mesh(new T.BoxGeometry(0.07, 0.02, 0.08), pink); tongue.position.set(0, -0.17, 0.33); head.add(tongue);
  for (const x of [-0.11, 0.11]) {
    const eye = new T.Mesh(new T.SphereGeometry(0.055, 10, 8), dark); eye.position.set(x, 0.06, 0.25); head.add(eye);
    const shine = new T.Mesh(new T.SphereGeometry(0.018, 6, 6), new T.MeshBasicMaterial({ color: 0xffffff })); shine.position.set(x + 0.02, 0.08, 0.3); head.add(shine);
    const ear = new T.Mesh(new T.CapsuleGeometry(0.07, 0.16, 4, 8), new T.MeshStandardMaterial({ color: 0xa8743f, roughness: 0.95 }));
    ear.position.set(x * 2.4, 0.02, -0.02); ear.rotation.z = x > 0 ? 0.35 : -0.35; head.add(ear);
  }
  for (const [x, z, name] of [[-0.13, 0.18, "legA"], [0.13, 0.18, "legB"], [-0.13, -0.18, "legB"], [0.13, -0.18, "legA"]] as const) {
    const pivot = new T.Group(); pivot.position.set(x, 0.3, z); pivot.name = name;
    const leg = new T.Mesh(new T.CapsuleGeometry(0.06, 0.14, 4, 8), fur); leg.position.y = -0.16; pivot.add(leg); g.add(pivot);
  }
  const tail = new T.Group(); tail.position.set(0, 0.55, -0.3); tail.name = "tail";
  const tailMesh = new T.Mesh(new T.CapsuleGeometry(0.04, 0.18, 4, 6), fur); tailMesh.position.y = 0.12; tail.add(tailMesh); tail.rotation.x = -0.9; g.add(tail);
  g.traverse((o) => { (o as import("three").Mesh).castShadow = true; });
  g.scale.setScalar(0.85);
  return g;
}

/** Sonidos de perro sintetizados: ladrido corto o aullido/gemido. */
function dogSound(kind: "ladrido" | "gemido") {
  if (muted || typeof window === "undefined") return;
  try {
    audioCtx = audioCtx ?? new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const ctx = audioCtx, now = ctx.currentTime;
    const voice = (start: number, f0: number, f1: number, dur: number, vol: number, type: OscillatorType) => {
      const osc = ctx.createOscillator(), filter = ctx.createBiquadFilter(), gain = ctx.createGain();
      osc.type = type; osc.frequency.setValueAtTime(f0, now + start); osc.frequency.exponentialRampToValueAtTime(f1, now + start + dur);
      filter.type = "bandpass"; filter.frequency.value = kind === "ladrido" ? 900 : 1400; filter.Q.value = kind === "ladrido" ? 1.2 : 4;
      gain.gain.setValueAtTime(0.0001, now + start); gain.gain.exponentialRampToValueAtTime(vol, now + start + 0.02); gain.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
      osc.connect(filter).connect(gain).connect(ctx.destination); osc.start(now + start); osc.stop(now + start + dur + 0.05);
    };
    if (kind === "ladrido") { voice(0, 520, 240, 0.13, 0.5, "sawtooth"); voice(0.2, 560, 250, 0.12, 0.45, "sawtooth"); }
    else { voice(0, 700, 1100, 0.35, 0.18, "sine"); voice(0.35, 1100, 650, 0.6, 0.15, "sine"); }
  } catch { /* sin audio */ }
}

// Voces con la síntesis de voz del navegador (sin archivos) y una sirena con WebAudio. Se pueden silenciar.
let muted = false;
// La mejor voz en español instalada: primero las «mejoradas/premium», luego las conocidas de macOS y Google.
function pickVoice(kind: "heroe" | "heroina" | "pueblo") {
  const voices = typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("es")) : [];
  const score = (v: SpeechSynthesisVoice) => {
    const n = v.name.toLowerCase();
    let points = /premium|enhanced|mejorad|neural|natural/.test(n) ? 50 : 0;
    if (/google/.test(n)) points += 25;
    const male = /eddy|reed|rocko|jorge|juan|diego|carlos|pablo|enrique|álvaro|alvaro/.test(n), female = /paulina|mónica|monica|flo|sandy|shelley|marisol|lucía|lucia|paloma|helena|laura/.test(n);
    if (/grandma|grandpa|bad news|bells|bubbles|jester|organ|whisper|zarvox|trinoids|cellos|wobble|boing|albert|bahh/.test(n)) points -= 100;
    if (kind === "heroe" && male) points += 30;
    if ((kind === "heroina" || kind === "pueblo") && female) points += 30;
    if (v.lang.toLowerCase().includes("mx") || v.lang.toLowerCase().includes("419")) points += 5;
    return points;
  };
  return voices.sort((a, b) => score(b) - score(a))[0] ?? null;
}
let heroKind: "heroe" | "heroina" = "heroe";
// Música: pistas de Kevin MacLeod (incompetech.com, CC BY 4.0) en /audio/musica/<clave>.m4a. Suena una a la vez:
// «fiesta» junto a la fiesta o dentro de la casa de la fiesta y «tension» durante un aviso. Al explorar, sin música.
type TrackKey = "fiesta" | "tension";
const TRACK_VOLUME: Record<TrackKey, number> = { fiesta: 0.5, tension: 0.42 };
const musicMissing = new Set<string>();
let track: { key: TrackKey; audio: HTMLAudioElement } | null = null;
function setTrack(key: TrackKey | null) {
  if ((track?.key ?? null) === key) return;
  track?.audio.pause();
  track = null;
  if (!key || typeof window === "undefined" || musicMissing.has(key)) return;
  const audio = new Audio(`/audio/musica/${key}.m4a`);
  audio.loop = true;
  audio.volume = TRACK_VOLUME[key];
  audio.addEventListener("error", () => musicMissing.add(key), { once: true });
  track = { key, audio };
  if (!muted) void audio.play().catch(() => {});
}
function applyMute() {
  if (!track) return;
  if (muted) track.audio.pause(); else void track.audio.play().catch(() => {});
}
// Voces grabadas: si existe /audio/voces/<clave>.mp3 se reproduce (por ejemplo, grabadas por el equipo).
// Solo se piden las que figuran en /audio/voces/voces.json: antes se pedía cada .mp3 a ciegas y, como no hay ninguno,
// la consola se llenaba de errores 404. El manifiesto se lee una sola vez por sesión.
let voiceFiles: Set<string> | null = null; // null: el manifiesto aún no llegó y no se pide ninguna voz
let voiceManifest: Promise<Set<string>> | null = null;
function loadVoiceManifest(): Promise<Set<string>> {
  voiceManifest = voiceManifest ?? fetch("/audio/voces/voces.json")
    .then((response) => (response.ok ? response.json() : []))
    .then((list: unknown) => new Set(Array.isArray(list) ? list.filter((name): name is string => typeof name === "string") : []))
    .catch(() => new Set<string>())
    .then((files) => (voiceFiles = files));
  return voiceManifest;
}
let clipsOn = true; // el botón «Voces» en «no» también calla las voces grabadas
const voiceCache = new Map<string, HTMLAudioElement | null>();
function voiceClip(key: string) {
  if (muted || !clipsOn || typeof window === "undefined" || !voiceFiles?.has(`${key}.mp3`)) return;
  const cached = voiceCache.get(key);
  if (cached === null) return;
  const audio = cached ?? new Audio(`/audio/voces/${key}.mp3`);
  if (!cached) { audio.addEventListener("error", () => voiceCache.set(key, null), { once: true }); voiceCache.set(key, audio); }
  audio.currentTime = 0; audio.volume = 1;
  void audio.play().catch(() => voiceCache.set(key, null));
}
let voicesOn = false; // las voces del navegador suenan robóticas: apagadas salvo que el jugador las active
function speak(text: string, opts: { pitch?: number; rate?: number; who?: "heroe" | "pueblo" } = {}) {
  if (muted || !voicesOn || typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const utter = new SpeechSynthesisUtterance(text);
  utter.voice = pickVoice(opts.who === "heroe" ? heroKind : "pueblo");
  utter.lang = utter.voice?.lang ?? "es-ES";
  utter.volume = 1;
  utter.pitch = opts.pitch ?? 1;
  utter.rate = opts.rate ?? 1.08;
  window.speechSynthesis.speak(utter);
}
// Efectos de videojuego sintetizados con WebAudio (sin archivos).
let audioCtx: AudioContext | null = null;
function sfx(kind: "boom" | "whoosh" | "powerup" | "fanfare") {
  if (muted || typeof window === "undefined") return;
  try {
    audioCtx = audioCtx ?? new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const ctx = audioCtx, now = ctx.currentTime;
    const tone = (freq: number, start: number, dur: number, type: OscillatorType, vol: number, to?: number) => {
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.type = type; osc.frequency.setValueAtTime(freq, now + start);
      if (to) osc.frequency.exponentialRampToValueAtTime(to, now + start + dur);
      gain.gain.setValueAtTime(vol, now + start); gain.gain.exponentialRampToValueAtTime(0.001, now + start + dur);
      osc.connect(gain).connect(ctx.destination); osc.start(now + start); osc.stop(now + start + dur);
    };
    if (kind === "boom") { tone(120, 0, 1.2, "sine", 0.6, 30); tone(60, 0, 1.5, "triangle", 0.5, 25); }
    if (kind === "whoosh") { tone(300, 0, 0.35, "sawtooth", 0.08, 1400); }
    if (kind === "powerup") { [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.07, 0.18, "square", 0.06)); }
    if (kind === "fanfare") { [392, 523, 659, 784].forEach((f, i) => tone(f, i * 0.12, i === 3 ? 0.6 : 0.2, "triangle", 0.12)); }
  } catch { /* sin audio */ }
}

/** Placas que ocupan sitio sobre el lienzo: los globos de diálogo y los carteles de los vecinos no se dibujan encima. */
const ZONES = ".gamePanel, .gameBrand, .gameHeroTag, .gameWorld :is(.gameScanner, .gameVitals, .gameObjective, .gameAlertCard, .gamePickup, .gameHelp, .gameVehicle, .gameHint, .gameBag, .gameSound, .gameWorldCredit, .gameNinoTicker, .gameCineTitle, .gameWelcome, .gameSpeech, .gameJump, .gameLesson, .gameNino, .gameCredits)";

/** Las teclas del juego solo se ignoran mientras la persona escribe en un campo de texto. */
function typing(event: KeyboardEvent) {
  const el = event.target as HTMLElement | null;
  return !!el?.closest?.("input, textarea, select") || !!el?.isContentEditable;
}

/** Ruido determinista barato para variar colores y repartir árboles sin que cambien en cada visita. */
function hash(x: number, y: number) {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return s - Math.floor(s);
}

export function MissionWorld({ mission, hero, checkpoints, visited, panelRight, panelBottom, onReach, onUnavailable, onLeave }: {
  mission: Mission;
  hero: Hero | null;
  checkpoints: Checkpoint[];
  visited: Set<string>;
  panelRight: number;
  panelBottom: number;
  onReach: (id: string) => void;
  onUnavailable: () => void;
  /** El héroe subió a su nave y despegó: volver al globo. */
  onLeave: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState<"cargando" | "listo">("cargando");
  const [phase, setPhase] = useState<"aterriza" | "suelo">("aterriza");
  const [labels, setLabels] = useState<{ id: string; x: number; y: number; visible: boolean }[]>([]);
  const [heroScreen, setHeroScreen] = useState<{ x: number; y: number } | null>(null);
  const [speech, setSpeech] = useState<Checkpoint | null>(null);
  const [scan, setScan] = useState<{ altitude: number; cover: string } | null>(null);
  const [prompt, setPrompt] = useState<Checkpoint | null>(null);
  const [savedCount, setSavedCount] = useState(0);
  const fireRef = useRef<() => void>(() => {});
  const timeRef = useRef<{ hour: number; night: boolean; dawn: boolean; fixed: boolean }>({ hour: 12, night: false, dawn: false, fixed: false });
  const weatherRef = useRef<string>("despejado");
  const [stoppedCount, setStoppedCount] = useState(0);
  const [trainedCount, setTrainedCount] = useState(0);
  const [welcome, setWelcome] = useState(false);
  const [objective, setObjective] = useState<{ text: string; meters: number; angle: number } | null>(null);
  const [vehicleHint, setVehicleHint] = useState<string | null>(null);
  const toggleRef = useRef<() => void>(() => {});
  const startEventRef = useRef<() => void>(() => {});
  const [alert, setAlert] = useState<{ kind: EventKind; left: number; nino: boolean; rescued: number; total: number } | null>(null);
  // La tarjeta del aviso se ve completa unos segundos y luego queda como una franja arriba, para no tapar el mundo.
  const [alertCompact, setAlertCompact] = useState(false);
  const alertActive = alert !== null;
  useEffect(() => { if (!alertActive) { setAlertCompact(false); return; } const t = window.setTimeout(() => setAlertCompact(true), 6000); return () => window.clearTimeout(t); }, [alertActive]);
  const [lesson, setLesson] = useState<{ kind: EventKind; saved: boolean; rescued?: number; total?: number; seconds?: number } | null>(null);
  const [soundOn, setSoundOn] = useState(true);
  const [insideHouse, setInsideHouse] = useState(false);
  const [kitDone, setKitDone] = useState(false);
  // Botón «Voces»: null = la persona aún no lo tocó; entonces dice «sí» solo si hay voces grabadas en el manifiesto.
  const [voices, setVoices] = useState<boolean | null>(null);
  const [recorded, setRecorded] = useState(0);
  useEffect(() => { let alive = true; void loadVoiceManifest().then((files) => { if (alive) setRecorded(files.size); }); return () => { alive = false; }; }, []);
  const voicesShown = voices ?? recorded > 0;
  // La voz sintetizada del navegador reemplaza a las grabadas: solo habla si la persona activa las voces y no hay
  // ninguna grabada (si no, sonarían las dos a la vez).
  useEffect(() => { voicesOn = voices === true && recorded === 0; clipsOn = voices !== false; }, [voices, recorded]);
  useEffect(() => { muted = !soundOn; applyMute(); if (!soundOn && typeof window !== "undefined") window.speechSynthesis?.cancel(); }, [soundOn]);
  // Mochila: objetos recogidos y el que va en la mano (teclas 1–6; la misma tecla o G lo guarda).
  const [bag, setBag] = useState<{ counts: Partial<Record<ItemId, number>>; equipped: ItemId | null }>({ counts: {}, equipped: null });
  const equipRef = useRef<(id: ItemId | null) => void>(() => {});
  const [ninoOpen, setNinoOpen] = useState(false);
  const [ninoIndex, setNinoIndex] = useState(0);
  const isNino = mission.country === NINO_COUNTRY;
  useEffect(() => { if (!isNino) return; const t = window.setInterval(() => setNinoIndex((i) => (i + 1) % NINO_FACTS.length), 9000); return () => window.clearInterval(t); }, [isNino]);
  const [speakers, setSpeakers] = useState<{ key: string; x: number; y: number; text: string; tone: string }[]>([]);
  useEffect(() => { if (!welcome) return; const t = window.setTimeout(() => setWelcome(false), 3800); return () => window.clearTimeout(t); }, [welcome]);
  const [hud, setHud] = useState<{ health: number; protectedFor: number }>({ health: 100, protectedFor: 0 });
  const [pickupNote, setPickupNote] = useState<string | null>(null);
  // Los mensajes largos (como las noticias de la radio) quedan más tiempo en pantalla.
  useEffect(() => { if (!pickupNote) return; const t = window.setTimeout(() => setPickupNote(null), Math.max(3500, pickupNote.length * 55)); return () => window.clearTimeout(t); }, [pickupNote]);
  const propsRef = useRef({ panelRight, panelBottom, checkpoints, onReach, onUnavailable, onLeave });
  useEffect(() => { propsRef.current = { panelRight, panelBottom, checkpoints, onReach, onUnavailable, onLeave }; }, [panelRight, panelBottom, checkpoints, onReach, onUnavailable, onLeave]);
  const leftRef = useRef(false);
  // Ayuda de teclas: sale sola al aterrizar («auto») y se oculta a los pocos segundos; el botón «Teclas» la vuelve a
  // mostrar («si») y entonces queda hasta que la persona la cierra («no»). Antes tapaba siempre el nombre del lugar.
  const [hintOpen, setHintOpen] = useState<"auto" | "si" | "no">("auto");
  useEffect(() => {
    if (phase !== "suelo" || welcome || hintOpen !== "auto") return;
    const t = window.setTimeout(() => setHintOpen((v) => (v === "auto" ? "no" : v)), 12000);
    return () => window.clearTimeout(t);
  }, [phase, welcome, hintOpen]);
  // Créditos completos (licencias) en una hoja chica que se abre desde el pie, en cualquier tamaño de pantalla.
  const [creditsOpen, setCreditsOpen] = useState(false);
  // En pantallas angostas el escáner queda plegado en un botón para no tapar el mundo; en las grandes siempre está abierto.
  const [scanOpen, setScanOpen] = useState(false);
  // Las tarjetas que piden cerrar o elegir reciben el foco al abrirse: el lector de pantalla las anuncia y Tab cae
  // en su botón. Al cerrarlas, el foco vuelve al lienzo para seguir jugando (el botón que lo tenía desaparece).
  const focusOnOpen = useCallback((el: HTMLElement | null) => { el?.focus({ preventScroll: true }); }, []);
  const backToCanvas = () => canvasRef.current?.focus({ preventScroll: true });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let disposed = false;
    let cleanup = () => {};
    const run = async () => {
      heroKind = hero?.gender === "mujer" ? "heroina" : "heroe";
      // Los dos modelos de personaje empiezan a bajar ya, a la vez que three y el terreno: antes se pedían recién al
      // crear el primer vecino, con el terreno ya construido.
      const rigImport = import("./hero-rig");
      void rigImport.then((module) => module.preloadHeroModels()).catch(() => undefined);
      const [T, { Sky }, rigModule, shipModule, response] = await Promise.all([
        import("three"), import("three/addons/objects/Sky.js"), rigImport, import("./hero-3d"),
        fetch(`/api/missions/${mission.id}/terrain`),
      ]);
      // Todos los personajes del mundo van con descarte por cámara (ver `fitBounds` en hero-rig.ts).
      const loadRig = (gender: Gender) => rigModule.loadHeroRig(T, gender, true);
      if (!response.ok) throw new Error("sin terreno");
      const terrain = (await response.json()) as Terrain;
      if (disposed) return;
      let renderer: THREE_NS.WebGLRenderer;
      try { renderer = new T.WebGLRenderer({ canvas, antialias: true }); } catch { throw new Error("sin WebGL"); }
      // Desde aquí toda salida deja limpio: si la persona vuelve al globo mientras bajan los modelos, `run` termina en
      // una salida temprana (`if (disposed) return`) sin llegar a la limpieza completa del final, y el renderer quedaba
      // vivo. Cada misión abre un contexto WebGL nuevo y el navegador admite pocos: también se suelta el contexto.
      cleanup = () => { renderer.dispose(); renderer.forceContextLoss(); };
      // Tope de 1,5: en pantallas de alta densidad, 2 dibuja casi el doble de píxeles que 1,5 y apenas se nota.
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      renderer.outputColorSpace = T.SRGBColorSpace;
      renderer.toneMapping = T.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 0.8;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = T.PCFSoftShadowMap;

      const scene = new T.Scene();
      const camera = new T.PerspectiveCamera(55, 1, 0.5, 30000);

      // --- Terreno -------------------------------------------------------------------------------------------
      const n = terrain.grid;
      const size = terrain.size_km * 1000;
      // Ciudades entre cerros (como Chosica, en el valle del Rímac): más relieve y menos suavizado para que se vean las quebradas.
      const mountainCity = mission.scale !== "paisaje" && terrain.max_elevation_m - terrain.base_elevation_m > 300;
      const exaggeration = mission.scale === "paisaje" ? 1.4 : mountainCity ? 1.3 : 1.15;
      const relief = decode(terrain.relief_dm, "u16") as Uint16Array;
      const cover = decode(terrain.cover, "u8") as Uint8Array;
      const heights = new Float32Array(n * n);
      for (let i = 0; i < n * n; i += 1) heights[i] = (relief[i] / 10) * exaggeration;
      // Copernicus GLO-30 mide la superficie con edificios y copas: en ciudad se suaviza para quedarse con el suelo.
      const smooth = (passes: number, radius: number) => {
        const tmp = new Float32Array(n * n);
        for (let p = 0; p < passes; p += 1) {
          for (let r = 0; r < n; r += 1) for (let c = 0; c < n; c += 1) {
            let sum = 0, count = 0;
            for (let dr = -radius; dr <= radius; dr += 1) for (let dc = -radius; dc <= radius; dc += 1) {
              const rr = r + dr, cc = c + dc;
              if (rr >= 0 && rr < n && cc >= 0 && cc < n) { sum += heights[rr * n + cc]; count += 1; }
            }
            tmp[r * n + c] = cover[r * n + c] === 80 ? heights[r * n + c] : sum / count;
          }
          heights.set(tmp);
        }
      };
      smooth(mission.scale === "paisaje" ? 1 : mountainCity ? 2 : 3, mission.scale === "paisaje" || mountainCity ? 1 : 2);
      // Bioma del lugar para la vegetación: trópico (palmeras y playas), frío (coníferas), desierto de América (cactus) o templado.
      const meanTemp = mission.temperature?.mean ?? 15;
      const arid = (mission.rain?.mean ?? 2) < 1 && mission.longitude < -30;
      // En desiertos cálidos de América también van palmeras (como en Phoenix), no árboles de hoja ancha.
      const biome: "tropical" | "boreal" | "templado" = (meanTemp >= 22 && Math.abs(mission.latitude) < 30) || (arid && meanTemp >= 18) ? "tropical" : meanTemp < 6 || Math.abs(mission.latitude) > 55 ? "boreal" : "templado";
      // Playas: tierra baja junto al agua (a ≤ 2 celdas y ≤ 4 m sobre ella).
      const beach = new Uint8Array(n * n);
      for (let r = 0; r < n; r += 1) for (let c = 0; c < n; c += 1) {
        const i = r * n + c;
        if (cover[i] === 80 || cover[i] === 50 || cover[i] === 70) continue;
        let water = -1;
        for (let dr = -2; dr <= 2 && water < 0; dr += 1) for (let dc = -2; dc <= 2; dc += 1) {
          const rr = r + dr, cc = c + dc;
          if (rr >= 0 && rr < n && cc >= 0 && cc < n && cover[rr * n + cc] === 80) { water = heights[rr * n + cc]; break; }
        }
        if (water >= 0 && heights[i] - water < 4) beach[i] = 1;
      }
      const geometry = new T.PlaneGeometry(size, size, n - 1, n - 1);
      geometry.rotateX(-Math.PI / 2); // x hacia el este, z hacia el sur, y hacia arriba
      const position = geometry.attributes.position as THREE_NS.BufferAttribute;
      const colors = new Float32Array(n * n * 3);
      const color = new T.Color();
      const rock = new T.Color(ROCK);
      const cell = size / (n - 1);
      for (let row = 0; row < n; row += 1) {
        for (let col = 0; col < n; col += 1) {
          const i = row * n + col;
          position.setY(i, heights[i]);
          const left = heights[row * n + Math.max(col - 1, 0)], right = heights[row * n + Math.min(col + 1, n - 1)];
          const up = heights[Math.max(row - 1, 0) * n + col], down = heights[Math.min(row + 1, n - 1) * n + col];
          const slope = Math.atan(Math.hypot(right - left, down - up) / (2 * cell)) * (180 / Math.PI);
          // Zonas urbanas: mosaico de techos (teja, cemento, arena) en vez de un gris parejo.
          const urban = [0x9b958c, 0xa9806a, 0x8b8e93, 0xb8ab95, 0x7f7a74];
          const street = cover[i] === 50 && (row % STREET_EVERY === 0 || col % STREET_EVERY === 0);
          if (beach[i]) { color.setHex(0xeadbb0); const j = 0.92 + hash(col, row) * 0.12; colors.set([color.r * j, color.g * j, color.b * j], i * 3); position.setY(i, heights[i]); continue; }
          color.setHex(street ? 0x4f4c49 : cover[i] === 50 ? urban[Math.floor(hash(Math.floor(col / 2), Math.floor(row / 2)) * urban.length)] : COVER_COLOR[cover[i]] ?? COVER_COLOR[0]);
          if (cover[i] !== 80 && cover[i] !== 70 && slope > 28) color.lerp(rock, Math.min((slope - 28) / 20, 0.85));
          const jitter = 0.9 + hash(col, row) * 0.2;
          colors.set([color.r * jitter, color.g * jitter, color.b * jitter], i * 3);
        }
      }
      geometry.setAttribute("color", new T.BufferAttribute(colors, 3));
      geometry.computeVertexNormals();
      // Grano fino del suelo para que de cerca no se vea liso (se multiplica por el color de la cobertura).
      const grainCanvas = document.createElement("canvas");
      grainCanvas.width = grainCanvas.height = 256;
      const g = grainCanvas.getContext("2d")!;
      const img = g.createImageData(256, 256);
      for (let i = 0; i < 256 * 256; i += 1) {
        const v = 205 + Math.floor((hash(i % 256, Math.floor(i / 256)) * 0.6 + hash(Math.floor((i % 256) / 8), Math.floor(i / 2048)) * 0.4) * 50);
        img.data.set([v, v, v, 255], i * 4);
      }
      g.putImageData(img, 0, 0);
      const grain = new T.CanvasTexture(grainCanvas);
      grain.wrapS = grain.wrapT = T.RepeatWrapping;
      grain.repeat.set(size / 9, size / 9);
      grain.colorSpace = T.SRGBColorSpace;
      grain.anisotropy = renderer.capabilities.getMaxAnisotropy();
      const ground = new T.Mesh(geometry, new T.MeshStandardMaterial({ vertexColors: true, map: grain, roughness: 0.95, metalness: 0 }));
      ground.receiveShadow = true;
      scene.add(ground);
      const heightAt = (x: number, z: number) => {
        const fx = Math.min(Math.max((x / size + 0.5) * (n - 1), 0), n - 1.001);
        const fz = Math.min(Math.max((z / size + 0.5) * (n - 1), 0), n - 1.001);
        const c0 = Math.floor(fx), r0 = Math.floor(fz), tx = fx - c0, tz = fz - r0;
        const h = (r: number, c: number) => heights[r * n + c];
        return (h(r0, c0) * (1 - tx) + h(r0, c0 + 1) * tx) * (1 - tz) + (h(r0 + 1, c0) * (1 - tx) + h(r0 + 1, c0 + 1) * tx) * tz;
      };
      const coverAt = (x: number, z: number) => {
        const c = Math.round((x / size + 0.5) * (n - 1)), r = Math.round((z / size + 0.5) * (n - 1));
        return cover[Math.min(Math.max(r, 0), n - 1) * n + Math.min(Math.max(c, 0), n - 1)];
      };

      // Tierra firme más cercana a un punto (para no aparecer dentro del mar o de un lago). Si casi todo es agua, se camina sobre ella.
      let waterCells = 0;
      for (let i = 0; i < n * n; i += 1) if (cover[i] === 80) waterCells += 1;
      const walkOnWater = waterCells / (n * n) > 0.9;
      const blockedRef = { current: (_x: number, _z: number) => false };
      const nearestLand = (x: number, z: number): [number, number] => {
        const free = (px: number, pz: number) => (walkOnWater || coverAt(px, pz) !== 80) && !blockedRef.current(px, pz);
        if (free(x, z)) return [x, z];
        for (let r = cell; r < size * 0.45; r += cell) {
          for (let a = 0; a < 16; a += 1) {
            const px = x + Math.cos((a / 16) * Math.PI * 2) * r, pz = z + Math.sin((a / 16) * Math.PI * 2) * r;
            if (Math.abs(px) < size * 0.45 && Math.abs(pz) < size * 0.45 && free(px, pz)) return [px, pz];
          }
        }
        return [x, z];
      };

      // --- Cielo, sol, niebla y reflejos ------------------------------------------------------------------------
      const sky = new Sky();
      sky.scale.setScalar(40000);
      // Sol alto desde el sur, detrás de la cámara inicial: ilumina al héroe y al terreno que tiene delante.
      const sunDir = new T.Vector3().setFromSphericalCoords(1, T.MathUtils.degToRad(48), T.MathUtils.degToRad(25));
      const uniforms = sky.material.uniforms;
      uniforms.turbidity.value = 6; uniforms.rayleigh.value = 1.6; uniforms.mieCoefficient.value = 0.004; uniforms.mieDirectionalG.value = 0.85;
      uniforms.sunPosition.value.copy(sunDir);
      // El cielo se dibuja al final de lo opaco: así su sombreador (caro) solo corre en los píxeles que el terreno,
      // las casas y los personajes dejaron libres, y no en toda la pantalla.
      sky.renderOrder = 10;
      scene.add(sky);
      const pmrem = new T.PMREMGenerator(renderer);
      const skyScene = new T.Scene();
      skyScene.add(sky.clone());
      const envMap = pmrem.fromScene(skyScene).texture;
      // El reflejo del cielo solo va en el agua: sobre el suelo lo deja blanco y lavado.
      scene.fog = new T.Fog(0xb7c8d8, size * 0.45, size * 2.2);
      const sun = new T.DirectionalLight(0xfff1dc, 2.6);
      sun.position.copy(sunDir).multiplyScalar(3000);
      sun.castShadow = true;
      sun.shadow.mapSize.set(2048, 2048);
      const shadowCam = sun.shadow.camera as THREE_NS.OrthographicCamera;
      shadowCam.left = -160; shadowCam.right = 160; shadowCam.top = 160; shadowCam.bottom = -160; shadowCam.near = 10; shadowCam.far = 8000;
      sun.shadow.bias = -0.0005;
      scene.add(sun, sun.target);
      scene.add(new T.HemisphereLight(0xdbe8ff, 0x6b5a45, 0.75));
      scene.add(new T.AmbientLight(0xffffff, 0.25));

      // Hora local real del lugar (hora solar por longitud): noche, amanecer, día o atardecer.
      // Para una demo o una grabación la luz se puede fijar desde la dirección de la página, sin tocar el reloj:
      //   /jugar?luz=dia     siempre de día        /jugar?luz=noche   siempre de noche (la escena más pesada)
      //   /jugar?luz=real    la hora real del lugar (lo mismo que no poner nada)
      // Con la luz fijada, la placa de salud dice «Luz de día (fijada)» o «Luz de noche (fijada)» en vez de la hora
      // local, para no mostrar una hora que contradiga lo que se ve.
      const luz = new URLSearchParams(window.location.search).get("luz");
      const fixedLight = luz === "dia" || luz === "noche" ? luz : null;
      const now = new Date();
      const localHour = (now.getUTCHours() + now.getUTCMinutes() / 60 + mission.longitude / 15 + 48) % 24;
      const night = fixedLight ? fixedLight === "noche" : localHour < 5.5 || localHour >= 19;
      const dawn = !fixedLight && !night && (localHour < 7.5 || localHour >= 17.5);
      timeRef.current = { hour: localHour, night, dawn, fixed: fixedLight !== null };
      if (night) {
        uniforms.sunPosition.value.set(0, -0.3, 1);
        sun.intensity = 0.35; sun.color.setHex(0x9fb4ff);
        renderer.toneMappingExposure = 0.55;
        scene.background = new T.Color(0x070b1c);
        sky.visible = false;
        // Estrellas.
        const starPos = new Float32Array(1500 * 3);
        for (let i = 0; i < 1500; i += 1) { const a = hash(i, 91) * Math.PI * 2, e = 0.1 + hash(i, 92) * 1.4; starPos.set([Math.cos(a) * Math.cos(e) * 9000, Math.sin(e) * 9000, Math.sin(a) * Math.cos(e) * 9000], i * 3); }
        const stars = new T.Points(new T.BufferGeometry().setAttribute("position", new T.BufferAttribute(starPos, 3)), new T.PointsMaterial({ color: 0xffffff, size: 18, sizeAttenuation: true, fog: false }));
        scene.add(stars);
      } else if (dawn) {
        uniforms.sunPosition.value.set(Math.cos(0.15), Math.sin(0.12), 0.3);
        sun.intensity = 1.6; sun.color.setHex(0xffb37a);
      }

      // Agua: un plano con reflejo al nivel del mar o del lago más bajo de la zona.
      let lowestWater = Infinity;
      for (let i = 0; i < n * n; i += 1) if (cover[i] === 80) lowestWater = Math.min(lowestWater, heights[i]);
      if (Number.isFinite(lowestWater) && !walkOnWater) {
        const water = new T.Mesh(new T.PlaneGeometry(size * 3, size * 3), new T.MeshStandardMaterial({ color: 0x2c5f86, roughness: 0.08, metalness: 0.3, transparent: true, opacity: 0.9, envMap, envMapIntensity: 0.7 }));
        water.rotation.x = -Math.PI / 2;
        water.position.y = lowestWater + 0.4;
        scene.add(water);
      }
      // Ríos que bajan con el valle (como el Rímac en Chosica): el agua de un plano plano no puede seguir la pendiente,
      // así que se dibuja una cinta por el cauce principal del relieve. Solo si ESA WorldCover marca agua a lo largo
      // de ese cauce (al menos 15 % de sus celdas a ≤ 2 celdas de agua): no se inventan ríos.
      const flow = drainage(heights, n);
      const flowTextures: THREE_NS.Texture[] = [];
      const riverAcc = Math.max(250, n * n * 0.004);
      const channel = mainChannel(flow, riverAcc);
      let riverCells = new Set<number>();
      if (!walkOnWater && channel.length > 40) {
        let wet = 0;
        for (const i of channel) {
          const r = Math.floor(i / n), c = i % n;
          let found = false;
          for (let dr = -2; dr <= 2 && !found; dr += 1) for (let dc = -2; dc <= 2; dc += 1) {
            const rr = r + dr, cc = c + dc;
            if (rr >= 0 && cc >= 0 && rr < n && cc < n && cover[rr * n + cc] === 80) { found = true; break; }
          }
          if (found) wet += 1;
        }
        if (wet / channel.length >= 0.15) {
          riverCells = new Set(channel);
          const muddy = mission.hazard === "huaico" || mission.hazard === "inundacion";
          const tex = flowTexture(T, muddy ? [111, 98, 74] : [44, 95, 128], muddy ? [150, 132, 100] : [90, 140, 170], true);
          tex.repeat.set(1, 1);
          flowTextures.push(tex);
          const path = smoothPath(channel.map((i) => cellXZ(i, n, size)), 6);
          const accMax = flow.acc[channel[channel.length - 1]];
          const river = buildRibbon(T, path, (k) => 16 + 12 * Math.sqrt(flow.acc[channel[Math.min(Math.round((k / path.length) * channel.length), channel.length - 1)]] / accMax), heightAt, 0.7,
            new T.MeshStandardMaterial({ map: tex, color: 0xffffff, roughness: 0.18, metalness: 0.1, envMap, envMapIntensity: 0.5, transparent: true, opacity: 0.94 }));
          scene.add(river.mesh);
        }
      }

      // Nubes: siluetas suaves altas, para que el cielo no sea plano.
      const cloudCanvas = document.createElement("canvas");
      cloudCanvas.width = cloudCanvas.height = 128;
      const ctx = cloudCanvas.getContext("2d")!;
      const grad = ctx.createRadialGradient(64, 64, 4, 64, 64, 64);
      grad.addColorStop(0, "rgba(255,255,255,.95)"); grad.addColorStop(0.5, "rgba(255,255,255,.55)"); grad.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = grad; ctx.fillRect(0, 0, 128, 128);
      const cloudTexture = new T.CanvasTexture(cloudCanvas);
      const cloudMaterial = new T.SpriteMaterial({ map: cloudTexture, transparent: true, depthWrite: false, fog: false, opacity: 0.8 });
      for (let i = 0; i < 26; i += 1) {
        const cloud = new T.Sprite(cloudMaterial);
        const angle = hash(i, 3) * Math.PI * 2, dist = size * (0.5 + hash(i, 7) * 1.4);
        cloud.position.set(Math.cos(angle) * dist, 900 + hash(i, 11) * 900, Math.sin(angle) * dist);
        const w = 900 + hash(i, 13) * 1400;
        cloud.scale.set(w, w * 0.38, 1);
        scene.add(cloud);
      }

      // --- Vegetación y rocas donde WorldCover lo dice ----------------------------------------------------------
      const placeAll = (classes: number[], max: number, step: number) => {
        const spots: [number, number, number][] = [];
        for (let row = 0; row < n && spots.length < max; row += step) {
          for (let col = 0; col < n && spots.length < max; col += step) {
            if (!classes.includes(cover[row * n + col])) continue;
            const x = (col / (n - 1) - 0.5) * size + (hash(col, row) - 0.5) * cell * step;
            const z = (row / (n - 1) - 0.5) * size + (hash(row, col) - 0.5) * cell * step;
            spots.push([x, heightAt(x, z), z]);
          }
        }
        return spots;
      };
      const matrix = new T.Matrix4();
      const quat = new T.Quaternion();
      const scaleV = new T.Vector3();
      const scatter = (spots: [number, number, number][], geom: THREE_NS.BufferGeometry, material: THREE_NS.Material, baseScale: number, lift: number) => {
        if (!spots.length) return;
        const mesh = new T.InstancedMesh(geom, material, spots.length);
        spots.forEach(([x, y, z], i) => {
          const s = baseScale * (0.7 + hash(x, z) * 0.7);
          quat.setFromAxisAngle(new T.Vector3(0, 1, 0), hash(z, x) * Math.PI * 2);
          matrix.compose(new T.Vector3(x, y + lift * s, z), quat, scaleV.set(s, s, s));
          mesh.setMatrixAt(i, matrix);
        });
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        scene.add(mesh);
      };
      const treeSpots = placeAll([10, 95], 7000, 2);
      // Formas de árbol según el bioma.
      const palmFronds = new T.ConeGeometry(1.4, 0.6, 7);
      const palmTrunk = new T.CylinderGeometry(0.1, 0.16, 3.2, 6);
      const conifer = new T.ConeGeometry(0.9, 2.8, 8);
      const crown = new T.IcosahedronGeometry(1, 1);
      crown.scale(1, 1.25, 1);
      const trunkMat = new T.MeshStandardMaterial({ color: 0x5a4030, roughness: 1 });
      if (biome === "tropical") {
        scatter(treeSpots, palmTrunk, new T.MeshStandardMaterial({ color: 0x8a6a45, roughness: 1 }), 4, 0.8);
        scatter(treeSpots, palmFronds, new T.MeshStandardMaterial({ color: 0x3f8a3a, roughness: 0.85, flatShading: true }), 4, 2.6);
      } else if (biome === "boreal") {
        scatter(treeSpots, conifer, new T.MeshStandardMaterial({ color: 0x24472b, roughness: 0.9, flatShading: true }), 4.5, 1.6);
        scatter(treeSpots, new T.CylinderGeometry(0.1, 0.14, 1.2, 6), trunkMat, 4.5, 0.3);
      } else {
        scatter(treeSpots, crown, new T.MeshStandardMaterial({ color: 0x2f5a27, roughness: 0.9, flatShading: true }), 5.5, 1.9);
        scatter(treeSpots, new T.CylinderGeometry(0.12, 0.18, 2, 6), trunkMat, 5.5, 0.5);
      }
      // Playas tropicales con palmeras sueltas.
      if (biome === "tropical") {
        const beachSpots: [number, number, number][] = [];
        for (let r = 0; r < n && beachSpots.length < 600; r += 3) for (let c = 0; c < n && beachSpots.length < 600; c += 3) {
          if (!beach[r * n + c] || hash(c, r * 3) > 0.35) continue;
          const x = (c / (n - 1) - 0.5) * size, z = (r / (n - 1) - 0.5) * size;
          beachSpots.push([x, heightAt(x, z), z]);
        }
        scatter(beachSpots, palmTrunk, new T.MeshStandardMaterial({ color: 0x8a6a45, roughness: 1 }), 3.6, 0.8);
        scatter(beachSpots, palmFronds, new T.MeshStandardMaterial({ color: 0x4a9a3e, roughness: 0.85, flatShading: true }), 3.6, 2.6);
      }
      // Casas con techo y algunos edificios en el centro, solo en celdas urbanas de WorldCover y fuera de las calles.
      const houseCells = new Set<number>();
      const houses: { x: number; y: number; z: number; w: number; d: number; h: number; tower: boolean; seed: number }[] = [];
      for (let row = 1; row < n - 1 && houses.length < 5500; row += 1) {
        for (let col = 1; col < n - 1 && houses.length < 5500; col += 1) {
          const i = row * n + col;
          if (cover[i] !== 50 || row % STREET_EVERY === 0 || col % STREET_EVERY === 0 || hash(col * 3, row * 7) > 0.72) continue;
          let urbanAround = 0;
          for (let dr = -2; dr <= 2; dr += 1) for (let dc = -2; dc <= 2; dc += 1) if (cover[Math.min(Math.max(row + dr, 0), n - 1) * n + Math.min(Math.max(col + dc, 0), n - 1)] === 50) urbanAround += 1;
          const x = (col / (n - 1) - 0.5) * size, z = (row / (n - 1) - 0.5) * size;
          const tower = urbanAround > 23 && hash(row, col * 5) > 0.93;
          const seed = hash(col * 11, row * 13);
          houses.push({ x, y: heightAt(x, z), z, w: cell * (tower ? 0.75 : 0.45 + seed * 0.25), d: cell * (tower ? 0.75 : 0.45 + hash(row, col) * 0.25), h: tower ? 12 + seed * 14 : 4 + seed * 3.5, tower, seed });
          houseCells.add(i);
        }
      }
      if (houses.length) {
        const kitColors = CULTURE[mission.id];
        const walls = kitColors?.walls ?? [0xefe6d6, 0xf4f1ea, 0xd9b48f, 0xc9d6df, 0xe8d38f, 0xcfc6bb];
        const roofs = kitColors?.roofs ?? [0xa4482f, 0x6b5a4e, 0x8a3c2a, 0x5b6068, 0xb5653d];
        // Ventanas: de noche se encienden.
        const winCanvas = document.createElement("canvas"); winCanvas.width = winCanvas.height = 64;
        const wctx = winCanvas.getContext("2d")!; wctx.fillStyle = "#000"; wctx.fillRect(0, 0, 64, 64);
        for (let wy = 0; wy < 2; wy += 1) for (let wx = 0; wx < 3; wx += 1) { wctx.fillStyle = (wx + wy) % 3 === 0 ? "#222" : "#ffd27a"; wctx.fillRect(6 + wx * 20, 10 + wy * 26, 12, 14); }
        const winTex = new T.CanvasTexture(winCanvas);
        const bodyMesh = new T.InstancedMesh(new T.BoxGeometry(1, 1, 1), new T.MeshStandardMaterial({ roughness: 0.85, emissive: 0xffc870, emissiveMap: winTex, emissiveIntensity: night ? 1.1 : 0 }), houses.length);
        const roofGeo = new T.ConeGeometry(0.75, 1, 4);
        roofGeo.rotateY(Math.PI / 4);
        const houseOnly = houses.filter((item) => !item.tower);
        const roofMesh = new T.InstancedMesh(roofGeo, new T.MeshStandardMaterial({ roughness: 0.8, flatShading: true }), Math.max(houseOnly.length, 1));
        const tint = new T.Color();
        houses.forEach((item, i) => {
          matrix.compose(new T.Vector3(item.x, item.y + item.h / 2, item.z), quat.identity(), scaleV.set(item.w, item.h, item.d));
          bodyMesh.setMatrixAt(i, matrix);
          bodyMesh.setColorAt(i, tint.setHex(item.tower ? [0xbfc5cc, 0xd8d2c6, 0x9aa7b4][Math.floor(item.seed * 3)] : walls[Math.floor(item.seed * walls.length)]));
        });
        houseOnly.forEach((item, i) => {
          matrix.compose(new T.Vector3(item.x, item.y + item.h + 1.6, item.z), quat.identity(), scaleV.set(item.w * 1.35, 3.2, item.d * 1.35));
          roofMesh.setMatrixAt(i, matrix);
          roofMesh.setColorAt(i, tint.setHex(roofs[Math.floor(hash(item.seed * 97, 3) * roofs.length)]));
        });
        for (const mesh of [bodyMesh, roofMesh]) { mesh.castShadow = true; mesh.receiveShadow = true; scene.add(mesh); }
      }
      // Choque solo con la casa misma (su planta), no con toda la celda: así no hay paredes invisibles.
      const houseAt = new Map<number, (typeof houses)[number]>();
      houses.forEach((item) => houseAt.set(Math.round((item.z / size + 0.5) * (n - 1)) * n + Math.round((item.x / size + 0.5) * (n - 1)), item));
      const blocked = (x: number, z: number): boolean => {
        const c = Math.round((x / size + 0.5) * (n - 1)), r = Math.round((z / size + 0.5) * (n - 1));
        const item = houseAt.get(Math.min(Math.max(r, 0), n - 1) * n + Math.min(Math.max(c, 0), n - 1));
        return !!item && Math.abs(x - item.x) < item.w / 2 + 0.4 && Math.abs(z - item.z) < item.d / 2 + 0.4;
      };

      blockedRef.current = blocked;
      // Árboles de calle y parques: pocos, repartidos en la ciudad.
      const cityTrees = placeAll([50], 380, 8);
      if (biome === "tropical") {
        scatter(cityTrees, palmTrunk, new T.MeshStandardMaterial({ color: 0x8a6a45, roughness: 1 }), 3.2, 0.8);
        scatter(cityTrees, palmFronds, new T.MeshStandardMaterial({ color: 0x4a9a3e, roughness: 0.85, flatShading: true }), 3.2, 2.6);
      } else if (biome === "boreal") {
        scatter(cityTrees, conifer, new T.MeshStandardMaterial({ color: 0x2a5230, roughness: 0.9, flatShading: true }), 3.4, 1.6);
      } else {
        scatter(cityTrees, crown, new T.MeshStandardMaterial({ color: 0x3d6b2f, roughness: 0.9, flatShading: true }), 3.8, 1.9);
        scatter(cityTrees, new T.CylinderGeometry(0.12, 0.18, 2, 6), new T.MeshStandardMaterial({ color: 0x5a4030, roughness: 1 }), 3.8, 0.5);
      }
      scatter(placeAll([20, 90, 100], 4000, 3), new T.IcosahedronGeometry(1, 0), new T.MeshStandardMaterial({ color: 0x6f7a38, roughness: 1, flatShading: true }), 2.2, 0.5);
      scatter(placeAll([60], 1500, 5), new T.DodecahedronGeometry(1, 0), new T.MeshStandardMaterial({ color: 0x9b8a70, roughness: 1, flatShading: true }), 2.4, 0.3);
      // Desiertos de América: cactus en suelo desnudo y matorral.
      if (arid) {
        const cactusSpots = placeAll([60, 20], 900, 6);
        scatter(cactusSpots, new T.CapsuleGeometry(0.35, 2.4, 4, 8), new T.MeshStandardMaterial({ color: 0x4f7a3a, roughness: 0.8 }), 1.6, 1.4);
      }

      // Punto más alto de la zona: una bandera con su altura real.
      let peakIndex = 0;
      for (let i = 1; i < n * n; i += 1) if (heights[i] > heights[peakIndex]) peakIndex = i;
      const peakX = ((peakIndex % n) / (n - 1) - 0.5) * size, peakZ = (Math.floor(peakIndex / n) / (n - 1) - 0.5) * size;
      const peakFlag = new T.Group();
      const peakPole = new T.Mesh(new T.CylinderGeometry(0.15, 0.15, 14, 8), new T.MeshStandardMaterial({ color: 0xeeeeee }));
      peakPole.position.y = 7; peakFlag.add(peakPole);
      const peakCloth = new T.Mesh(new T.PlaneGeometry(6, 3.5), new T.MeshStandardMaterial({ color: 0xffd23a, side: T.DoubleSide }));
      peakCloth.position.set(3, 12, 0); peakFlag.add(peakCloth);
      peakFlag.position.set(peakX, heights[peakIndex], peakZ);
      scene.add(peakFlag);
      const peakMeters = Math.round(terrain.base_elevation_m + relief[peakIndex] / 10);

      // --- Puntos de aviso: un haz de luz por vecino ------------------------------------------------------------
      const spread = mission.scale === "paisaje" ? 220 : 140; // a unos segundos de carrera del aterrizaje
      const spots = propsRef.current.checkpoints.map((item) => {
        const b = (item.bearing * Math.PI) / 180;
        const [x, z] = nearestLand(Math.sin(b) * spread, -Math.cos(b) * spread);
        return { item, position: new T.Vector3(x, heightAt(x, z), z) };
      });
      const beamMaterial = new T.MeshBasicMaterial({ color: 0xffe08a, transparent: true, opacity: 0.28, depthWrite: false, blending: T.AdditiveBlending });
      // Vecinos en peligro: personas 3D con un aura (roja = en peligro, verde = ayudada) y un haz de luz para encontrarlas.
      const npcs: { id: string; rig: import("./hero-rig").HeroRig | null; aura: THREE_NS.Mesh; beam: THREE_NS.Mesh; saved: boolean }[] = [];
      // Los personajes de cada grupo se piden a la vez (el orden no importa); antes se esperaba a cada uno antes de
      // pedir el siguiente. Si uno falla queda en null y el resto sigue.
      const npcRigs = await Promise.all(spots.map((_, index) => loadRig(index % 2 ? "mujer" : "hombre").catch(() => null)));
      for (const [index, spot] of spots.entries()) {
        const beam = new T.Mesh(new T.CylinderGeometry(2.2, 2.2, 140, 16, 1, true), beamMaterial.clone());
        beam.position.copy(spot.position).add(new T.Vector3(0, 70, 0));
        scene.add(beam);
        const aura = new T.Mesh(new T.RingGeometry(1.4, 2.2, 40), new T.MeshBasicMaterial({ color: 0xff4f4f, transparent: true, opacity: 0.85, side: T.DoubleSide, depthWrite: false }));
        aura.rotation.x = -Math.PI / 2;
        aura.position.copy(spot.position).add(new T.Vector3(0, 0.15, 0));
        scene.add(aura);
        const npcRig = npcRigs[index]; // sin vecino 3D: queda el aura y el haz
        if (npcRig) {
          npcRig.object.position.copy(spot.position);
          npcRig.object.rotation.y = hash(index, 9) * Math.PI * 2;
          npcRig.object.traverse((o) => { (o as THREE_NS.Mesh).castShadow = true; });
          scene.add(npcRig.object);
        }
        npcs.push({ id: spot.item.id, rig: npcRig, aura, beam, saved: false });
      }
      // Proyectil del lanzador de ayuda.
      const shot = new T.Mesh(new T.SphereGeometry(0.6, 16, 12), new T.MeshBasicMaterial({ color: 0xffffff }));
      shot.visible = false;
      scene.add(shot);
      // El resplandor del proyectil era una luz puntual que seguía encendida (con intensidad 0) toda la partida: cada luz
      // puntual se calcula en cada píxel de la pantalla. Ahora es un halo que brilla solo, pegado al proyectil.
      const shotGlow = new T.Sprite(new T.SpriteMaterial({ map: cloudTexture, color: 0xffffff, transparent: true, opacity: 0.8, depthWrite: false, blending: T.AdditiveBlending }));
      shotGlow.scale.setScalar(14);
      shot.add(shotGlow);
      let flying: { from: THREE_NS.Vector3; to: THREE_NS.Vector3; t: number; spotIndex: number; polluter: number } | null = null;
      const near = (position: THREE_NS.Vector3, radius: number) => Math.hypot(position.x - heroObj.position.x, position.z - heroObj.position.z) < radius;
      const fire = () => {
        if (!landed || flying) return;
        // Primero el perrito herido, luego un vecino en peligro y, si no hay, un contaminador cercano.
        if (dogState === "herido" && near(dog.position, 20)) {
          (shot.material as THREE_NS.MeshBasicMaterial).color.setHex(0xff6b81); shotGlow.material.color.setHex(0xff6b81);
          flying = { from: heroObj.position.clone().add(new T.Vector3(0, 1.6, 0)), to: dog.position.clone().add(new T.Vector3(0, 0.8, 0)), t: 0, spotIndex: -2, polluter: -1 };
          heading = Math.atan2(dog.position.x - heroObj.position.x, dog.position.z - heroObj.position.z);
          return;
        }
        const index = spots.findIndex((spot, i) => !npcs[i].saved && near(spot.position, 34));
        const polluter = index === -1 ? polluters.findIndex((item) => !item.stopped && near(item.position, 34)) : -1;
        if (index === -1 && polluter === -1) return;
        const to = index !== -1 ? spots[index].position : polluters[polluter].position;
        const color = index !== -1 ? toolFor(spots[index].item).color : 0x5ee08a;
        (shot.material as THREE_NS.MeshBasicMaterial).color.setHex(color);
        shotGlow.material.color.setHex(color);
        flying = { from: heroObj.position.clone().add(new T.Vector3(0, 1.6, 0)), to: to.clone().add(new T.Vector3(0, 1.2, 0)), t: 0, spotIndex: index, polluter };
        sfx("whoosh");
        // El héroe gira hacia quien ayuda o detiene.
        heading = Math.atan2(to.x - heroObj.position.x, to.z - heroObj.position.z);
      };
      fireRef.current = fire;
      // ESPACIO salta; F ayuda a un vecino o detiene a un contaminador.
      let jumpY = 0, jumpV = 0, lastJump = 0, flyUntil = 0;
      let droneView = false; // V: cámara alta para ver venir el huaico o la avalancha
      let tabFocus = false; // el foco actual llegó con Tab (un clic o toque en cualquier parte lo vuelve falso)
      const onAction = (event: KeyboardEvent) => {
        // Las teclas del juego solo se ignoran al escribir en un campo de texto (y en los atajos del navegador, como
        // Ctrl+F). Antes también se ignoraban con el foco en un botón: tras un clic en «Sonido», Espacio apagaba el
        // sonido en vez de saltar y F, E y 1 a 6 no respondían.
        if (event.code === "Tab") { tabFocus = true; return; }
        // Escape cierra las tarjetas abiertas (lección, mochila lista, noticias de El Niño, créditos) y devuelve el
        // foco al lienzo si estaba en un botón del mundo: con el foco puesto por Tab, Espacio es del botón y no salta.
        if (event.code === "Escape" && !typing(event)) {
          setLesson(null); setKitDone(false); setNinoOpen(false); setCreditsOpen(false);
          if ((event.target as HTMLElement)?.closest?.(".gameWorld")) { tabFocus = false; canvas.focus({ preventScroll: true }); }
          return;
        }
        if (!/^(Space|Key[FEGV]|(Digit|Numpad)[1-6])$/.test(event.code) || typing(event) || event.ctrlKey || event.metaKey || event.altKey) return;
        // Botón al que se llegó con Tab: Espacio lo activa y el héroe no salta. Si el foco quedó en un botón por un
        // clic del mouse (por ejemplo, en el panel), vuelve al lienzo y la tecla es del juego. No se usa
        // «:focus-visible» porque Chrome lo enciende en cuanto se pulsa cualquier tecla.
        const control = (event.target as HTMLElement)?.closest?.("button, a[href], summary");
        if (control && tabFocus) { if (event.code === "Space") return; }
        else if (control) canvas.focus({ preventScroll: true });
        // Tecla mantenida: la autorrepetición no repite la acción (sostener Espacio activaba el vuelo y sostener E
        // subía y bajaba del vehículo sin parar).
        if (event.repeat) { event.preventDefault(); return; }
        if (event.code === "Space") {
          event.preventDefault();
          if (!landed) return;
          if (jumpY === 0) { jumpV = 9.5; lastJump = elapsed; }
          else if (elapsed - lastJump < 0.6 && flyUntil < elapsed) { flyUntil = elapsed + 4; sfx("whoosh"); setPickupNote("🦸 ¡Vuelo de superhéroe! (4 s)"); }
        }
        if (event.code === "KeyF") { event.preventDefault(); fire(); }
        if (event.code === "KeyE") { event.preventDefault(); toggleRef.current(); }
        const digit = /^(?:Digit|Numpad)([1-6])$/.exec(event.code);
        if (digit) { event.preventDefault(); equipRef.current(ITEMS[Number(digit[1]) - 1].id); }
        if (event.code === "KeyG") { event.preventDefault(); equipRef.current(null); }
        if (event.code === "KeyV") { event.preventDefault(); droneView = !droneView; setPickupNote(droneView ? "🛰 Vista desde el cielo (V para volver)" : "Vista normal"); }
      };
      // `onAction` se registra más abajo, junto al resto del teclado: aquí todavía faltan cargar modelos y declarar
      // `elapsed` y `landed`, y pulsar Espacio o F durante la carga lanzaba «Cannot access 'landed' before initialization».

      // --- Nave y héroe -----------------------------------------------------------------------------------------
      const [sx, sz] = nearestLand(18, 30);
      const spawn = new T.Vector3(sx, heightAt(sx, sz), sz);
      const ship = shipModule.buildShip(T);
      ship.scale.setScalar(5);
      ship.traverse((o) => { (o as THREE_NS.Mesh).castShadow = true; });
      scene.add(ship);
      const [lx, lz] = nearestLand(spawn.x - 14, spawn.z + 6);
      const landing = new T.Vector3(lx, heightAt(lx, lz) + 2.5, lz);
      const rig = hero ? await loadRig(hero.gender) : null;
      if (disposed) return;
      const heroObj = new T.Group();
      if (rig) {
        rig.object.traverse((o) => { (o as THREE_NS.Mesh).castShadow = true; });
        heroObj.add(rig.object);
        heroObj.visible = false;
        heroObj.position.copy(spawn);
        scene.add(heroObj);
      }

      // --- Identidad cultural del lugar: elementos de su país o región, bandera, geoglifo y humo volcánico -------
      const kit = CULTURE[mission.id];
      const spinners: THREE_NS.Object3D[] = [];
      let plume: THREE_NS.Object3D | null = null;
      if (kit) {
        const waterSpots: [number, number][] = [];
        for (let r = 0; r < n; r += 4) for (let c = 0; c < n; c += 4) {
          if (cover[r * n + c] !== 80) continue;
          const x = (c / (n - 1) - 0.5) * size, z = (r / (n - 1) - 0.5) * size;
          if (Math.hypot(x - spawn.x, z - spawn.z) < 600) waterSpots.push([x, z]);
        }
        let seed = 0;
        for (const prop of kit.props) {
          for (let i = 0; i < prop.count; i += 1) {
            seed += 1;
            let x: number, z: number;
            if (prop.onWater) {
              if (!waterSpots.length) break;
              [x, z] = waterSpots[Math.floor(hash(seed, 5) * waterSpots.length)];
            } else {
              const a = hash(seed, 3) * Math.PI * 2, r = 30 + hash(seed, 4) * 120;
              [x, z] = nearestLand(spawn.x + Math.cos(a) * r, spawn.z + Math.sin(a) * r);
            }
            const obj = prop.build(T);
            obj.position.set(x, heightAt(x, z) + (prop.onWater ? 0.2 : 0), z);
            obj.rotation.y = hash(seed, 6) * Math.PI * 2;
            scene.add(obj);
            if (prop.spin) { const blades = obj.getObjectByName("spin"); if (blades) spinners.push(blades); }
          }
        }
        if (kit.geoglyph) {
          const glyph = nazcaHummingbird(T);
          const [gx, gz] = nearestLand(spawn.x + 70, spawn.z - 90);
          glyph.position.set(gx, heightAt(gx, gz), gz);
          scene.add(glyph);
        }
        if (kit.plume) {
          plume = volcanoPlume(T);
          if (plume) { plume.position.set(peakX, heights[peakIndex], peakZ); scene.add(plume); }
        }
        const flagCanvas = kit.flag ? drawFlag(kit.flag) : null;
        if (flagCanvas) {
          const flagTex = new T.CanvasTexture(flagCanvas); flagTex.colorSpace = T.SRGBColorSpace;
          const pole = new T.Mesh(new T.CylinderGeometry(0.12, 0.12, 9, 8), new T.MeshStandardMaterial({ color: 0xdddddd, metalness: 0.5 }));
          const cloth = new T.Mesh(new T.PlaneGeometry(4.5, 3), new T.MeshStandardMaterial({ map: flagTex, side: T.DoubleSide }));
          const flagGroup = new T.Group(); pole.position.y = 4.5; cloth.position.set(2.25, 7.4, 0); cloth.name = "spinFlag"; flagGroup.add(pole, cloth);
          const [fx, fz] = nearestLand(spawn.x - 6, spawn.z - 10);
          flagGroup.position.set(fx, heightAt(fx, fz), fz);
          scene.add(flagGroup);
        }
      }

      // --- Contaminadores: queman basura; el rayo verde de conciencia los detiene y se vuelven aliados -------------
      const smokeCanvas = document.createElement("canvas");
      smokeCanvas.width = smokeCanvas.height = 64;
      const sctx = smokeCanvas.getContext("2d")!;
      const sgrad = sctx.createRadialGradient(32, 32, 2, 32, 32, 32);
      sgrad.addColorStop(0, "rgba(70,70,70,.9)"); sgrad.addColorStop(1, "rgba(70,70,70,0)");
      sctx.fillStyle = sgrad; sctx.fillRect(0, 0, 64, 64);
      const smokeTexture = new T.CanvasTexture(smokeCanvas);
      const polluters: { position: THREE_NS.Vector3; rig: import("./hero-rig").HeroRig | null; aura: THREE_NS.Mesh; smoke: THREE_NS.Sprite[]; stopped: boolean }[] = [];
      // En la Antártida no hay pueblos que quemen basura: allí no aparecen contaminadores.
      const polluterBearings = mission.continent === "Antártida" ? [] : [100, 225];
      const polluterRigs = await Promise.all(polluterBearings.map((_, k) => loadRig(k % 2 ? "mujer" : "hombre").catch(() => null)));
      for (const [k, bearing] of polluterBearings.entries()) {
        const b = (bearing * Math.PI) / 180;
        const [px, pz] = nearestLand(Math.sin(b) * spread * 0.75, -Math.cos(b) * spread * 0.75);
        const position = new T.Vector3(px, heightAt(px, pz), pz);
        const pile = new T.Mesh(new T.DodecahedronGeometry(1.6, 0), new T.MeshStandardMaterial({ color: 0x3b3530, roughness: 1, flatShading: true }));
        pile.position.copy(position).add(new T.Vector3(2.5, 0.6, 0));
        pile.scale.set(1.4, 0.7, 1.2);
        scene.add(pile);
        const smoke: THREE_NS.Sprite[] = [];
        for (let i = 0; i < 9; i += 1) {
          const puff = new T.Sprite(new T.SpriteMaterial({ map: smokeTexture, transparent: true, depthWrite: false, opacity: 0.7 }));
          puff.position.copy(pile.position);
          scene.add(puff);
          smoke.push(puff);
        }
        const aura = new T.Mesh(new T.RingGeometry(1.4, 2.2, 40), new T.MeshBasicMaterial({ color: 0xffa040, transparent: true, opacity: 0.85, side: T.DoubleSide, depthWrite: false }));
        aura.rotation.x = -Math.PI / 2;
        aura.position.copy(position).add(new T.Vector3(0, 0.15, 0));
        scene.add(aura);
        const prig = polluterRigs[k]; // sin modelo: queda el humo y el aura
        if (prig) {
          prig.object.position.copy(position);
          prig.object.rotation.y = Math.PI / 2;
          scene.add(prig.object);
        }
        polluters.push({ position, rig: prig, aura, smoke, stopped: false });
      }

      // --- Clima del lugar según los datos de la misión (NASA POWER) -----------------------------------------
      const meanT = mission.temperature?.mean ?? 15;
      // Lluvia solo donde llueve de verdad: media alta, o media moderada con extremos que aumentan (no en un desierto).
      const rainMean = mission.rain?.mean ?? 0;
      const rainy = rainMean > 3.5 || (rainMean > 1.5 && mission.extremes.some((e) => e.significant && e.direction === "increasing"));
      const weatherKind: "nieve" | "lluvia" | "calor" | "despejado" = meanT < 4 ? "nieve" : rainy ? "lluvia" : meanT > 24 ? "calor" : "despejado";
      weatherRef.current = weatherKind;
      const precipCount = weatherKind === "lluvia" ? 4200 : weatherKind === "nieve" ? 2600 : weatherKind === "calor" ? 900 : 0;
      const precipBox = { w: 90, h: 50 };
      const precipPositions = new Float32Array(precipCount * (weatherKind === "lluvia" ? 6 : 3));
      for (let i = 0; i < precipCount; i += 1) {
        const x = (hash(i, 1) - 0.5) * precipBox.w, y = hash(i, 2) * precipBox.h, z = (hash(i, 3) - 0.5) * precipBox.w;
        if (weatherKind === "lluvia") precipPositions.set([x, y, z, x, y - 1.1, z], i * 6);
        else precipPositions.set([x, y, z], i * 3);
      }
      const precipGeo = new T.BufferGeometry();
      precipGeo.setAttribute("position", new T.BufferAttribute(precipPositions, 3));
      const precip = weatherKind === "lluvia"
        ? new T.LineSegments(precipGeo, new T.LineBasicMaterial({ color: 0xb8c8dc, transparent: true, opacity: 0.55, fog: false }))
        : new T.Points(precipGeo, new T.PointsMaterial({ color: weatherKind === "nieve" ? 0xffffff : 0xf3e2c0, size: weatherKind === "nieve" ? 4 : 2, sizeAttenuation: false, map: cloudTexture, alphaTest: 0.05, transparent: true, depthWrite: false, opacity: weatherKind === "nieve" ? 0.95 : 0.35, fog: false }));
      precip.frustumCulled = false;
      if (precipCount) scene.add(precip);
      // Lluvia de tormenta: solo aparece durante un aviso de huaico (llueve fuerte en la sierra).
      const stormCount = 1800;
      const stormPositions = new Float32Array(stormCount * 6);
      for (let i = 0; i < stormCount; i += 1) {
        const x = (hash(i, 31) - 0.5) * 90, y = hash(i, 32) * 50, z = (hash(i, 33) - 0.5) * 90;
        stormPositions.set([x, y, z, x, y - 1.3, z], i * 6);
      }
      const stormGeo = new T.BufferGeometry();
      stormGeo.setAttribute("position", new T.BufferAttribute(stormPositions, 3));
      const stormRain = new T.LineSegments(stormGeo, new T.LineBasicMaterial({ color: 0xb8c8dc, transparent: true, opacity: 0.5, fog: false }));
      stormRain.visible = false;
      stormRain.frustumCulled = false;
      scene.add(stormRain);
      if (weatherKind === "lluvia") {
        uniforms.turbidity.value = 20; uniforms.rayleigh.value = 0.3; uniforms.mieCoefficient.value = 0.02;
        scene.fog = new T.Fog(0x7f8892, 40, 900);
        sun.intensity = 0.8;
      } else if (weatherKind === "nieve") {
        scene.fog = new T.Fog(0xdfe6ee, 60, 1300);
        sun.intensity = 1.6;
      } else if (weatherKind === "calor") {
        scene.fog = new T.Fog(0xe6cfa2, 200, size * 1.4);
        sun.intensity = 3.3;
        sun.color.setHex(0xffe0b0);
      }
      if (timeRef.current.night) scene.fog = new T.Fog(0x0b1024, 60, size * 0.9);
      const ambientFlash = new T.AmbientLight(0xdfe8ff, 0);
      scene.add(ambientFlash);
      let nextLightning = 4;

      // --- Objetos para recoger y salud ------------------------------------------------------------------------
      const ITEM: Record<string, { icon: string; name: string }> = {
        paraguas: { icon: "☂️", name: "Paraguas" }, agua: { icon: "💧", name: "Agua" }, abrigo: { icon: "🧥", name: "Abrigo" }, botiquin: { icon: "❤️", name: "Botiquín" },
      };
      const protectionFor = weatherKind === "lluvia" ? "paraguas" : weatherKind === "nieve" ? "abrigo" : weatherKind === "calor" ? "agua" : null;
      const pickups: { kind: string; sprite: THREE_NS.Sprite; base: number; taken: boolean }[] = [];
      const iconTexture = (icon: string) => {
        const c = document.createElement("canvas");
        c.width = c.height = 128;
        const x = c.getContext("2d")!;
        x.fillStyle = "rgba(255,240,180,.35)"; x.beginPath(); x.arc(64, 64, 60, 0, Math.PI * 2); x.fill();
        x.font = "84px serif"; x.textAlign = "center"; x.textBaseline = "middle"; x.fillText(icon, 64, 70);
        const t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; return t;
      };
      const kinds = [protectionFor, protectionFor, protectionFor, "botiquin", "botiquin", protectionFor ?? "botiquin", "agua", "paraguas", "abrigo"].filter(Boolean) as string[];
      kinds.forEach((kind, i) => {
        const a = hash(i, 21) * Math.PI * 2, r = 30 + hash(i, 22) * spread * 1.2;
        const [ix, iz] = nearestLand(spawn.x + Math.cos(a) * r, spawn.z + Math.sin(a) * r);
        const sprite = new T.Sprite(new T.SpriteMaterial({ map: iconTexture(ITEM[kind].icon), transparent: true, depthWrite: false }));
        const base = heightAt(ix, iz) + 2;
        sprite.position.set(ix, base, iz);
        sprite.scale.setScalar(2.6);
        scene.add(sprite);
        pickups.push({ kind, sprite, base, taken: false });
      });
      let health = 100;
      const protectedUntil: Record<string, number> = {};
      // Mochila y objeto en la mano.
      const bagCounts: Partial<Record<ItemId, number>> = {};
      let equipped: ItemId | null = null;
      let inHand: { id: ItemId; item: HandItem } | null = null;
      let botiquinUntil = 0, radioNext = 0, radioIndex = -1;
      const syncBag = () => setBag({ counts: { ...bagCounts }, equipped });
      const keyOf = (id: ItemId) => ITEMS.findIndex((it) => it.id === id) + 1;
      const infoOf = (id: ItemId) => ITEMS.find((it) => it.id === id)!;
      const addToBag = (id: ItemId) => { bagCounts[id] = (bagCounts[id] ?? 0) + 1; syncBag(); };
      const putAway = () => { if (inHand) { scene.remove(inHand.item.object); disposeHandItem(inHand.item); inHand = null; } equipped = null; };
      equipRef.current = (id: ItemId | null) => {
        if (!landed) return;
        if (id === null || id === equipped) {
          if (equipped) { const info = infoOf(equipped); setPickupNote(`${info.icon} ${info.name}: guardado en la mochila`); }
          putAway(); syncBag(); return;
        }
        const info = infoOf(id);
        if (!(bagCounts[id] ?? 0)) { setPickupNote(`${info.icon} Aún no tienes ${info.name.toLowerCase()}: búscalo en el mapa o en la casa`); return; }
        putAway();
        equipped = id;
        inHand = { id, item: buildHandItem(T, id) };
        scene.add(inHand.item.object);
        if (id === "botiquin") botiquinUntil = elapsed + 1.6;
        if (id === "radio") radioNext = 0;
        sfx("powerup");
        setPickupNote(`${info.icon} Sacaste: ${info.name} (${info.use}) · pulsa ${keyOf(id)} o G para guardarlo`);
        syncBag();
      };

      // --- Compañero: otra persona que te acompaña ---------------------------------------------------------------
      let buddy: import("./hero-rig").HeroRig | null = null;
      try {
        buddy = await loadRig(hero?.gender === "mujer" ? "hombre" : "mujer");
        buddy.object.position.copy(spawn).add(new T.Vector3(-3, 0, 3));
        buddy.object.visible = false;
        buddy.object.traverse((o) => { (o as THREE_NS.Mesh).castShadow = true; });
        scene.add(buddy.object);
      } catch { /* sin compañero */ }
      if (disposed) return;

      // --- Vehículos: camioneta de rescate y moto, junto a la nave ---------------------------------------------
      type Vehicle = { obj: THREE_NS.Group; speed: number; heading: number; max: number; accel: number; lift: number; name: string };
      const vehicles: Vehicle[] = [];
      for (const [kind, ox, oz] of [["camioneta", 12, -8], ["moto", -10, -10]] as const) {
        const [vx, vz] = nearestLand(spawn.x + ox, spawn.z + oz);
        const obj = kind === "camioneta" ? buildTruck(T) : buildMoto(T);
        obj.position.set(vx, heightAt(vx, vz), vz);
        obj.rotation.y = Math.PI;
        scene.add(obj);
        vehicles.push({ obj, speed: 0, heading: Math.PI, max: kind === "camioneta" ? 48 : 60, accel: kind === "camioneta" ? 30 : 42, lift: 0, name: kind });
      }
      let driving: Vehicle | null = null;
      let takeoff = 0;
      let usedVehicle = false;
      const toggleVehicle = () => {
        if (!landed) return;
        // Dentro de una casa: salir por la puerta.
        if (inside) {
          if (heroObj.position.distanceTo(temp.copy(inside.room.origin).add(inside.room.exit)) < 4) {
            heroObj.position.copy(inside.door).add(new T.Vector3(0, 0, 2));
            inside = null;
            showRoom(null);
            precip.visible = true;
            setInsideHouse(false);
          }
          return;
        }
        const doorNear = !driving ? doors.find((d) => Math.hypot(d.at.x - heroObj.position.x, d.at.z - heroObj.position.z) < 7) : undefined;
        if (doorNear) {
          inside = { door: doorNear.at.clone(), room: doorNear.room };
          showRoom(doorNear.room);
          heroObj.position.copy(doorNear.room.origin).add(doorNear.room.exit).add(new T.Vector3(1.5, 0, 0));
          heading = Math.PI / 2;
          yaw = -Math.PI / 2;
          precip.visible = false;
          setInsideHouse(true);
          setPickupNote(doorNear.room.name === "fiesta" ? "🎉 ¡Llegaste a la fiesta! Saluda y baila" : "🏠 ¡Bienvenida a casa! La familia te necesita");
          return;
        }
        if (driving) {
          const side = driving.heading + Math.PI / 2;
          heroObj.position.set(driving.obj.position.x + Math.sin(side) * 3, 0, driving.obj.position.z + Math.cos(side) * 3);
          driving.speed = 0;
          driving = null;
          heroObj.visible = true;
          return;
        }
        const close = vehicles.find((v) => Math.hypot(v.obj.position.x - heroObj.position.x, v.obj.position.z - heroObj.position.z) < 7);
        if (close) { driving = close; usedVehicle = true; heroObj.visible = false; yaw = close.heading + Math.PI; return; }
        // Junto a la nave: subir y despegar hacia otro lugar del planeta.
        if (Math.hypot(ship.position.x - heroObj.position.x, ship.position.z - heroObj.position.z) < 16 && !takeoff) {
          takeoff = elapsed;
          heroObj.visible = false;
          if (buddy) buddy.object.visible = false;
          dog.visible = false;
          sfx("powerup");
        }
      };
      toggleRef.current = toggleVehicle;

      // --- Refugio: centro de reciclaje -------------------------------------------------------------------------
      const [rfx, rfz] = nearestLand(Math.sin(5.2) * spread * 1.1, -Math.cos(5.2) * spread * 1.1);
      const refuge = buildRefuge(T);
      refuge.position.set(rfx, heightAt(rfx, rfz), rfz);
      scene.add(refuge);
      const following = new Set<number>();
      const trained = new Set<number>();

      // --- Perrito herido cerca de la nave: al curarlo, te acompaña -------------------------------------------
      const dog = buildDog(T);
      const [dgx, dgz] = nearestLand(spawn.x + 26, spawn.z - 14);
      dog.position.set(dgx, heightAt(dgx, dgz), dgz);
      dog.rotation.z = Math.PI / 2.2; // echado de lado, herido
      scene.add(dog);
      const crossCanvas = document.createElement("canvas"); crossCanvas.width = crossCanvas.height = 64;
      const cx = crossCanvas.getContext("2d")!; cx.fillStyle = "#fff"; cx.beginPath(); cx.arc(32, 32, 30, 0, Math.PI * 2); cx.fill(); cx.fillStyle = "#e5262f"; cx.fillRect(26, 12, 12, 40); cx.fillRect(12, 26, 40, 12);
      const dogCross = new T.Sprite(new T.SpriteMaterial({ map: new T.CanvasTexture(crossCanvas), depthWrite: false }));
      dogCross.scale.setScalar(1.6); scene.add(dogCross);
      let dogState: "herido" | "amigo" = "herido";
      let dogHeading = 0;
      let nextBark = 0;

      // --- Vida cotidiana: una fiesta con gente bailando, una mesa con comida y luces de colores -----------------
      const [ptx, ptz] = nearestLand(spawn.x - 40, spawn.z + 30);
      const party = new T.Group();
      party.position.set(ptx, heightAt(ptx, ptz), ptz);
      scene.add(party);
      const table = new T.Mesh(new T.BoxGeometry(6, 0.2, 2), new T.MeshStandardMaterial({ color: 0x8a5a3c })); table.position.y = 1; party.add(table);
      for (const x of [-2.6, 2.6]) for (const z of [-0.8, 0.8]) { const leg = new T.Mesh(new T.CylinderGeometry(0.08, 0.08, 1), new T.MeshStandardMaterial({ color: 0x5a4030 })); leg.position.set(x, 0.5, z); party.add(leg); }
      const foodColors = [0xffb21a, 0xe5262f, 0x5ee08a, 0xf2e6cf, 0x8a3c2a];
      for (let i = 0; i < 8; i += 1) { const plate = new T.Mesh(new T.CylinderGeometry(0.28, 0.28, 0.05, 14), new T.MeshStandardMaterial({ color: 0xffffff })); plate.position.set(-2.4 + i * 0.7, 1.13, (i % 2 ? 0.45 : -0.45)); party.add(plate); const food = new T.Mesh(new T.SphereGeometry(0.16, 10, 8), new T.MeshStandardMaterial({ color: foodColors[i % foodColors.length] })); food.scale.y = 0.5; food.position.set(plate.position.x, 1.2, plate.position.z); party.add(food); }
      const bulbs: THREE_NS.Mesh[] = [];
      for (let i = 0; i < 16; i += 1) { const bulb = new T.Mesh(new T.SphereGeometry(0.14, 8, 6), new T.MeshBasicMaterial({ color: [0xff3d7f, 0xffd23a, 0x2bb3e0, 0x5ee08a][i % 4] })); bulb.position.set(-6 + i * 0.8, 4 - Math.sin((i / 15) * Math.PI) * 0.8, -3); party.add(bulb); bulbs.push(bulb); }
      for (const x of [-6.4, 6.4]) { const post = new T.Mesh(new T.CylinderGeometry(0.1, 0.1, 4.2), new T.MeshStandardMaterial({ color: 0x5a4030 })); post.position.set(x, 2.1, -3); party.add(post); }
      if (night) { const partyLight = new T.PointLight(0xffc0e0, 60, 40); partyLight.position.set(0, 4, 0); party.add(partyLight); }
      const dancers: { object: THREE_NS.Object3D; update: (dt: number) => void }[] = [];
      (await Promise.all([0, 1].map(() => rigModule.loadDancer(T).catch(() => null)))).forEach((d, i) => {
        if (!d) return; // sin bailarina
        d.object.position.set(-2 + i * 4, 0, -5); d.object.rotation.y = i ? -0.4 : 0.4; party.add(d.object); dancers.push(d);
      });
      const eaters: import("./hero-rig").HeroRig[] = [];
      (await Promise.all([0, 1].map(() => loadRig("hombre").catch(() => null)))).forEach((e, i) => {
        if (!e) return; // sin comensal
        e.object.position.set(-1.5 + i * 3, 0, 1.6); e.object.rotation.y = Math.PI; party.add(e.object); eaters.push(e);
      });
      // Faroles en las calles cercanas: se encienden de noche.
      if (night) {
        for (let i = 0; i < 8; i += 1) {
          const a = (i / 8) * Math.PI * 2, r = 35 + (i % 2) * 30;
          const [lx2, lz2] = nearestLand(spawn.x + Math.cos(a) * r, spawn.z + Math.sin(a) * r);
          const lamp = new T.Group();
          const post = new T.Mesh(new T.CylinderGeometry(0.1, 0.12, 6), new T.MeshStandardMaterial({ color: 0x3b3b3b })); post.position.y = 3; lamp.add(post);
          const head = new T.Mesh(new T.SphereGeometry(0.35, 10, 8), new T.MeshBasicMaterial({ color: 0xffe2a0 })); head.position.y = 6.1; lamp.add(head);
          const light = new T.PointLight(0xffd8a0, 45, 30); light.position.y = 6; lamp.add(light);
          lamp.position.set(lx2, heightAt(lx2, lz2), lz2);
          scene.add(lamp);
        }
      }

      // --- Casas a las que se puede entrar: puertas con 🚪 (familia) o 🎉 (fiesta), cada una con su sala -------------
      type Room = { name: "familia" | "fiesta"; group: THREE_NS.Group; origin: THREE_NS.Vector3; exit: THREE_NS.Vector3; half: { w: number; d: number } };
      const doors: { at: THREE_NS.Vector3; room: Room }[] = [];
      const markerTexture = (icon: string) => { const c = document.createElement("canvas"); c.width = c.height = 128; const x = c.getContext("2d")!; x.fillStyle = "rgba(255,224,138,.45)"; x.beginPath(); x.arc(64, 64, 60, 0, Math.PI * 2); x.fill(); x.font = "80px serif"; x.textAlign = "center"; x.textBaseline = "middle"; x.fillText(icon, 64, 70); return new T.CanvasTexture(c); };
      const doorSprite = markerTexture("🚪"), partySprite = markerTexture("🎉");
      const addDoorMarker = (at: THREE_NS.Vector3, room: Room) => { const sp = new T.Sprite(new T.SpriteMaterial({ map: room.name === "fiesta" ? partySprite : doorSprite, depthWrite: false })); sp.position.copy(at).add(new T.Vector3(0, 3.6, 0)); sp.scale.setScalar(2.2); scene.add(sp); doors.push({ at: at.clone(), room }); };
      let minGround = Infinity;
      for (let i = 0; i < n * n; i += 2) minGround = Math.min(minGround, heights[i]);
      const interiorNews = mission.hazard ? `${EVENT_INFO[mission.hazard].title} en ${mission.name}. ${EVENT_INFO[mission.hazard].order}` : `Hoy en ${mission.name}: un día tranquilo. Revisa que tu familia tenga su mochila de emergencia.`;
      const interior = buildInterior(T, night, interiorNews);
      interior.group.position.set(spawn.x, minGround - 260, spawn.z);
      scene.add(interior.group);
      const roomOrigin = interior.group.position.clone();
      const familyRoom: Room = { name: "familia", group: interior.group, origin: roomOrigin, exit: interior.exit, half: interior.half };
      // En el Perú, el noticiero pasa las noticias de El Niño con su fuente (nino-2026.ts).
      let tvIndex = -1, tvNext = 0;
      const partyRoomParts = buildPartyRoom(T);
      partyRoomParts.group.position.set(spawn.x + 80, minGround - 260, spawn.z);
      scene.add(partyRoomParts.group);
      const partyRoom: Room = { name: "fiesta", group: partyRoomParts.group, origin: partyRoomParts.group.position.clone(), exit: partyRoomParts.exit, half: partyRoomParts.half };
      // Una casa familiar siempre junto a la nave, con la puerta mirando a la nave.
      const [fhx, fhz] = nearestLand(spawn.x - 22, spawn.z - 30);
      const familyHouse = buildFamilyHouse(T);
      familyHouse.position.set(fhx, heightAt(fhx, fhz), fhz);
      scene.add(familyHouse);
      addDoorMarker(new T.Vector3(fhx, heightAt(fhx, fhz + 5.2), fhz + 5.2), familyRoom);
      // Y las casas del pueblo más cercanas a la nave.
      houses.filter((item) => !item.tower).map((item) => ({ item, d: Math.hypot(item.x - spawn.x, item.z - spawn.z) })).sort((a, b) => a.d - b.d).slice(0, 3).forEach(({ item }) => {
        const front = new T.Vector3(item.x, item.y, item.z + item.d / 2 + 1);
        const door = new T.Mesh(new T.BoxGeometry(1.4, 2.4, 0.2), new T.MeshStandardMaterial({ color: 0x6b3f22 }));
        door.position.set(item.x, item.y + 1.2, item.z + item.d / 2 + 0.1);
        scene.add(door);
        addDoorMarker(front, familyRoom);
      });
      // La casa de la fiesta, junto a la fiesta de afuera: adentro hay música, baile y torta.
      const [phx, phz] = nearestLand(party.position.x + 16, party.position.z - 14);
      const partyHouse = buildFamilyHouse(T);
      ((partyHouse.children[0] as THREE_NS.Mesh).material as THREE_NS.MeshStandardMaterial).color.setHex(0xf3c66f);
      partyHouse.position.set(phx, heightAt(phx, phz), phz);
      scene.add(partyHouse);
      addDoorMarker(new T.Vector3(phx, heightAt(phx, phz + 5.2), phz + 5.2), partyRoom);
      const family: import("./hero-rig").HeroRig[] = [];
      const familySpots = [["hombre", 4.5, -2.2, 0.2], ["mujer", -2, 3.6, Math.PI]] as const;
      (await Promise.all(familySpots.map(([gender]) => loadRig(gender).catch(() => null)))).forEach((f, i) => {
        if (!f) return; // sin familia
        const [, fx, fz, ry] = familySpots[i];
        f.object.position.set(roomOrigin.x + fx, roomOrigin.y, roomOrigin.z + fz); f.object.rotation.y = ry; scene.add(f.object); family.push(f);
      });
      // Invitados de la fiesta de adentro: tres bailan samba y dos conversan junto a la torta.
      const roomDancers: { object: THREE_NS.Object3D; update: (dt: number) => void }[] = [];
      const dancerSpots = [[-1.5, -1.2, 0.5], [1.6, -0.8, -0.6], [0, 1.6, Math.PI]] as const;
      (await Promise.all(dancerSpots.map(() => rigModule.loadDancer(T).catch(() => null)))).forEach((d, i) => {
        if (!d) return; // sin bailarina
        const [dx0, dz0, ry] = dancerSpots[i];
        d.object.position.set(partyRoom.origin.x + dx0, partyRoom.origin.y, partyRoom.origin.z + dz0); d.object.rotation.y = ry; scene.add(d.object); roomDancers.push(d);
      });
      const guests: import("./hero-rig").HeroRig[] = [];
      const guestSpots = [["hombre", 4.2, 2.6], ["mujer", 5.8, 2.6]] as const;
      (await Promise.all(guestSpots.map(([gender]) => loadRig(gender).catch(() => null)))).forEach((guest, i) => {
        if (!guest) return; // sin invitado
        const [gender, gx, gz] = guestSpots[i];
        guest.object.position.set(partyRoom.origin.x + gx, partyRoom.origin.y, partyRoom.origin.z + gz); guest.object.rotation.y = gender === "hombre" ? Math.PI / 2 : -Math.PI / 2; scene.add(guest.object); guests.push(guest);
      });
      const KIT: { icon: string; name: string; id: ItemId }[] = [{ icon: "🔦", name: "Linterna", id: "linterna" }, { icon: "💧", name: "Agua", id: "agua" }, { icon: "🩹", name: "Botiquín", id: "botiquin" }, { icon: "📻", name: "Radio a pilas", id: "radio" }];
      const kitItems = KIT.map((item, i) => {
        const sp = new T.Sprite(new T.SpriteMaterial({ map: iconTexture(item.icon), depthWrite: false }));
        const spots: [number, number][] = [[6, 4.5], [-6, -4.5], [5.5, -4.6], [-5.5, 4.2]];
        sp.position.set(roomOrigin.x + spots[i][0], roomOrigin.y + 1.2, roomOrigin.z + spots[i][1]);
        sp.scale.setScalar(0.9); scene.add(sp);
        return { ...item, sprite: sp, taken: false };
      });
      let inside: { door: THREE_NS.Vector3; room: Room } | null = null;
      // Las dos salas están bajo tierra y solo se ven desde adentro. Mientras el héroe está afuera quedan ocultas, con
      // sus luces y su gente: antes sus 6 luces puntuales seguían encendidas siempre (cada píxel del mundo pagaba por
      // ellas) y sus 7 personajes se dibujaban en cada cuadro. Se muestran al entrar y se ocultan al salir, no en cada
      // cuadro: cambiar el número de luces obliga a three.js a cambiar de programa en todos los materiales.
      const showRoom = (room: Room | null) => {
        interior.group.visible = room === familyRoom;
        partyRoomParts.group.visible = room === partyRoom;
        for (const f of family) f.object.visible = room === familyRoom;
        for (const item of kitItems) item.sprite.visible = room === familyRoom && !item.taken;
        for (const d of roomDancers) d.object.visible = room === partyRoom;
        for (const guest of guests) guest.object.visible = room === partyRoom;
      };
      showRoom(null);

      // --- Gente caminando por el lugar --------------------------------------------------------------------------
      // De a dos se encuentran, se saludan y conversan («¡Hola! ¿Cómo estás?» «¡Sí, todo bien!»); a veces dan un saltito.
      const crowd: { rig: import("./hero-rig").HeroRig; goal: THREE_NS.Vector3; pair: number; hopAt: number; nextHop: number }[] = [];
      (await Promise.all([0, 1, 2, 3].map((i) => loadRig(i % 2 ? "mujer" : "hombre").catch(() => null)))).forEach((walker, i) => {
        if (!walker) return; // sin peatón
        const a = hash(i, 41) * Math.PI * 2, r = 20 + hash(i, 42) * 90;
        const [wx, wz] = nearestLand(spawn.x + Math.cos(a) * r, spawn.z + Math.sin(a) * r);
        walker.object.position.set(wx, heightAt(wx, wz), wz);
        walker.object.traverse((o) => { (o as THREE_NS.Mesh).castShadow = true; });
        scene.add(walker.object);
        crowd.push({ rig: walker, goal: walker.object.position.clone(), pair: Math.floor(i / 2), hopAt: -10, nextHop: 6 + hash(i, 43) * 10 });
      });
      // Personas que quedarán atrapadas cuando estalle el evento (se cargan desde ya, ocultas).
      const trapped: { rig: import("./hero-rig").HeroRig; aura: THREE_NS.Mesh; state: "atrapado" | "siguiendo" | "salvo" }[] = [];
      (await Promise.all([0, 1, 2].map((i) => loadRig(i === 1 ? "mujer" : "hombre").catch(() => null)))).forEach((person) => {
        if (!person) return; // sin persona
        person.object.visible = false;
        person.object.traverse((o) => { (o as THREE_NS.Mesh).castShadow = true; });
        scene.add(person.object);
        const aura = new T.Mesh(new T.RingGeometry(1.2, 2, 32), new T.MeshBasicMaterial({ color: 0xff3b3b, transparent: true, opacity: 0.9, side: T.DoubleSide, depthWrite: false }));
        aura.rotation.x = -Math.PI / 2; aura.visible = false; scene.add(aura);
        trapped.push({ rig: person, aura, state: "atrapado" });
      });
      const boat = buildBoat(T);
      boat.visible = false;
      scene.add(boat);
      let floodLevel = -Infinity;
      let rescueStart = 0;
      if (disposed) return;

      // --- Evento extremo según el lugar ------------------------------------------------------------------------
      const reliefRange = terrain.max_elevation_m - terrain.base_elevation_m;
      // Cada lugar tiene su peligro real (o ninguno): no se inventan huaicos donde no ocurren.
      const eventKind: EventKind | null = mission.hazard ?? null;
      // El aviso de El Niño solo va en el Perú: es de lo que tratan las fuentes citadas (nino-2026.ts).
      const nino = mission.country === NINO_COUNTRY && (eventKind === "huaico" || eventKind === "inundacion");
      // Huaico y avalancha bajan por el camino del agua en el relieve: la cinta de lodo o nieve se revela tramo a tramo.
      type FlowRun = { path: [number, number][]; width: (k: number) => number; geometry: THREE_NS.BufferGeometry; quads: number; texture: THREE_NS.Texture; debris: THREE_NS.Group; splash: THREE_NS.Sprite[]; travelled: number; speed: number; front: number; delay: number };
      type LiveEvent = { kind: EventKind; started: number; duration: number; safe: THREE_NS.Vector3; hazard: THREE_NS.Object3D | null; from: THREE_NS.Vector3; dir: THREE_NS.Vector3; done: boolean; flow: FlowRun | null };
      let liveEvent: LiveEvent | null = null;
      let eventTriggered = false;
      let firstFootTime = 0;
      const safeRing = new T.Mesh(new T.RingGeometry(5, 7, 48), new T.MeshBasicMaterial({ color: 0x5ee08a, transparent: true, opacity: 0.85, side: T.DoubleSide, depthWrite: false }));
      safeRing.rotation.x = -Math.PI / 2;
      safeRing.visible = false;
      scene.add(safeRing);
      const safeBeam = new T.Mesh(new T.CylinderGeometry(5, 5, 160, 24, 1, true), new T.MeshBasicMaterial({ color: 0x5ee08a, transparent: true, opacity: 0.18, depthWrite: false, blending: T.AdditiveBlending }));
      safeBeam.visible = false;
      scene.add(safeBeam);
      const gradientAt = (x: number, z: number) => new T.Vector3(heightAt(x + 6, z) - heightAt(x - 6, z), 0, heightAt(x, z + 6) - heightAt(x, z - 6));
      const rocks: { mesh: THREE_NS.Mesh; v: number }[] = [];
      // Las rocas de la erupción comparten una geometría y un material: antes cada roca creaba los suyos (unas tres
      // por segundo durante el aviso) y ninguno se liberaba.
      const rockGeometry = new T.SphereGeometry(1.2, 10, 8);
      const rockMaterial = new T.MeshStandardMaterial({ color: 0x331d14, emissive: 0xff4a10, emissiveIntensity: 1.5 });
      const startEvent = () => {
        eventTriggered = true;
        const hp = heroObj.position.clone();
        let safe = landing.clone();
        let hazard: THREE_NS.Object3D | null = null;
        let from = hp.clone();
        let dir = new T.Vector3(0, 0, 1);
        if (eventKind === "huaico" || eventKind === "inundacion" || eventKind === "calor") {
          // Zona segura: el punto más alto y libre a 60–150 m (en el calor, un toldo de sombra).
          let best = -Infinity;
          for (let i = 0; i < 48; i += 1) {
            const a = (i / 48) * Math.PI * 2, r = 60 + (i % 3) * 45;
            const [x, z] = nearestLand(hp.x + Math.cos(a) * r, hp.z + Math.sin(a) * r);
            const h = heightAt(x, z) + (eventKind === "calor" ? -Math.abs(r - 80) * 0.01 : 0);
            if (h > best && !blocked(x, z)) { best = h; safe = new T.Vector3(x, heightAt(x, z), z); }
          }
        }
        let flowRun: FlowRun | null = null;
        if (eventKind === "huaico" || eventKind === "avalancha") {
          // Quebrada: una celda alta a 90–450 m que drena poca área (no el río) y cuyo camino cuesta abajo pasa cerca
          // del héroe. El lodo sigue ese camino hasta el río (o el borde). Si no hay ninguna, baja en línea recta.
          const heroC = Math.min(Math.max(Math.round((hp.x / size + 0.5) * (n - 1)), 0), n - 1);
          const heroR = Math.min(Math.max(Math.round((hp.z / size + 0.5) * (n - 1)), 0), n - 1);
          const heroH = heights[heroR * n + heroC];
          let best: { cells: number[]; score: number } | null = null;
          for (let r = 1; r < n - 1; r += 2) for (let c = 1; c < n - 1; c += 2) {
            const i = r * n + c;
            const [x, z] = cellXZ(i, n, size);
            const dist = Math.hypot(x - hp.x, z - hp.z);
            if (dist < 90 || dist > 450) continue;
            const rise = heights[i] - heroH;
            if (rise < (eventKind === "huaico" ? 25 : 35)) continue;
            if (eventKind === "huaico" && (flow.acc[i] < 6 || flow.acc[i] >= riverAcc)) continue;
            const cells = traceDown(flow, i, 240, (cell) => riverCells.has(cell));
            if (cells.length < 15) continue;
            let minD = Infinity;
            for (let k = 0; k < cells.length; k += 2) { const [px, pz] = cellXZ(cells[k], n, size); minD = Math.min(minD, Math.hypot(px - hp.x, pz - hp.z)); }
            if (minD > 120) continue;
            const score = rise * 0.4 - minD * 1.5 + Math.min(flow.acc[i], 200) * 0.05;
            if (!best || score > best.score) best = { cells, score };
          }
          let path: [number, number][];
          if (best) path = smoothPath(best.cells.map((i) => cellXZ(i, n, size)), 4);
          else {
            const up = gradientAt(hp.x, hp.z);
            if (up.lengthSq() < 0.01) up.set(0.3, 0, -1);
            up.normalize();
            path = [];
            for (let d = 240; d >= -120; d -= 4) path.push([hp.x + up.x * d, hp.z + up.z * d]);
          }
          // Limitar a ~1,2 km para que el lodo llegue en el tiempo del aviso.
          path = path.slice(0, 300);
          const m = path.length;
          const width = eventKind === "huaico" ? (k: number) => 12 + 14 * (k / m) : (k: number) => 24 + 20 * (k / m);
          const texture = eventKind === "huaico" ? flowTexture(T, [74, 54, 36], [122, 94, 64], false) : flowTexture(T, [236, 241, 247], [206, 215, 228], false);
          flowTextures.push(texture);
          const material = new T.MeshStandardMaterial({ map: texture, color: 0xffffff, roughness: eventKind === "huaico" ? 0.3 : 0.85, metalness: eventKind === "huaico" ? 0.05 : 0 });
          const ribbon = buildRibbon(T, path, width, heightAt, eventKind === "huaico" ? 1.4 : 1.8, material);
          ribbon.mesh.geometry.setDrawRange(0, 0);
          scene.add(ribbon.mesh);
          hazard = ribbon.mesh;
          // Frente del flujo: una ola de lodo con rocas y troncos que ruedan (pequeños: nunca tapan la cámara).
          const debris = new T.Group();
          const frontMat = new T.MeshStandardMaterial({ color: eventKind === "huaico" ? 0x4a3524 : 0xf4f7fb, roughness: eventKind === "huaico" ? 0.35 : 0.9 });
          const surge = new T.Mesh(new T.SphereGeometry(1, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2), frontMat); surge.name = "surge"; debris.add(surge);
          const rockMat = new T.MeshStandardMaterial({ color: eventKind === "huaico" ? 0x5b4a3c : 0xe8eef5, roughness: 1, flatShading: true });
          for (let i = 0; i < 12; i += 1) { const rock = new T.Mesh(new T.DodecahedronGeometry(0.4 + hash(i, 5) * 0.9, 0), rockMat); rock.castShadow = true; rock.userData.seed = i; debris.add(rock); }
          if (eventKind === "huaico") for (let i = 0; i < 4; i += 1) { const log = new T.Mesh(new T.CylinderGeometry(0.18, 0.2, 3, 7), new T.MeshStandardMaterial({ color: 0x5a4030, roughness: 1 })); log.rotation.z = Math.PI / 2; log.userData.seed = 20 + i; debris.add(log); }
          debris.visible = false;
          scene.add(debris);
          const splash: THREE_NS.Sprite[] = [];
          for (let i = 0; i < 10; i += 1) { const sp = new T.Sprite(new T.SpriteMaterial({ map: cloudTexture, color: eventKind === "huaico" ? 0x6b5038 : 0xffffff, transparent: true, opacity: 0, depthWrite: false })); sp.visible = false; scene.add(sp); splash.push(sp); }
          // Velocidad: el frente llega al punto más cercano al héroe unos 20 s después de empezar a bajar.
          const nearest = distanceToPath(path, hp.x, hp.z);
          const speed = Math.min(Math.max((nearest.index * 4) / 20, 6), 22) * (eventKind === "avalancha" ? 1.4 : 1);
          flowRun = { path, width, geometry: ribbon.mesh.geometry, quads: ribbon.quadsPerSegment, texture, debris, splash, travelled: 0, speed, front: 0, delay: 6 };
          from = new T.Vector3(path[0][0], heightAt(path[0][0], path[0][1]), path[0][1]);
          const near = path[Math.min(nearest.index, m - 1)], before = path[Math.max(nearest.index - 1, 0)];
          dir = new T.Vector3(near[0] - before[0], 0, near[1] - before[1]).normalize();
          // Zona segura: alta y lejos del cauce, a 50–170 m del héroe.
          let bestSafe = -Infinity;
          for (let i = 0; i < 48; i += 1) {
            const a = (i / 48) * Math.PI * 2, r = 50 + (i % 3) * 60;
            const [x, z] = nearestLand(hp.x + Math.cos(a) * r, hp.z + Math.sin(a) * r);
            const away = distanceToPath(path, x, z);
            if (away.dist < width(away.index) / 2 + 25 || blocked(x, z)) continue;
            const score = heightAt(x, z) + Math.min(away.dist, 100) * 0.4;
            if (score > bestSafe) { bestSafe = score; safe = new T.Vector3(x, heightAt(x, z), z); }
          }
          if (eventKind === "huaico") {
            // Tormenta en la sierra: cielo gris, menos sol y lluvia alrededor.
            scene.fog = new T.Fog(timeRef.current.night ? 0x0b1024 : 0x8d8a84, 50, 1100);
            uniforms.turbidity.value = 14; uniforms.rayleigh.value = 0.5;
            sun.intensity *= 0.55;
            stormRain.visible = true;
          }
        }
        if (eventKind === "inundacion") {
          const flood = new T.Mesh(new T.PlaneGeometry(size * 2, size * 2), new T.MeshStandardMaterial({ color: 0x7a6a4c, roughness: 0.25, metalness: 0.1, transparent: true, opacity: 0.8 }));
          flood.rotation.x = -Math.PI / 2;
          flood.position.y = hp.y - 1.2;
          scene.add(flood);
          hazard = flood;
          from = new T.Vector3(0, hp.y - 1.2, 0);
        }
        if (eventKind === "erupcion") {
          scene.fog = new T.Fog(0x6d625c, 60, 900);
          uniforms.turbidity.value = 20; uniforms.rayleigh.value = 0.2;
        }
        if (eventKind === "calor") {
          // Ola de calor: aire caliente y luz anaranjada; la reverberación se ve en pantalla (sin temblor).
          scene.fog = new T.Fog(timeRef.current.night ? 0x1a1424 : 0xf2c27a, 60, size * 0.7);
          if (!timeRef.current.night) { uniforms.turbidity.value = 16; uniforms.rayleigh.value = 0.5; uniforms.mieCoefficient.value = 0.02; sun.color.setHex(0xffb35a); sun.intensity = 3.6; }
          const tent = new T.Group();
          const canopy = new T.Mesh(new T.ConeGeometry(8, 3, 4), new T.MeshStandardMaterial({ color: 0x2b8fd6, roughness: 0.6 }));
          canopy.rotation.y = Math.PI / 4; canopy.position.y = 5.5; tent.add(canopy);
          for (const [x, z] of [[-4, -4], [4, -4], [-4, 4], [4, 4]]) { const pole = new T.Mesh(new T.CylinderGeometry(0.15, 0.15, 5), new T.MeshStandardMaterial({ color: 0xdddddd })); pole.position.set(x, 2.5, z); tent.add(pole); }
          tent.position.copy(safe);
          scene.add(tent);
        }
        safeRing.position.copy(safe).add(new T.Vector3(0, 0.3, 0));
        safeBeam.position.copy(safe).add(new T.Vector3(0, 80, 0));
        safeRing.visible = safeBeam.visible = true;
        speak(eventKind === "erupcion" ? "¡Ayuda! ¡El volcán! ¡Corran!" : eventKind === "avalancha" ? "¡Avalancha! ¡Ayuda!" : eventKind === "calor" ? "¡Ayuda! ¡Hace demasiado calor!" : "¡Ayuda! ¡Ayuda! ¡Viene el agua!", { pitch: 1.35, rate: 1.15 });
        sfx("boom");
        voiceClip("ayuda");
        // (Si la persona ya salió de la misión, estas voces diferidas no deben sonar en el globo.)
        window.setTimeout(() => { if (!disposed) voiceClip("vamos-a-salir"); }, 2200);
        window.setTimeout(() => { if (!disposed) speak("¡Tranquilos! ¡Vamos a salir de esto! ¡Síganme!", { pitch: 0.75, rate: 1.12, who: "heroe" }); }, 2400);
        // Operación de rescate: 3 personas atrapadas alrededor, a rescatar y llevar a la zona segura.
        trapped.forEach((person, i) => {
          const a = (i / 3) * Math.PI * 2 + hash(i, 77) * 1.2, r = 45 + i * 25;
          let [px, pz] = eventKind === "inundacion" ? [hp.x + Math.cos(a) * r, hp.z + Math.sin(a) * r] : nearestLand(hp.x + Math.cos(a) * r, hp.z + Math.sin(a) * r);
          if (flowRun) {
            // En el huaico o la avalancha, las personas están en la orilla del cauce, por donde va a pasar el flujo.
            const { path } = flowRun;
            const ci = distanceToPath(path, hp.x, hp.z).index;
            const k = Math.min(Math.max(ci + [-12, 2, 14][i], 1), path.length - 2);
            const [ax, az] = path[k - 1], [bx, bz] = path[k + 1];
            const tl = Math.hypot(bx - ax, bz - az) || 1;
            const side = i % 2 ? 1 : -1, off = 4 + hash(i, 8) * 3;
            [px, pz] = nearestLand(path[k][0] + (-(bz - az) / tl) * side * off, path[k][1] + ((bx - ax) / tl) * side * off);
          }
          person.rig.object.position.set(px, heightAt(px, pz), pz);
          person.rig.object.visible = true;
          person.aura.visible = true;
          person.state = "atrapado";
        });
        if (eventKind === "inundacion") {
          const [bx, bz] = [hp.x + 8, hp.z - 6];
          boat.position.set(bx, heightAt(bx, bz) + 0.3, bz);
          boat.visible = true;
          vehicles.push({ obj: boat, speed: 0, heading: 0, max: 34, accel: 30, lift: 0, name: "bote" });
        }
        rescueStart = elapsed;
        const kind = eventKind as EventKind;
        const ev: LiveEvent = { kind, started: elapsed, duration: kind === "avalancha" ? 50 : 60, safe, hazard, from, dir, done: false, flow: flowRun };
        liveEvent = ev;
        setAlert({ kind, left: ev.duration, nino, rescued: 0, total: trapped.length });
      };
      startEventRef.current = () => { if (eventKind && !eventTriggered && landed) startEvent(); };

      // --- Lo que dicen las personas (frases del juego; las que tienen cifras salen de los datos de la misión) -----
      const fmt1 = (v: number, d = 1) => v.toLocaleString("es-PE", { minimumFractionDigits: d, maximumFractionDigits: d });
      const tempLine = mission.temperature?.significant && mission.temperature.slope_per_year != null
        ? `Dicen que aquí la temperatura ${mission.temperature.slope_per_year > 0 ? "sube" : "baja"} ${fmt1(Math.abs(mission.temperature.slope_per_year * 10), 2)} °C por década…`
        : "Los científicos dicen que aún no hay datos suficientes para saber si aquí se calienta.";
      const townLines = [
        tempLine,
        mission.rain?.mean != null ? `Aquí llueven en promedio ${fmt1(mission.rain.mean)} mm al día, según NASA.` : "Ojalá midieran mejor la lluvia aquí.",
        `¡${hero?.name ?? "Ese héroe"} vino de la Luna! 😮`,
        "Cuando llueve fuerte, no hay que acercarse a las quebradas.",
        `Vivimos a ${Math.round(terrain.base_elevation_m + (heightAt(0, 0) / exaggeration))} metros de altura, dice el escáner.`,
        "¿Tú también reciclas? Yo sí ♻",
      ];
      const heroName = hero?.name ?? "héroe";
      const chats = mission.country === NINO_COUNTRY ? NINO_CHATS : PLAIN_CHATS;
      type Talk = { phase: "pasea" | "se-junta" | "conversa"; next: number; start: number; lines: string[] };
      const talks: Talk[] = [0, 1].map((k) => ({ phase: "pasea", next: 10 + k * 14, start: 0, lines: chats[k % chats.length] }));
      const LINE_SECONDS = 2.8;
      const buddyLines = ["¡Sigue la flecha amarilla!", "¡Allá hay alguien que necesita ayuda!", "¡Recoge protección para el clima!", "¡Con la camioneta llegamos más rápido!"];

      // --- Entrada: la nave baja del cielo hasta su lugar ------------------------------------------------------
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const landDuration = reduced ? 0 : 6;
      const shipStart = landing.clone().add(new T.Vector3(-260, 420, 520));
      let elapsed = 0;
      // Siempre empieza en falso: con «reducir movimiento» (duración 0) aterriza en el primer cuadro. Antes empezaba
      // en verdadero y nunca pasaba por el aterrizaje: el héroe quedaba invisible y la pantalla en «Aterrizando».
      let landed = false;
      let heading = Math.PI;
      let yaw = 0; // la cámara mira al norte al empezar
      const held = new Set<string>();
      let target: THREE_NS.Vector3 | null = null;
      const keys: Record<string, [number, number]> = { ArrowUp: [0, 1], KeyW: [0, 1], ArrowDown: [0, -1], KeyS: [0, -1], ArrowLeft: [-1, 0], KeyA: [-1, 0], ArrowRight: [1, 0], KeyD: [1, 0], KeyQ: [0, 0], KeyR: [0, 0], ShiftLeft: [0, 0], ShiftRight: [0, 0] };
      const onKey = (event: KeyboardEvent) => {
        if (!(event.code in keys) || typing(event)) return;
        // Los atajos del navegador (Ctrl+S, Alt+←…) no son del juego; al soltar la tecla sí se atiende siempre.
        if (event.type === "keydown" && (event.ctrlKey || event.metaKey || event.altKey)) return;
        event.preventDefault();
        if (event.type === "keydown") { held.add(event.code); target = null; } else held.delete(event.code);
      };
      const raycaster = new T.Raycaster();
      // Arrastrar con el mouse (o el dedo) gira la cámara; un toque sin arrastrar lleva al héroe hasta ahí.
      let dragging = false, dragMoved = 0, lastX = 0;
      const onPointerDown = (event: PointerEvent) => { dragging = true; dragMoved = 0; lastX = event.clientX; };
      const onPointerMove = (event: PointerEvent) => {
        if (!dragging) return;
        const dxp = event.clientX - lastX;
        lastX = event.clientX;
        dragMoved += Math.abs(dxp);
        yaw -= dxp * 0.006;
      };
      const onPointerUp = () => { dragging = false; tabFocus = false; };
      canvas.addEventListener("pointerdown", onPointerDown);
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
      const onClick = (event: MouseEvent) => {
        if (!landed || dragMoved > 6) return;
        const rect = canvas.getBoundingClientRect();
        raycaster.setFromCamera(new T.Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1), camera);
        const hit = raycaster.intersectObject(ground)[0];
        if (hit) target = hit.point.clone();
      };
      window.addEventListener("keydown", onKey);
      window.addEventListener("keyup", onKey);
      window.addEventListener("keydown", onAction); // recién aquí: ya no quedan esperas y todo lo que usa existe
      canvas.addEventListener("click", onClick);

      const resize = () => {
        const w = canvas.clientWidth, h = canvas.clientHeight;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        // El panel de la misión tapa una parte: se corre el centro de la vista hacia el espacio libre.
        const { panelRight: pr, panelBottom: pb } = propsRef.current;
        camera.setViewOffset(w, h, pr / 2, pb / 2, w, h);
        camera.updateProjectionMatrix();
      };
      resize();
      const observer = new ResizeObserver(resize);
      observer.observe(canvas);

      const clock = new T.Clock();
      const camPos = new T.Vector3();
      const lookAt = new T.Vector3();
      const temp = new T.Vector3();
      let lastPrompt = "";
      let overlayClock = 0;
      let lastScan = 0;
      let lastHud = 0;
      let lastAlert = 0;
      let lastZones = -1;
      let zones: [number, number, number, number][] = []; // izquierda, arriba, derecha, abajo (en píxeles del lienzo)
      let frame = 0;
      setStatus("listo");
      const tick = () => {
        const dt = Math.min(clock.getDelta(), 0.05);
        elapsed += dt;
        if (!landed) {
          const t = landDuration ? Math.min(elapsed / landDuration, 1) : 1;
          const ease = 1 - Math.pow(1 - t, 3);
          ship.position.lerpVectors(shipStart, landing, ease);
          ship.rotation.set(0, Math.PI * 0.82, (1 - ease) * 0.25);
          camPos.copy(ship.position).add(temp.set(-60 * (1 - ease) + 30, 26 + 30 * (1 - ease), 70));
          camera.position.lerp(camPos, elapsed < 0.1 ? 1 : 0.08);
          camera.lookAt(ship.position);
          if (t >= 1) { landed = true; heroObj.visible = true; setPhase("suelo"); setWelcome(true); sfx("fanfare"); voiceClip("bienvenido"); }
        } else {
          if (takeoff) {
            // Despegue: la nave sube y se aleja; luego se vuelve al globo para elegir otro lugar.
            const k = elapsed - takeoff;
            ship.position.y = landing.y + k * k * 14;
            ship.position.x = landing.x - k * k * 6;
            camera.position.lerp(temp.set(landing.x + 40, landing.y + 25 + k * 10, landing.z + 50), 0.05);
            camera.lookAt(ship.position);
            if (k > 2.8 && !leftRef.current) { leftRef.current = true; propsRef.current.onLeave(); }
            renderer.render(scene, camera);
            frame = requestAnimationFrame(tick);
            return;
          }
          ship.position.y = landing.y + Math.sin(elapsed * 1.6) * 0.15;
          // Movimiento relativo a la cámara: arriba avanza hacia donde mira.
          // La cámara mira hacia (−sin yaw, −cos yaw): «arriba» avanza en esa dirección y «derecha» va a su derecha.
          let moving = false;
          if (driving) {
            // Manejo: adelante acelera, atrás frena o retrocede, izquierda y derecha giran (más con velocidad).
            const v = driving;
            const throttle = (held.has("ArrowUp") || held.has("KeyW") ? 1 : 0) - (held.has("ArrowDown") || held.has("KeyS") ? 1 : 0);
            const steer = (held.has("ArrowLeft") || held.has("KeyA") ? 1 : 0) - (held.has("ArrowRight") || held.has("KeyD") ? 1 : 0);
            v.speed = Math.min(v.max, Math.max(-v.max * 0.35, (v.speed + throttle * v.accel * dt) * (1 - 0.7 * dt)));
            v.heading += steer * dt * 1.7 * Math.min(Math.abs(v.speed) / 12, 1) * Math.sign(v.speed || 1);
            const nx = v.obj.position.x + Math.sin(v.heading) * v.speed * dt, nz = v.obj.position.z + Math.cos(v.heading) * v.speed * dt;
            const limit = size * 0.45;
            const isBoat = v.name === "bote";
            const floats = (x: number, z: number) => coverAt(x, z) === 80 || floodLevel > heightAt(x, z) - 0.5;
            if (Math.abs(nx) < limit && Math.abs(nz) < limit && (isBoat ? floats(nx, nz) : walkOnWater || coverAt(nx, nz) !== 80) && !blocked(nx, nz)) { v.obj.position.x = nx; v.obj.position.z = nz; }
            else v.speed = 0;
            v.obj.position.y = isBoat ? Math.max(heightAt(v.obj.position.x, v.obj.position.z), floodLevel) + 0.25 + Math.sin(elapsed * 2.5) * 0.12 : heightAt(v.obj.position.x, v.obj.position.z);
            v.obj.rotation.y = v.heading;
            v.obj.children.forEach((child) => { if (child.name === "wheel") child.rotation.x += v.speed * dt * 2; if (child.name === "siren") child.visible = Math.floor(elapsed * 4) % 2 === 0; });
            heroObj.position.copy(v.obj.position);
            heading = v.heading;
            yaw += (((v.heading + Math.PI - yaw + Math.PI * 3) % (Math.PI * 2)) - Math.PI) * dt * 3;
          }
          let dx = 0, dz = 0, right = 0, forward = 0;
          if (!driving) held.forEach((code) => { right += keys[code][0]; forward += keys[code][1]; });
          // Movimiento relativo a la cámara (8 direcciones, respuesta inmediata); Q y R o arrastrar giran la vista.
          // Q gira a la izquierda y R a la derecha (E, la tecla vecina, ya es del vehículo y de las puertas): antes
          // con el teclado solo se podía girar hacia un lado.
          if (held.has("KeyQ")) yaw += dt * 2.2;
          if (held.has("KeyR")) yaw -= dt * 2.2;
          if (right || forward) {
            dx = -Math.sin(yaw) * forward + Math.cos(yaw) * right;
            dz = -Math.cos(yaw) * forward - Math.sin(yaw) * right;
          } else if (target && !driving) {
            const gap = Math.hypot(target.x - heroObj.position.x, target.z - heroObj.position.z);
            if (gap < 1.5) target = null; else { dx = (target.x - heroObj.position.x) / gap; dz = (target.z - heroObj.position.z) / gap; }
          }
          moving = !!(dx || dz);
          if (moving && !driving) {
            const len = Math.hypot(dx, dz);
            // En el agua se vadea más lento; solo el borde de la zona y las casas detienen al héroe.
            const swimming = floodLevel > heightAt(heroObj.position.x, heroObj.position.z) + 0.6;
            const sprint = held.has("ShiftLeft") || held.has("ShiftRight") || flyUntil > elapsed ? 1.9 : 1;
            const speed = (swimming ? 9 : coverAt(heroObj.position.x, heroObj.position.z) === 80 && !walkOnWater ? 10 : 26) * sprint;
            const nx = heroObj.position.x + (dx / len) * speed * dt, nz = heroObj.position.z + (dz / len) * speed * dt;
            const limit = size * 0.47;
            if (inside) {
              const { origin, half } = inside.room;
              heroObj.position.x = Math.min(Math.max(nx, origin.x - half.w), origin.x + half.w);
              heroObj.position.z = Math.min(Math.max(nz, origin.z - half.d), origin.z + half.d);
            } else if (Math.abs(nx) < limit && Math.abs(nz) < limit && !blocked(nx, nz)) { heroObj.position.x = nx; heroObj.position.z = nz; }
            else { target = null; if (Math.abs(nx) >= limit || Math.abs(nz) >= limit) setPickupNote("Este es el borde de la zona de la misión"); }
            heading = Math.atan2(dx, dz);
            // Yendo con un clic, la cámara gira despacio para quedar detrás del héroe; con el teclado la maneja el jugador.
            if (!forward && !right) {
              const behind = Math.atan2(-dx, -dz);
              yaw += (((behind - yaw + Math.PI * 3) % (Math.PI * 2)) - Math.PI) * dt * 1.5;
            }
          }
          // Salto con gravedad.
          if (flyUntil > elapsed) { jumpY += (16 - jumpY) * dt * 2; jumpV = 0; }
          else if (jumpV !== 0 || jumpY > 0) { jumpV -= 26 * dt; jumpY = Math.max(jumpY + jumpV * dt, 0); if (jumpY === 0) jumpV = 0; }
          if (inside) heroObj.position.y = inside.room.origin.y + jumpY;
          else if (!driving) {
            const ground = heightAt(heroObj.position.x, heroObj.position.z);
            // Nadar: si la inundación cubre el suelo, el héroe flota y avanza más lento.
            heroObj.position.y = floodLevel > ground + 0.6 ? floodLevel - 1.2 + Math.sin(elapsed * 3) * 0.15 : ground + jumpY;
          }
          heroObj.rotation.y += (((heading - heroObj.rotation.y + Math.PI * 3) % (Math.PI * 2)) - Math.PI) * 0.35;
          rig?.play(moving ? "Run" : "Idle");
          // Compañero: te sigue a unos pasos.
          if (buddy) {
            buddy.object.visible = !driving;
            const bp = buddy.object.position;
            const goal = temp.set(heroObj.position.x - Math.sin(heading) * 3.5 + Math.cos(heading) * 2, 0, heroObj.position.z - Math.cos(heading) * 3.5 - Math.sin(heading) * 2);
            const gap = Math.hypot(goal.x - bp.x, goal.z - bp.z);
            if (gap > 0.6) { const step = Math.min(gap, 25 * dt); bp.x += ((goal.x - bp.x) / gap) * step; bp.z += ((goal.z - bp.z) / gap) * step; buddy.object.rotation.y = Math.atan2(goal.x - bp.x, goal.z - bp.z); }
            bp.y = heightAt(bp.x, bp.z);
            buddy.play(gap > 1.2 ? "Run" : "Idle");
            buddy.update(dt);
          }
          // Perrito: herido, gime y pide ayuda; ya curado, te sigue moviendo la cola.
          const tail = dog.getObjectByName("tail"), headD = dog.getObjectByName("head");
          if (dogState === "herido") {
            dogCross.position.copy(dog.position).add(temp.set(0, 2.6 + Math.sin(elapsed * 3) * 0.2, 0));
            if (headD) headD.rotation.x = Math.sin(elapsed * 2) * 0.1;
          } else {
            const goal = temp.set(heroObj.position.x + Math.cos(heading) * 2.2, 0, heroObj.position.z - Math.sin(heading) * 2.2);
            const gap = Math.hypot(goal.x - dog.position.x, goal.z - dog.position.z);
            if (driving) { dog.position.set(goal.x, 0, goal.z); dog.visible = false; }
            else { dog.visible = true; if (gap > 0.8) { const step = Math.min(gap, 27 * dt); dog.position.x += ((goal.x - dog.position.x) / gap) * step; dog.position.z += ((goal.z - dog.position.z) / gap) * step; dogHeading = Math.atan2(goal.x - dog.position.x, goal.z - dog.position.z); } }
            dog.position.y = heightAt(dog.position.x, dog.position.z) + (gap > 0.8 ? Math.abs(Math.sin(elapsed * 14)) * 0.12 : 0);
            dog.rotation.y += (((dogHeading - dog.rotation.y + Math.PI * 3) % (Math.PI * 2)) - Math.PI) * 0.25;
            const swing = gap > 0.8 ? Math.sin(elapsed * 14) * 0.7 : 0;
            dog.children.forEach((child) => { if (child.name === "legA") child.rotation.x = swing; if (child.name === "legB") child.rotation.x = -swing; });
            if (tail) tail.rotation.z = Math.sin(elapsed * 12) * 0.6;
            if (elapsed > nextBark) { nextBark = elapsed + 12 + Math.random() * 10; dogSound("ladrido"); }
          }
          // Dentro de la casa: la familia y la mochila de emergencia.
          family.forEach((f) => { f.play("Idle"); if (inside?.room.name === "familia") f.update(dt); });
          // Noticiero: en el Perú rota las noticias de El Niño con su fuente cada 8 s.
          if (inside?.room.name === "familia" && mission.country === NINO_COUNTRY && elapsed > tvNext) {
            tvNext = elapsed + 8;
            tvIndex = (tvIndex + 1) % NINO_FACTS.length;
            interior.setNews(NINO_FACTS[tvIndex].text, ninoCredit(NINO_FACTS[tvIndex]));
          }
          // Fiesta de adentro: baile, bola de espejos, luces que giran y baldosas que laten con la música.
          if (inside?.room.name === "fiesta") {
            roomDancers.forEach((d) => d.update(dt));
            guests.forEach((guest, i) => { guest.play("Idle"); guest.update(dt); guest.object.position.y = partyRoom.origin.y + Math.max(0, Math.sin(elapsed * 6 + i * 1.7)) * (Math.floor(elapsed / 4 + i) % 3 === 0 ? 0.5 : 0); });
            partyRoomParts.ball.rotation.y += dt * 1.2;
            partyRoomParts.spots.forEach((light, i) => { const a = elapsed * (0.9 + i * 0.35) + i * 2.1; light.position.set(Math.cos(a) * 4.5, 3, Math.sin(a) * 3.5); });
            partyRoomParts.bulbs.forEach((bulb, i) => { bulb.visible = Math.floor(elapsed * 3 + i) % 3 !== 0; });
            partyRoomParts.tiles.forEach((tile, i) => { ((tile.material as THREE_NS.MeshStandardMaterial).emissiveIntensity = 0.1 + Math.max(0, Math.sin(elapsed * 4.2 + i * 0.8)) * 0.5); });
          }
          if (inside?.room.name === "familia") {
            kitItems.forEach((item) => {
              if (item.taken) return;
              item.sprite.position.y = roomOrigin.y + 1.2 + Math.sin(elapsed * 2 + item.sprite.position.x) * 0.15;
              if (Math.hypot(item.sprite.position.x - heroObj.position.x, item.sprite.position.z - heroObj.position.z) < 1.6) {
                item.taken = true; item.sprite.visible = false; sfx("powerup");
                addToBag(item.id);
                const left = kitItems.filter((k) => !k.taken).length;
                setPickupNote(left ? `${item.icon} ${item.name} a la mochila (tecla ${keyOf(item.id)} para sacarla) · faltan ${left}` : "🎒 ¡Mochila de emergencia lista! +150 XP · usa las teclas 1–4");
                if (!left) { sfx("fanfare"); setKitDone(true); }
              }
            });
          }
          // Peatones: pasean entre puntos cercanos; cada pareja, de vez en cuando, se junta a conversar.
          talks.forEach((talk, k) => {
            const pair = crowd.filter((person) => person.pair === k);
            if (pair.length < 2) return;
            const [a, b] = pair;
            if (talk.phase === "pasea" && elapsed > talk.next) {
              const [mx, mz] = nearestLand((a.rig.object.position.x + b.rig.object.position.x) / 2, (a.rig.object.position.z + b.rig.object.position.z) / 2);
              a.goal.set(mx - 0.9, 0, mz); b.goal.set(mx + 0.9, 0, mz);
              talk.phase = "se-junta"; talk.start = elapsed;
            } else if (talk.phase === "se-junta" && (Math.hypot(a.goal.x - a.rig.object.position.x, a.goal.z - a.rig.object.position.z) < 0.6 && Math.hypot(b.goal.x - b.rig.object.position.x, b.goal.z - b.rig.object.position.z) < 0.6 || elapsed - talk.start > 40)) {
              talk.phase = "conversa"; talk.start = elapsed;
            } else if (talk.phase === "conversa" && elapsed - talk.start > talk.lines.length * LINE_SECONDS + 1) {
              talk.phase = "pasea"; talk.next = elapsed + 20 + hash(elapsed, k) * 12;
              talk.lines = chats[(chats.indexOf(talk.lines) + 1) % chats.length];
            }
          });
          for (const person of crowd) {
            const pos = person.rig.object.position;
            const talk = talks[person.pair];
            const partner = crowd.find((other) => other !== person && other.pair === person.pair);
            if (talk?.phase === "conversa" && partner) {
              // Conversando: se miran y se quedan quietos.
              person.rig.object.rotation.y = Math.atan2(partner.rig.object.position.x - pos.x, partner.rig.object.position.z - pos.z);
              pos.y = heightAt(pos.x, pos.z);
              if (camera.position.distanceTo(pos) < 150) { person.rig.play("Idle"); person.rig.update(dt); }
              continue;
            }
            const gap = Math.hypot(person.goal.x - pos.x, person.goal.z - pos.z);
            if (gap < 0.6) {
              if (talk?.phase !== "se-junta") {
                const a = Math.random() * Math.PI * 2, r = 10 + Math.random() * 40;
                const [gx, gz] = nearestLand(pos.x + Math.cos(a) * r, pos.z + Math.sin(a) * r);
                person.goal.set(gx, 0, gz);
              }
            } else {
              const step = Math.min(gap, 1.6 * dt);
              pos.x += ((person.goal.x - pos.x) / gap) * step; pos.z += ((person.goal.z - pos.z) / gap) * step;
              person.rig.object.rotation.y = Math.atan2(person.goal.x - pos.x, person.goal.z - pos.z);
            }
            // Saltito de vez en cuando.
            if (elapsed > person.nextHop) { person.hopAt = elapsed; person.nextHop = elapsed + 9 + Math.random() * 12; }
            const hop = elapsed - person.hopAt < 0.55 ? Math.sin(((elapsed - person.hopAt) / 0.55) * Math.PI) * 0.9 : 0;
            pos.y = heightAt(pos.x, pos.z) + hop;
            if (camera.position.distanceTo(pos) < 150) { person.rig.play(gap < 0.6 ? "Idle" : "Walk"); person.rig.update(dt); }
          }
          // Contaminadores detenidos: te siguen hasta el centro de reciclaje, donde los capacitan.
          for (const index of following) {
            const polluter = polluters[index];
            if (!polluter.rig) continue;
            const pos = polluter.rig.object.position;
            const goal = temp.set(heroObj.position.x - Math.sin(heading) * 5, 0, heroObj.position.z - Math.cos(heading) * 5);
            const gap = Math.hypot(goal.x - pos.x, goal.z - pos.z);
            if (driving) { pos.set(goal.x, 0, goal.z); polluter.rig.object.visible = false; }
            else if (gap > 1) { polluter.rig.object.visible = true; const step = Math.min(gap, 24 * dt); pos.x += ((goal.x - pos.x) / gap) * step; pos.z += ((goal.z - pos.z) / gap) * step; polluter.rig.object.rotation.y = Math.atan2(goal.x - pos.x, goal.z - pos.z); }
            pos.y = heightAt(pos.x, pos.z);
            polluter.rig.play(gap > 1.5 ? "Run" : "Idle");
            if (Math.hypot(refuge.position.x - pos.x, refuge.position.z - pos.z) < 16) {
              following.delete(index);
              trained.add(index);
              polluter.rig.object.visible = true;
              polluter.rig.object.position.set(refuge.position.x + (trained.size * 3 - 4), refuge.position.y, refuge.position.z + 6);
              polluter.rig.play("Idle");
              setPickupNote("♻ ¡Capacitado en el centro de reciclaje! Ahora ayuda a cuidar su pueblo. +150 XP");
              setTrainedCount(trained.size);
            }
          }
          // Objetos: se recogen al pasar cerca.
          for (const item of pickups) {
            if (item.taken) continue;
            item.sprite.position.y = item.base + Math.sin(elapsed * 2 + item.base) * 0.4;
            if (Math.hypot(item.sprite.position.x - heroObj.position.x, item.sprite.position.z - heroObj.position.z) < 3.5) {
              item.taken = true;
              item.sprite.visible = false;
              const id = item.kind as ItemId;
              addToBag(id);
              sfx("powerup");
              setPickupNote(`${infoOf(id).icon} ${infoOf(id).name} a la mochila · pulsa ${keyOf(id)} para sacarlo`);
            }
          }
          // Peligro del clima: sin protección, baja la salud; al llegar a 0 vuelves a la nave.
          // Protegido mientras lleva en la mano (o puesto) el objeto que pide el clima.
          const exposed = protectionFor && equipped !== protectionFor && !((protectedUntil[protectionFor] ?? 0) > elapsed);
          if (exposed) health = Math.max(0, health - 0.8 * dt);
          if (health === 0) {
            health = 100;
            heroObj.position.copy(spawn);
            setPickupNote("Te desmayaste por el clima: vuelves a la nave. Busca protección.");
          }
          // Cámara en tercera persona, detrás y arriba del héroe.
          const drone = droneView && !inside;
          const camDist = inside ? 7.5 : drone ? 75 : driving ? 20 : 14, camHeight = inside ? 3.6 : drone ? 95 : driving ? 9 : 7.5;
          camPos.set(heroObj.position.x + Math.sin(yaw) * camDist, heroObj.position.y + camHeight, heroObj.position.z + Math.cos(yaw) * camDist);
          if (inside) {
            const { origin, half } = inside.room;
            camPos.x = Math.min(Math.max(camPos.x, origin.x - half.w - 0.2), origin.x + half.w + 0.2);
            camPos.z = Math.min(Math.max(camPos.z, origin.z - half.d - 0.2), origin.z + half.d + 0.2);
            camPos.y = Math.min(camPos.y, origin.y + (inside.room.name === "fiesta" ? 4.2 : 3.9));
          } else camPos.y = Math.max(camPos.y, heightAt(camPos.x, camPos.z) + 2.5, floodLevel + 2.5);
          camera.position.lerp(camPos, 0.12);
          lookAt.copy(heroObj.position).add(temp.set(0, 2.2, 0));
          camera.lookAt(lookAt);
          // Vecinos en peligro: cerca de uno aparece el aviso para usar el lanzador de ayuda.
          if (dogState === "herido" && near(dog.position, 20)) { if (lastPrompt !== "perro") { lastPrompt = "perro"; setPrompt(DOG); dogSound("gemido"); } }
          const nearIndex = dogState === "herido" && near(dog.position, 20) ? -1 : spots.findIndex((spot, i) => !npcs[i].saved && near(spot.position, 34));
          const nearPolluter = nearIndex === -1 ? polluters.findIndex((item) => !item.stopped && near(item.position, 34)) : -1;
          const nearId = nearIndex !== -1 ? spots[nearIndex].item.id : nearPolluter !== -1 ? `cont-${nearPolluter}` : "";
          if (!(dogState === "herido" && near(dog.position, 20)) && nearId !== lastPrompt) { lastPrompt = nearId; if (nearIndex !== -1) voiceClip(nearIndex % 2 ? "necesito-ayuda" : "hola-heroe"); setPrompt(nearIndex !== -1 ? spots[nearIndex].item : nearPolluter !== -1 ? POLLUTER : null); }
        }
        // Proyectil en vuelo: arco hasta el vecino; al llegar, el vecino queda a salvo y el héroe le explica el dato.
        if (flying) {
          flying.t = Math.min(flying.t + dt / 0.7, 1);
          shot.visible = true;
          shot.position.lerpVectors(flying.from, flying.to, flying.t);
          shot.position.y += Math.sin(flying.t * Math.PI) * 6;
          if (flying.t >= 1 && flying.spotIndex === -2) {
            dogState = "amigo";
            dog.rotation.set(0, 0, 0);
            dogCross.visible = false;
            setPickupNote("🐶 ¡Curaste al perrito! Ahora es tu compañero. +100 XP");
            dogSound("ladrido");
            setPrompt(null); lastPrompt = "";
            shot.visible = false; flying = null;
          } else if (flying.t >= 1 && flying.polluter !== -1) {
            const polluter = polluters[flying.polluter];
            polluter.stopped = true;
            following.add(flying.polluter);
            polluter.smoke.forEach((puff) => { puff.visible = false; });
            (polluter.aura.material as THREE_NS.MeshBasicMaterial).color.setHex(0x5ee08a);
            setSpeech(POLLUTER_DONE);
            setStoppedCount((count) => count + 1);
            setPrompt(null);
            lastPrompt = "";
            shot.visible = false;
            flying = null;
          } else if (flying && flying.t >= 1) {
            const npc = npcs[flying.spotIndex];
            npc.saved = true;
            (npc.aura.material as THREE_NS.MeshBasicMaterial).color.setHex(0x5ee08a);
            (npc.beam.material as THREE_NS.MeshBasicMaterial).color.setHex(0x5ee08a);
            const item = spots[flying.spotIndex].item;
            setSpeech(item);
            setSavedCount((count) => count + 1);
            sfx("fanfare");
            voiceClip("gracias");
            speak("¡Gracias, héroe!", { pitch: 1.25 });
            setPrompt(null);
            lastPrompt = "";
            propsRef.current.onReach(item.id);
            shot.visible = false;
            flying = null;
          }
        }
        // Evento extremo: arranca a los 25 s en tierra (o tras salvar al primer vecino) y dura unos segundos.
        if (landed && !firstFootTime) firstFootTime = elapsed;
        if (eventKind && landed && !eventTriggered && (elapsed - firstFootTime > 25 || npcs.some((npc) => npc.saved))) startEvent();
        if (liveEvent && !liveEvent.done) {
          const ev = liveEvent;
          const t = (elapsed - ev.started) / ev.duration;
          const hp = heroObj.position;
          const inSafe = Math.hypot(ev.safe.x - hp.x, ev.safe.z - hp.z) < 8;
          safeRing.scale.setScalar(1 + Math.sin(elapsed * 5) * 0.08);
          let hit = false;
          let shake = ev.kind === "erupcion" ? 0.12 : 0;
          if (ev.flow) {
            // El lodo (o la nieve) baja por la quebrada: avanza el frente, se revela la cinta y ruedan rocas y troncos.
            const fr = ev.flow;
            const since = elapsed - ev.started;
            if (since > fr.delay) {
              if (fr.travelled === 0) { sfx("boom"); setPickupNote(ev.kind === "huaico" ? "🟤 ¡Se escucha un ruido fuerte en la quebrada! ¡Ya baja el huaico!" : "❄️ ¡Se desprendió la nieve! ¡Ya baja la avalancha!"); }
              fr.travelled += fr.speed * Math.min(1, (since - fr.delay) / 4) * dt;
            }
            const m = fr.path.length;
            fr.front = Math.min(Math.floor(fr.travelled / 4), m - 1);
            fr.geometry.setDrawRange(0, fr.front * fr.quads * 6);
            fr.texture.offset.y -= dt * (ev.kind === "huaico" ? 0.9 : 1.3);
            const [fx, fz] = fr.path[fr.front];
            const [px0, pz0] = fr.path[Math.max(fr.front - 1, 0)];
            const fy = heightAt(fx, fz);
            const w = fr.width(fr.front);
            fr.debris.visible = fr.front > 0 && fr.front < m - 1;
            fr.debris.position.set(fx, fy, fz);
            fr.debris.rotation.y = Math.atan2(fx - px0, fz - pz0);
            fr.debris.children.forEach((child) => {
              if (child.name === "surge") { child.scale.set(w * 0.5, 1.8 + Math.sin(elapsed * 6) * 0.3, 3.5); return; }
              const seed = child.userData.seed as number;
              child.position.set((hash(seed, 1) - 0.5) * w * 0.8, 0.6 + Math.abs(Math.sin(elapsed * 4 + seed)) * 1.6, (hash(seed, 3) - 0.5) * 6);
              child.rotation.x += dt * (3 + (seed % 3)); child.rotation.y += dt * 1.5;
            });
            fr.splash.forEach((sp, i) => {
              const life = (elapsed * 0.9 + i / fr.splash.length) % 1;
              sp.position.set(fx + (hash(i, 4) - 0.5) * w, fy + 1 + life * 6, fz + (hash(i, 6) - 0.5) * 6);
              sp.scale.setScalar(2 + life * 3);
              const tooClose = camera.position.distanceTo(sp.position) < 12;
              sp.visible = fr.debris.visible && !tooClose;
              (sp.material as THREE_NS.SpriteMaterial).opacity = 0.55 * (1 - life);
            });
            // Peligro: estar dentro del cauce por donde ya pasó el flujo (volando o en la zona segura no cuenta).
            const inFlow = distanceToPath(fr.path, hp.x, hp.z, fr.front + 1);
            hit = !inSafe && fr.front > 0 && jumpY < 2.5 && flyUntil < elapsed && inFlow.dist < fr.width(inFlow.index) / 2;
            // El temblor se siente solo cuando el frente está cerca (a menos de 160 m).
            const frontGap = Math.hypot(fx - hp.x, fz - hp.z);
            if (fr.debris.visible) shake = 0.35 * Math.max(0, 1 - frontGap / 160);
          }
          // Con «reducir movimiento» el evento sigue igual, pero la cámara no se sacude.
          if (shake && !reduced) { camera.position.x += (Math.random() - 0.5) * shake; camera.position.y += (Math.random() - 0.5) * shake * 0.7; }
          if (ev.kind === "inundacion" && ev.hazard) {
            // El agua sube rápido al principio y luego más despacio: hay que nadar o tomar el bote.
            ev.hazard.position.y = ev.from.y + Math.sqrt(Math.min(t, 1)) * 5.5;
            floodLevel = ev.hazard.position.y;
            hit = false;
          }
          if (ev.kind === "erupcion") {
            if (Math.random() < dt * 3) {
              const rock = new T.Mesh(rockGeometry, rockMaterial);
              rock.position.set(hp.x + (Math.random() - 0.5) * 60, hp.y + 80, hp.z + (Math.random() - 0.5) * 60);
              scene.add(rock); rocks.push({ mesh: rock, v: 0 });
            }
            hit = false;
          }
          // De atrás hacia adelante, porque la roca que toca el suelo se retira de la escena y de la lista.
          for (let i = rocks.length - 1; i >= 0; i -= 1) {
            const rock = rocks[i];
            rock.v += 30 * dt; rock.mesh.position.y -= rock.v * dt;
            if (rock.mesh.position.y <= heightAt(rock.mesh.position.x, rock.mesh.position.z)) {
              scene.remove(rock.mesh); rocks.splice(i, 1);
              if (Math.hypot(rock.mesh.position.x - hp.x, rock.mesh.position.z - hp.z) < 4) { health = Math.max(1, health - 15); setPickupNote("¡Te golpeó una roca volcánica! −15 de salud"); }
            }
          }
          if (ev.kind === "calor" && !inSafe) health = Math.max(1, health - 4 * dt);
          // Rescate: al acercarte (a pie, en vehículo o en bote) la persona te sigue; en la zona segura queda a salvo.
          for (const person of trapped) {
            if (person.state === "salvo") continue;
            const pos = person.rig.object.position;
            const reach = driving ? 9 : 5;
            if (person.state === "atrapado") {
              if (Math.hypot(pos.x - hp.x, pos.z - hp.z) < reach) { person.state = "siguiendo"; sfx("powerup"); setPickupNote(`¡Lo tienes! Llévalo a la zona segura`); }
              person.rig.play("Idle");
            } else {
              const goal = temp.set(hp.x - Math.sin(heading) * 3, 0, hp.z - Math.cos(heading) * 3);
              const gap = Math.hypot(goal.x - pos.x, goal.z - pos.z);
              if (driving) { pos.set(goal.x, 0, goal.z); person.rig.object.visible = false; }
              else { person.rig.object.visible = true; if (gap > 1) { const step = Math.min(gap, 24 * dt); pos.x += ((goal.x - pos.x) / gap) * step; pos.z += ((goal.z - pos.z) / gap) * step; person.rig.object.rotation.y = Math.atan2(goal.x - pos.x, goal.z - pos.z); } }
              person.rig.play(gap > 1.5 ? "Run" : "Idle");
              if (Math.hypot(ev.safe.x - pos.x, ev.safe.z - pos.z) < 11 || (inSafe && driving)) {
                person.state = "salvo"; person.rig.object.visible = true;
                pos.set(ev.safe.x + (Math.random() - 0.5) * 6, 0, ev.safe.z + (Math.random() - 0.5) * 6);
                (person.aura.material as THREE_NS.MeshBasicMaterial).color.setHex(0x5ee08a);
                sfx("fanfare");
              }
            }
            const ground = heightAt(pos.x, pos.z);
            pos.y = floodLevel > ground ? floodLevel - 1.1 + Math.sin(elapsed * 3) * 0.2 : ground;
            person.aura.position.set(pos.x, pos.y + 0.1, pos.z);
            if (camera.position.distanceTo(pos) < 160) person.rig.update(dt);
          }
          const savedNow = trapped.filter((p) => p.state === "salvo").length;
          if (ev.kind === "erupcion") hit = false;
          const survived = inSafe && savedNow === trapped.length && t > 0.1;
          if (hit) {
            ev.done = true;
            health = Math.max(1, health - 60);
            heroObj.position.copy(ev.safe);
            setAlert(null);
            setLesson({ kind: ev.kind, saved: false, rescued: savedNow, total: trapped.length, seconds: Math.round(elapsed - rescueStart) });
          } else if (survived || t >= 1) {
            ev.done = true;
            setAlert(null);
            setLesson({ kind: ev.kind, saved: survived, rescued: savedNow, total: trapped.length, seconds: Math.round(elapsed - rescueStart) });
            if (survived) { voiceClip("lo-logramos"); sfx("fanfare"); speak("¡Lo logramos! ¡Estamos a salvo!", { pitch: 0.8, rate: 1.1, who: "heroe" }); }
          } else if (elapsed - lastAlert > 0.25) {
            lastAlert = elapsed;
            setAlert({ kind: ev.kind, left: Math.max(0, Math.ceil(ev.duration - (elapsed - ev.started))), nino, rescued: savedNow, total: trapped.length });
          }
          if (ev.done) {
            floodLevel = ev.kind === "inundacion" ? floodLevel : -Infinity;
            safeRing.visible = safeBeam.visible = false;
            stormRain.visible = false;
            // Las rocas volcánicas que aún caían se retiran: al terminar el aviso quedaban quietas en el aire.
            for (const rock of rocks) scene.remove(rock.mesh);
            rocks.length = 0;
            // El lodo o la nieve quedan en el cauce (así queda una quebrada después de un huaico); se quitan las rocas.
            if (ev.flow) { ev.flow.debris.visible = false; ev.flow.splash.forEach((sp) => { sp.visible = false; }); ev.flow.geometry.setDrawRange(0, (ev.flow.path.length - 1) * ev.flow.quads * 6); }
            else if (ev.hazard && ev.kind !== "inundacion") scene.remove(ev.hazard);
          }
        }
        // Fiesta: baile, luces que parpadean y música al acercarse.
        dancers.forEach((d) => { if (camera.position.distanceTo(party.position) < 150) d.update(dt); });
        eaters.forEach((e, i) => { e.play("Idle"); if (camera.position.distanceTo(party.position) < 150) e.update(dt); e.object.rotation.y = Math.PI + Math.sin(elapsed + i) * 0.3; });
        bulbs.forEach((bulb, i) => { bulb.visible = Math.floor(elapsed * 3 + i) % 3 !== 0; });
        const nearParty = Math.hypot(party.position.x - heroObj.position.x, party.position.z - heroObj.position.z) < 45;
        // Música: tensión durante el aviso y fiesta junto a la fiesta o adentro de su casa; al explorar, sin música.
        setTrack(!landed || takeoff ? null : liveEvent && !liveEvent.done ? "tension" : inside?.room.name === "fiesta" || (nearParty && !inside) ? "fiesta" : null);
        // Ríos que corren y lluvia de tormenta.
        for (const texture of flowTextures) if (texture !== liveEvent?.flow?.texture) texture.offset.y -= dt * 0.25;
        if (stormRain.visible) {
          const arr = stormGeo.attributes.position.array as Float32Array;
          for (let i = 0; i < stormCount; i += 1) {
            const o = i * 6;
            arr[o + 1] -= 46 * dt;
            if (arr[o + 1] < 0) arr[o + 1] += 50;
            arr[o + 4] = arr[o + 1] - 1.3;
          }
          stormGeo.attributes.position.needsUpdate = true;
          stormRain.position.set(camera.position.x, heroObj.position.y - 5, camera.position.z);
        }
        // Molinos que giran y humo volcánico que sube despacio.
        for (const blades of spinners) blades.rotation.z += dt * 0.8;
        if (plume) plume.children.forEach((puff, i) => { puff.position.y = ((i * 22 + elapsed * 6) % 320); puff.scale.setScalar(1 + puff.position.y / 320); });
        // Humo de los contaminadores que siguen quemando basura.
        for (const polluter of polluters) {
          polluter.rig?.play("Idle");
          if (polluter.rig && camera.position.distanceTo(polluter.position) < 160) polluter.rig.update(dt);
          if (polluter.stopped) continue;
          polluter.smoke.forEach((puff, i) => {
            const life = (elapsed * 0.35 + i / polluter.smoke.length) % 1;
            puff.position.set(polluter.position.x + 2.5 + Math.sin(i * 3 + elapsed) * life * 2, polluter.position.y + 1 + life * 16, polluter.position.z + Math.cos(i * 2) * life * 1.5);
            puff.scale.setScalar(2 + life * 7);
            (puff.material as THREE_NS.SpriteMaterial).opacity = 0.7 * (1 - life);
            puff.visible = camera.position.distanceTo(puff.position) > 8; // nunca una nube gris pegada a la cámara
          });
        }
        // Lluvia, nieve o polvo caen alrededor de la cámara.
        if (precipCount) {
          const arr = precipGeo.attributes.position.array as Float32Array;
          const fall = weatherKind === "lluvia" ? 42 : weatherKind === "nieve" ? 3 : 0.6;
          const stride = weatherKind === "lluvia" ? 6 : 3;
          for (let i = 0; i < precipCount; i += 1) {
            const o = i * stride;
            arr[o + 1] -= fall * dt;
            if (weatherKind !== "lluvia") { arr[o] += Math.sin(elapsed + i) * dt * (weatherKind === "nieve" ? 0.8 : 1.5); }
            if (weatherKind === "lluvia") arr[o + 4] = arr[o + 1] - 1.1;
            if (arr[o + 1] < 0) {
              arr[o + 1] += precipBox.h;
              if (weatherKind === "lluvia") arr[o + 4] = arr[o + 1] - 1.1;
            }
          }
          precipGeo.attributes.position.needsUpdate = true;
          precip.position.set(camera.position.x, heroObj.position.y - 5, camera.position.z);
        }
        if (weatherKind === "lluvia") {
          // Relámpagos de vez en cuando (con «reducir movimiento» no destella la pantalla; la lluvia sigue).
          if (elapsed > nextLightning) { if (!reduced) ambientFlash.intensity = 4; nextLightning = elapsed + 6 + hash(elapsed, 1) * 8; }
          ambientFlash.intensity = Math.max(0, ambientFlash.intensity - dt * 9);
        }
        if (landed && elapsed - lastHud > 0.25) {
          // Siguiente parada: el primer objetivo pendiente, con flecha y distancia.
          const pendingSpot = spots.findIndex((_, i) => !npcs[i].saved);
          const pendingStop = polluters.findIndex((item) => !item.stopped);
          const stuck = trapped.find((p) => p.state === "atrapado" && p.rig.object.visible);
          const goal = liveEvent && !liveEvent.done
            ? (stuck ? { text: `${EVENT_INFO[liveEvent.kind].icon} ¡Rescata a la persona atrapada!${eventKind === "inundacion" ? " (sube al bote con E)" : ""}`, at: stuck.rig.object.position }
              : { text: `${EVENT_INFO[liveEvent.kind].icon} ¡Lleva a todos a la zona segura!`, at: liveEvent.safe })
            : dogState === "herido" ? { text: "🐶 Hay un perrito herido cerca: cúralo (F)", at: dog.position }
            : !usedVehicle && vehicles.length ? { text: "Sube a la camioneta o la moto (tecla E)", at: vehicles[0].obj.position }
            : pendingSpot !== -1 ? { text: `Ayuda: ${spots[pendingSpot].item.icon} ${spots[pendingSpot].item.quest}`, at: spots[pendingSpot].position }
            : pendingStop !== -1 ? { text: "Detén la quema de basura (rayo de conciencia, F)", at: polluters[pendingStop].position }
            : following.size ? { text: "Lleva a los contaminadores al ♻ centro de reciclaje", at: refuge.position }
            : { text: "¡Lugar salvado! Sube a tu nave (E) y vuela a otro lugar", at: landing };
          const targetAngle = Math.atan2(goal.at.x - heroObj.position.x, goal.at.z - heroObj.position.z);
          const camAngle = Math.atan2(-Math.sin(yaw), -Math.cos(yaw));
          setObjective({ text: goal.text, meters: Math.round(Math.hypot(goal.at.x - heroObj.position.x, goal.at.z - heroObj.position.z)), angle: -((targetAngle - camAngle) * 180) / Math.PI });
          const nearVehicle = !driving && vehicles.some((v) => Math.hypot(v.obj.position.x - heroObj.position.x, v.obj.position.z - heroObj.position.z) < 7);
          const nearShip = !driving && !inside && Math.hypot(ship.position.x - heroObj.position.x, ship.position.z - heroObj.position.z) < 16;
          const doorClose = !inside && !driving ? doors.find((d) => Math.hypot(d.at.x - heroObj.position.x, d.at.z - heroObj.position.z) < 7) : undefined;
          const exitClose = inside && heroObj.position.distanceTo(temp.copy(inside.room.origin).add(inside.room.exit)) < 4;
          if (doorClose || exitClose) { setVehicleHint(doorClose ? (doorClose.room.name === "fiesta" ? "🎉 Pulsa E para entrar a la fiesta" : "🚪 Pulsa E para entrar a la casa") : "🚪 Pulsa E para salir"); } else setVehicleHint(driving ? `🚙 Manejando la ${driving.name} · E para bajar` : nearVehicle ? "🚙 Pulsa E para subir" : nearShip ? "🚀 Pulsa E para subir a tu nave y despegar" : null);
        }
        if (elapsed - lastHud > 0.25) { lastHud = elapsed; setHud({ health: Math.round(health), protectedFor: protectionFor && equipped === protectionFor ? -1 : protectionFor && (protectedUntil[protectionFor] ?? 0) > elapsed ? Math.ceil(protectedUntil[protectionFor] - elapsed) : 0 }); }
        // Auras: laten mientras el vecino está en peligro.
        for (const npc of npcs) {
          const pulse = npc.saved ? 1 : 1 + Math.sin(elapsed * 4) * 0.15;
          npc.aura.scale.setScalar(pulse);
          // Solo se animan los vecinos cercanos a la cámara: los lejanos no se notan y cuestan.
          if (npc.rig && camera.position.distanceTo(npc.aura.position) < 160) { npc.rig.play("Idle"); npc.rig.update(dt); }
        }
        // La sombra sigue al héroe.
        sun.target.position.copy(heroObj.position);
        sun.position.copy(heroObj.position).add(temp.copy(sunDir).multiplyScalar(1500));
        rig?.update(dt);
        // Objeto en la mano: sigue la mano derecha (o el torso, el abrigo) y mira hacia donde mira el héroe.
        if (inHand) {
          const obj = inHand.item.object;
          obj.visible = heroObj.visible && !driving;
          const anchor = inHand.item.worn ? rig?.bone("Spine2") ?? rig?.bone("Spine1") : rig?.bone("RightHand");
          if (anchor) anchor.getWorldPosition(obj.position);
          else obj.position.copy(heroObj.position).add(temp.set(0, inHand.item.worn ? 1.35 : 1, 0));
          if (!inHand.item.worn) obj.position.add(temp.set(Math.sin(heroObj.rotation.y) * 0.06, -0.02, Math.cos(heroObj.rotation.y) * 0.06));
          obj.rotation.set(0, heroObj.rotation.y, inHand.id === "paraguas" ? 0.08 : 0);
          if (inHand.id === "botiquin" && elapsed > botiquinUntil) {
            // Botiquín: se usa al sacarlo y se gasta.
            health = Math.min(100, health + 40);
            bagCounts.botiquin = Math.max(0, (bagCounts.botiquin ?? 1) - 1);
            putAway(); syncBag();
            sfx("fanfare");
            setPickupNote("🩹 Te curaste: +40 de salud");
          } else if (inHand?.id === "radio" && elapsed > radioNext) {
            // Radio: en el Perú, las noticias de El Niño con su fuente; en otros lugares, el aviso del lugar.
            radioNext = elapsed + 8;
            if (mission.country === NINO_COUNTRY) { radioIndex = (radioIndex + 1) % NINO_FACTS.length; setPickupNote(`📻 ${NINO_FACTS[radioIndex].text} (${ninoCredit(NINO_FACTS[radioIndex])})`); }
            else setPickupNote(mission.hazard ? `📻 ${EVENT_INFO[mission.hazard].title}: ${EVENT_INFO[mission.hazard].order}` : `📻 Radio: hoy en ${mission.name} todo está tranquilo.`);
          }
        }
        renderer.render(scene, camera);
        // Etiquetas HTML encima de cada haz y posición del héroe en pantalla (a ~30 cuadros por segundo).
        overlayClock += dt;
        if (overlayClock < 1 / 30) { frame = requestAnimationFrame(tick); return; }
        overlayClock = 0;
        const w = canvas.clientWidth, h = canvas.clientHeight;
        // Globos de diálogo sobre las personas cercanas que están en pantalla.
        const talk: { key: string; x: number; y: number; text: string; tone: string }[] = [];
        // Zonas ocupadas: las placas del mundo, el panel de la misión y la barra del juego, medidas tres veces por
        // segundo. Un globo o un cartel que caería encima de una placa o fuera del lienzo no se dibuja: antes se
        // montaban sobre el objetivo y el panel y se salían de la pantalla.
        if (elapsed - lastZones > 0.33) {
          lastZones = elapsed;
          const origin = canvas.getBoundingClientRect();
          zones = [];
          document.querySelectorAll<HTMLElement>(ZONES).forEach((el) => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && (el.checkVisibility?.({ checkOpacity: true, checkVisibilityCSS: true }) ?? true)) zones.push([r.left - origin.left, r.top - origin.top, r.right - origin.left, r.bottom - origin.top]);
          });
        }
        // (cx, bottom) = punta del globo; bw × bh = su tamaño estimado por el largo del texto, con 6 px de aire.
        const fits = (cx: number, bottom: number, bw: number, bh: number) => {
          const left = cx - bw / 2 - 6, right = cx + bw / 2 + 6, top = bottom - bh - 6;
          return left >= 0 && right <= w && top >= 0 && bottom + 6 <= h && !zones.some((z) => left < z[2] && right > z[0] && top < z[3] && bottom + 6 > z[1]);
        };
        const say = (key: string, at: THREE_NS.Vector3, text: string, tone: string) => {
          if (camera.position.distanceTo(at) > 70) return;
          const p = temp.copy(at).add(new T.Vector3(0, 2.6, 0)).project(camera);
          if (p.z < -1 || p.z > 1) return;
          const x = ((p.x + 1) / 2) * w, y = ((1 - p.y) / 2) * h;
          // Globo de 210 px de ancho como máximo (ver `.gameTalk`): unas 26 letras por línea de 16 px.
          if (!fits(x, y, Math.min(210, text.length * 7.4 + 28), Math.ceil(text.length / 26) * 16 + 24)) return;
          talk.push({ key, x, y, text, tone });
        };
        const slot = Math.floor(elapsed / 6);
        if (landed) {
          spots.forEach((spot, i) => say(`v${i}`, spot.position, npcs[i].saved ? `¡Gracias, ${heroName}! 💚` : i % 2 ? `¡${heroName}, por aquí! ¡Te necesito! 🙏` : `¡Hola! ¿Tú eres ${heroName}? Tengo una misión para ti`, npcs[i].saved ? "ok" : "help"));
          trapped.forEach((person, i) => { if (person.rig.object.visible) say(`t${i}`, person.rig.object.position, person.state === "salvo" ? "¡Estamos vivos! 🙌" : person.state === "siguiendo" ? `¡Vamos, ${heroName}, te sigo!` : ["¡No puedo salir de aquí!", `¡${heroName}, aquí abajo!`, "¡El agua me alcanza!"][i % 3], person.state === "atrapado" ? "help" : "ok"); });
          polluters.forEach((item, i) => item.rig && say(`c${i}`, item.rig.object.position, trained.has(i) ? "Ahora separo mi basura ♻" : item.stopped ? "Está bien… te sigo al centro de reciclaje" : i % 2 ? "¡Yo quemo mi basura, ¿y qué?!" : "Total, el humo se va solito…", item.stopped ? "ok" : "bad"));
          if (inside?.room.name === "familia") family.forEach((f, i) => say(`f${i}`, f.object.position, kitItems.every((k) => k.taken) ? (mission.country === NINO_COUNTRY && slot % 2 ? (i ? "¿Viste el noticiero? El choclo subió 45,3 % en octubre…" : "Y llega menos pescado por el oleaje. Hay que cuidarnos.") : i ? "¡Gracias! Ahora estamos preparados 💚" : "¿Te quedas a cenar? 🍲") : (i ? `¡Bienvenida, ${heroName}! ¡Pasa, pasa!` : `¿Nos ayudas a armar la mochila de emergencia? Busca la linterna, el agua, el botiquín y la radio.`), "town"));
          dancers.forEach((d, i) => say(`d${i}`, d.object.getWorldPosition(new T.Vector3()), [`¡Ven a bailar, ${heroName}! 💃`, "¡Qué buena fiesta!"][(i + slot) % 2], "town"));
          eaters.forEach((e, i) => say(`e${i}`, e.object.getWorldPosition(new T.Vector3()), ["¡Está rica la comida! 😋", `¡Siéntate con nosotros, ${heroName}!`, "Hoy celebramos el cumpleaños de la abuela 🎂"][(i + slot) % 3], "town"));
          crowd.forEach((person, i) => {
            const talk = talks[person.pair];
            if (talk?.phase === "conversa") {
              // Hablan por turnos: primero uno, luego el otro.
              const line = Math.floor((elapsed - talk.start) / LINE_SECONDS);
              const first = crowd.find((other) => other.pair === person.pair) === person;
              if (line < talk.lines.length && (line % 2 === 0) === first) say(`p${i}`, person.rig.object.position, talk.lines[line], "town");
            } else if ((slot + i) % 3 === 0) say(`p${i}`, person.rig.object.position, townLines[(i + slot) % townLines.length], "town");
          });
          if (inside?.room.name === "fiesta") {
            const partyChat = ["¡Hola! ¿Cómo estás?", "¡Sí, todo bien! ¡Qué buena fiesta! 🎉", `¡Mira, llegó ${heroName}!`, "¡Ven a bailar con nosotros! 💃"];
            const line = Math.floor(elapsed / LINE_SECONDS) % partyChat.length;
            guests.forEach((guest, i) => { if (line % 2 === i) say(`g${i}`, guest.object.position, partyChat[line], "town"); });
            roomDancers.forEach((d, i) => { if ((slot + i) % 3 === 0) say(`rd${i}`, d.object.position, ["¡Esta canción me encanta! 🎶", `¡Baila, ${heroName}!`, "¡Feliz cumpleaños, abuela! 🎂"][i % 3], "town"); });
          }
          if (camera.position.distanceTo(peakFlag.position) < 1500) {
            const p = temp.copy(peakFlag.position).add(new T.Vector3(0, 16, 0)).project(camera);
            if (p.z > -1 && p.z < 1 && fits(((p.x + 1) / 2) * w, ((1 - p.y) / 2) * h, 210, 56)) talk.push({ key: "peak", x: ((p.x + 1) / 2) * w, y: ((1 - p.y) / 2) * h, text: `⛰ Punto más alto: ${peakMeters.toLocaleString("es-PE")} m`, tone: "peak" });
          }
          if (dogState === "herido" || slot % 3 === 0) say("dog", dog.position, dogState === "herido" ? "Auuu… 🐶🩹" : "¡Guau! 🐾", dogState === "herido" ? "help" : "buddy");
          if (buddy && buddy.object.visible && slot % 2 === 0) say("buddy", buddy.object.position, buddyLines[slot % buddyLines.length], "buddy");
        }
        setSpeakers(talk);
        setLabels(spots.map((spot) => {
          const p = temp.copy(spot.position).add(new T.Vector3(0, 30, 0)).project(camera);
          // El cartel (una línea, con el «!» encima) tampoco se dibuja sobre una placa ni fuera del lienzo.
          const x = ((p.x + 1) / 2) * w, y = ((1 - p.y) / 2) * h;
          return { id: spot.item.id, x, y, visible: p.z < 1 && p.z > -1 && fits(x, y, spot.item.quest.length * 7.6 + 56, 64) };
        }));
        if (landed) {
          const p = temp.copy(heroObj.position).add(new T.Vector3(0, 2.4, 0)).project(camera);
          setHeroScreen({ x: ((p.x + 1) / 2) * w, y: ((1 - p.y) / 2) * h });
          // Escáner: altitud real bajo los pies (sin exagerar) y cobertura de ESA en esa celda; se refresca 4 veces por segundo.
          if (elapsed - lastScan > 0.25) {
            lastScan = elapsed;
            setScan({ altitude: terrain.base_elevation_m + heightAt(heroObj.position.x, heroObj.position.z) / exaggeration, cover: COVER_NAME[coverAt(heroObj.position.x, heroObj.position.z)] ?? "Sin dato" });
          }
        }
        frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
      cleanup = () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
        window.removeEventListener("keydown", onKey);
        window.removeEventListener("keyup", onKey);
        setTrack(null);
        // Las voces en curso (sintetizada o grabadas) no siguen sonando en el globo.
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
        voiceCache.forEach((audio) => audio?.pause());
        putAway();
        window.removeEventListener("keydown", onAction);
        canvas.removeEventListener("pointerdown", onPointerDown);
        window.removeEventListener("pointermove", onPointerMove);
        window.removeEventListener("pointerup", onPointerUp);
        canvas.removeEventListener("click", onClick);
        scene.traverse((object) => {
          const mesh = object as THREE_NS.Mesh;
          mesh.geometry?.dispose();
          const material = mesh.material as THREE_NS.Material | THREE_NS.Material[] | undefined;
          (Array.isArray(material) ? material : material ? [material] : []).forEach((item) => {
            // Texturas del material: las de lienzo (carteles, íconos, banderas, ventanas, televisor, ríos) y las de
            // los modelos. Liberar el material no las libera, y cada una ocupa memoria de video.
            for (const value of Object.values(item)) if ((value as THREE_NS.Texture | null)?.isTexture) (value as THREE_NS.Texture).dispose();
            item.dispose();
          });
        });
        // Rocas de la erupción: si ya se retiraron de la escena, el recorrido de arriba no las alcanza.
        rockGeometry.dispose();
        rockMaterial.dispose();
        envMap.dispose();
        pmrem.dispose();
        cloudTexture.dispose();
        smokeTexture.dispose();
        grain.dispose();
        renderer.dispose();
        // Cada misión abre un contexto WebGL nuevo: se suelta para que el navegador no acumule contextos.
        renderer.forceContextLoss();
      };
    };
    run().catch(() => { if (!disposed) propsRef.current.onUnavailable(); });
    return () => { disposed = true; cleanup(); };
    // Se reconstruye solo al cambiar de misión o de figura del héroe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mission.id, hero?.gender]);

  return (
    // Un clic con el mouse (detail > 0) en un botón del mundo no se queda con el foco: vuelve al lienzo, y así Espacio
    // sigue siendo saltar. Quien activa el botón con el teclado (detail = 0) conserva el foco en él.
    <div className="gameWorld" onClick={(event) => { if (event.detail > 0 && (event.target as HTMLElement).closest("button")) canvasRef.current?.focus({ preventScroll: true }); }}>
      {/* tabIndex −1: el lienzo puede recibir el foco por código, pero no entra en el recorrido con Tab. La clave rehace
          el lienzo si cambia la figura del héroe: el anterior ya soltó su contexto WebGL y no sirve para otro renderer. */}
      <canvas key={hero?.gender ?? "sin-heroe"} ref={canvasRef} tabIndex={-1} style={{ outline: "none" }} className="gameWorldCanvas" aria-label={`Mundo 3D de ${mission.name}: relieve Copernicus DEM y cobertura ESA WorldCover`} role="img" />
      {alert?.kind === "calor" && <div className="gameHeat" aria-hidden />}
      {status === "cargando" && <p className="gameWorldLoading" role="status">Construyendo {mission.name} con datos satelitales…</p>}
      {labels.map((label) => {
        const item = checkpoints.find((c) => c.id === label.id);
        if (!item || !label.visible) return null;
        return (
          <div key={label.id} className={`gamePin world ${visited.has(label.id) ? "done" : ""}`} style={{ left: label.x, top: label.y }} aria-hidden>
            <b><em>{item.icon}</em>{item.quest}{visited.has(label.id) ? " ✓" : ""}</b>
            {!visited.has(label.id) && <span className="bang">!</span>}
          </div>
        );
      })}
      {speakers.map((item) => (
        <p key={item.key} className={`gameTalk tone-${item.tone}`} style={{ left: item.x, top: item.y }} aria-hidden>{item.text}</p>
      ))}
      {speech && heroScreen && (
        <div className="gameWalker" style={{ left: heroScreen.x, top: heroScreen.y }}>
          <div className={`gameSpeech tone-${speech.tone}`} role="status">
            <p className="ask"><span>{speech.icon}</span> «{speech.ask.replace(/h[ée]roe/gi, hero?.name ?? "héroe")}»</p>
            <p className="answer"><b>{hero?.name ?? "Héroe"}:</b> {speech.message}</p>
            <span className="xp">+100 XP</span>
          </div>
        </div>
      )}
      <div className={`gameCine ${phase === "suelo" ? "out" : ""}`} aria-hidden={phase === "suelo"}>
        <span className="bar top" /><span className="bar bottom" />
        <div className="gameCineTitle">
          <b>{mission.name}, {mission.country}</b>
          <small>{Math.abs(mission.latitude).toFixed(4)}° {mission.latitude < 0 ? "S" : "N"}   {Math.abs(mission.longitude).toFixed(4)}° {mission.longitude < 0 ? "O" : "E"}</small>
          {phase !== "suelo" && <em>Aterrizando</em>}
        </div>
      </div>
      {phase === "suelo" && hero && (
        <div className="gameVitals" aria-label="Salud del héroe">
          <span>❤️</span><i style={{ width: `${hud.health}%` }} className={hud.health < 35 ? "low" : ""} /><b>{hud.health}</b>
          <small>{timeRef.current.night ? "🌙" : timeRef.current.dawn ? "🌅" : "☀️"} {timeRef.current.fixed ? (timeRef.current.night ? "Luz de noche (fijada)" : "Luz de día (fijada)") : `${String(Math.floor(timeRef.current.hour)).padStart(2, "0")}:${String(Math.floor((timeRef.current.hour % 1) * 60)).padStart(2, "0")} hora local`} ·{weatherRef.current === "lluvia" ? "🌧️ Lluvia" : weatherRef.current === "nieve" ? "❄️ Nieve" : weatherRef.current === "calor" ? "🔥 Calor" : "☀️ Despejado"}{hud.protectedFor === -1 ? " · protección puesta ✔" : hud.protectedFor ? ` · protegido ${hud.protectedFor} s` : weatherRef.current !== "despejado" ? " · ¡busca protección!" : ""}</small>
        </div>
      )}
      {pickupNote && <p className="gamePickup" role="status">{pickupNote}</p>}
      {alert && (
        <div className="gameAlert" role="alert">
          <div className={`gameAlertCard${alertCompact ? " compact" : ""}`}>
            {alert.nino && <small className="nino">⚠ ALERTA DE EL NIÑO COSTERO · {NINO_FACTS[1].text} <i>Fuente: {ninoCredit(NINO_FACTS[1])}</i></small>}
            <b>{EVENT_INFO[alert.kind].icon} {EVENT_INFO[alert.kind].title}</b>
            <p>{EVENT_INFO[alert.kind].order}</p>
            <strong>{alert.left} s</strong>
            <p className="rescue">🛟 Rescatados: {alert.rescued}/{alert.total} · llévalos a la zona segura</p>
            <em>Evento simulado del juego, inspirado en los riesgos reales de la zona (relieve Copernicus y lluvia NASA).</em>
          </div>
        </div>
      )}
      {lesson && (
        <div className="gameLesson" role="dialog" aria-labelledby="lesson-title" tabIndex={-1} ref={focusOnOpen}>
          <b id="lesson-title">{lesson.saved ? `¡Aviso atendido! +${200 + (lesson.rescued ?? 0) * 100} XP` : lesson.rescued ? `Rescataste ${lesson.rescued}/${lesson.total}` : "Te alcanzó… pero aprendiste"} · {EVENT_INFO[lesson.kind].icon} {EVENT_INFO[lesson.kind].title}</b>
          {lesson.total != null && <p className="score">🛟 Rescataste {lesson.rescued}/{lesson.total} personas en {lesson.seconds} s</p>}
          <p>Qué hacer en la vida real:</p>
          <ul>{EVENT_INFO[lesson.kind].lesson.map((line) => <li key={line}>{line}</li>)}</ul>
          <p className="detect">🛰️ Cómo se detecta desde el espacio: <span>{EVENT_DETECT[lesson.kind]}</span></p>
          <small>Recomendaciones generales de defensa civil. Sigue siempre a las autoridades de tu zona.</small>
          <button type="button" onClick={() => { setLesson(null); backToCanvas(); }}>Seguir la misión</button>
        </div>
      )}
      {kitDone && (
        <div className="gameLesson" role="dialog" aria-labelledby="kit-title" tabIndex={-1} ref={focusOnOpen}>
          <b id="kit-title">🎒 ¡Mochila de emergencia lista! +150 XP</b>
          <p>Qué debe tener una mochila de emergencia de verdad:</p>
          <ul>
            <li>Agua y comida que no se malogre para unos días.</li>
            <li>Linterna y radio a pilas, con pilas de repuesto.</li>
            <li>Botiquín, medicinas personales y copias de documentos.</li>
            <li>Ropa de abrigo, silbato y un punto de encuentro acordado con la familia.</li>
          </ul>
          <small>Recomendaciones generales de defensa civil. Revisa la mochila cada pocos meses.</small>
          <button type="button" onClick={() => { setKitDone(false); backToCanvas(); }}>Seguir</button>
        </div>
      )}
      {welcome && (
        <div className="gameWelcome" role="status" lang="en"><small>Welcome to</small><b>{mission.name}</b><span lang="es">{mission.country}</span></div>
      )}
      {phase === "suelo" && objective && !welcome && (
        // La región viva es solo el texto del objetivo: la distancia cambia varias veces por segundo y, dentro de
        // `role="status"`, el lector de pantalla la anunciaba sin parar. Ahora se anuncia cuando cambia la parada.
        <div className="gameObjective">
          <span className="arrow" style={{ transform: `rotate(${objective.angle}deg)` }} aria-hidden>➤</span>
          <p><small>Siguiente parada</small><b role="status">{objective.text}</b><em>{objective.meters} m</em></p>
        </div>
      )}
      {phase === "suelo" && vehicleHint && (
        <button type="button" className="gameVehicle" onClick={() => toggleRef.current()}>{vehicleHint}</button>
      )}
      {/* Pantalla táctil: no hay tecla Espacio; el botón envía la misma tecla y reutiliza el salto (dos toques: vuela). */}
      {phase === "suelo" && hero && (
        <button type="button" className="gameJump" onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { code: "Space" }))}>Saltar</button>
      )}
      {phase === "suelo" && hero && !speech && !prompt && !welcome && hintOpen !== "no" && (
        <div className="gameHint" role="note">
          <p className="keys">W A S D para correr · Shift supervelocidad · ESPACIO salta (dos veces: ¡vuela!) · E vehículo o puerta · F ayuda · V vista desde el cielo · Q y R giran la vista · arrastra para girar. Sigue la flecha amarilla.</p>
          <p className="touch">Toca el suelo para caminar hasta ahí · arrastra para girar la vista · usa los botones para ayudar, subir a un vehículo y saltar. Sigue la flecha amarilla.</p>
          <button type="button" aria-label="Cerrar la ayuda de teclas" onClick={() => setHintOpen("no")}>×</button>
        </div>
      )}
      {phase === "suelo" && hero && prompt && (
        <div className="gameHelp" role="status">
          <p><b>{prompt.icon} {prompt.quest}</b> · «{prompt.ask.replace(/h[ée]roe/gi, hero?.name ?? "héroe")}»</p>
          {prompt.id === "perro"
            ? <button type="button" onClick={() => fireRef.current()}>❤️ Curar al perrito <kbd>F</kbd></button>
            : prompt.id === "contaminador"
            ? <button type="button" onClick={() => fireRef.current()}>🛑 Detener con el rayo de conciencia <kbd>F</kbd></button>
            : <button type="button" onClick={() => fireRef.current()}>{toolFor(prompt).icon} Ayudar con {toolFor(prompt).name} <kbd>F</kbd></button>}
        </div>
      )}
      {scan && phase === "suelo" && (
        <aside className={`gameScanner${scanOpen ? " open" : ""}`} aria-label="Escáner NASA del héroe">
          {/* Solo se ve en pantallas angostas (CSS): pliega y despliega el escáner. */}
          <button type="button" className="gameScannerMore" onClick={() => setScanOpen((v) => !v)} aria-expanded={scanOpen}>{scanOpen ? "Ocultar escáner" : "Escáner NASA"}</button>
          <b>Escáner NASA</b>
          <p className="gameSaved">Vecinos a salvo: <strong>{savedCount}/{checkpoints.length}</strong> · Contaminación detenida: <strong>{stoppedCount}/{mission.continent === "Antártida" ? 0 : 2}</strong> · Capacitados: <strong>{trainedCount}/{mission.continent === "Antártida" ? 0 : 2}</strong></p>
          <dl>
            <dt>Altitud aquí</dt><dd>{Math.round(scan.altitude).toLocaleString("es-PE")} m <small>Copernicus DEM</small></dd>
            <dt>Suelo</dt><dd>{scan.cover} <small>ESA WorldCover</small></dd>
            {mission.temperature?.mean != null && <><dt>Temperatura media</dt><dd>{mission.temperature.mean.toFixed(1)} °C <small>NASA POWER, desde 2001</small></dd></>}
            {mission.temperature?.significant && mission.temperature.slope_per_year != null && <><dt>Tendencia</dt><dd className={mission.temperature.slope_per_year > 0 ? "hot" : "cold"}>{mission.temperature.slope_per_year > 0 ? "+" : "−"}{Math.abs(mission.temperature.slope_per_year * 10).toFixed(2)} °C por década</dd></>}
            {mission.rain?.mean != null && <><dt>Lluvia media</dt><dd>{mission.rain.mean.toFixed(1)} mm/día <small>NASA POWER</small></dd></>}
          </dl>
        </aside>
      )}
      {status === "listo" && phase === "suelo" && Object.values(bag.counts).some(Boolean) && (
        <div className="gameBag" role="toolbar" aria-label="Mochila">{/* su sitio (derecha y abajo) lo fija game.css según el panel */}
          <p>🎒 Mochila · {bag.equipped ? `en la mano: ${ITEMS.find((it) => it.id === bag.equipped)?.name} · pulsa ${ITEMS.findIndex((it) => it.id === bag.equipped) + 1} o G para guardarlo` : "pulsa el número para sacar un objeto; otra vez para guardarlo"}</p>
          <div>
            {ITEMS.map((item, i) => {
              const count = bag.counts[item.id] ?? 0;
              if (!count) return null;
              const on = bag.equipped === item.id;
              return (
                <button key={item.id} type="button" aria-pressed={on} className={on ? "on" : undefined} onClick={() => equipRef.current(item.id)} title={`${item.name}: ${item.use}`}>
                  <kbd>{i + 1}</kbd><span aria-hidden>{item.icon}</span><small>{item.name}{count > 1 ? ` ×${count}` : ""}</small>
                </button>
              );
            })}
          </div>
        </div>
      )}
      <div className="gameSound">
        <button type="button" onClick={() => setSoundOn((v) => !v)} aria-pressed={soundOn}>{soundOn ? "🔊 Sonido" : "🔇 Sin sonido"}</button>
        <button type="button" onClick={() => setVoices(!voicesShown)} aria-pressed={voicesShown} title={recorded ? `Voces grabadas disponibles: ${recorded}` : "No hay voces grabadas. Al activarlas habla la voz sintetizada del navegador."}>{voicesShown ? "🗣 Voces: sí" : "🗣 Voces: no"}</button>
        {isNino && <button type="button" onClick={() => setNinoOpen((v) => !v)} aria-expanded={ninoOpen}>📰 El Niño hoy</button>}
        {phase === "suelo" && hero && <button type="button" onClick={() => setHintOpen((v) => (v === "no" ? "si" : "no"))} aria-expanded={hintOpen !== "no"}>Teclas</button>}
      </div>
      {isNino && !ninoOpen && status === "listo" && (
        <button type="button" className="gameNinoTicker" onClick={() => setNinoOpen(true)}>
          <b>EL NIÑO COSTERO</b> {NINO_FACTS[ninoIndex].text} <i>{ninoCredit(NINO_FACTS[ninoIndex])}</i>
        </button>
      )}
      {ninoOpen && (
        <div className="gameNino" role="dialog" aria-labelledby="nino-title" tabIndex={-1} ref={focusOnOpen}>
          <b id="nino-title">📰 El Niño Costero 2026: lo que dicen las noticias</b>
          <p>Noticias de medios y entidades, con su fuente. Son contexto, no datos medidos por la plataforma.</p>
          <ul>
            {NINO_FACTS.map((fact) => (
              <li key={fact.text}>{fact.text} <a href={fact.url} target="_blank" rel="noreferrer">{ninoCredit(fact)}</a></li>
            ))}
          </ul>
          <button type="button" onClick={() => { setNinoOpen(false); backToCanvas(); }}>Cerrar</button>
        </div>
      )}
      {/* Créditos: al pie, un botón que abre la hoja con el texto completo de las licencias (en celular antes se
          ocultaban todos) y, donde hay ancho, una línea corta con los nombres. */}
      <div className="gameWorldCredit">
        <button type="button" onClick={() => setCreditsOpen((v) => !v)} aria-expanded={creditsOpen}>Créditos</button>
        <span>Copernicus DEM GLO-30 · ESA WorldCover 2021 (CC BY 4.0) · música de Kevin MacLeod (CC BY 4.0) · personajes de Mixamo · mundo recreado: no es una foto</span>
      </div>
      {creditsOpen && (
        <div className="gameCredits" role="dialog" aria-labelledby="credits-title" tabIndex={-1} ref={focusOnOpen}>
          <b id="credits-title">Créditos del mundo 3D</b>
          <ul>
            <li>Relieve: Copernicus DEM GLO-30 — dato adaptado, © DLR e.V. 2010-2014 y © Airbus Defence and Space GmbH 2014-2018, provisto bajo COPERNICUS por la Unión Europea y la ESA.</li>
            <li>Cobertura del suelo: ESA WorldCover 2021, CC BY 4.0 — © ESA WorldCover project 2021 / contiene datos Copernicus Sentinel modificados (2021).</li>
            <li>Música: «Samba Isobel» y «Volatile Reaction», Kevin MacLeod (incompetech.com). Licensed under Creative Commons: By Attribution 4.0 — <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">https://creativecommons.org/licenses/by/4.0/</a></li>
            <li>Personajes: Mixamo (Adobe), tomados de los ejemplos de three.js.</li>
            <li>Mundo recreado: no es una foto; las casas y las calles se reparten en las celdas urbanas y no son las reales.</li>
          </ul>
          <button type="button" onClick={() => { setCreditsOpen(false); backToCanvas(); }}>Cerrar</button>
        </div>
      )}
    </div>
  );
}
