// QA de Energía eólica e hidroeléctrica en 3100 (1440/768/390): ejecución real con los sitios de ejemplo, lectura,
// gráfico con su segunda fuente, evidencia, recortes de texto, desborde horizontal, errores de consola y PDF.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "energia");
fs.mkdirSync(OUT, { recursive: true });
const TECHS = [
  { name: "eolica", radio: 1, editor: ".siteEditor", firstTab: "Viento 50 m", evidence: "Atlas Eólico Global" },
  { name: "hidro", radio: 2, editor: ".hydroEditor", firstTab: "Caudal", evidence: "Curva de duración" },
];

// Texto que no cabe en su caja sin un mecanismo declarado (scroll propio o elipsis). Mismo criterio que release_ui.cjs.
const clipped = (page) => page.evaluate(() => {
  const scrolls = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const s = getComputedStyle(p); if (["auto", "scroll"].includes(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; } return false; };
  return [...document.querySelectorAll("button, a, label, input, select, th, td, h1, h2, h3, h4, p, b, small, span, em, strong, legend, figcaption")]
    .filter((el) => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (s.display === "inline" || s.display === "none" || s.visibility === "hidden" || r.width === 0 || el.clientWidth === 0) return false;
      if (s.textOverflow === "ellipsis" || scrolls(el) || el.closest("[aria-hidden='true'], .srOnly, .maplibregl-map")) return false;
      if (el.matches("input, select")) return false;
      return el.scrollWidth > el.clientWidth + 1;
    })
    .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(" ").filter(Boolean)[0] || ""} "${(el.innerText || "").trim().slice(0, 40)}" ${el.scrollWidth}>${el.clientWidth}`)
    .slice(0, 12);
});
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

async function run(viewport, tag) {
  const out = { tag };
  for (const tech of TECHS) {
    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport, acceptDownloads: true });
    const errors = [];
    page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
    page.on("pageerror", (err) => errors.push(String(err)));
    await page.goto(BASE, { waitUntil: "networkidle" });
    // Hidratación: el selector de tecnología responde solo cuando React ya montó. Energía es el módulo inicial.
    await page.waitForFunction(() => document.querySelectorAll('input[name="tecnologia"]').length === 3, null, { timeout: 60000 });
    await page.locator('input[name="tecnologia"]').nth(tech.radio).check();
    await page.locator(tech.editor).waitFor({ timeout: 20000 });
    await page.waitForFunction((label) => document.querySelector('[aria-label="Variable NASA POWER"] button')?.textContent === label, tech.firstTab, { timeout: 20000 });
    const result = { clippedBefore: await clipped(page), overflowBefore: await overflow(page) };
    const button = page.locator("button.runAnalysis");
    await button.scrollIntoViewIfNeeded();
    const started = Date.now();
    await button.click();
    await page.waitForFunction(() => document.querySelector("button.runAnalysis")?.getAttribute("aria-busy") !== "true"
      && (document.querySelector(".verdict") || document.querySelector(".errorMessage")), null, { timeout: 400000 });
    result.seconds = Math.round((Date.now() - started) / 1000);
    result.failure = await page.locator(".errorMessage").first().innerText().catch(() => "");
    if (!result.failure) {
      await page.waitForTimeout(800);
      Object.assign(result, {
        reading: await page.locator(".verdictTable tbody tr").allInnerTexts(),
        checkLegend: await page.locator(".checkKey").first().innerText().catch(() => ""),
        evidenceFound: (await page.locator(".siteResults").last().innerText()).includes(tech.evidence),
        scorecard: await page.locator(".scorecardPanel").count(), sensitivity: await page.locator(".sensitivityPanel").count(),
        questions: await page.locator(".question").count(), discoveries: await page.locator(".discoveriesPanel .discovery").count(),
        gaps: await page.locator(".gapPanel article").count(),
        clippedAfter: await clipped(page), overflowAfter: await overflow(page),
      });
      await page.locator(".siteResults").last().screenshot({ path: path.join(OUT, `${tech.name}-evidencia-${tag}.png`) });
      if (!isCompact(viewport)) {
        const [download] = await Promise.all([page.waitForEvent("download", { timeout: 120000 }), page.locator(".primaryExport").click()]);
        const file = path.join(OUT, `${tech.name}-reporte.pdf`);
        await download.saveAs(file);
        result.pdfBytes = fs.statSync(file).size;
      }
    }
    result.errors = errors;
    out[tech.name] = result;
    await browser.close();
  }
  return out;
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
