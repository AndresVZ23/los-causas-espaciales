// Escenas de las cinemáticas de TERRA 2045 (ADR-050). Cada escena dibuja un fotograma: el planeta o el terreno en
// WebGL (gl.js) y encima, en Canvas 2D, la colonia, las siluetas, la interfaz y los textos. Diseño propio: ninguna
// imagen de referencia se copia. Los textos en pantalla salen de TXT[lang]; las voces y subtítulos van aparte.
"use strict";

const SCENES = {};
let W = 1280, H = 720, U = 1, LANG = "es", DATA = {};
const ui = () => document.getElementById("ui").getContext("2d");
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const ease = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
const lerp = (a, b, k) => a + (b - a) * k;
const rnd = (seed) => { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); };
const FONT = "Inter, 'Inter Display', 'DejaVu Sans', sans-serif";
const HAND = "Caladea, 'DejaVu Serif', serif";

const TXT = {
  es: {
    log: "REGISTRO HISTÓRICO 847 · COLONIA NEW HORIZON", link: "GÉNESIS · ENLACE CON 2045", weak: "señal débil",
    layers: ["Nubes de hoy · MODIS", "Temperatura del mar · GHRSST", "Vegetación · NDVI", "Focos de calor · VIIRS", "Lluvia · GPM IMERG", "Humedad del suelo · SMAP"],
    layersTitle: "Datos reales de observación de la Tierra · NASA",
    terrainSrc: "Relieve: Copernicus DEM GLO-30 · Cobertura: ESA WorldCover 2021",
    chartTitle: (n) => `${n} · Temperatura media anual del aire`, chartSrc: "NASA POWER (MERRA-2), celda de unos 50 km",
    perDecade: (v) => `${v > 0 ? "+" : "−"}${Math.abs(v).toFixed(2).replace(".", ",")} °C por década`, signif: "significativa tras Benjamini–Hochberg",
    second: { coincide: "Segunda fuente (ERA5): lo confirma", sin_respaldo: "Segunda fuente (ERA5): no lo confirma", contradice: "Segunda fuente (ERA5): lo contradice", solo_contraste: "Solo ERA5 ve tendencia", sin_tendencia: "Ninguna fuente ve tendencia" },
    unknown: "Lo que no se mide aquí: la inestabilidad de las laderas", decTitle: "Decide antes de la temporada de lluvias", indiff: "La indiferencia dice: «Aquí siempre ha bajado agua y no ha pasado nada.»",
    budget: "Recursos", axes: ["Protege a las personas", "Cuida agua, suelo y ecosistemas", "Suma a la comunidad"],
    measures: ["Rutas de evacuación y simulacros", "Alerta temprana: pluviómetros y sirena", "Muros y diques en la quebrada", "Reforestar la parte alta de la cuenca"],
    planet: "Estado del planeta en 2045", tiers: ["Crítico", "Deteriorado", "En recuperación", "Saludable", "En equilibrio"], gamified: "Avance del juego, no una medición",
    title2: "El último viaje", tagline: "El futuro no está escrito. Pero cada decisión deja una huella.", by: "Los Causas Espaciales · NASA Space Apps Challenge 2026",
    fiction: "Ficción. Las cifras de las misiones del juego son datos reales.",
    letterLost: ["Para quien encuentre esto:", "Me llamo Killa y tengo nueve años.", "Mi abuela dice que antes el río avisaba.", "Esa noche no avisó nadie.", "Después, en la radio, dijeron que los", "satélites lo estaban viendo desde hacía años.", "Si lo estaban viendo, ¿por qué nadie", "vino a decirnos?"],
    letterSaved: ["Para quien encuentre esto:", "Me llamo Killa y tengo nueve años.", "Hoy el río creció. Sonó la sirena y", "subimos todos al cerro, como en los ensayos.", "Mi abuela dice que antes el río avisaba.", "Ahora avisamos nosotros.", "El lunes hay clases."],
    pageChanged: "La hoja cambió",
  },
  en: {
    log: "HISTORICAL LOG 847 · NEW HORIZON COLONY", link: "GENESIS · LINK TO 2045", weak: "weak signal",
    layers: ["Today's clouds · MODIS", "Sea temperature · GHRSST", "Vegetation · NDVI", "Fire hotspots · VIIRS", "Rainfall · GPM IMERG", "Soil moisture · SMAP"],
    layersTitle: "Real Earth observation data · NASA",
    terrainSrc: "Terrain: Copernicus DEM GLO-30 · Land cover: ESA WorldCover 2021",
    chartTitle: (n) => `${n} · Mean annual air temperature`, chartSrc: "NASA POWER (MERRA-2), ~50 km grid cell",
    perDecade: (v) => `${v > 0 ? "+" : "−"}${Math.abs(v).toFixed(2)} °C per decade`, signif: "significant after Benjamini–Hochberg",
    second: { coincide: "Second source (ERA5): confirms it", sin_respaldo: "Second source (ERA5): does not confirm it", contradice: "Second source (ERA5): contradicts it", solo_contraste: "Only ERA5 sees a trend", sin_tendencia: "Neither source sees a trend" },
    unknown: "Not measured here: slope instability", decTitle: "Decide before the rainy season", indiff: "Indifference says: “Water has always come down here and nothing happened.”",
    budget: "Resources", axes: ["Protects people", "Cares for water, soil and ecosystems", "Brings the community in"],
    measures: ["Evacuation routes and drills", "Early warning: rain gauges and siren", "Walls and dams in the ravine", "Reforest the upper watershed"],
    planet: "State of the planet in 2045", tiers: ["Critical", "Deteriorated", "Recovering", "Healthy", "In balance"], gamified: "Game progress, not a measurement",
    title2: "The Last Journey", tagline: "The future is not written. But every decision leaves a mark.", by: "Los Causas Espaciales · NASA Space Apps Challenge 2026",
    fiction: "Fiction. The figures in the game's missions are real data.",
    letterLost: ["To whoever finds this:", "My name is Killa and I'm nine years old.", "My grandma says the river used to warn us.", "That night, nobody warned us.", "Later, on the radio, they said the", "satellites had been watching for years.", "If they were watching, why didn't", "anyone come to tell us?"],
    letterSaved: ["To whoever finds this:", "My name is Killa and I'm nine years old.", "Today the river rose. The siren sounded and", "we all climbed the hill, like we practiced.", "My grandma says the river used to warn us.", "Now we warn each other.", "There's school on Monday."],
    pageChanged: "The page changed",
  },
};
const T = () => TXT[LANG];

// --- arranque -------------------------------------------------------------------------------------------------
window.boot = async function (w, h, opts) {
  W = w; H = h; U = h / 720;
  for (const id of ["gl", "ui"]) { const c = document.getElementById(id); c.width = w; c.height = h; c.style.width = w + "px"; c.style.height = h + "px"; }
  GL.init(document.getElementById("gl"));
  const A = opts.assets || "../../../videos/assets/";
  await Promise.all([
    GL.loadTexture("day", A + (opts.earth || "earth_fallback.jpg")),
    GL.loadTexture("night", A + (opts.night || "landmask.png")),
    GL.loadTexture("land", A + "landmask.png"),
    GL.loadTexture("moon", A + "lroc_color_2k.jpg"),
    GL.loadTexture("noise", A + "noise.png"),
  ]);
  DATA = opts.data || {};
  for (const [id, terrain] of Object.entries(opts.terrains || {})) GL.addTerrain(id, terrain);
  await document.fonts.ready;
  return "ok";
};

window.drawShot = function (name, t, dur, p) {
  LANG = p.lang || "es";
  const ctx = ui();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, W, H);
  const fn = SCENES[name];
  if (!fn) throw new Error("escena desconocida: " + name);
  fn(ctx, t, dur, p);
  post(ctx, t, dur, p);
  return 1;
};

function blackGL() { const gl = GL.gl; gl.viewport(0, 0, W, H); gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT); }

