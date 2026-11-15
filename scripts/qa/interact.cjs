const { chromium } = require("playwright");
// URL de la consola: QA_BASE_URL o el puerto oficial 3100.
const BASE_URL = process.env.QA_BASE_URL || "http://localhost:3100";
const path = require("path");
const out = process.argv[2];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${BASE_URL}/plataforma`, { waitUntil: "networkidle" });
  const checks = {};
  checks.h1 = await page.locator("h1").count();
  await page.locator("button.runAnalysis").click();
  await page.waitForSelector(".verdict");
  await page.waitForFunction(() => !document.querySelector(".pipelineStrip.isRunning"));
  checks.yTicksSolar = await page.locator(".trendChart .recharts-yAxis .recharts-cartesian-axis-tick text").allTextContents();
  for (const name of ["Temperatura", "Precipitación"]) {
    await page.locator(".trendHeader button", { hasText: name }).click();
    await page.waitForFunction((n) => document.querySelector(".trendHeader button.active")?.textContent === n, name);
    checks[`yTicks${name}`] = await page.locator(".trendChart .recharts-yAxis .recharts-cartesian-axis-tick text").allTextContents();
    checks[`unit${name}`] = await page.locator(".seriesKey b").textContent();
    await page.screenshot({ path: path.join(out, `serie-${name}.png`), clip: { x: 190, y: 510, width: 1250, height: 270 } });
  }
  checks.panelOpenBefore = await page.locator(".assumptionPanel").evaluate((el) => el.open);
  await page.locator(".verdictAssumptions button").click();
  await page.waitForFunction(() => document.querySelector(".assumptionPanel")?.open === true);
  checks.focusedAfterEdit = await page.evaluate(() => document.activeElement?.closest("label")?.textContent?.trim());
  await page.locator(".assumptionFields input").first().fill("25");
  await page.waitForSelector(".verdictAssumptions.isStale");
  checks.staleText = await page.locator(".verdictAssumptions span").first().textContent();
  await page.screenshot({ path: path.join(out, "supuestos-editados.png"), clip: { x: 845, y: 90, width: 595, height: 420 } });
  checks.findings = await page.locator(".findingsPanel p").allTextContents();
  checks.consoleErrors = errors;
  console.log(JSON.stringify(checks, null, 2));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
