const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch();
  for (const [w, h] of [[1366, 768], [1536, 864], [1440, 900]]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto(`${process.env.QA_BASE_URL || "http://localhost:3100"}/plataforma`, { waitUntil: "networkidle" });
    const top = await p.locator(".pipelineStrip").evaluate((el) => Math.round(el.getBoundingClientRect().top));
    console.log(`${w}x${h}: el pipeline empieza en y=${top}px -> ${top < h ? "visible sin bajar (" + (h - top) + " px)" : "hay que bajar " + (top - h + 150) + " px para verlo"}`);
    await p.close();
  }
  await b.close();
})();
