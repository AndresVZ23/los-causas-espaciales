// QA del asistente C4 en 3100: preguntas sugeridas y libres en Energía y Clima. Usa solo «Preguntar» (modo reglas):
// nunca pulsa «Preguntar a Gemini», para no gastar la cuota del usuario.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "asistente");
fs.mkdirSync(OUT, { recursive: true });

async function askAndRead(page, action) {
  const before = await page.locator(".assistantLog article").count();
  await action();
  await page.waitForFunction((n) => document.querySelectorAll(".assistantLog article").length > n, before, { timeout: 60000 });
  const first = page.locator(".assistantLog article").first();
  return { answer: await first.locator(".assistantAnswer").innerText(), meta: await first.locator(".assistantMeta").innerText() };
}

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(BASE, { waitUntil: "networkidle" });
  const out = { tag, solar: [], climate: [] };

  await page.waitForFunction(() => !document.querySelector("button.runAnalysis")?.disabled);
  await page.locator("button.runAnalysis").click();
  await page.locator(".assistantPanel").waitFor({ timeout: 240000 });
  await page.locator(".assistantPanel").scrollIntoViewIfNeeded();
  out.solar.push(await askAndRead(page, () => page.locator(".assistantSuggestions button").first().click()));
  out.solar.push(await askAndRead(page, async () => { await page.getByLabel("Pregunta sobre el análisis").fill("¿Qué factor mueve más el VAN en Arequipa?"); await page.getByRole("button", { name: "Preguntar", exact: true }).click(); }));
  out.solar.push(await askAndRead(page, async () => { await page.getByLabel("Pregunta sobre el análisis").fill("¿Quién ganó el mundial?"); await page.getByRole("button", { name: "Preguntar", exact: true }).click(); }));
  await page.locator(".assistantPanel").screenshot({ path: path.join(OUT, `solar-${tag}.png`) });

  if (isCompact(viewport)) await page.locator(".mobileBottomNav button", { hasText: "Clima" }).click();
  else await page.locator(".moduleNav button", { hasText: "Clima" }).click();
  await page.waitForFunction(() => !document.querySelector("button.runAnalysis")?.disabled);
  await page.locator("button.runAnalysis").scrollIntoViewIfNeeded();
  await page.locator("button.runAnalysis").click();
  await page.locator(".climateTable").first().waitFor({ timeout: 240000 });
  await page.locator(".assistantPanel").scrollIntoViewIfNeeded();
  for (const index of [1, 2, 3]) out.climate.push(await askAndRead(page, () => page.locator(".assistantSuggestions button").nth(index).click()));
  out.overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  out.errors = errors;
  await browser.close();
  return out;
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
