// QA del puntaje multicriterio en 3100 (piloto solar): resumen, tabla, edición de pesos y recálculo en el backend.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "puntaje");
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
  const panel = page.locator(".scorecardPanel");
  await panel.waitFor({ timeout: 240000 });
  await panel.scrollIntoViewIfNeeded();
  const summary = await panel.locator(".scoreSummary").innerText();
  const rows = await panel.locator(".scoreTable tbody tr").count();
  const fragility = await panel.locator(".scoreNotes p").first().innerText();
  await panel.screenshot({ path: path.join(OUT, `panel-${tag}.png`) });

  // Todo el peso al VAN: la suma deja de ser 100 y aparece el aviso; «Llevar a 100 %» renormaliza y recalcula.
  await panel.getByLabel("Peso de VAN / CAPEX (%)").fill("80");
  const unbalanced = await panel.locator(".weightBar p").innerText();
  await panel.getByRole("button", { name: "Llevar a 100 %" }).click();
  await page.waitForFunction(() => !document.querySelector(".weightBar button.primary")?.textContent?.includes("Recalculando"));
  await page.waitForTimeout(300);
  const after = await panel.locator(".scoreSummary").innerText();
  const balanced = await panel.locator(".weightBar p").innerText();
  await panel.getByRole("button", { name: "Pesos por defecto" }).click();
  await page.waitForTimeout(600);
  const restored = await panel.locator(".scoreSummary").innerText();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await browser.close();
  return { tag, summary, rows, fragility, unbalanced, after, balanced, restoredEqual: restored === summary, overflow, errors };
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
