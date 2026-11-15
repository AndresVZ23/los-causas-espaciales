const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto("http://localhost:3100/plataforma", { waitUntil: "networkidle" });
  const hasta = await p.locator(".filterStrip input[type=date]").nth(1).inputValue();
  await p.locator("button.runAnalysis").click(); await p.waitForSelector(".verdict", { timeout: 180000 });
  console.log(JSON.stringify({ hasta, cabecera: await p.locator(".systemLine small").first().textContent(), anioEnCurso: await p.locator(".verdictNote").nth(1).textContent() }, null, 1));
  await b.close();
})();
