// QA del modo jugador (/jugar) con la tarjeta gráfica real (Chromium «nuevo headless» + D3D11).
// El headless normal de Playwright dibuja por software y va a 1 cuadro por segundo: no sirve para juzgar el juego.
//
//   node scripts/qa/game_ui.cjs <prefijo> <1440|768|390> <mundo|globo|luna|panel> [texto de la misión] [segundos en el mundo] [teclas]
//
// - Capturas en .claude-qa/jugar/<prefijo>-<ancho>-<escena>-N-<momento>.png
// - QA_BASE_URL: dirección de la aplicación (por defecto http://localhost:3100).
// - QA_QUERY="?luz=dia" fija la luz del mundo (dia, noche o real); QA_REDUCED_MOTION=1 pide «reducir movimiento».
// - [teclas]: lista separada por comas que se pulsa en el mundo, cada una 1.5 s (p. ej. "w,w,d,v,Space").
// Imprime JSON: cuadros por segundo, texto visible, placas que se pisan o se salen, botones sin nombre, errores de consola y 4xx/5xx.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "jugar");
fs.mkdirSync(OUT, { recursive: true });
const [prefix = "prueba", width = "1440", scene = "mundo", wanted = "Chosica", seconds = "45", keys = "w,w,d,v"] = process.argv.slice(2);
const viewport = { 1440: { width: 1440, height: 900 }, 768: { width: 768, height: 1024 }, 390: { width: 390, height: 844 } }[width] || { width: 1440, height: 900 };

