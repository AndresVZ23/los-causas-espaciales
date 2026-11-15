// Tomas fijas de la aplicación real para el demo de 30 segundos (ADR-051): el globo del modo espectador con capas de
// NASA GIBS, la portada del juego y la plataforma después de un análisis de clima. Salen a 2880 × 1620 (una vez y media
// la pantalla) para poder acercar la cámara sin perder nitidez; overlay.html las usa por nombre.
//
//   node scripts/video/demo30/tomas.cjs [carpeta de salida]        # por defecto videos/demo30/tomas
//
// Necesita la aplicación en marcha (QA_BASE_URL, por defecto http://localhost:3100) con su API, y Playwright para Node
// (PLAYWRIGHT_DIR = carpeta node_modules que lo contiene, si no se resuelve solo). El análisis de clima usa los dos
// sitios que la plataforma trae por defecto (Moquegua y Arequipa) y puede tardar un minuto la primera vez.
// Las posiciones de los resaltes de overlay.html dependen de estas tomas: si cambia la interfaz, hay que revisarlas.
const path = require("path");
const fs = require("fs");
const { chromium } = require(process.env.PLAYWRIGHT_DIR ? path.join(process.env.PLAYWRIGHT_DIR, "playwright") : "playwright");

const BASE = (process.env.QA_BASE_URL || "http://localhost:3100").replace(/\/+$/, "");
const OUT = path.resolve(process.argv[2] || path.join(__dirname, "..", "..", "..", "videos", "demo30", "tomas"));
fs.mkdirSync(OUT, { recursive: true });
// Paneles y controles que se ocultan en las tomas «limpias» del globo (la atribución va en los créditos del video).
const CLEAN = ".gameContinents, .gameHud, .gameFoot, [class*='gameVision'], .maplibregl-ctrl { visibility: hidden !important; }";

(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--ignore-gpu-blocklist"] });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1.5 });
  const page = await context.newPage();
  page.on("pageerror", (error) => console.log("PAGEERROR", error.message));
  const shot = async (name) => { await page.screenshot({ path: path.join(OUT, `${name}.jpg`), type: "jpeg", quality: 93 }); console.log("ok", name); };
  const settle = async (ms) => { await page.waitForLoadState("networkidle").catch(() => undefined); await page.waitForTimeout(ms); };
  const clean = async (work) => { const style = await page.addStyleTag({ content: CLEAN }); await page.waitForTimeout(400); await work(); await style.evaluate((el) => el.remove()); };

  // 1. Portada del juego.
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await settle(3500);
  await shot("portada");

  // 2. Globo del modo espectador: los lugares, la lluvia del día y la anomalía de temperatura del mar.
  await page.getByRole("button", { name: /Espectador/ }).click();
  await settle(3000);
  await page.getByRole("button", { name: /^Sudamérica/ }).click();
  await settle(3500);
  await shot("globo-lugares");
  await page.getByRole("button", { name: "Lluvia", exact: true }).click();
  await settle(7000);
  await clean(() => shot("globo-lluvia-limpio"));
  await page.getByRole("button", { name: "Mar más caliente", exact: true }).click();
  await settle(4000);
  await clean(async () => {
    // Se gira el globo arrastrando para dejar el Pacífico frente al Perú en el centro.
    await page.mouse.move(1130, 560); await page.mouse.down(); await page.mouse.move(1330, 590, { steps: 24 }); await page.mouse.up();
    await settle(7000);
    await shot("globo-mar-pacifico-limpio");
  });

  // 3. Plataforma: análisis de clima con los sitios por defecto.
  await page.goto(BASE + "/plataforma", { waitUntil: "networkidle" });
  await settle(1500);
  await page.getByRole("button", { name: "Clima", exact: true }).first().click();
  await page.waitForTimeout(800);
  await page.getByRole("button", { name: "Ejecutar análisis" }).click();
  let finished = false;
  for (let i = 0; i < 80 && !finished; i += 1) {
    await page.waitForTimeout(2500);
    finished = /9 Exportación (Listo|Completado|Parcial)/.test((await page.locator("body").innerText()).replace(/\s+/g, " "));
  }
  if (!finished) throw new Error("El análisis de clima no terminó en 200 s.");
  await settle(2500);
  for (const [tab, name] of [["Temperatura", "plataforma-temperatura"], ["Precipitación", "plataforma-precipitacion"]]) {
    await page.getByRole("button", { name: tab, exact: true }).first().click();
    await page.waitForTimeout(1300);
    await shot(name);
  }
  // Fila = el antecesor ancho (más de 1300 px) más cercano al título; se deja a `top` píxeles del borde superior.
  const rowTo = async (title, top) => {
    const y = await page.evaluate((text) => {
      const el = [...document.querySelectorAll("*")].find((e) => e.children.length === 0 && (e.textContent || "").trim().startsWith(text));
      if (!el) return null;
      let row = el;
      while (row.parentElement && row.getBoundingClientRect().width < 1300) row = row.parentElement;
      return row.getBoundingClientRect().y + window.scrollY;
    }, title);
    if (y == null) throw new Error(`No se encontró la fila «${title}».`);
    await page.evaluate((to) => window.scrollTo(0, to), Math.max(0, y - top));
    await page.waitForTimeout(700);
  };
  await rowTo("Las preguntas del reto NASA", 70);
  await shot("plataforma-preguntas");
  // 311 y no 300: es donde quedó esta fila en la toma del 15-nov, y el resalte de overlay.html está puesto ahí.
  await rowTo("Moquegua: temperatura del aire a 2 m: la tendencia se confirma con ERA5", 311);
  await shot("fuentes-confirmado");
  await rowTo("Moquegua: el evento de 2022 solo aparece en el reanálisis", 300);
  await shot("fuentes-artefacto");

  await browser.close();
  console.log("tomas en", OUT);
})().catch((error) => { console.error("FALLO", error.message.slice(0, 600)); process.exit(1); });