function post(ctx, t, dur, p) {
  // Viñeta, franjas de cine y fundidos al negro de entrada y salida del plano.
  if (!p.noVignette) {
    const g = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.95);
    g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(1, "rgba(0,0,0,0.55)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  }
  if (!p.noBars) { ctx.fillStyle = "#000"; const b = Math.round(H * 0.075); ctx.fillRect(0, 0, W, b); ctx.fillRect(0, H - b, W, b); }
  const fi = p.fadeIn ?? 0.2, fo = p.fadeOut ?? 0.2;
  let a = 0;
  if (fi > 0 && t < fi) a = 1 - t / fi;
  if (fo > 0 && t > dur - fo) a = Math.max(a, (t - (dur - fo)) / fo);
  if (p.flashEnd && t > dur - 0.7) { ctx.fillStyle = `rgba(255,255,255,${ease((t - (dur - 0.7)) / 0.7)})`; ctx.fillRect(0, 0, W, H); return; }
  if (a > 0) { ctx.fillStyle = `rgba(0,0,0,${clamp(a)})`; ctx.fillRect(0, 0, W, H); }
}

// --- piezas 2D ------------------------------------------------------------------------------------------------
function text(ctx, s, x, y, size, o = {}) {
  ctx.save();
  ctx.font = `${o.weight || 600} ${size * U}px ${o.font || FONT}`;
  ctx.textAlign = o.align || "center"; ctx.textBaseline = o.base || "middle";
  if (o.spacing) ctx.letterSpacing = `${o.spacing * U}px`;
  ctx.globalAlpha = o.alpha ?? 1;
  if (o.glow) { ctx.shadowColor = o.glow; ctx.shadowBlur = 18 * U; }
  ctx.fillStyle = o.color || "#eef2f5";
  ctx.fillText(s, x, y);
  ctx.restore();
}

function lunarGround(ctx, y0, seed, light = 1, tint = [150, 150, 158]) {
  const r = rnd(seed);
  const phases = [r() * 6, r() * 6, r() * 6, r() * 6];
  const ridge = (x, k) => y0 - k * U * (14 * Math.sin(x / (W * 0.31) + phases[0]) + 9 * Math.sin(x / (W * 0.13) + phases[1]) + 4 * Math.sin(x / (W * 0.05) + phases[2]) + 2 * Math.sin(x / (W * 0.017) + phases[3]));
  // Cordillera lejana
  ctx.beginPath(); ctx.moveTo(0, H);
  for (let x = 0; x <= W; x += 8) ctx.lineTo(x, ridge(x * 0.7 + 300, 2.6) - 34 * U);
  ctx.lineTo(W, H); ctx.closePath();
  let g = ctx.createLinearGradient(0, y0 - 80 * U, 0, H);
  g.addColorStop(0, `rgba(${tint[0] * 0.55 * light},${tint[1] * 0.55 * light},${tint[2] * 0.55 * light},1)`); g.addColorStop(1, "rgb(10,10,12)");
  ctx.fillStyle = g; ctx.fill();
  // Suelo cercano
  ctx.beginPath(); ctx.moveTo(0, H);
  for (let x = 0; x <= W; x += 6) ctx.lineTo(x, ridge(x, 1.0));
  ctx.lineTo(W, H); ctx.closePath();
  g = ctx.createLinearGradient(0, y0 - 30 * U, 0, H);
  g.addColorStop(0, `rgba(${tint[0] * light},${tint[1] * light},${tint[2] * light},1)`); g.addColorStop(0.35, `rgba(${tint[0] * 0.45 * light},${tint[1] * 0.45 * light},${tint[2] * 0.45 * light},1)`); g.addColorStop(1, "rgb(8,8,10)");
  ctx.fillStyle = g; ctx.fill();
  // Cráteres
  const rc = rnd(seed + 9);
  for (let i = 0; i < 26; i += 1) {
    const x = rc() * W, depth = rc(), y = lerp(y0 + 18 * U, H, depth), rx = lerp(6, 46, depth) * U * (0.5 + rc()), ry = rx * 0.22;
    ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); ctx.fillStyle = `rgba(0,0,0,${0.25 + 0.2 * depth})`; ctx.fill();
    ctx.beginPath(); ctx.ellipse(x - rx * 0.08, y - ry * 0.15, rx, ry, 0, Math.PI * 1.05, Math.PI * 1.95); ctx.strokeStyle = `rgba(220,220,225,${0.12 * light})`; ctx.lineWidth = 1.2 * U; ctx.stroke();
  }
}

function dome(ctx, x, y, w, h, lights, t) {
  const g = ctx.createRadialGradient(x - w * 0.2, y - h * 0.7, w * 0.05, x, y - h * 0.3, w * 0.75);
  g.addColorStop(0, "#9aa3ad"); g.addColorStop(0.5, "#454b53"); g.addColorStop(1, "#17191c");
  ctx.beginPath(); ctx.ellipse(x, y, w / 2, h, 0, Math.PI, 0); ctx.closePath(); ctx.fillStyle = g; ctx.fill();
  ctx.strokeStyle = "rgba(200,210,220,0.18)"; ctx.lineWidth = 1 * U;
  for (let i = 1; i < 6; i += 1) { ctx.beginPath(); ctx.ellipse(x, y, (w / 2) * (i / 6), h, 0, Math.PI, 0); ctx.stroke(); }
  for (let i = 1; i < 4; i += 1) { const yy = y - h * (i / 4); const ww = (w / 2) * Math.sqrt(1 - (i / 4) ** 2); ctx.beginPath(); ctx.moveTo(x - ww, yy); ctx.lineTo(x + ww, yy); ctx.stroke(); }
  if (lights) {
    ctx.fillStyle = "rgba(255,196,120,0.9)";
    for (let i = 0; i < 5; i += 1) { const lx = x - w * 0.3 + i * w * 0.15; ctx.fillRect(lx, y - 7 * U, 5 * U, 4 * U); }
    ctx.fillStyle = "rgba(255,190,110,0.08)"; ctx.beginPath(); ctx.ellipse(x, y, w * 0.7, h * 0.25, 0, 0, Math.PI * 2); ctx.fill();
  }
}

function module(ctx, x, y, w, h) {
  const g = ctx.createLinearGradient(0, y - h, 0, y);
  g.addColorStop(0, "#7d858f"); g.addColorStop(0.5, "#3a3f46"); g.addColorStop(1, "#15171a");
  ctx.fillStyle = g; ctx.beginPath(); ctx.roundRect(x, y - h, w, h, h / 2); ctx.fill();
  ctx.strokeStyle = "rgba(220,225,235,0.15)"; ctx.lineWidth = U;
  for (let i = 1; i < w / (h * 0.8); i += 1) { ctx.beginPath(); ctx.moveTo(x + i * h * 0.8, y - h); ctx.lineTo(x + i * h * 0.8, y); ctx.stroke(); }
  ctx.fillStyle = "rgba(255,200,130,0.85)";
  for (let i = 0; i < w / (h * 0.8) - 1; i += 2) ctx.fillRect(x + (i + 0.6) * h * 0.8, y - h * 0.55, 3 * U, 3 * U);
}

function colony(ctx, x0, y0, s, t) {
  module(ctx, x0 - 260 * s, y0, 190 * s, 26 * s);
  module(ctx, x0 + 70 * s, y0, 230 * s, 30 * s);
  dome(ctx, x0 - 300 * s, y0 + 2 * s, 120 * s, 46 * s, true, t);
  dome(ctx, x0, y0 + 4 * s, 260 * s, 96 * s, true, t);
  dome(ctx, x0 + 330 * s, y0 + 2 * s, 140 * s, 52 * s, true, t);
  // Torre con baliza
  ctx.strokeStyle = "#5a6068"; ctx.lineWidth = 2 * s;
  const tx = x0 - 420 * s, th = 210 * s;
  ctx.beginPath(); ctx.moveTo(tx - 12 * s, y0); ctx.lineTo(tx - 4 * s, y0 - th); ctx.moveTo(tx + 12 * s, y0); ctx.lineTo(tx + 4 * s, y0 - th); ctx.stroke();
  for (let i = 0; i < 12; i += 1) { const yy = y0 - (i / 12) * th; const ww = lerp(12, 4, i / 12) * s; ctx.beginPath(); ctx.moveTo(tx - ww, yy); ctx.lineTo(tx + ww, yy - th / 12); ctx.stroke(); }
  const blink = (Math.sin(t * 3) > 0.6) ? 1 : 0.15;
  ctx.fillStyle = `rgba(255,60,50,${blink})`; ctx.beginPath(); ctx.arc(tx, y0 - th - 4 * s, 3.5 * s, 0, Math.PI * 2); ctx.fill();
  if (blink > 0.5) { ctx.fillStyle = "rgba(255,60,50,0.15)"; ctx.beginPath(); ctx.arc(tx, y0 - th - 4 * s, 14 * s, 0, Math.PI * 2); ctx.fill(); }
}

