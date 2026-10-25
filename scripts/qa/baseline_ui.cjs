// QA de la línea base (módulos 4 y 5) en 3100: Ambiente con Moquegua (radio 1 km) y Patrimonio con Moquegua + distrito de Ilo.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "linea-base");
fs.mkdirSync(OUT, { recursive: true });

async function openModule(page, viewport, name) {
  if (isCompact(viewport)) await page.getByRole("button", { name: /Más/ }).click();
  await page.locator(".moduleNav button", { hasText: name }).first().click();
}

async function runAndRead(page, heading) {
  const button = page.locator("button.runAnalysis");
  await button.scrollIntoViewIfNeeded();
  const started = Date.now();
  await button.click();
  await page.locator(".verdict", { hasText: heading }).first().waitFor({ timeout: 400000 });
  await page.waitForFunction(() => !document.querySelector("button.runAnalysis")?.getAttribute("aria-busy")?.includes("true"));
  return (Date.now() - started) / 1000;
}

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(BASE, { waitUntil: "networkidle" });
  const out = { tag };

  // Módulo 4 · Ambiente: un sitio con radio de 1 km.
  await openModule(page, viewport, "Ambiente");
  await page.getByRole("button", { name: /Quitar Arequipa/ }).click();
  out.environmentSeconds = await runAndRead(page, "Lectura de la línea base");
  out.environmentReading = (await page.locator(".verdict").first().innerText()).slice(0, 500);
  out.environmentStatus = await page.locator(".systemLine b").first().innerText().catch(() => "(oculta)");
  out.tabs = await page.locator('[aria-label="Variable NASA POWER"] button').allInnerTexts();
  out.chartPoints = await page.locator(".recharts-line path, .recharts-line-dot").count();
  out.environmentTables = await page.locator(".baselineLayers").count();
  out.environmentHighlights = await page.locator(".layerHighlights li").count();
  out.environmentOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await page.screenshot({ path: path.join(OUT, `ambiente-${tag}.png`), fullPage: true });

  // Módulo 5 · Patrimonio: el mismo sitio más el distrito de Ilo.
  await openModule(page, viewport, "Territorio");
  await page.getByLabel("Buscar departamento, provincia o distrito").fill("Ilo");
  await page.locator(".territoryResults button", { hasText: "Distrito" }).first().click();
  await page.locator(".territoryChosen li").first().waitFor();
  out.heritageSeconds = await runAndRead(page, "Lectura patrimonial");
  out.heritageReading = (await page.locator(".verdict").first().innerText()).slice(0, 500);
  out.heritageTables = await page.locator(".baselineLayers").count();
  out.heritageRows = await page.locator(".baselineLayers tbody tr").count();
  out.heritageUnavailable = await page.locator(".baselineLayers td.figure", { hasText: "No disponible" }).count();
  out.heritageLinks = await page.locator(".layerHighlights a").count();
  out.terrainHidden = (await page.locator(".terrainReadout").count()) === 0;
  out.questions = await page.locator(".question").count();
  out.heritageOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await page.screenshot({ path: path.join(OUT, `patrimonio-${tag}.png`), fullPage: true });
  await page.locator(".siteResults").first().screenshot({ path: path.join(OUT, `patrimonio-tablas-${tag}.png`) });
  out.errors = errors;
  await browser.close();
  return out;
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
