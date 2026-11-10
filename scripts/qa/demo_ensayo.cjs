// Ensayo del recorrido principal del demo (DEMO_SCENARIOS.md) en 1440 px, con los actos 2A a 2D: mide la espera de cada acto,
// registra la procedencia visible, captura cada pantalla y descarga el PDF ejecutivo.
// Uso: node scripts/qa/demo_ensayo.cjs [etiqueta]. Correrlo el mismo día del demo deja la caché caliente (TTL 24 h).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const LABEL = process.argv[2] || "ensayo";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "demo", LABEL);
fs.mkdirSync(OUT, { recursive: true });

const PROVENANCE = ["REAL_DATA", "CACHED_DATA", "MODEL_ESTIMATE", "USER_ASSUMPTION", "ILLUSTRATIVE_DEMO", "DATA_UNAVAILABLE"];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  const acts = [];
  // Una captura fallida no detiene el ensayo: se reintenta una vez y, si vuelve a fallar, queda anotada en el informe.
  const missedShots = [];
  const shot = async (name) => {
    for (let attempt = 0; attempt < 2; attempt++) {
      try { await page.screenshot({ path: path.join(OUT, `${name}.png`) }); return; } catch (error) { await page.waitForTimeout(800); }
    }
    missedShots.push(name);
  };
  // Procedencia citada en la fuente del mapa y en el contenido del resultado (no en la leyenda fija de la cabecera).
  const provenanceSeen = () => page.evaluate((codes) => {
    const text = [...document.querySelectorAll(".mapSource, .controlContent, .resultsPane, main section:not(.consoleHeader)")].map((el) => el.innerText).join(" ");
    return Object.fromEntries(codes.map((code) => [code, text.split(code).length - 1]));
  }, PROVENANCE);
  const runAndWait = async (ready) => {
    const button = page.locator("button.runAnalysis");
    await button.scrollIntoViewIfNeeded();
    const started = Date.now();
    await button.click();
    await ready();
    await page.waitForFunction(() => !document.querySelector("button.runAnalysis")?.textContent?.includes("Consultando"), null, { timeout: 400000 });
    return (Date.now() - started) / 1000;
  };

  let started = Date.now();
  await page.goto(BASE, { waitUntil: "networkidle" });
  acts.push({ act: "0 · apertura", seconds: (Date.now() - started) / 1000 });
  await shot("0-apertura");

  // Acto 1 · Territorio + tendencia + extremos: departamento de Moquegua en Clima.
  await page.locator(".moduleNav button", { hasText: "Clima" }).click();
  await page.locator(".territorySection").waitFor();
  await page.getByRole("button", { name: /Quitar Arequipa/ }).click();
  await page.getByLabel("Buscar departamento, provincia o distrito").fill("Moquegua");
  await page.locator(".territoryResults button", { hasText: "Departamento" }).first().click();
  await page.locator(".territoryChosen li").first().waitFor();
  const climateWait = await runAndWait(() => page.locator(".climateTable").first().waitFor({ timeout: 400000 }));
  await page.locator(".cellLegend").waitFor({ timeout: 15000 });
  await page.waitForTimeout(1500);
  await shot("1a-clima-celdas");
  const climate = {
    status: await page.locator(".systemLine b").first().innerText(),
    mapSource: await page.locator(".mapSource").first().innerText(),
    legend: await page.locator(".cellLegend").innerText(),
    reading: (await page.locator(".climateTable").first().innerText()).slice(0, 700),
    extremes: await page.locator(".climateExtremes").allInnerTexts(),
    scale: await page.locator(".territoryScale").allInnerTexts(),
    countercheck: await page.locator("td.agreement").allInnerTexts(),
    provenance: await provenanceSeen(),
  };
  await page.locator('[aria-label="Variable NASA POWER"] button', { hasText: "Lluvia máx. 5 días" }).click();
  await page.waitForTimeout(600);
  await shot("1b-clima-rx5day");
  await page.locator(".siteResult").first().scrollIntoViewIfNeeded();
  await page.locator(".siteResult").first().screenshot({ path: path.join(OUT, "1c-clima-imerg.png") });
  acts.push({ act: "1 · territorio, tendencia y extremos", seconds: climateWait, climate });

  // Acto 1B · Amenazas en el distrito de Lurigancho (Chosica): el mapa de CENEPRED frente a los deslizamientos de NASA.
  await page.locator(".moduleNav button", { hasText: "Amenazas" }).click();
  await page.locator(".territorySection").waitFor();
  await page.getByLabel("Buscar departamento, provincia o distrito").fill("Lurigancho");
  await page.locator('.territoryResults button:has(b:text-is("Lurigancho"))').first().click();
  await page.locator(".territoryChosen li", { hasText: "Lurigancho" }).waitFor();
  await page.locator(".territoryChosen li", { hasText: "Moquegua" }).locator("button").click();
  await page.locator(".siteRemove").first().click();
  const hazardsWait = await runAndWait(() => page.locator(".verdict", { hasText: "Lectura de amenazas" }).first().waitFor({ timeout: 400000 }));
  await page.waitForTimeout(1500);
  await shot("1d-amenazas-lectura");
  const hazards = {
    status: await page.locator(".systemLine b").first().innerText(),
    reading: (await page.locator(".verdict").first().innerText()).slice(0, 900),
    discoveries: await page.locator(".discoveriesPanel .discovery").evaluateAll((items) => items.map((item) => `${item.querySelector(".discoveryKind")?.textContent} · ${item.querySelector("h4")?.textContent} — ${item.querySelector("p")?.textContent}`)),
    nasaLayers: (await page.locator(".baselineLayers tbody tr", { hasText: "NASA" }).allInnerTexts()).map((row) => row.replace(/\s+/g, " ").slice(0, 260)),
    provenance: await provenanceSeen(),
  };
  await page.locator(".discoveriesPanel").first().scrollIntoViewIfNeeded();
  await shot("1e-amenazas-descubrimientos");
  acts.push({ act: "1B · amenazas, CENEPRED frente a los deslizamientos de NASA", seconds: hazardsWait, hazards });

  // Acto 2 · Activo: corredor Moquegua–Ilo (piloto vial) con exposición, puntaje, sensibilidad y decisión.
  await page.locator(".moduleNav button", { hasText: "Infraestructura" }).click();
  await page.locator(".roadControls").waitFor();
  const roadWait = await runAndWait(() => page.locator(".verdict").first().waitFor({ timeout: 400000 }));
  await page.waitForTimeout(1500);
  await shot("2a-vial-lectura");
  const road = {
    status: await page.locator(".systemLine b").first().innerText(),
    mapSource: await page.locator(".mapSource").first().innerText(),
    verdict: (await page.locator(".verdict").first().innerText()).slice(0, 900),
    territorial: (await page.locator(".siteResult").nth(1).innerText()).slice(0, 900),
    scorecard: (await page.locator(".scorecardPanel").first().innerText()).slice(0, 700),
    sensitivity: (await page.locator(".sensitivityPanel").first().innerText()).slice(0, 700),
    provenance: await provenanceSeen(),
  };
  await page.locator(".scorecardPanel").first().scrollIntoViewIfNeeded();
  await shot("2b-vial-puntaje");
  await page.locator(".sensitivityPanel").first().scrollIntoViewIfNeeded();
  await shot("2c-vial-sensibilidad");
  acts.push({ act: "2A · corredor, exposición, puntaje y decisión", seconds: roadWait, road });

  // Acto 2B · Energía: Moquegua frente a Arequipa (el acto 1 quitó Arequipa; «Restablecer» la devuelve).
  await page.locator(".moduleNav button", { hasText: "Energía" }).click();
  await page.getByRole("button", { name: "Restablecer" }).click();
  const solarWait = await runAndWait(() => page.locator(".scorecardPanel").first().waitFor({ timeout: 400000 }));
  await page.waitForTimeout(1500);
  await shot("2d-solar-lectura");
  const solar = {
    status: await page.locator(".systemLine b").first().innerText(),
    scorecard: (await page.locator(".scorecardPanel").first().innerText()).slice(0, 500),
    sensitivity: (await page.locator(".sensitivityPanel").first().innerText()).slice(0, 900),
    provenance: await provenanceSeen(),
  };
  await page.locator(".scorecardPanel").first().scrollIntoViewIfNeeded();
  await shot("2e-solar-puntaje");
  await page.locator(".sensitivityPanel").first().scrollIntoViewIfNeeded();
  await shot("2f-solar-equilibrio");
  acts.push({ act: "2B · solar, empate y punto de equilibrio", seconds: solarWait, solar });

  // Actos 2C y 2D · Eólica e hidroeléctrica con sus sitios de ejemplo: lectura, lo que dice la segunda fuente y el VAN.
  const energyAct = async (radio, editor, firstTab, file) => {
    await page.locator('input[name="tecnologia"]').nth(radio).check();
    await page.locator(editor).waitFor({ timeout: 20000 });
    await page.waitForFunction((label) => document.querySelector('[aria-label="Variable NASA POWER"] button')?.textContent === label, firstTab, { timeout: 20000 });
    const seconds = await runAndWait(() => page.locator(".verdict").first().waitFor({ timeout: 400000 }));
    await page.waitForTimeout(1500);
    await shot(`${file}-lectura`);
    const detail = {
      status: await page.locator(".systemLine b").first().innerText(),
      reading: await page.locator(".verdictTable tbody tr").allInnerTexts(),
      discoveries: await page.locator(".discoveriesPanel .discovery").evaluateAll((items) => items.map((item) => `${item.querySelector(".discoveryKind")?.textContent} · ${item.querySelector("h4")?.textContent}`)),
      scorecard: (await page.locator(".scorecardPanel").first().innerText()).slice(0, 500),
      sensitivity: (await page.locator(".sensitivityPanel").first().innerText()).slice(0, 900),
      provenance: await provenanceSeen(),
    };
    await page.locator(".discoveriesPanel").first().scrollIntoViewIfNeeded();
    await shot(`${file}-descubrimientos`);
    return { seconds, detail };
  };
  const wind = await energyAct(1, ".siteEditor", "Viento 50 m", "2g-eolica");
  acts.push({ act: "2C · eólica, el atlas frente al reanálisis", seconds: wind.seconds, wind: wind.detail });
  const hydro = await energyAct(2, ".hydroEditor", "Caudal", "2h-hidro");
  acts.push({ act: "2D · hidroeléctrica, dos modelos de caudal y dos de relieve", seconds: hydro.seconds, hydro: hydro.detail });

  // Acto 3 · Exportación: PDF ejecutivo del último análisis en pantalla (el hidroeléctrico del acto 2D).
  const pdfButton = page.locator(".exportAction.primaryExport");
  await pdfButton.scrollIntoViewIfNeeded();
  started = Date.now();
  const [download] = await Promise.all([page.waitForEvent("download", { timeout: 120000 }), pdfButton.click()]);
  const target = path.join(OUT, download.suggestedFilename());
  await download.saveAs(target);
  const bytes = fs.readFileSync(target);
  acts.push({ act: "3 · PDF ejecutivo", seconds: (Date.now() - started) / 1000, pdf: { file: download.suggestedFilename(), header: bytes.subarray(0, 4).toString(), kb: Math.round(bytes.length / 1024) } });
  await shot("3-exportado");

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await browser.close();
  const waitTotal = acts.reduce((sum, item) => sum + item.seconds, 0);
  const report = { label: LABEL, at: new Date().toISOString(), waitSeconds: Math.round(waitTotal * 10) / 10, acts, overflow, errors, missedShots };
  fs.writeFileSync(path.join(OUT, "ensayo.json"), JSON.stringify(report, null, 1));
  console.log(JSON.stringify(report, null, 1));
})().catch((err) => { console.error(err); process.exit(1); });
