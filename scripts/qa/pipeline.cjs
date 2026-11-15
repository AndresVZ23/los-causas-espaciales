const { chromium } = require("playwright");
// URL de la consola: QA_BASE_URL o el puerto oficial 3100.
const BASE_URL = process.env.QA_BASE_URL || "http://localhost:3100";
const path = require("path");
const out = process.argv[2];

(async () => {
  const browser = await chromium.launch();
  const checks = {};
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${BASE_URL}/plataforma`, { waitUntil: "networkidle" });
  // Antes de ejecutar: el inspector explica la etapa 4.
  await page.locator(".pipelineStrip li button").nth(3).click();
  checks.guideBefore = await page.locator(".inspectorSummary").textContent();
  await page.screenshot({ path: path.join(out, "1440-antes.png") });
  await page.locator("button.runAnalysis").click();
  await page.waitForSelector(".verdict");
  await page.waitForFunction(() => !document.querySelector(".pipelineStrip.isRunning"));
  await page.waitForTimeout(800);
  checks.selectedAfterRun = await page.locator(".inspectorHead h3").textContent();
  checks.statuses = await page.locator(".pipelineStrip li small").allTextContents();
  await page.screenshot({ path: path.join(out, "1440-resultado.png") });
  await page.locator(".pipelineStrip li button").nth(3).click();
  checks.analysisEvidence = await page.locator(".inspectorEvidence div").allTextContents();
  await page.screenshot({ path: path.join(out, "1440-analisis.png"), clip: { x: 190, y: 740, width: 1250, height: 160 } });
  // Del inspector a la pregunta y de la pregunta a la etapa.
  await page.locator(".inspectorAnswers button", { hasText: "¿Cuánto?" }).click();
  await page.waitForTimeout(900);
  checks.focusedQuestion = await page.evaluate(() => document.activeElement?.id);
  const panel = page.locator(".questionsPanel");
  await panel.screenshot({ path: path.join(out, "1440-preguntas.png") });
  await page.locator("#pregunta-significant .questionStages button").first().click();
  await page.waitForTimeout(900);
  checks.backToStage = await page.locator(".inspectorHead h3").textContent();
  // Exportar marca la etapa 9 como completada.
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar JSON" }).click();
  await download;
  await page.locator(".pipelineStrip li button").nth(8).click();
  checks.exportStatus = await page.locator(".inspectorHead em").textContent();
  checks.overflow1440 = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  checks.consoleErrors = errors;
  await page.close();

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mobile.goto(`${BASE_URL}/plataforma`, { waitUntil: "networkidle" });
  await mobile.locator("button.runAnalysis").click();
  await mobile.waitForSelector(".mobileVerdict .verdict");
  await mobile.waitForFunction(() => !document.querySelector(".pipelineStrip.isRunning"));
  await mobile.locator(".pipelineStrip").scrollIntoViewIfNeeded();
  await mobile.waitForTimeout(500);
  await mobile.locator(".pipelineStrip").screenshot({ path: path.join(out, "390-pipeline.png") });
  await mobile.locator(".questionsPanel").screenshot({ path: path.join(out, "390-preguntas.png") });
  checks.overflow390 = await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  console.log(JSON.stringify(checks, null, 2));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
