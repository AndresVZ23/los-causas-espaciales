// QA del Módulo 1 · Clima en 3100: corre el análisis real, recorre pestañas, exporta PDF y captura 1440/390 px.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "clima");
fs.mkdirSync(OUT, { recursive: true });

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport, acceptDownloads: true });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(`${BASE}/plataforma`, { waitUntil: "networkidle" });
  const isMobile = isCompact(viewport);
  if (isMobile) await page.locator(".mobileBottomNav button", { hasText: "Clima" }).click();
  else await page.locator(".moduleNav button", { hasText: "Clima" }).click();
  await page.waitForFunction(() => !document.querySelector("button.runAnalysis")?.disabled);
  const runButton = page.locator("button.runAnalysis");
  await runButton.scrollIntoViewIfNeeded();
  const started = Date.now();
  await runButton.click();
  await page.waitForSelector(".climateTable", { timeout: 240000 });
  const seconds = (Date.now() - started) / 1000;
  const reading = await page.locator(".climateTable").first().innerText();
  const extremes = await page.locator(".climateExtremes b").first().innerText();
  const tabs = await page.locator('[aria-label="Variable NASA POWER"] button').allInnerTexts();
  const tabChecks = [];
  for (const label of ["Lluvia máx. 1 día", "Racha seca"]) {
    await page.locator('[aria-label="Variable NASA POWER"] button', { hasText: label }).click();
    await page.waitForTimeout(400);
    tabChecks.push({ label, foot: await page.locator(".chartFoot span").nth(1).innerText(), points: await page.locator(".recharts-line-dot, .recharts-line path").count() });
  }
  const evidenceTables = await page.locator(".siteResult table").count();
  const method = await page.locator(".methodPanel p").count();
  const questions = await page.locator(".question").count();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await page.screenshot({ path: path.join(OUT, `clima-${tag}.png`), fullPage: true });
  let pdf = null;
  if (!isMobile) {
    const pdfButton = page.getByRole("button", { name: /PDF/ }).first();
    if (await pdfButton.count()) {
      const [download] = await Promise.all([page.waitForEvent("download", { timeout: 120000 }), pdfButton.click()]);
      const target = path.join(OUT, download.suggestedFilename());
      await download.saveAs(target);
      pdf = { file: download.suggestedFilename(), bytes: fs.statSync(target).size };
    }
  }
  await browser.close();
  return { tag, seconds, tabs, reading, extremes, tabChecks, evidenceTables, method, questions, overflow, pdf, errors };
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
