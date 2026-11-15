// QA de escenarios y sensibilidad del VAN en 3100 (piloto solar): tabla, tornado, tooltip, cambio de sujeto y supuestos.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "sensibilidad");
fs.mkdirSync(OUT, { recursive: true });

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(`${BASE}/plataforma`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => !document.querySelector("button.runAnalysis")?.disabled);
  await page.locator("button.runAnalysis").click();
  await page.waitForSelector(".sensitivityPanel", { timeout: 240000 });
  const panel = page.locator(".sensitivityPanel");
  await panel.scrollIntoViewIfNeeded();
  const scenarios = await panel.locator(".scenarioTable").innerText();
  const factors = await panel.locator(".tornadoLabel b").allInnerTexts();
  const evens = await panel.locator(".breakEvens small").allInnerTexts();
  await panel.locator(".tornadoRow").first().hover();
  const tip = await panel.locator(".tornadoRow").first().locator(".tornadoTip").isVisible();
  const before = await panel.locator(".breakEvens h4").innerText();
  await panel.locator(".tornadoHead button").nth(1).click();
  const after = await panel.locator(".breakEvens h4").innerText();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await panel.screenshot({ path: path.join(OUT, `panel-${tag}.png`) });
  // Cambiar un rango deja los escenarios marcados como desactualizados.
  if (!(await page.locator(".assumptionPanel").getAttribute("open"))) await page.locator(".assumptionPanel summary").click();
  await page.getByLabel("Precio ± (fracción)").fill("0.3");
  const stale = await page.locator(".sensitivityStale").isVisible();
  await browser.close();
  return { tag, scenarios, factors, evens, tip, subjectSwitch: [before, after], overflow, stale, errors };
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