(async () => {
  const browser = await chromium.launch({ channel: "chromium", args: ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11", "--autoplay-policy=no-user-gesture-required"] });
  const context = await browser.newContext({ viewport, reducedMotion: process.env.QA_REDUCED_MOTION ? "reduce" : "no-preference" });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text().slice(0, 240)); });
  page.on("pageerror", (err) => errors.push("pageerror: " + String(err).slice(0, 240)));
  page.on("response", (response) => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url().replace(BASE, "").slice(0, 110)}`); });
  let shots = 0;
  const shot = async (name) => { shots += 1; await page.screenshot({ path: path.join(OUT, `${prefix}-${width}-${scene}-${shots}-${name}.png`) }).catch((error) => errors.push(`captura: ${error.message.slice(0, 80)}`)); };
  const fps = () => page.evaluate(() => new Promise((resolve) => { let count = 0; const start = performance.now(); const tick = () => { count += 1; if (performance.now() - start < 2000) requestAnimationFrame(tick); else resolve(Math.round(count / 2)); }; requestAnimationFrame(tick); }));
  const text = (limit = 900) => page.evaluate((max) => document.querySelector("main").innerText.replace(/\s+/g, " ").slice(0, max), limit);
  // Placas visibles que se pisan entre sí o se salen de la pantalla (solo elementos con texto, posicionados absolutos o fijos).
  const overlaps = () => page.evaluate(() => {
    const boxes = [...document.querySelectorAll("main *")].filter((el) => {
      const style = getComputedStyle(el);
      if (!["absolute", "fixed"].includes(style.position) || style.visibility === "hidden" || style.display === "none" || +style.opacity === 0 || style.pointerEvents === "none" && !el.innerText) return false;
      const r = el.getBoundingClientRect();
      return r.width > 30 && r.height > 14 && r.width < innerWidth * 0.98 && (el.innerText || "").trim().length > 2 && !el.closest(".maplibregl-map");
    }).map((el) => ({ el, name: String(el.className).split(" ")[0] || el.tagName.toLowerCase(), r: el.getBoundingClientRect() }));
    const top = boxes.filter((a) => !boxes.some((b) => b !== a && b.el.contains(a.el)));
    const hit = (a, b) => a.r.left < b.r.right - 2 && b.r.left < a.r.right - 2 && a.r.top < b.r.bottom - 2 && b.r.top < a.r.bottom - 2;
    const pairs = [];
    for (let i = 0; i < top.length; i += 1) for (let j = i + 1; j < top.length; j += 1) if (hit(top[i], top[j])) pairs.push(`${top[i].name} × ${top[j].name}`);
    const outside = top.filter((a) => a.r.left < -1 || a.r.top < -1 || a.r.right > innerWidth + 1 || a.r.bottom > innerHeight + 1).map((a) => a.name);
    return { pisadas: [...new Set(pairs)].slice(0, 20), fuera: [...new Set(outside)].slice(0, 12) };
  });
  const unnamed = () => page.evaluate(() => [...document.querySelectorAll("main button, main a")].filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && !(el.getAttribute("aria-label") || el.title || el.innerText.replace(/[^\p{L}\p{N}]/gu, "")); }).length);
  const out = { prefix, width: +width, scene, base: BASE };
  out.webgl = await page.evaluate(() => { const gl = document.createElement("canvas").getContext("webgl2"); const info = gl && gl.getExtension("WEBGL_debug_renderer_info"); return info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : "?"; });

  await page.goto(`${BASE}/${process.env.QA_QUERY || ""}`, { waitUntil: "networkidle", timeout: 120000 });   // QA_QUERY="?luz=noche" fija la luz del mundo
  await page.getByRole("button", { name: /Jugador/ }).click();
  await page.getByRole("radio", { name: /Mujer/ }).click();
  await page.locator(".gameName input").fill("Detective Andina");
  await page.locator(".gameCard .gameGo").click();
  // Prólogo de la historia (ADR-049): se salta para llegar a la Luna.
  await page.locator(".gameStorySkip").click({ timeout: 20000 }).catch(() => undefined);
  await page.waitForTimeout(2500);
  if (scene === "luna") { out.cuadros = await fps(); out.texto = await text(); await shot("luna"); }
  else {
    await page.locator(".gameCard .gameGo").click({ timeout: 90000 });
    await page.locator(".gameContinents").waitFor({ timeout: 30000 });
    await page.waitForTimeout(2500);
    if (scene === "globo") {
      out.cuadros = await fps();
      await shot("globo");
      await page.locator(".gameContinentList button").first().click();
      await page.waitForTimeout(2500);
      out.cuadrosContinente = await fps();
      out.texto = await text(1400);
      out.solapes = await overlaps();
      out.sinNombre = await unnamed();
      await shot("continente");
    } else {
      const continents = await page.locator(".gameContinentList button").count();
      for (let index = 0; index < continents; index += 1) {
        await page.locator(".gameContinentList button").nth(index).click();
        await page.waitForTimeout(400);
        if (await page.locator(".gameMissionList button", { hasText: new RegExp(wanted, "i") }).count()) break;
      }
      await page.locator(".gameMissionList button", { hasText: new RegExp(wanted, "i") }).first().click();
      await page.waitForTimeout(3500);
      out.panel = await page.evaluate(() => { const at = document.querySelector("main").innerText; const from = at.indexOf("Contexto"); return at.slice(Math.max(0, from)).replace(/\s+/g, " ").slice(0, 1500); });
      await shot("panel");
      if (scene === "mundo") {
        const timeline = [];
        const mark = async (name) => { timeline.push({ momento: name, cuadros: await fps(), solapes: await overlaps() }); await shot(name); };
        await page.waitForTimeout(12000);
        await mark("aterrizado");
        await page.mouse.click(viewport.width * 0.3, viewport.height * 0.45).catch(() => undefined);
        for (const key of keys.split(",").filter(Boolean)) {
          await page.keyboard.down(key);
          await page.waitForTimeout(1500);
          await page.keyboard.up(key);
        }
        await mark("teclas");
        await page.waitForTimeout(Math.max(0, +seconds * 1000 - 20000));
        await mark("final");
        out.linea = timeline;
        out.texto = await text(1600);
        out.sinNombre = await unnamed();
      }
    }
  }
  out.errores = [...new Set(errors)].slice(0, 15);
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})().catch((error) => { console.log(JSON.stringify({ error: String(error).slice(0, 700) })); process.exit(1); });
