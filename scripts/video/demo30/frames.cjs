// Dibuja los cuadros de la capa de imagen y texto (overlay.html) como PNG con transparencia.
//
//   node frames.cjs <spec.json> <carpeta de salida> [desde hasta] [trabajadores]
//
// Usa Playwright para Node. PLAYWRIGHT_DIR indica dónde está instalado si no se resuelve solo.
const path = require("path");
const fs = require("fs");
const { chromium } = require(process.env.PLAYWRIGHT_DIR ? path.join(process.env.PLAYWRIGHT_DIR, "playwright") : "playwright");

const [specPath, outDir, fromArg, toArg, workersArg] = process.argv.slice(2);
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const from = fromArg ? +fromArg : 0, to = toArg ? +toArg : spec.cuadros;
const workers = workersArg ? +workersArg : 4;
fs.mkdirSync(outDir, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const page0 = path.join(__dirname, "overlay.html");
  let next = from, done = 0;
  const started = Date.now();
  const work = async (index) => {
    // La ventana mide una fila más que el video (1081). Esa fila queda siempre transparente, y así cada cuadro se guarda
    // como PNG con transparencia. Sin ella, los cuadros totalmente opacos salen sin canal alfa; al cambiar de formato
    // en mitad de la serie, ffmpeg rehace el montaje y uno o dos cuadros del video quedan sin esta capa (un parpadeo).
    // build.py recorta la fila sobrante y comprueba el formato de todos los cuadros.
    const context = await browser.newContext({ viewport: { width: 1920, height: 1081 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
    await page.goto("file://" + page0);
    const info = await page.evaluate((s) => window.setup(s), spec);
    if (index === 0) console.log("listo:", JSON.stringify(info));
    for (;;) {
      const frame = next; next += 1;
      if (frame >= to) break;
      await page.evaluate((t) => window.render(t), frame / spec.fps);
      await page.screenshot({ path: path.join(outDir, `${String(frame).padStart(4, "0")}.png`), omitBackground: true });
      done += 1;
      if (done % 150 === 0) console.log(`${done}/${to - from} cuadros · ${((Date.now() - started) / 1000).toFixed(0)} s`);
    }
    await context.close();
  };
  await Promise.all(Array.from({ length: workers }, (_, i) => work(i)));
  await browser.close();
  console.log(`cuadros: ${done} en ${((Date.now() - started) / 1000).toFixed(0)} s`);
})().catch((e) => { console.error("FALLO", e.message.slice(0, 600)); process.exit(1); });
