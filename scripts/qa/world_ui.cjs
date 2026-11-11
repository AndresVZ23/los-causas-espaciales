// QA del alcance global en 3100 (1440/768/390): alertas del mundo con sus pulsos, vuelo a un evento, análisis de amenazas
// en ese punto, filtro del Perú y búsqueda de un lugar del mundo. Revisa recortes, desborde y errores de consola.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "mundo");
fs.mkdirSync(OUT, { recursive: true });

const clipped = (page) => page.evaluate(() => {
  const scrolls = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const s = getComputedStyle(p); if (["auto", "scroll"].includes(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; } return false; };
  return [...document.querySelectorAll("button, a, label, th, td, h1, h2, h3, h4, p, b, small, span, em, strong")]
    .filter((el) => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (s.display === "inline" || s.display === "none" || s.visibility === "hidden" || r.width === 0 || el.clientWidth === 0) return false;
      if (s.textOverflow === "ellipsis" || scrolls(el) || el.closest("[aria-hidden='true'], .srOnly, .maplibregl-map")) return false;
      return el.scrollWidth > el.clientWidth + 1;
    })
    .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(" ").filter(Boolean)[0] || ""} "${(el.innerText || "").trim().slice(0, 40)}" ${el.scrollWidth}>${el.clientWidth}`)
    .slice(0, 10);
});
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelectorAll('input[name="tecnologia"]').length === 3, null, { timeout: 60000 });
  const out = { tag };

  // 1 · Alertas del mundo: panel, lista y pulsos.
  await page.locator(".alertsToggle").click();
  await page.locator(".alertsList li").first().waitFor({ timeout: 90000 });
  await page.waitForTimeout(1600);
  out.alerts = await page.locator(".alertsList li").count();
  out.pulses = await page.locator(".alertPulse").count();
  out.animated = await page.locator(".alertPulse").evaluateAll((items) => items.filter((item) => getComputedStyle(item, "::after").animationName !== "none").length);
  out.levels = await page.locator(".alertsList li").evaluateAll((items) => items.reduce((acc, item) => { const level = [...item.classList].find((name) => name.startsWith("level-")); acc[level] = (acc[level] || 0) + 1; return acc; }, {}));
  out.sources = await page.locator(".alertsFoot > p").allInnerTexts();
  out.panelClipped = await clipped(page);
  out.panelOverflow = await overflow(page);
  await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `mundo-${tag}.png`) });

  // Los pulsos deben caer donde está el evento: uno del Perú queda al oeste (izquierda) de uno de la India, y ambos dentro del mapa.
  out.placement = await page.evaluate(() => {
    const map = document.querySelector(".mapViewport").getBoundingClientRect();
    const at = (word) => { const el = [...document.querySelectorAll(".alertPulse")].find((item) => item.getAttribute("aria-label").includes(word)); return el ? el.getBoundingClientRect() : null; };
    const peru = at("Peru"), india = at("India");
    return peru && india ? { peruWestOfIndia: peru.x < india.x, peruSouthOfIndia: peru.y > india.y, peruInside: peru.x > map.left && peru.right < map.right } : null;
  });
  // Al cerrar el panel los pulsos siguen: captura del mundo completo.
  await page.locator(".alertsPanel .layerPanelHead button", { hasText: "Cerrar" }).click();
  await page.waitForTimeout(600);
  out.pulsesAfterClose = await page.locator(".alertPulse").count();
  await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `pulsos-${tag}.png`) });
  await page.locator(".alertsToggle").click();
  await page.locator(".alertsList li").first().waitFor();

  // 2 · Filtro del Perú.
  await page.locator(".alertsFilter button", { hasText: "Perú" }).click();
  out.peru = await page.locator(".alertsList li .alertRow").allInnerTexts().then((rows) => rows.map((row) => row.replace(/\s+/g, " ")));
  await page.locator(".alertsFilter button", { hasText: "Mundo" }).click();

  // 3 · Elegir la primera alerta con nivel (GDACS): se abre el detalle y el mapa vuela al evento.
  const first = page.locator(".alertsList li.level-red .alertRow, .alertsList li.level-orange .alertRow").first();
  out.picked = (await first.innerText()).replace(/\s+/g, " ");
  await first.click();
  await page.locator(".alertDetail").waitFor();
  out.detail = (await page.locator(".alertDetail").innerText()).replace(/\s+/g, " ");
  await page.waitForTimeout(1800);
  await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `evento-${tag}.png`) });

  // 4 · Analizar amenazas en ese punto: un solo sitio, fuera del Perú.
  await page.locator(".alertActions button", { hasText: "Analizar amenazas aquí" }).click();
  await page.locator("button.runAnalysis").waitFor();
  out.siteAfterPick = await page.locator(".siteRow input").first().inputValue();
  const button = page.locator("button.runAnalysis");
  await button.scrollIntoViewIfNeeded();
  const started = Date.now();
  await button.click();
  await page.waitForFunction(() => document.querySelector("button.runAnalysis")?.getAttribute("aria-busy") !== "true"
    && (document.querySelector(".verdict") || document.querySelector(".errorMessage")), null, { timeout: 400000 });
  out.seconds = Math.round((Date.now() - started) / 1000);
  out.failure = await page.locator(".controlContent > .errorMessage").first().innerText().catch(() => "");
  if (!out.failure) {
    await page.waitForTimeout(800);
    out.reading = (await page.locator(".verdict").first().innerText()).replace(/\s+/g, " ").slice(0, 260);
    out.layers = await page.locator(".baselineLayers tbody tr th").allInnerTexts().then((rows) => rows.map((row) => row.replace(/\s+/g, " ").slice(0, 70)));
    out.abroadGap = (await page.locator(".gapPanel article", { hasText: "fuera del Perú" }).allInnerTexts()).map((text) => text.replace(/\s+/g, " ").slice(0, 200));
    out.resultClipped = await clipped(page);
    out.resultOverflow = await overflow(page);
  }

  // 5 · Buscar un lugar del mundo en Clima.
  if (isCompact(viewport)) await page.getByRole("button", { name: /Más/ }).click();
  await page.locator(".moduleNav button", { hasText: "Clima" }).first().click();
  await page.locator("#buscar-lugar").fill("Nairobi");
  await page.locator(".placeSearch .territoryResults button").first().waitFor({ timeout: 60000 });
  out.places = await page.locator(".placeSearch .territoryResults button").allInnerTexts().then((rows) => rows.map((row) => row.replace(/\s+/g, " ")));
  await page.locator(".placeSearch .territoryResults button").first().click();
  out.siteAfterSearch = await page.locator(".siteRow").first().locator("input").evaluateAll((inputs) => inputs.map((input) => input.value));
  out.searchClipped = await clipped(page);
  out.errors = errors;
  await browser.close();
  return out;
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
