const { chromium } = require("playwright");
// URL de la consola: QA_BASE_URL o el puerto oficial 3100.
const BASE_URL = process.env.QA_BASE_URL || "http://localhost:3100";
const fs = require("fs");
const path = require("path");
const out = process.argv[2];
const base = BASE_URL;

(async () => {
  const browser = await chromium.launch();
  const checks = {};
  for (const vp of [{ name: "1440", width: 1440, height: 900 }, { name: "390", width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height }, acceptDownloads: true });
    const errors = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(`${base}/plataforma`, { waitUntil: "networkidle", timeout: 180000 });
    await page.locator("button.runAnalysis").click();
    await page.waitForSelector(".verdict", { timeout: 180000 });
    await page.waitForFunction(() => !document.querySelector(".pipelineStrip.isRunning"), null, { timeout: 180000 });
    const pdfButton = page.locator(".exportAction.primaryExport");
    await pdfButton.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(out, `${vp.name}-botones.png`) });
    const download = page.waitForEvent("download", { timeout: 120000 });
    await pdfButton.click();
    const file = await download;
    const target = path.join(out, `${vp.name}-${file.suggestedFilename()}`);
    await file.saveAs(target);
    const bytes = fs.readFileSync(target);
    await page.locator(".pipelineStrip li button").nth(8).click();
    checks[vp.name] = {
      filename: file.suggestedFilename(),
      pdfHeader: bytes.subarray(0, 4).toString(),
      sizeKb: Math.round(bytes.length / 1024),
      exportStatus: await page.locator(".inspectorHead em").textContent(),
      exportSummary: await page.locator(".inspectorSummary").textContent(),
      overflow: await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth),
      consoleErrors: errors,
    };
    await page.close();
  }
  console.log(JSON.stringify(checks, null, 2));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