/** Silueta de espaldas, a contraluz. kind: viajero, andres, mario, nikol. rim: color de la luz que llega de adelante. */
function person(ctx, kind, x, yFeet, h, rim = "rgba(120,170,255,0.55)") {
  const child = kind === "mario";
  const hh = h * (child ? 0.15 : 0.118), top = yFeet - h;
  const shW = (h * (child ? 0.25 : kind === "andres" ? 0.3 : kind === "viajero" ? 0.255 : 0.27)) / 2;
  const neckY = top + hh * 1.05, shY = neckY + hh * 0.32, hipY = top + h * (child ? 0.58 : 0.54), hipW = shW * (kind === "viajero" || kind === "nikol" ? 0.9 : 0.8);
  const coat = kind === "nikol" ? h * 0.045 : 0;
  const path = new Path2D();
  const side = (sx) => {
    // Medio cuerpo: del cuello al pie, por un lado (sx = -1 izquierda, 1 derecha)
    return [[x + sx * hh * 0.17, neckY], [x + sx * shW * 0.55, shY - hh * 0.06], [x + sx * shW, shY + hh * 0.35], [x + sx * (shW * 1.0 + coat * 0.4), hipY], [x + sx * (shW * 0.92 + coat), hipY + h * 0.09],
      [x + sx * (hipW * 0.9 + coat), hipY + h * 0.11], [x + sx * hipW * 0.72, yFeet], [x + sx * h * 0.025, yFeet], [x, hipY + h * 0.13]];
  };
  const L = side(-1), R = side(1);
  path.moveTo(...L[0]);
  path.quadraticCurveTo(x - hh * 0.2, shY - hh * 0.12, ...L[1]);
  path.quadraticCurveTo(x - shW * 1.02, shY - hh * 0.02, ...L[2]);
  for (const pnt of L.slice(3)) path.lineTo(...pnt);
  for (const pnt of R.slice(3).reverse()) path.lineTo(...pnt);
  path.lineTo(...R[2]);
  path.quadraticCurveTo(x + shW * 1.02, shY - hh * 0.02, ...R[1]);
  path.quadraticCurveTo(x + hh * 0.2, shY - hh * 0.12, ...R[0]);
  path.closePath();
  path.ellipse(x, top + hh * 0.55, hh * 0.42, hh * 0.55, 0, 0, Math.PI * 2);
  if (kind === "viajero") path.ellipse(x, top + hh * 0.75, hh * 0.47, hh * 0.5, 0, 0, Math.PI * 2);
  // Contraluz: la silueta entera en el color de la luz, con halo, y encima la misma silueta oscura apenas más chica.
  ctx.save();
  ctx.shadowColor = rim; ctx.shadowBlur = Math.max(6, h * 0.05);
  ctx.fillStyle = rim; ctx.fill(path);
  ctx.shadowBlur = 0;
  const cy = top + h * 0.5, k = Math.max(0.975, 1 - 3 / h);
  ctx.translate(x, cy + h * 0.004); ctx.scale(k, k + (1 - k) * 0.4); ctx.translate(-x, -cy);
  ctx.fillStyle = "#04060a"; ctx.fill(path);
  ctx.restore();
}

function crowd(ctx, y, n, seed, h, rim) {
  const r = rnd(seed);
  for (let i = 0; i < n; i += 1) person(ctx, i % 3 === 0 ? "nikol" : "andres", lerp(W * 0.08, W * 0.92, r()), y + r() * h * 0.2, h * (0.8 + r() * 0.3), rim);
}

/** Sala de observación: paredes oscuras con tres ventanales. La Tierra (WebGL) se ve por el ventanal del centro. */
function observationRoom(ctx, t, o) {
  const panes = [[W * 0.16, W * 0.31], [W * 0.355, W * 0.645], [W * 0.69, W * 0.84]];
  const top = H * 0.14, bottom = H * 0.8;
  // Afuera: suelo lunar dentro de los vidrios
  ctx.save();
  ctx.beginPath(); for (const [a, b] of panes) ctx.roundRect(a, top, b - a, bottom - top, 14 * U); ctx.clip();
  lunarGround(ctx, H * 0.67, 11, 0.8);
  colony(ctx, W * 0.5, H * 0.72, 0.42 * U, t);
  ctx.restore();
  // Interior: todo menos los vidrios
  ctx.save();
  ctx.beginPath(); ctx.rect(0, 0, W, H); for (const [a, b] of panes) ctx.roundRect(a, top, b - a, bottom - top, 14 * U);
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, "#0b0e13"); g.addColorStop(0.7, "#12161d"); g.addColorStop(1, "#07090c");
  ctx.fillStyle = g; ctx.fill("evenodd");
  // Marcos
  ctx.strokeStyle = "#2a313b"; ctx.lineWidth = 10 * U; for (const [a, b] of panes) { ctx.beginPath(); ctx.roundRect(a, top, b - a, bottom - top, 14 * U); ctx.stroke(); }
  ctx.strokeStyle = "rgba(140,170,210,0.18)"; ctx.lineWidth = 2 * U; for (const [a, b] of panes) { ctx.beginPath(); ctx.roundRect(a + 6 * U, top + 6 * U, b - a - 12 * U, bottom - top - 12 * U, 10 * U); ctx.stroke(); }
  // Luz de la Tierra en el piso
  const floor = ctx.createRadialGradient(W / 2, H * 0.95, 10, W / 2, H * 0.95, W * 0.45);
  floor.addColorStop(0, o.floor || "rgba(90,130,200,0.18)"); floor.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = floor; ctx.fillRect(0, H * 0.8, W, H * 0.2);
  // Detalles: plantas de cultivo a la izquierda, pantalla a la derecha
  ctx.fillStyle = "#0c1a10"; ctx.fillRect(W * 0.02, H * 0.42, W * 0.1, H * 0.2);
  for (let i = 0; i < 18; i += 1) { ctx.fillStyle = `rgba(${60 + i * 3},${120 + i * 4},70,0.5)`; ctx.fillRect(W * 0.025 + (i % 6) * W * 0.016, H * 0.44 + Math.floor(i / 6) * H * 0.06, W * 0.01, H * 0.04); }
  ctx.fillStyle = "rgba(60,140,220,0.25)"; ctx.fillRect(W * 0.88, H * 0.45, W * 0.1, H * 0.16);
  ctx.restore();
  if (o.alarm) { const a = 0.5 + 0.5 * Math.sin(t * 6); ctx.fillStyle = `rgba(220,30,20,${0.18 * a})`; ctx.fillRect(0, 0, W, H); }
}

function genesisRing(ctx, cx, cy, r, t, power) {
  ctx.save();
  // Aro físico
  ctx.lineWidth = r * 0.12; ctx.strokeStyle = "#1c222b"; ctx.beginPath(); ctx.ellipse(cx, cy, r, r, 0, 0, Math.PI * 2); ctx.stroke();
  ctx.lineWidth = r * 0.02; ctx.strokeStyle = "#3b4552"; ctx.beginPath(); ctx.ellipse(cx, cy, r * 1.06, r * 1.06, 0, 0, Math.PI * 2); ctx.stroke();
  // Segmentos y energía
  for (let i = 0; i < 24; i += 1) {
    const a = (i / 24) * Math.PI * 2 + t * 0.1;
    const on = power > (i / 24) * 0.9 ? 1 : 0.15;
    ctx.strokeStyle = `rgba(110,210,255,${0.25 + 0.6 * on * power})`; ctx.lineWidth = r * 0.03;
    ctx.beginPath(); ctx.arc(cx, cy, r, a, a + 0.18); ctx.stroke();
  }
  if (power > 0.05) {
    const g = ctx.createRadialGradient(cx, cy, r * 0.1, cx, cy, r * 0.95);
    g.addColorStop(0, `rgba(200,240,255,${0.55 * power})`); g.addColorStop(0.6, `rgba(70,160,255,${0.25 * power})`); g.addColorStop(1, "rgba(30,80,200,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r * 0.94, 0, Math.PI * 2); ctx.fill();
    // Remolino
    ctx.strokeStyle = `rgba(180,230,255,${0.35 * power})`; ctx.lineWidth = 2 * U;
    for (let k = 0; k < 7; k += 1) { ctx.beginPath(); for (let s = 0; s < 60; s += 1) { const rr = r * 0.9 * (s / 60); const a = s * 0.18 + t * (1.2 + power * 3) + k; const px = cx + Math.cos(a) * rr, py = cy + Math.sin(a) * rr; s ? ctx.lineTo(px, py) : ctx.moveTo(px, py); } ctx.stroke(); }
    // Arcos eléctricos
    const rr = rnd(Math.floor(t * 12));
    ctx.strokeStyle = `rgba(220,245,255,${0.7 * power})`; ctx.lineWidth = 1.5 * U;
    for (let k = 0; k < Math.floor(power * 6); k += 1) { const a = rr() * Math.PI * 2; ctx.beginPath(); let px = cx + Math.cos(a) * r, py = cy + Math.sin(a) * r; ctx.moveTo(px, py); for (let s = 0; s < 6; s += 1) { px = lerp(px, cx, 0.22) + (rr() - 0.5) * r * 0.15; py = lerp(py, cy, 0.22) + (rr() - 0.5) * r * 0.15; ctx.lineTo(px, py); } ctx.stroke(); }
  }
  ctx.restore();
}

function lab(ctx, t, power, o = {}) {
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, "#05070b"); g.addColorStop(1, "#0b1018");
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // Pórticos al fondo
  ctx.strokeStyle = "rgba(90,120,160,0.12)"; ctx.lineWidth = 3 * U;
  for (let i = -4; i <= 4; i += 1) { ctx.beginPath(); ctx.moveTo(W / 2 + i * W * 0.12, H * 0.1); ctx.lineTo(W / 2 + i * W * 0.2, H); ctx.stroke(); }
  const cx = W / 2, cy = H * (o.cy || 0.45), r = H * (o.r || 0.3);
  genesisRing(ctx, cx, cy, r, t, power);
  // Piso con reflejo
  const fl = ctx.createLinearGradient(0, H * 0.78, 0, H);
  fl.addColorStop(0, `rgba(80,170,255,${0.08 + 0.12 * power})`); fl.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = fl; ctx.fillRect(0, H * 0.78, W, H * 0.22);
  // Consolas
  for (const side of [-1, 1]) { ctx.fillStyle = "#0d1219"; ctx.beginPath(); ctx.roundRect(W / 2 + side * W * 0.33 - W * 0.08, H * 0.7, W * 0.16, H * 0.12, 6 * U); ctx.fill(); ctx.fillStyle = `rgba(80,190,255,${0.3 + 0.2 * Math.sin(t * 2 + side)})`; ctx.fillRect(W / 2 + side * W * 0.33 - W * 0.065, H * 0.715, W * 0.13, H * 0.03); }
}

