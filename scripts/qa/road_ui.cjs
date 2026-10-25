// QA del piloto vial (C5 sobre K2) en 3100: corredor piloto real, lectura, mapa, puntaje, escenarios, tablas y asistente.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "vial");
fs.mkdirSync(OUT, { recursive: true });

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(BASE, { waitUntil: "networkidle" });
  if (isCompact(viewport)) {
    await page.getByRole("button", { name: /Más/ }).click();
    await page.locator(".moduleNav button", { hasText: "Infraestructura" }).click();
  } else {
    await page.locator(".moduleNav button", { hasText: "Infraestructura" }).click();
  }
  await page.locator(".roadControls").waitFor();
  const run = page.locator("button.runAnalysis");
  await run.scrollIntoViewIfNeeded();
  const started = Date.now();
  await run.click();
  await page.locator(".verdict").first().waitFor({ timeout: 400000 });
  const seconds = (Date.now() - started) / 1000;
  const reading = await page.locator(".verdict").first().innerText();
  await page.waitForTimeout(1200);
  await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `mapa-${tag}.png`) });
  const panels = {
    scorecard: await page.locator(".scorecardPanel").count(),
    sensitivity: await page.locator(".sensitivityPanel").count(),
    segmentsTable: await page.locator(".siteResult").first().innerText().then((text) => text.slice(0, 400)),
    territorial: await page.locator(".siteResult").nth(1).innerText().then((text) => text.slice(0, 500)),
    questions: await page.locator(".question").count(),
  };
  await page.locator(".assistantPanel").scrollIntoViewIfNeeded();
  const ask = async (index) => {
    const before = await page.locator(".assistantLog article").count();
    await page.locator(".assistantSuggestions button").nth(index).click();
    await page.waitForFunction((n) => document.querySelectorAll(".assistantLog article").length > n, before, { timeout: 60000 });
    return page.locator(".assistantLog article .assistantAnswer").first().innerText();
  };
  const assistant = [await ask(0), await ask(1)];
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await page.screenshot({ path: path.join(OUT, `pagina-${tag}.png`), fullPage: true });
  await browser.close();
  return { tag, seconds, reading, panels, assistant, overflow, errors };
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
