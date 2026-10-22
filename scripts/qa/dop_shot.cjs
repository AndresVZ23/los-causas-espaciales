// Capturas del DOP interno (solo escritorio): una por vista y una con un nodo seleccionado en el mapa.
// Uso: node scripts\qa\dop_shot.cjs docs\interno\dop-neuronal.html .claude-qa\capturas\dop
const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto("file:///" + path.resolve(process.argv[2]).replace(/\\/g, "/"));
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  const out = process.argv[3];
  for (const view of ["net", "orch", "asme", "map", "neural", "plan", "backlog"]) {
    await page.click(`[data-view="${view}"]`);
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(out, `dop-${view}.png`), fullPage: true });
  }
  await page.click('[data-view="map"]');
  await page.click('.node[data-id="labels"]');
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(out, "dop-map-seleccion.png"), fullPage: true });
  // Red: seleccionar un resultado ilumina su cadena; una entrada, sus resultados.
  await page.click('[data-view="net"]');
  await page.click('.unit[data-unit="o-infra"]');
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(out, "dop-net-resultado.png"), fullPage: true });
  await page.click('.unit[data-unit="in-power"]');
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(out, "dop-net-entrada.png"), fullPage: true });
  const unitOverlaps = await page.evaluate(() => {
    const boxes = [...document.querySelectorAll(".unit")].map((n) => n.getBoundingClientRect());
    let hits = 0;
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) hits++;
    }
    return hits;
  });
  console.log(JSON.stringify({ unitOverlaps, metrics: await page.evaluate(() => ["m-inputs", "m-engines", "m-outputs", "m-waves", "next-title"].map((id) => document.getElementById(id).textContent)) }));
  const overlaps = await page.evaluate(() => {
    const boxes = [...document.querySelectorAll(".node")].map((n) => n.getBoundingClientRect());
    let hits = 0;
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) hits++;
    }
    return hits;
  });
  console.log(JSON.stringify({ errors, nodeOverlaps: overlaps }));
  await browser.close();
})();
