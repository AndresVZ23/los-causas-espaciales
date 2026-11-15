// QA del piloto inmobiliario (C5 sobre K3) en 3100: áreas de ejemplo, territorio IGN como terreno, lectura, tablas y asistente.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "inmobiliario");
fs.mkdirSync(OUT, { recursive: true });

async function runAnalysis(page) {
  const button = page.locator("button.runAnalysis");
  await button.scrollIntoViewIfNeeded();
  const started = Date.now();
  await button.click();
  await page.locator(".verdict", { hasText: "Lectura de terrenos" }).first().waitFor({ timeout: 400000 });
  await page.waitForFunction(() => !document.querySelector("button.runAnalysis")?.textContent?.includes("Consultando"));
  return (Date.now() - started) / 1000;
}

async function run(viewport, tag, withTerritory) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(`${BASE}/plataforma`, { waitUntil: "networkidle" });
  if (isCompact(viewport)) {
    await page.locator(".mobileBottomNav button", { hasText: "Inversión" }).click();
  } else {
    await page.locator(".moduleNav button", { hasText: "Inversión" }).click();
  }
  await page.locator(".roadControls", { hasText: "Terrenos a comparar" }).waitFor();
  const out = { tag };
  out.secondsExample = await runAnalysis(page);
  out.reading = await page.locator(".verdict").first().innerText();
  await page.waitForTimeout(1000);
  await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `mapa-ejemplo-${tag}.png`) });
  out.panels = { scorecard: await page.locator(".scorecardPanel").count(), sensitivity: await page.locator(".sensitivityPanel").count(), questions: await page.locator(".question").count() };
  out.parcelsTable = (await page.locator(".siteResult").first().innerText()).slice(0, 450);
  // Relieve del punto representativo de cada terreno: NASADEM frente a Copernicus GLO-30.
  out.discoveries = await page.locator(".discoveriesPanel .discovery").evaluateAll((items) => items.map((item) => `${item.querySelector(".discoveryKind")?.textContent} · ${item.querySelector("h4")?.textContent}`));
  await page.locator(".assistantPanel").scrollIntoViewIfNeeded();
  const before = await page.locator(".assistantLog article").count();
  await page.locator(".assistantSuggestions button").nth(1).click();
  await page.waitForFunction((n) => document.querySelectorAll(".assistantLog article").length > n, before, { timeout: 60000 });
  out.assistant = await page.locator(".assistantLog article .assistantAnswer").first().innerText();
  if (withTerritory) {
    await page.locator(".roadControls").scrollIntoViewIfNeeded();
    await page.locator(".layerOption", { hasText: "Territorios IGN" }).click();
    await page.getByLabel("Buscar departamento, provincia o distrito").fill("Samegua");
    await page.locator(".territoryResults button", { hasText: "Distrito" }).first().click();
    await page.locator(".territoryChosen li").first().waitFor();
    out.secondsTerritory = await runAnalysis(page);
    out.territoryReading = await page.locator(".verdict").first().innerText();
    await page.locator(".verdict").first().screenshot({ path: path.join(OUT, `lectura-territorio-${tag}.png`) });
    await page.waitForTimeout(1000);
    await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `mapa-territorio-${tag}.png`) });
  }
  out.overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  out.errors = errors;
  await browser.close();
  return out;
}

// Tras reconstruir el stack, la API tarda unos segundos en aceptar consultas: se espera su salud antes de empezar.
async function waitForApi() {
  for (let attempt = 0; attempt < 60; attempt++) {
    try { if ((await fetch("http://localhost:8000/api/v1/health")).ok) return; } catch { /* aún arrancando */ }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error("La API no respondió en 2 minutos.");
}

(async () => {
  await waitForApi();
  const results = await runAll(run, true);
  console.log(JSON.stringify(results, null, 1));
})();
