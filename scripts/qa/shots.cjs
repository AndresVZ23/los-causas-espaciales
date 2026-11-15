// Uso: node shots.cjs <carpeta-salida> [selectorResultado]
const { chromium } = require("playwright");
// URL de la consola: QA_BASE_URL o el puerto oficial 3100.
const BASE_URL = process.env.QA_BASE_URL || "http://localhost:3100";
const path = require("path");
const fs = require("fs");

const out = process.argv[2];
const resultSelector = process.argv[3] || ".readingGrid";
fs.mkdirSync(out, { recursive: true });
const viewports = [
  { name: "1440", width: 1440, height: 900 },
  { name: "768", width: 768, height: 1024 },
  { name: "390", width: 390, height: 844 },
];

(async () => {
  const browser = await chromium.launch();
  const report = [];
  for (const vp of viewports) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    const errors = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(`${BASE_URL}/plataforma`, { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(out, `${vp.name}-antes.png`) });
    await page.locator("button.runAnalysis").first().click();
    await page.waitForSelector(resultSelector, { timeout: 180000 });
    await page.waitForFunction(() => !document.querySelector(".pipelineStrip.isRunning"), null, { timeout: 180000 });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(out, `${vp.name}-resultado.png`) });
    await page.screenshot({ path: path.join(out, `${vp.name}-completa.png`), fullPage: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const scrollY = await page.evaluate(() => window.scrollY);
    report.push({ viewport: vp.name, overflowPx: overflow, scrollYAfterRun: scrollY, consoleErrors: errors });
    await page.close();
  }
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
})().catch((e) => { console.error(e); process.exit(1); });