function letterBlock(ctx, lines, progress, saved, t) {
  // Hoja de cuaderno sobre una mesa, luz cálida
  const bg = ctx.createRadialGradient(W / 2, H * 0.45, 10, W / 2, H * 0.5, W * 0.7);
  bg.addColorStop(0, saved ? "#2a2a24" : "#1c1712"); bg.addColorStop(1, "#050404");
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  const pw = H * 0.92, ph = H * 0.72, px = W / 2 - pw / 2, py = H * 0.13;
  ctx.save();
  ctx.translate(W / 2, H / 2); ctx.rotate(-0.025); ctx.translate(-W / 2, -H / 2);
  ctx.shadowColor = "rgba(0,0,0,0.6)"; ctx.shadowBlur = 30 * U;
  ctx.fillStyle = saved ? "#f2efe2" : "#e6dcc6"; ctx.fillRect(px, py, pw, ph);
  ctx.shadowBlur = 0;
  ctx.strokeStyle = "rgba(90,130,200,0.35)"; ctx.lineWidth = U;
  const lh = ph / 11;
  for (let i = 1; i < 11; i += 1) { ctx.beginPath(); ctx.moveTo(px, py + i * lh); ctx.lineTo(px + pw, py + i * lh); ctx.stroke(); }
  ctx.strokeStyle = "rgba(200,60,60,0.4)"; ctx.beginPath(); ctx.moveTo(px + pw * 0.1, py); ctx.lineTo(px + pw * 0.1, py + ph); ctx.stroke();
  // Texto que se va escribiendo
  const total = lines.join("").length; let budget = progress * total;
  ctx.font = `italic 400 ${lh * 0.52}px ${HAND}`; ctx.fillStyle = "#24304a"; ctx.textBaseline = "alphabetic";
  lines.forEach((line, i) => {
    if (budget <= 0) return;
    const shown = line.slice(0, Math.max(0, Math.floor(budget)));
    budget -= line.length;
    ctx.fillText(shown, px + pw * 0.13, py + (i + 1.75) * lh);
  });
  if (!saved) { ctx.fillStyle = "rgba(120,90,50,0.15)"; ctx.beginPath(); ctx.ellipse(px + pw * 0.8, py + ph * 0.75, pw * 0.12, ph * 0.08, 0.4, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore();
}

// --- utilidades de cámara del terreno -------------------------------------------------------------------------
function terrainCam(id, t, dur, o = {}) {
  const Tr = GL.terrains[id];
  // Órbita dentro del cuadro de datos, mirando hacia abajo: el borde del terreno queda lejos y se funde con el cielo.
  const R = Tr.half * (o.radius || 0.45), alt = Tr.maxH * 0.85 + Tr.half * (o.alt || 0.45);
  const a = (o.angle || 0.6) + (t / dur) * (o.sweep || 0.55);
  const eye = [Math.cos(a) * R, alt, Math.sin(a) * R];
  const target = [Math.cos(a + Math.PI) * Tr.half * 0.25, Tr.maxH * 0.25, Math.sin(a + Math.PI) * Tr.half * 0.25];
  return { eye, target };
}

function project(eye, target, fov, p) {
  const proj = GL.perspective(fov, W / H, 5, 1e6), view = GL.lookAt(eye, target, [0, 1, 0]), m = GL.mul(proj, view);
  const x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12], y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13], w = m[3] * p[0] + m[7] * p[1] + m[11] * p[2] + m[15];
  return w > 0 ? [(x / w * 0.5 + 0.5) * W, (1 - (y / w * 0.5 + 0.5)) * H] : null;
}

function skyFor(health, mood = "dia") {
  if (mood === "amanecer") return [lerp(0.55, 0.85, health), lerp(0.42, 0.62, health), lerp(0.35, 0.55, health)];
  if (mood === "tarde") return [0.62, 0.48, 0.42];
  return [lerp(0.62, 0.55, health), lerp(0.55, 0.72, health), lerp(0.48, 0.88, health)];
}

function placeLabel(ctx, name, t) {
  const a = ease(t / 0.8);
  ctx.save(); ctx.globalAlpha = a;
  ctx.fillStyle = "rgba(0,0,0,0.45)"; ctx.fillRect(W * 0.05, H * 0.72, W * 0.36, H * 0.09);
  ctx.fillStyle = "#f1c84b"; ctx.fillRect(W * 0.05, H * 0.72, 4 * U, H * 0.09);
  text(ctx, name, W * 0.065, H * 0.748, 24, { align: "left", weight: 700 });
  text(ctx, "Copernicus DEM GLO-30 · ESA WorldCover 2021", W * 0.065, H * 0.788, 11.5, { align: "left", weight: 400, color: "#c9d2da" });
  ctx.restore();
}

// --- escenas ----------------------------------------------------------------------------------------------------
SCENES.negro_titulo = (ctx, t, dur, p) => {
  blackGL();
  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
  if (p.caption) text(ctx, p.caption, W / 2, H / 2, 120, { weight: 800, spacing: 18, color: "#e8ecef", alpha: ease(t / 1.2) * (1 - ease((t - dur + 0.8) / 0.8)), glow: "rgba(255,140,80,0.5)" });
  else { const r = rnd(5); for (let i = 0; i < 60; i += 1) { const y = (r() * H - t * 12 * U * (0.5 + r())) % H; ctx.fillStyle = `rgba(255,${120 + r() * 80},60,${0.15 + 0.3 * r()})`; ctx.fillRect(r() * W, (y + H) % H, 2 * U, 2 * U); } }
};

SCENES.negro_radio = (ctx, t, dur) => {
  blackGL();
  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
  text(ctx, T().log, W / 2, H * 0.36, 15, { weight: 600, spacing: 4, color: "#8fb4d8", alpha: ease(t / 0.8) });
  ctx.strokeStyle = "rgba(120,190,255,0.85)"; ctx.lineWidth = 2 * U; ctx.beginPath();
  for (let x = W * 0.25; x <= W * 0.75; x += 3) { const k = (x - W * 0.25) / (W * 0.5); const env = Math.sin(Math.PI * k); const v = (Math.sin(x * 0.07 + t * 22) * 0.6 + Math.sin(x * 0.19 - t * 31) * 0.4) * env * (0.4 + 0.6 * Math.abs(Math.sin(t * 3.1))); ctx.lineTo(x, H / 2 + v * H * 0.06); }
  ctx.stroke();
};

SCENES.tierra_desde_luna = (ctx, t, dur, p) => {
  const k = t / dur, health = p.health ?? 0;
  const r = H * (0.31 + 0.03 * k);
  GL.drawPlanet({ earth: [W * 0.56, H * 0.4 - 10 * U * k, r], rot: 2.1 + t * 0.012, tilt: 0.38, health, time: t + (p.seed || 0), sun: [-0.75, 0.3, 0.6] });
  lunarGround(ctx, H * 0.74 + 10 * U * k, 3, 0.9);
  colony(ctx, W * 0.8, H * 0.79, 0.3 * U, t);
};

SCENES.tierra_hoy = (ctx, t, dur, p) => SCENES.tierra_desde_luna(ctx, t, dur, { ...p, health: p.health ?? 0.75, seed: 40 });

