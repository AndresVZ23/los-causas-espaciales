// QA del selector territorial (C7) en 3100: búsqueda, niveles, análisis real por territorio y grilla de tendencias por celda.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "territorio");
fs.mkdirSync(OUT, { recursive: true });

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(`${BASE}/plataforma`, { waitUntil: "networkidle" });
  if (isCompact(viewport)) await page.locator(".mobileBottomNav button", { hasText: "Clima" }).click();
  else await page.locator(".moduleNav button", { hasText: "Clima" }).click();
  await page.locator(".territorySection").waitFor();

  // Quitar el segundo sitio (Arequipa) y agregar el departamento de Moquegua por búsqueda.
  await page.getByRole("button", { name: /Quitar Arequipa/ }).click();
  await page.getByLabel("Buscar departamento, provincia o distrito").fill("Moquegua");
  const result = page.locator(".territoryResults button", { hasText: "Departamento" }).first();
  await result.waitFor({ timeout: 15000 });
  const searchHits = await page.locator(".territoryResults button").allInnerTexts();
  await result.click();
  await page.locator(".territoryChosen li").first().waitFor();

  // Distrito de Mollendo por niveles: Arequipa → Islay → Mollendo.
  await page.getByRole("button", { name: "Por niveles" }).click();
  const department = page.getByLabel("Departamento");
  await page.waitForFunction(() => document.querySelectorAll(".territoryLevels select")[0]?.options.length > 20);
  await department.selectOption({ label: "Arequipa" });
  await page.waitForFunction(() => document.querySelectorAll(".territoryLevels select")[1]?.options.length > 2);
  await page.getByLabel("Provincia").selectOption({ label: "Islay" });
  await page.waitForFunction(() => document.querySelectorAll(".territoryLevels select")[2]?.options.length > 2);
  await page.getByLabel("Distrito").selectOption({ label: "Mollendo" });
  await page.locator(".territoryAdd").click();
  await page.waitForFunction(() => document.querySelectorAll(".territoryChosen li").length === 2);
  const chosen = await page.locator(".territoryChosen li").allInnerTexts();

  const runButton = page.locator("button.runAnalysis");
  await runButton.scrollIntoViewIfNeeded();
  const started = Date.now();
  await runButton.click();
  await page.locator(".climateTable").first().waitFor({ timeout: 300000 });
  const seconds = (Date.now() - started) / 1000;
  await page.locator(".cellLegend").waitFor({ timeout: 10000 });
  const legendT = await page.locator(".cellLegend").innerText();
  await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `celdas-t2m-${tag}.png`) });
  await page.locator(".cellLegend button", { hasText: "Precipitación" }).click();
  await page.waitForTimeout(500);
  const legendP = await page.locator(".cellLegend").innerText();
  await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `celdas-pp-${tag}.png`) });
  const reading = await page.locator(".climateTable").first().innerText();
  const scales = await page.locator(".territoryScale").allInnerTexts();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await browser.close();
  return { tag, seconds, searchHits: searchHits.slice(0, 3), chosen, legendT, legendP, reading, scales, overflow, errors };
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
