// QA de capas visuales GIBS en 3100: catálogo, selección, teselas reales, leyenda, fecha y opacidad (1440 y 390 px).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "capas");
fs.mkdirSync(OUT, { recursive: true });

async function pick(page, label) {
  if ((await page.locator(".layerToggle").getAttribute("aria-expanded")) !== "true") await page.locator(".layerToggle").click();
  const tiles = [];
  const listener = (response) => { if (response.url().includes("gibs.earthdata.nasa.gov/wmts") && !response.url().includes("BlueMarble")) tiles.push(response.status()); };
  page.on("response", listener);
  await page.locator(".layerOption", { hasText: label }).click();
  await page.waitForTimeout(3500);
  page.off("response", listener);
  return { label, tiles: tiles.length, ok: tiles.filter((s) => s === 200).length, legend: await page.locator(".layerLegend p").innerText() };
}

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.locator(".layerToggle").click();
  await page.locator(".layerOption").nth(1).waitFor({ timeout: 90000 });
  const catalog = await page.locator(".layerOption").allInnerTexts();
  const out = { tag, catalog: catalog.map((t) => t.replace(/\n/g, " ")) };
  out.anomaly = await pick(page, "Anomalía de temperatura del mar");
  const legendImg = await page.locator(".layerLegend img").evaluate((img) => ({ loaded: img.complete && img.naturalWidth > 0, w: img.naturalWidth }));
  out.legendImg = legendImg;
  await page.locator(".mapViewport").screenshot({ path: path.join(OUT, `anomalia-${tag}.png`) });
  out.wind = await pick(page, "Viento sobre el mar");
  out.windNotice = await page.locator(".layerNotice").innerText().catch(() => null);
  out.trueColor = await pick(page, "Color real del día");
  await page.locator(".layerSettings input[type=range]").fill("0.4");
  out.opacityLabel = await page.locator(".layerSettings input[type=range]").inputValue();
  await page.locator(".layerOption", { hasText: "Solo mapa base" }).click();
  out.cleared = (await page.locator(".layerLegend").count()) === 0;
  out.overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  out.errors = errors;
  await browser.close();
  return out;
}

(async () => {
  const results = [await run({ width: 1440, height: 900 }, "1440"), await run({ width: 390, height: 844 }, "390")];
  console.log(JSON.stringify(results, null, 1));
})();