SCENES.colonia = (ctx, t, dur, p) => {
  const k = t / dur;
  GL.drawPlanet({ earth: [W * 0.27, H * 0.27, H * 0.17], rot: 2.4 + t * 0.01, tilt: 0.38, health: p.health ?? 0, time: t, sun: [-0.7, 0.35, 0.6] });
  ctx.save(); ctx.translate(-30 * U * k, 0);
  lunarGround(ctx, H * 0.66, 17, 1);
  colony(ctx, W * 0.56, H * 0.72, 0.85 * U, t);
  // Vehículo y dos figuras pequeñas
  ctx.fillStyle = "#2b3038"; ctx.beginPath(); ctx.roundRect(W * 0.3, H * 0.79, 70 * U, 22 * U, 6 * U); ctx.fill();
  ctx.fillStyle = "rgba(255,220,160,0.9)"; ctx.fillRect(W * 0.3 + 64 * U, H * 0.795, 6 * U, 4 * U);
  person(ctx, "andres", W * 0.42, H * 0.84, 34 * U, "rgba(200,210,230,0.5)");
  person(ctx, "viajero", W * 0.44, H * 0.84, 32 * U, "rgba(200,210,230,0.5)");
  ctx.restore();
};

function windowScene(ctx, t, dur, p, o = {}) {
  const k = t / dur;
  const health = p.from != null ? lerp(p.from, p.to, ease((t - dur * 0.12) / (dur * 0.6))) : (p.health ?? 0);
  const close = o.close ? 1 : 0;
  const zoom = 1 + 0.06 * k + close * 0.35;
  const er = H * 0.21 * zoom;
  GL.drawPlanet({ earth: [W * 0.5, H * (0.38 - close * 0.02), er], rot: 2.0 + t * 0.012, tilt: 0.36, health, doom: o.doom || 0, time: t + 12, sun: [-0.6, 0.3, 0.72] });
  const rimH = health > 0.5 ? "rgba(130,180,255,0.6)" : "rgba(255,160,90,0.55)";
  ctx.save();
  ctx.translate(W / 2, H / 2); ctx.scale(zoom * (close ? 0.95 : 1), zoom * (close ? 0.95 : 1)); ctx.translate(-W / 2, -H / 2);
  observationRoom(ctx, t, { alarm: o.alarm, floor: health > 0.5 ? "rgba(90,140,220,0.2)" : "rgba(220,120,60,0.16)" });
  ctx.restore();
  const who = p.who || ["mario", "andres"];
  const base = H * (close ? 1.25 : 0.98), tall = H * (close ? 0.95 : 0.62);
  const slots = who.length === 1 ? [0.5] : who.length === 2 ? [0.43, 0.57] : [0.36, 0.5, 0.64];
  who.forEach((kind, i) => {
    const h = tall * (kind === "mario" ? 0.72 : kind === "andres" ? 1.04 : 1);
    person(ctx, kind, W * slots[i] + Math.sin(t * 0.7 + i) * 1.5 * U, base + (kind === "mario" ? 0 : 0), h, o.alarm ? "rgba(255,80,60,0.6)" : rimH);
  });
}

SCENES.ventana = (ctx, t, dur, p) => windowScene(ctx, t, dur, p);
SCENES.ventana_cerca = (ctx, t, dur, p) => windowScene(ctx, t, dur, p, { close: true });
SCENES.ventana_revela = (ctx, t, dur, p) => windowScene(ctx, t, dur, p);
SCENES.ventana_oscura = (ctx, t, dur, p) => windowScene(ctx, t, dur, { ...p, health: 0 }, { doom: 0.9 });
SCENES.alarma = (ctx, t, dur, p) => windowScene(ctx, t, dur, { ...p, who: ["andres", "mario", "viajero"], health: 0 }, { alarm: true, doom: 0.25 * ease(t / dur) });

SCENES.genesis = (ctx, t, dur, p) => {
  blackGL();
  lab(ctx, t, 0.35 + 0.15 * Math.sin(t * 0.8));
  person(ctx, "nikol", W * 0.3, H * 0.86, H * 0.42, "rgba(110,200,255,0.6)");
  crowd(ctx, H * 0.96, 14, 4, H * 0.3, "rgba(110,200,255,0.35)");
};

SCENES.genesis_cerca = (ctx, t, dur, p) => {
  blackGL();
  ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(1.25, 1.25); ctx.translate(-W / 2, -H / 2);
  lab(ctx, t, 0.4 + 0.1 * Math.sin(t));
  ctx.restore();
  const who = p.who || ["viajero", "nikol"];
  const slots = who.length === 2 ? [0.3, 0.7] : [0.24, 0.5, 0.76];
  who.forEach((kind, i) => person(ctx, kind, W * slots[i], H * 1.12, H * (kind === "mario" ? 0.6 : 0.85), "rgba(110,200,255,0.6)"));
};

SCENES.colonia_calma = (ctx, t, dur, p) => {
  blackGL();
  lab(ctx, t, 0.08 * (1 - t / dur), { cy: 0.42, r: 0.26 });
  // Humo del salto
  ctx.fillStyle = `rgba(200,230,255,${0.12 * (1 - t / dur)})`; ctx.fillRect(0, 0, W, H);
  person(ctx, "viajero", W * 0.5, H * 0.95, H * 0.5, "rgba(170,220,255,0.6)");
  const run = ease(t / (dur * 0.5));
  person(ctx, "mario", lerp(W * 0.95, W * 0.62, run), H * 0.95, H * 0.36, "rgba(170,220,255,0.6)");
};

