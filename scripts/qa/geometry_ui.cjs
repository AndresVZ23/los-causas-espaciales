// QA de geometrías de estudio en 3100: dibujo de corredor y polígono, carga de GeoJSON con casos límite y exportación.
// Las geometrías de prueba son sintéticas (solo QA); no representan corredores ni terrenos reales.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "geometrias");
fs.mkdirSync(OUT, { recursive: true });

const fixtures = {
  "corredor-prueba.geojson": { type: "FeatureCollection", features: [{ type: "Feature", properties: { name: "Corredor de prueba" }, geometry: { type: "LineString", coordinates: [[-70.95, -17.2], [-71.1, -17.4], [-71.3, -17.6]] } }] },
  "multiparte.geojson": { type: "Feature", properties: { nombre: "Lotes de prueba" }, geometry: { type: "MultiPolygon", coordinates: [
    [[[-71.55, -16.42], [-71.54, -16.42], [-71.54, -16.41], [-71.55, -16.41], [-71.55, -16.42]]],
    [[[-71.53, -16.42], [-71.52, -16.42], [-71.52, -16.41], [-71.53, -16.41], [-71.53, -16.42]]],
  ] } },
  "crs-utm.geojson": { type: "FeatureCollection", crs: { type: "name", properties: { name: "urn:ogc:def:crs:EPSG::32719" } }, features: [] },
  "utm-sin-crs.geojson": { type: "LineString", coordinates: [[293000, 8097000], [300000, 8090000]] },
  "ejes-invertidos.geojson": { type: "LineString", coordinates: [[-17.2, -70.95], [-17.4, -71.1]] },
  "anillo-abierto.geojson": { type: "Polygon", coordinates: [[[-71.55, -16.42], [-71.54, -16.42], [-71.54, -16.41], [-71.55, -16.41]]] },
  "corbatin.geojson": { type: "Polygon", coordinates: [[[-71.55, -16.42], [-71.54, -16.41], [-71.54, -16.42], [-71.55, -16.41], [-71.55, -16.42]]] },
};
for (const [name, data] of Object.entries(fixtures)) fs.writeFileSync(path.join(OUT, name), JSON.stringify(data));

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport, acceptDownloads: true });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  // El corbatín se rechaza a propósito con 422 en la inspección; el navegador lo anota en consola y no es un defecto.
  let expectedRejections = 0;
  page.on("response", (response) => { if (response.status() === 422 && response.url().includes("geometry-inspect")) expectedRejections += 1; });
  await page.goto(BASE, { waitUntil: "networkidle" });
  const nav = isCompact(viewport) ? ".mobileBottomNav button" : ".moduleNav button";
  if (isCompact(viewport)) {
    await page.getByRole("button", { name: /Más/ }).click();
    await page.locator(".moduleNav button", { hasText: "Infraestructura" }).click();
  } else {
    await page.locator(nav, { hasText: "Infraestructura" }).click();
  }
  // En Infraestructura el panel de geometrías vive dentro de «Dibujar o cargar corredores» (cerrado al inicio).
  const drawer = page.locator(".corridorDraw summary");
  if (await drawer.count()) await drawer.click();
  await page.waitForSelector(".geometryPanel");
  const canvas = page.locator(".mapViewport canvas");
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  const at = (fx, fy) => ({ x: box.x + box.width * fx, y: box.y + box.height * fy });

  // Corredor dibujado: tres clics y doble clic para cerrar.
  await page.getByRole("button", { name: "Dibujar corredor" }).click();
  for (const [fx, fy] of [[0.3, 0.3], [0.5, 0.45]]) { const p = at(fx, fy); await page.mouse.click(p.x, p.y); await page.waitForTimeout(150); }
  const last = at(0.7, 0.6);
  await page.mouse.dblclick(last.x, last.y);
  await page.waitForSelector(".geometryStatus.valida");
  const drawn = await page.locator(".geometryList li").first().innerText();

  // Polígono dibujado con el botón Terminar.
  await page.getByRole("button", { name: "Dibujar polígono" }).click();
  for (const [fx, fy] of [[0.35, 0.65], [0.55, 0.65], [0.55, 0.8], [0.35, 0.8]]) { const p = at(fx, fy); await page.mouse.click(p.x, p.y); await page.waitForTimeout(150); }
  await page.getByRole("button", { name: "Terminar" }).click();
  await page.waitForFunction(() => document.querySelectorAll(".geometryStatus.valida").length >= 2);

  const uploads = {};
  for (const name of Object.keys(fixtures)) {
    await page.getByLabel("Archivo GeoJSON").setInputFiles(path.join(OUT, name));
    await page.waitForSelector(".geometryNotice");
    uploads[name] = await page.locator(".geometryNotice").innerText();
    await page.getByRole("button", { name: "Cerrar aviso" }).click();
  }
  await page.waitForFunction(() => !document.querySelector(".geometryStatus.validando"), null, { timeout: 30000 });
  const list = await page.locator(".geometryList li").allInnerTexts();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await page.screenshot({ path: path.join(OUT, `consola-${tag}.png`) });

  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Exportar GeoJSON" }).click()]);
  const exported = path.join(OUT, `export-${tag}.geojson`);
  await download.saveAs(exported);
  await browser.close();
  let pending = expectedRejections;
  const unexpected = errors.filter((text) => !(text.includes("status of 422") && pending-- > 0));
  return { tag, drawn, list, uploads, overflow, exported, expectedRejections, errors: unexpected };
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
