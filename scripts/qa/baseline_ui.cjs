// QA de la línea base (módulos 3, 4 y 5) en 3100: Ambiente y Amenazas con Moquegua (radio 1 km) y Patrimonio con Moquegua + distrito de Ilo.
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
  const page = await browser.newPage({ viewport, acceptDownloads: true });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(`${BASE}/plataforma`, { waitUntil: "networkidle" });
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

  // Módulo 3 · Amenazas: el mismo sitio; extremos con contraste IMERG y capas de riesgo.
  await openModule(page, viewport, "Amenazas");
  out.hazardsSeconds = await runAndRead(page, "Lectura de amenazas");
  out.hazardsReading = (await page.locator(".verdict").first().innerText()).slice(0, 400);
  out.hazardsTabs = await page.locator('[aria-label="Variable NASA POWER"] button').allInnerTexts();
  out.hazardsExtremeRows = await page.locator(".siteResult .agreement").count();
  out.hazardsCheckColumns = await page.locator(".siteResult thead th", { hasText: "Contraste" }).allInnerTexts();
  out.hazardsAtypical = await page.locator(".siteResult small.atypical").allInnerTexts();
  out.hazardsDiscoveries = await page.locator(".discoveriesPanel .discovery h4").allInnerTexts();
  out.hazardsLayers = await page.locator(".baselineLayers tbody tr").count();
  out.hazardsNasaLayers = (await page.locator(".baselineLayers tbody tr", { hasText: "NASA" }).allInnerTexts()).map((row) => row.replace(/\s+/g, " ").slice(0, 220));
  out.hazardsChartPoints = await page.locator(".recharts-line path, .recharts-line-dot").count();
  out.hazardsOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await page.screenshot({ path: path.join(OUT, `amenazas-${tag}.png`), fullPage: true });

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
  // PDF ejecutivo desde el botón de la pantalla: debe llegar con la sección de línea base.
  const pdfButton = page.locator(".exportAction.primaryExport");
  await pdfButton.scrollIntoViewIfNeeded();
  const [download] = await Promise.all([page.waitForEvent("download", { timeout: 120000 }), pdfButton.click()]);
  const pdfPath = path.join(OUT, `patrimonio-${tag}.pdf`);
  await download.saveAs(pdfPath);
  const bytes = fs.readFileSync(pdfPath);
  out.heritagePdf = { header: bytes.subarray(0, 4).toString(), kb: Math.round(bytes.length / 1024) };
  out.errors = errors;
  await browser.close();
  return out;
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