SCENES.activacion = (ctx, t, dur, p) => {
  blackGL();
  const k = t / dur;
  const shake = k > 0.6 ? (k - 0.6) * 6 * U : 0;
  ctx.save(); ctx.translate((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake);
  lab(ctx, t, 0.5 + 0.5 * ease(k));
  person(ctx, "viajero", W * 0.5, H * 0.79, H * 0.2, "rgba(220,245,255,0.9)");
  person(ctx, "nikol", W * 0.18, H * 0.95, H * 0.5, "rgba(110,200,255,0.6)");
  person(ctx, "mario", W * 0.84, H * 0.97, H * 0.36, "rgba(110,200,255,0.6)");
  ctx.restore();
  if (p.flashEnd) return;
};

SCENES.activacion_debil = (ctx, t, dur) => {
  blackGL();
  const flick = Math.max(0, Math.sin(t * 7) * Math.sin(t * 2.3)) * 0.5 + 0.1;
  lab(ctx, t, flick);
  ctx.fillStyle = "rgba(255,90,60,0.06)"; ctx.fillRect(0, 0, W, H);
};

SCENES.tunel = (ctx, t, dur, p) => {
  const k = t / dur;
  GL.drawTunnel({ time: t, speed: 1 + 2 * ease(k), flash: k > 0.9 ? (k - 0.9) * 10 : (k < 0.06 ? 1 - k / 0.06 : 0) });
  const year = Math.round(lerp(2045, 2026, ease((t - dur * 0.15) / (dur * 0.7))));
  text(ctx, String(year), W / 2, H / 2, 96, { weight: 800, spacing: 12, color: "#ffffff", glow: "rgba(120,200,255,0.9)", alpha: clamp(t / 0.6) * (1 - clamp((k - 0.88) * 8)) });
};

SCENES.llegada = (ctx, t, dur, p) => {
  const id = "chosica";
  const cam = terrainCam(id, t, dur, { angle: 2.2, sweep: 0.25, alt: 0.3, radius: 0.45 });
  GL.drawTerrain({ id, ...cam, health: p.health ?? 0.75, sky: skyFor(0.75, "amanecer"), sun: [0.9, 0.25, 0.2], time: t });
  // Enlace por radio
  const x = W * 0.06, y = H * 0.66, w = W * 0.3, h = H * 0.13;
  ctx.fillStyle = "rgba(5,12,20,0.72)"; ctx.beginPath(); ctx.roundRect(x, y, w, h, 8 * U); ctx.fill();
  ctx.strokeStyle = "rgba(110,200,255,0.5)"; ctx.lineWidth = U; ctx.stroke();
  text(ctx, "GÉNESIS · 2045 ⇄ 2026", x + 14 * U, y + 18 * U, 12, { align: "left", spacing: 2, color: "#8fd0ff" });
  for (let i = 0; i < 4; i += 1) { ctx.fillStyle = i < 1 ? "#f1c84b" : "rgba(241,200,75,0.25)"; ctx.fillRect(x + w - 40 * U + i * 7 * U, y + 22 * U - (i + 1) * 3 * U, 5 * U, (i + 1) * 3 * U); }
  ctx.fillStyle = "rgba(120,200,255,0.85)";
  for (let i = 0; i < 40; i += 1) { const v = Math.abs(Math.sin(i * 0.7 + t * 9) * Math.sin(i * 0.23 - t * 4)) * (Math.random() * 0.4 + 0.6); const bh = v * h * 0.5; ctx.fillRect(x + 14 * U + i * (w - 28 * U) / 40, y + h * 0.62 - bh / 2, (w - 28 * U) / 60, bh); }
};

SCENES.terreno = (ctx, t, dur, p) => {
  const id = p.place;
  const cam = terrainCam(id, t, dur, { angle: p.angle ?? 0.7, sweep: 0.5, alt: p.alt, radius: p.radius });
  const health = p.health ?? 0.8;
  GL.drawTerrain({ id, ...cam, health, sky: skyFor(health), sun: [0.55, 0.6, 0.35], haze: p.haze || 0, time: t });
  if (p.label) placeLabel(ctx, p.label, t);
};

function montage(ctx, t, dur, p, healthOf) {
  const places = p.places || ["chosica"];
  const seg = dur / places.length, i = Math.min(places.length - 1, Math.floor(t / seg)), lt = t - i * seg;
  const id = places[i], health = healthOf(i);
  const cam = terrainCam(id, lt, seg, { angle: 0.4 + i * 1.7, sweep: 0.35 });
  GL.drawTerrain({ id, ...cam, health, sky: skyFor(health), sun: [0.55, 0.6, 0.35], haze: health < 0.5 ? 0.55 : 0, time: t });
  placeLabel(ctx, DATA.names?.[id] || id, lt);
  if (health > 0.9) { const a = ease((lt - 0.6) / 0.6); ctx.save(); ctx.globalAlpha = a; ctx.fillStyle = "#3fbf8f"; ctx.beginPath(); ctx.arc(W * 0.93, H * 0.16, 18 * U, 0, Math.PI * 2); ctx.fill(); ctx.restore(); text(ctx, "✓", W * 0.93, H * 0.16, 20, { weight: 800, color: "#06140d", alpha: a }); }
  // corte con fundido entre lugares
  const edge = Math.min(lt, seg - lt);
  if (edge < 0.3 && i > 0 && lt < 0.3) { ctx.fillStyle = `rgba(0,0,0,${1 - lt / 0.3})`; ctx.fillRect(0, 0, W, H); }
  if (seg - lt < 0.3 && i < places.length - 1) { ctx.fillStyle = `rgba(0,0,0,${1 - (seg - lt) / 0.3})`; ctx.fillRect(0, 0, W, H); }
}
SCENES.montaje_lugares = (ctx, t, dur, p) => montage(ctx, t, dur, p, () => 1);
SCENES.montaje_mixto = (ctx, t, dur, p) => montage(ctx, t, dur, p, (i) => (i % 2 === 0 ? 1 : 0.25));
SCENES.montaje_perdido = (ctx, t, dur, p) => montage(ctx, t, dur, p, () => 0.1);

SCENES.aviso = (ctx, t, dur, p) => {
  const id = p.place || "chosica";
  const cam = terrainCam(id, t, dur, { angle: 3.4, sweep: 0.3, alt: 0.5 });
  GL.drawTerrain({ id, ...cam, health: 0.75, sky: skyFor(0.6, "tarde"), sun: [0.8, 0.35, 0.2], time: t });
  const Tr = GL.terrains[id];
  const r = rnd(21);
  for (let i = 0; i < 6; i += 1) {
    const x = (r() - 0.5) * Tr.half * 1.2, z = (r() - 0.5) * Tr.half * 1.2, y = GL.terrainHeight(id, x, z);
    const s = project(cam.eye, cam.target, 0.9, [x, y + 20, z]); if (!s) continue;
    const appear = ease((t - 0.6 - i * 0.7) / 0.5); if (appear <= 0) continue;
    const pulse = (t * 0.9 + i * 0.3) % 1;
    ctx.strokeStyle = `rgba(241,200,75,${(1 - pulse) * appear})`; ctx.lineWidth = 2 * U; ctx.beginPath(); ctx.arc(s[0], s[1], (10 + pulse * 46) * U, 0, Math.PI * 2); ctx.stroke();
    const done = t > 1.6 + i * 0.9;
    ctx.fillStyle = done ? "#3fbf8f" : "#f1c84b"; ctx.beginPath(); ctx.arc(s[0], s[1] - 26 * U, 13 * U * appear, 0, Math.PI * 2); ctx.fill();
    text(ctx, done ? "✓" : "!", s[0], s[1] - 26 * U, 16, { weight: 800, color: "#0b1418" });
    ctx.strokeStyle = "rgba(255,255,255,0.6)"; ctx.lineWidth = 1.5 * U; ctx.beginPath(); ctx.moveTo(s[0], s[1] - 13 * U); ctx.lineTo(s[0], s[1]); ctx.stroke();
  }
};

SCENES.tierra_datos = (ctx, t, dur, p) => {
  const cx = W * 0.64, cy = H * 0.48, r = H * 0.34, rot = 1.9 + t * 0.03;
  GL.drawPlanet({ earth: [cx, cy, r], rot, tilt: 0.3, health: p.health ?? 0.75, time: t, sun: [-0.5, 0.3, 0.8] });
  // Retícula de latitud y longitud (proyección ortográfica, la misma rotación del planeta)
  ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.clip();
  ctx.strokeStyle = "rgba(120,200,255,0.18)"; ctx.lineWidth = U;
  const tilt = 0.3;
  const toScreen = (lat, lon) => { let x = Math.cos(lat) * Math.sin(lon - rot), y = Math.sin(lat), z = Math.cos(lat) * Math.cos(lon - rot); const yy = Math.cos(tilt) * y + Math.sin(tilt) * z, zz = -Math.sin(tilt) * y + Math.cos(tilt) * z; return zz > 0 ? [cx + x * r, cy - yy * r] : null; };
  for (let lat = -60; lat <= 60; lat += 30) { ctx.beginPath(); let on = false; for (let lon = -180; lon <= 180; lon += 4) { const s = toScreen(lat * Math.PI / 180, lon * Math.PI / 180); if (s) { on ? ctx.lineTo(...s) : ctx.moveTo(...s); on = true; } else on = false; } ctx.stroke(); }
  for (let lon = -180; lon < 180; lon += 30) { ctx.beginPath(); let on = false; for (let lat = -90; lat <= 90; lat += 4) { const s = toScreen(lat * Math.PI / 180, lon * Math.PI / 180); if (s) { on ? ctx.lineTo(...s) : ctx.moveTo(...s); on = true; } else on = false; } ctx.stroke(); }
  // Banda de barrido del satélite
  const sweep = ((t * 0.35) % 1.4) - 0.2;
  const g = ctx.createLinearGradient(cx - r, 0, cx + r, 0);
  g.addColorStop(clamp(sweep - 0.08), "rgba(80,200,255,0)"); g.addColorStop(clamp(sweep), "rgba(80,200,255,0.28)"); g.addColorStop(clamp(sweep + 0.02), "rgba(80,200,255,0)");
  ctx.fillStyle = g; ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
  ctx.restore();
  // Capas
  const L = T().layers, active = Math.floor(t / (dur / L.length)) % L.length;
  text(ctx, T().layersTitle, W * 0.07, H * 0.2, 15, { align: "left", color: "#8fd0ff", weight: 600, spacing: 1 });
  const colors = ["#e8eef4", "#ff7a59", "#62c26b", "#ff5a36", "#5aa8ff", "#c9a36b"];
  L.forEach((name, i) => {
    const y = H * 0.27 + i * H * 0.065, on = i === active;
    ctx.fillStyle = on ? "rgba(20,40,60,0.85)" : "rgba(10,18,26,0.6)"; ctx.beginPath(); ctx.roundRect(W * 0.07, y - H * 0.025, W * 0.26, H * 0.05, 6 * U); ctx.fill();
    ctx.fillStyle = colors[i]; ctx.beginPath(); ctx.arc(W * 0.085, y, 5 * U, 0, Math.PI * 2); ctx.fill();
    text(ctx, name, W * 0.1, y, 14, { align: "left", weight: on ? 700 : 500, color: on ? "#ffffff" : "#9fb0bf" });
  });
};

SCENES.datos = (ctx, t, dur, p) => {
  blackGL();
  const m = DATA.missions?.[p.place];
  ctx.fillStyle = "#070b10"; ctx.fillRect(0, 0, W, H);
  if (!m) return;
  const tr = m.temperature;
  const pts = tr.annual_series.filter((d) => d.value != null);
  const x0 = W * 0.12, x1 = W * 0.88, y0 = H * 0.7, y1 = H * 0.3;
  const vs = pts.map((d) => d.value), lo = Math.min(...vs) - 0.2, hi = Math.max(...vs) + 0.2;
  const X = (yr) => lerp(x0, x1, (yr - pts[0].year) / (pts[pts.length - 1].year - pts[0].year)), Y = (v) => lerp(y0, y1, (v - lo) / (hi - lo));
  text(ctx, T().chartTitle(m.name), W * 0.12, H * 0.17, 24, { align: "left", weight: 700 });
  text(ctx, T().chartSrc, W * 0.12, H * 0.215, 13, { align: "left", weight: 400, color: "#9fb0bf" });
  ctx.strokeStyle = "rgba(255,255,255,0.12)"; ctx.lineWidth = U;
  for (let v = Math.ceil(lo * 2) / 2; v <= hi; v += 0.5) { ctx.beginPath(); ctx.moveTo(x0, Y(v)); ctx.lineTo(x1, Y(v)); ctx.stroke(); text(ctx, `${v.toFixed(1)} °C`, x0 - 10 * U, Y(v), 11, { align: "right", weight: 400, color: "#7f8f9c" }); }
  for (const yr of [pts[0].year, 2010, 2020, pts[pts.length - 1].year]) text(ctx, String(yr), X(yr), y0 + 18 * U, 11, { weight: 400, color: "#7f8f9c" });
  const draw = ease((t - 0.4) / (dur * 0.45));
  ctx.strokeStyle = "#e9eef2"; ctx.lineWidth = 2.5 * U; ctx.beginPath();
  const n = Math.max(1, Math.floor(draw * pts.length));
  pts.slice(0, n).forEach((d, i) => (i ? ctx.lineTo(X(d.year), Y(d.value)) : ctx.moveTo(X(d.year), Y(d.value))));
  ctx.stroke();
  pts.slice(0, n).forEach((d) => { ctx.fillStyle = "#e9eef2"; ctx.beginPath(); ctx.arc(X(d.year), Y(d.value), 2.6 * U, 0, Math.PI * 2); ctx.fill(); });
  const fit = ease((t - dur * 0.5) / 0.8);
  if (fit > 0 && tr.significant && tr.slope_per_year != null) {
    const sorted = [...vs].sort((a, b) => a - b), med = sorted[Math.floor(sorted.length / 2)], mid = (pts[0].year + pts[pts.length - 1].year) / 2;
    ctx.strokeStyle = `rgba(255,110,80,${fit})`; ctx.lineWidth = 3 * U; ctx.setLineDash([10 * U, 6 * U]);
    ctx.beginPath(); ctx.moveTo(X(pts[0].year), Y(med + tr.slope_per_year * (pts[0].year - mid))); ctx.lineTo(X(pts[pts.length - 1].year), Y(med + tr.slope_per_year * (pts[pts.length - 1].year - mid))); ctx.stroke(); ctx.setLineDash([]);
    text(ctx, T().perDecade(tr.slope_per_year * 10), W * 0.88, H * 0.17, 26, { align: "right", weight: 800, color: "#ff8a6a", alpha: fit });
    text(ctx, T().signif, W * 0.88, H * 0.215, 12, { align: "right", weight: 400, color: "#d7a99c", alpha: fit });
  }
  const sec = ease((t - dur * 0.68) / 0.6);
  if (sec > 0) {
    const code = tr.second_source?.agreement || "sin_tendencia";
    const ok = code === "coincide";
    ctx.save(); ctx.globalAlpha = sec;
    ctx.fillStyle = ok ? "rgba(30,90,60,0.9)" : "rgba(110,80,20,0.9)"; ctx.beginPath(); ctx.roundRect(W * 0.12, H * 0.76, W * 0.38, H * 0.06, 8 * U); ctx.fill();
    text(ctx, T().second[code] || code, W * 0.135, H * 0.79, 15, { align: "left", weight: 700 });
    ctx.fillStyle = "rgba(50,60,70,0.9)"; ctx.beginPath(); ctx.roundRect(W * 0.52, H * 0.76, W * 0.36, H * 0.06, 8 * U); ctx.fill();
    text(ctx, T().unknown, W * 0.535, H * 0.79, 13.5, { align: "left", weight: 500, color: "#d9e1e7" });
    ctx.restore();
  }
};

SCENES.decision = (ctx, t, dur, p) => {
  blackGL();
  ctx.fillStyle = "#06090d"; ctx.fillRect(0, 0, W, H);
  const x = W * 0.2, w = W * 0.6;
  text(ctx, T().decTitle, x, H * 0.16, 24, { align: "left", weight: 700 });
  ctx.fillStyle = "rgba(60,20,26,0.9)"; ctx.beginPath(); ctx.roundRect(x, H * 0.2, w, H * 0.06, 8 * U); ctx.fill();
  text(ctx, T().indiff, x + 14 * U, H * 0.23, 13.5, { align: "left", weight: 500, color: "#f0c4ca" });
  const picks = [0, 1, 3]; const costs = [1, 2, 2, 1];
  const chosen = picks.filter((_, i) => t > 1.2 + i * 1.1);
  const used = chosen.reduce((s, i) => s + costs[i], 0);
  text(ctx, T().budget, x, H * 0.31, 13, { align: "left", color: "#9fb0bf", weight: 600 });
  for (let i = 0; i < 4; i += 1) { ctx.beginPath(); ctx.arc(x + 100 * U + i * 24 * U, H * 0.31, 8 * U, 0, Math.PI * 2); ctx.strokeStyle = "#4aa3ff"; ctx.lineWidth = 2 * U; ctx.stroke(); if (i < used) { ctx.fillStyle = "#4aa3ff"; ctx.fill(); } }
  T().measures.forEach((m, i) => {
    const y = H * 0.37 + i * H * 0.075, on = chosen.includes(i);
    ctx.fillStyle = on ? "rgba(16,34,54,1)" : "rgba(17,27,29,1)"; ctx.strokeStyle = on ? "#4aa3ff" : "#34454a"; ctx.lineWidth = 1.5 * U;
    ctx.beginPath(); ctx.roundRect(x, y, w, H * 0.06, 8 * U); ctx.fill(); ctx.stroke();
    text(ctx, m, x + 14 * U, y + H * 0.03, 15, { align: "left", weight: on ? 700 : 500 });
    text(ctx, "●".repeat(costs[i]), x + w - 14 * U, y + H * 0.03, 12, { align: "right", color: "#7f8f9c" });
  });
  const bars = ease((t - 4.6) / 1.0);
  if (bars > 0) {
    const vals = [6, 3, 3];
    T().axes.forEach((a, i) => {
      const y = H * 0.7 + i * H * 0.045;
      text(ctx, a, x, y, 13, { align: "left", weight: 500, color: "#c9d2da" });
      ctx.fillStyle = "#1b2427"; ctx.beginPath(); ctx.roundRect(x + w * 0.45, y - 7 * U, w * 0.55, 14 * U, 7 * U); ctx.fill();
      ctx.fillStyle = "#3fbf8f"; ctx.beginPath(); ctx.roundRect(x + w * 0.45, y - 7 * U, w * 0.55 * (vals[i] / 6) * bars, 14 * U, 7 * U); ctx.fill();
    });
  }
};

SCENES.planeta_cambia = (ctx, t, dur, p) => {
  const k = ease((t - 0.5) / (dur - 1.2));
  const health = lerp(p.from ?? 0, p.to ?? 1, k);
  GL.drawPlanet({ earth: [W * 0.5, H * 0.45, H * 0.33], rot: 1.2 + t * 0.08, tilt: 0.32, health, time: t * 3, sun: [-0.55, 0.3, 0.78] });
  const pct = Math.round(health * 100);
  const x = W * 0.3, w = W * 0.4, y = H * 0.86;
  ctx.fillStyle = "rgba(0,0,0,0.5)"; ctx.fillRect(x - 10 * U, y - 30 * U, w + 20 * U, 52 * U);
  text(ctx, T().planet, x, y - 16 * U, 12.5, { align: "left", color: "#c9d2da", weight: 600 });
  const tier = T().tiers[Math.min(4, Math.floor(Math.max(0, pct - 1) / 20))];
  text(ctx, `${tier} · ${pct} %`, x + w, y - 16 * U, 13, { align: "right", weight: 700 });
  const g = ctx.createLinearGradient(x, 0, x + w, 0); g.addColorStop(0, "#c2412c"); g.addColorStop(0.4, "#e0a83c"); g.addColorStop(0.7, "#3fbf8f"); g.addColorStop(1, "#4aa3ff");
  ctx.fillStyle = "rgba(255,255,255,0.1)"; ctx.fillRect(x, y, w, 8 * U); ctx.fillStyle = g; ctx.fillRect(x, y, w * health, 8 * U);
  text(ctx, T().gamified, x, y + 18 * U, 10, { align: "left", weight: 400, color: "#8796a3" });
};

SCENES.titulo = (ctx, t, dur, p) => {
  GL.drawPlanet({ earth: [W * 0.5, H * 1.78, H * 1.05], rot: 1.4 + t * 0.01, tilt: 0.2, health: 1, time: t, sun: [0.0, 0.9, 0.4], exposure: 0.9 });
  const a = ease(t / 1.2);
  text(ctx, "TERRA 2045", W / 2, H * 0.4, 92, { weight: 800, spacing: 20, color: "#f4f7fa", alpha: a, glow: "rgba(110,190,255,0.55)" });
  text(ctx, T().title2.toUpperCase(), W / 2, H * 0.5, 22, { weight: 500, spacing: 12, color: "#cfe3f7", alpha: ease((t - 0.6) / 1.0) });
  text(ctx, T().tagline, W / 2, H * 0.585, 19, { weight: 400, color: "#e6c9a8", alpha: ease((t - 1.8) / 1.0), font: HAND });
  text(ctx, T().by, W / 2, H * 0.86, 13, { weight: 500, spacing: 2, color: "#9fb0bf", alpha: ease((t - 2.4) / 1.0) });
};

SCENES.cuaderno = (ctx, t, dur, p) => { blackGL(); letterBlock(ctx, p.letter || T().letterLost, ease((t - 0.6) / (dur * 0.85)), false, t); };
SCENES.cuaderno_salvado = (ctx, t, dur, p) => { blackGL(); letterBlock(ctx, T().letterSaved, ease((t - 0.6) / (dur * 0.85)), true, t); };

SCENES.satelites = (ctx, t, dur, p) => {
  const cx = W * 0.5, cy = H * 0.48, r = H * 0.27;
  GL.drawPlanet({ earth: [cx, cy, r], rot: 1.0 + t * 0.05, tilt: 0.3, health: 0.7, time: t, sun: [-0.5, 0.35, 0.8] });
  const names = ["Terra", "Aqua", "GPM", "SMAP", "Landsat", "Suomi NPP"];
  names.forEach((name, i) => {
    const tilt = 0.25 + i * 0.22, rr = r * (1.25 + i * 0.09), a = t * (0.5 + i * 0.07) + i * 1.3;
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.3 + i * 0.5);
    ctx.strokeStyle = "rgba(120,200,255,0.18)"; ctx.lineWidth = U; ctx.beginPath(); ctx.ellipse(0, 0, rr, rr * tilt, 0, 0, Math.PI * 2); ctx.stroke();
    const sx = Math.cos(a) * rr, sy = Math.sin(a) * rr * tilt, front = Math.sin(a) > 0;
    if (front || Math.hypot(sx, sy) > r) {
      ctx.fillStyle = "#e8f4ff"; ctx.fillRect(sx - 3 * U, sy - 2 * U, 6 * U, 4 * U); ctx.fillStyle = "#4aa3ff"; ctx.fillRect(sx - 9 * U, sy - 1 * U, 5 * U, 2 * U); ctx.fillRect(sx + 4 * U, sy - 1 * U, 5 * U, 2 * U);
    }
    ctx.restore();
    const pos = (() => { const ang = -0.3 + i * 0.5; const x = Math.cos(a) * rr, y = Math.sin(a) * rr * tilt; return [cx + x * Math.cos(ang) - y * Math.sin(ang), cy + x * Math.sin(ang) + y * Math.cos(ang)]; })();
    text(ctx, name, pos[0] + 12 * U, pos[1] - 10 * U, 11, { align: "left", color: "#9fd4ff", weight: 600 });
  });
  const year = Math.round(lerp(2001, 2026, ease((t - 0.5) / (dur - 1.5))));
  text(ctx, String(year), W * 0.9, H * 0.2, 48, { align: "right", weight: 800, color: "#ffffff", glow: "rgba(110,190,255,0.6)" });
};

