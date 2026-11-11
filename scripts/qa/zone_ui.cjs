// QA de «Entrar a la zona» en 3100 (1440/768/390): del globo a la maqueta de Moquegua, caminar, fichas de las balizas,
// vista de pendientes, salida al mapa y enlace directo a la zona del volcán Taal. Revisa recortes, desborde y consola.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "zona");
fs.mkdirSync(OUT, { recursive: true });

const clipped = (page) => page.evaluate(() => [...document.querySelectorAll(".zoneScreen button, .zoneScreen h2, .zoneScreen h3, .zoneScreen p, .zoneScreen b, .zoneScreen small, .zoneScreen dd, .zoneScreen dt, .zoneScreen li")]
  .filter((el) => { const s = getComputedStyle(el); return s.display !== "inline" && s.display !== "none" && el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1; })
  .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]} "${(el.innerText || "").trim().slice(0, 40)}" ${el.scrollWidth}>${el.clientWidth}`).slice(0, 10));
// Elementos de la consola que se salen de la pantalla o se montan unos sobre otros.
const layout = (page) => page.evaluate(() => {
  const box = (selector) => { const el = document.querySelector(selector); if (!el) return null; const r = el.getBoundingClientRect(); return { l: Math.round(r.left), t: Math.round(r.top), r: Math.round(r.right), b: Math.round(r.bottom) }; };
  const names = [".zoneBar", ".zonePanel", ".zoneReadout", ".zoneCard", ".zoneIntro", ".zonePad", ".zoneHint"];
  const boxes = Object.fromEntries(names.map((name) => [name, box(name)]).filter(([, value]) => value));
  const outside = Object.entries(boxes).filter(([, r]) => r.l < 0 || r.t < 0 || r.r > innerWidth || r.b > innerHeight).map(([name]) => name);
  const hit = (a, b) => a && b && a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b;
  const pairs = [[".zoneBar", ".zonePanel"], [".zoneBar", ".zoneCard"], [".zoneCard", ".zoneReadout"], [".zonePanel", ".zoneCard"], [".zoneBar", ".zoneIntro"]];
  return { outside, overlaps: pairs.filter(([a, b]) => hit(boxes[a], boxes[b])).map((pair) => pair.join(" × ")) };
});
const readout = (page) => page.locator(".zoneReadout").innerText().then((text) => text.replace(/\s+/g, " ").trim());
// Con el mouse capturado los clics van a la escena: se suelta antes de usar los paneles, como hace la tecla Esc.
const unlock = (page) => page.evaluate(() => document.exitPointerLock());
const ready = (page) => page.waitForSelector("canvas.zoneCanvas[data-ready='true']", { timeout: 90000 });

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  page.on("response", (response) => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url().replace(BASE, "")}`); });
  const shot = async (name) => { try { await page.screenshot({ path: path.join(OUT, `${tag}-${name}.png`) }); } catch (error) { errors.push(`captura ${name}: ${error.message}`); } };
  const narrow = viewport.width < 760;
  const out = { tag };

  // 1 · Del globo a la zona: lista de zonas, marcadores y entrada.
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelectorAll('input[name="tecnologia"]').length === 3, null, { timeout: 60000 });
  await page.locator(".alertsToggle").click();
  await page.locator(".zoneRow").first().waitFor({ timeout: 60000 });
  out.zones = await page.locator(".zoneRowName b").allInnerTexts();
  await page.waitForTimeout(1500);
  out.zoneMarkers = await page.locator(".zoneBlock").count();
  await page.locator(".zoneRow", { hasText: "Moquegua" }).locator(".zoneRowName").click();
  await page.waitForTimeout(4500);
  await shot("1-globo-zona");
  await page.locator(".zoneRow", { hasText: "Moquegua" }).locator(".zoneEnter").click();
  await ready(page);
  await page.waitForTimeout(1200);
  out.title = await page.locator(".zoneTitle h2").innerText();
  out.intro = await page.locator(".zoneIntro").innerText().then((text) => text.replace(/\s+/g, " ").slice(0, 220));
  out.introLayout = await layout(page);
  await shot("2-entrada");

  // 2 · Empezar, bajar a caminar y avanzar.
  await page.locator(".zoneStart").click();
  await page.waitForTimeout(600);
  out.pointerLocked = await page.evaluate(() => Boolean(document.pointerLockElement));
  out.hint = await page.locator(".zoneHint").innerText().catch(() => null);
  out.flyingReadout = await readout(page);
  await shot("3-vuelo");
  await page.keyboard.press("p");
  await page.waitForTimeout(500);
  out.slopeKey = await page.locator(".zoneTools button").first().getAttribute("aria-pressed");
  await shot("3b-pendientes-aire");
  await page.keyboard.press("p");
  await page.keyboard.press("f");
  await page.waitForFunction(() => document.querySelector('canvas.zoneCanvas')?.dataset.height === '0.0', null, { timeout: 30000 });
  out.mode = await page.locator(".zoneTools button").nth(1).innerText();
  out.groundBefore = await readout(page);
  await page.keyboard.down("w");
  await page.waitForTimeout(2500);
  await page.keyboard.up("w");
  out.groundAfter = await readout(page);
  await shot("4-caminando");
  await unlock(page);

  // 3 · Balizas: cada una abre su ficha con cifra, segunda fuente y qué mirar primero.
  out.cards = [];
  const count = await page.locator(".zoneBeacons button").count().catch(() => 0) || (narrow ? await (async () => { await page.locator(".zoneTools button").nth(2).click(); return page.locator(".zoneBeacons button").count(); })() : 0);
  for (let index = 0; index < count; index += 1) {
    if (!(await page.locator(".zonePanel").count())) await page.locator(".zoneTools button").nth(2).click();
    await page.locator(".zoneBeacons button").nth(index).click();
    await page.locator(".zoneCard").waitFor({ timeout: 10000 });
    await page.waitForFunction(() => document.querySelector('canvas.zoneCanvas')?.dataset.height === '0.0', null, { timeout: 30000 });
    await page.waitForTimeout(300);
    const card = page.locator(".zoneCard");
    out.cards.push({ title: await card.locator("h3").innerText(), figures: await card.locator("dd").allInnerTexts(), lines: await card.locator(".zoneCardLine").count(), near: await readout(page) });
    if (index < 2) { out[`cardLayout${index}`] = await layout(page); await shot(`5-baliza-${index + 1}`); }
  }
  out.cardClipped = await clipped(page);

  // 4 · Vista de pendientes.
  await page.locator(".zoneCard header button").click().catch(() => undefined);
  await page.locator(".zoneTools button").first().click();
  if (!(await page.locator(".zonePanel").count())) await page.locator(".zoneTools button").nth(2).click();
  out.slopeLegend = await page.locator(".zoneLegend li").allInnerTexts();
  await page.keyboard.press("f");
  await page.keyboard.down("Space");
  await page.waitForTimeout(1400);
  await page.keyboard.up("Space");
  if (narrow) await page.locator(".zoneTools button").nth(2).click();
  await page.waitForTimeout(400);
  await shot("6-pendientes");
  out.panelClipped = await clipped(page);
  out.overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

  // 5 · Salir: se vuelve al globo con el panel de alertas como estaba.
  await page.locator(".zoneExit").click();
  await page.waitForTimeout(500);
  out.afterExit = { zoneScreen: await page.locator(".zoneScreen").count(), alertsPanel: await page.locator(".alertsPanel").count(), zoneMarkers: await page.locator(".zoneBlock").count() };

  // 6 · Enlace directo a la segunda zona.
  await page.goto(`${BASE}/zona/taal`, { waitUntil: "domcontentloaded" });
  await ready(page);
  await page.waitForTimeout(1500);
  out.taal = { title: await page.locator(".zoneTitle h2").innerText() };
  await shot("7-taal-entrada");
  await page.locator(".zoneStart").click();
  await unlock(page);
  if (!(await page.locator(".zonePanel").count())) await page.locator(".zoneTools button").nth(2).click();
  out.taal.beacons = await page.locator(".zoneBeacons b").allInnerTexts();
  await page.locator(".zoneBeacons button").first().click();
  await page.locator(".zoneCard").waitFor({ timeout: 10000 });
  await page.waitForFunction(() => document.querySelector('canvas.zoneCanvas')?.dataset.height === '0.0', null, { timeout: 30000 });
  await page.waitForTimeout(400);
  out.taal.asked = await page.locator(".zoneBeacons b").first().innerText().catch(() => null);
  out.taal.card = await page.locator(".zoneCard h3").innerText();
  out.taal.near = await readout(page);
  out.taal.layout = await layout(page);
  await shot("8-taal-baliza");
  await page.locator(".zoneExit").click();
  await page.waitForURL(`${BASE}/`, { timeout: 30000 });
  out.taal.exitUrl = page.url();
  out.errors = errors;
  await browser.close();
  return out;
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