SCENES.foto = (ctx, t, dur, p) => {
  const cx = W * 0.52, cy = H * 0.45, r = H * 0.15;
  GL.drawPlanet({ earth: [cx, cy, r], rot: 2.0, tilt: 0.35, health: 1, time: 3, sun: [-0.5, 0.3, 0.8], stars: 0.35 });
  const pw = H * 0.42, ph = H * 0.5, px = cx - pw / 2, py = cy - H * 0.21;
  ctx.save();
  ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.rect(px + 14 * U, py + 14 * U, pw - 28 * U, pw - 28 * U);
  ctx.fillStyle = "#0b0907"; ctx.fill("evenodd");
  ctx.restore();
  ctx.save(); ctx.beginPath(); ctx.rect(px, py, pw, ph); ctx.rect(px + 14 * U, py + 14 * U, pw - 28 * U, pw - 28 * U); ctx.fillStyle = "#efe9dc"; ctx.fill("evenodd"); ctx.restore();
  ctx.strokeStyle = "rgba(0,0,0,0.3)"; ctx.lineWidth = U; ctx.strokeRect(px, py, pw, ph);
  text(ctx, "Tierra · 2001", cx, py + ph - 30 * U, 15, { font: HAND, weight: 400, color: "#3a3226" });
  const warm = ctx.createRadialGradient(cx, cy, 10, cx, cy, H * 0.7); warm.addColorStop(0, "rgba(255,200,140,0.05)"); warm.addColorStop(1, "rgba(0,0,0,0.3)"); ctx.fillStyle = warm; ctx.fillRect(0, 0, W, H);
};

SCENES.tierra_amanecer = (ctx, t, dur, p) => {
  const k = t / dur;
  GL.drawPlanet({ earth: [W * 0.5, H * 1.62, H * 1.15], rot: 4.4 + t * 0.006, tilt: -0.35, health: p.health ?? 1, time: t, sun: [0.15, 0.97 - 0.1 * (1 - k), 0.05 + 0.25 * k] });
  const g = ctx.createRadialGradient(W * 0.55, H * 0.47, 2, W * 0.55, H * 0.47, H * (0.25 + 0.2 * k));
  g.addColorStop(0, `rgba(255,250,235,${0.9 * ease(k * 1.4)})`); g.addColorStop(0.2, `rgba(255,210,140,${0.35 * ease(k * 1.4)})`); g.addColorStop(1, "rgba(255,180,100,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
};

SCENES.tierra_orbita = (ctx, t, dur, p) => {
  const k = t / dur;
  GL.drawPlanet({ earth: [W * (0.5 + 0.04 * Math.sin(k * 2)), H * 0.5, H * (0.36 + 0.06 * k)], rot: 3.6 + t * 0.03, tilt: 0.38, health: p.health ?? 1, time: t, sun: [-0.45, 0.25, 0.85],
    moon: [W * (0.12 + 0.05 * k), H * 0.78, H * 0.06], moonRot: 0.5 });
};

SCENES.colapso = (ctx, t, dur, p) => {
  const k = t / dur;
  const doom = ease(k * 1.05);
  const r = H * (0.36 + 0.04 * k);
  const shake = doom > 0.6 ? (doom - 0.6) * 5 * U : 0;
  GL.drawPlanet({ earth: [W * 0.5 + (Math.random() - 0.5) * shake, H * 0.47 + (Math.random() - 0.5) * shake, r], rot: 2.3 + t * 0.02, tilt: 0.36, health: 0, doom, time: t * 2, sun: [-0.6, 0.3, 0.74], exposure: 1 - 0.55 * ease((k - 0.85) / 0.15) });
  // Ceniza y resplandor
  const rr = rnd(9);
  for (let i = 0; i < 90; i += 1) { const x = rr() * W, y = ((rr() * H) + t * (20 + rr() * 40) * U) % H; ctx.fillStyle = `rgba(255,${100 + rr() * 80},40,${0.1 + 0.4 * rr() * doom})`; ctx.fillRect(x, y, 2 * U, 2 * U); }
  ctx.fillStyle = `rgba(120,20,5,${0.12 * doom})`; ctx.fillRect(0, 0, W, H);
};

SCENES.creditos = (ctx, t, dur, p) => {
  GL.drawPlanet({ earth: [W * 0.82, H * 0.5, H * 0.22], rot: 2 + t * 0.02, tilt: 0.3, health: p.health ?? 1, time: t, sun: [-0.6, 0.3, 0.7], exposure: 0.8 });
  const lines = DATA.credits?.[LANG] || [];
  const lh = 30 * U, total = lines.length * lh + H;
  const y0 = H - (t / dur) * total;
  lines.forEach((line, i) => {
    const y = y0 + i * lh; if (y < -lh || y > H + lh) return;
    const head = line.startsWith("#");
    text(ctx, head ? line.slice(1) : line, W * 0.36, y, head ? 17 : 13.5, { weight: head ? 700 : 400, color: head ? "#f1c84b" : "#dfe6ec" });
  });
};
