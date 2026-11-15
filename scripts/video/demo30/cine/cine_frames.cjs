// Saca los cuadros de las cinemáticas en 3D (cine.html) con la tarjeta gráfica real.
//
//   node cine_frames.cjs prueba <escena> <t1,t2,...> <carpeta>        # cuadros sueltos para revisar
//   node cine_frames.cjs serie <plan.json> <carpeta>                  # plan: [{ escena, cuadros, fps, desde_s? }]
//
// Levanta un servidor local solo de lectura: /repo/ es la raíz del repositorio (three.js, texturas, relieve) y /cine/
// esta carpeta. PLAYWRIGHT_DIR indica dónde está Playwright si no se resuelve solo; REPO_DIR, la raíz del repositorio.
const http = require("http");
const fs = require("fs");
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT_DIR ? path.join(process.env.PLAYWRIGHT_DIR, "playwright") : "playwright");

const REPO = path.resolve(process.env.REPO_DIR || path.join(__dirname, "..", "..", "..", ".."));
const ROOTS = { "/repo/": REPO, "/cine/": __dirname };
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json", ".jpg": "image/jpeg", ".png": "image/png", ".glb": "model/gltf-binary" };

function serve() {
  const server = http.createServer((request, response) => {
    const url = decodeURIComponent(request.url.split("?")[0]);
    const prefix = Object.keys(ROOTS).find((p) => url.startsWith(p));
    const file = prefix ? path.normalize(path.join(ROOTS[prefix], url.slice(prefix.length))) : null;
    if (!file || !file.startsWith(ROOTS[prefix]) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { response.writeHead(404); response.end("no"); return; }
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream", "cache-control": "no-store" });
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

(async () => {
  const [mode, a, b, c] = process.argv.slice(2);
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--ignore-gpu-blocklist", "--enable-gpu"] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on("pageerror", (error) => console.log("PAGEERROR", error.message.slice(0, 400)));
  page.on("console", (message) => { if (message.type() === "error" || message.text().startsWith("cine:")) console.log("consola:", message.text().slice(0, 300)); });
  await page.goto(`${base}/cine/cine.html`, { waitUntil: "load" });
  await page.waitForFunction(() => typeof window.draw === "function", null, { timeout: 60000 });
  const canvas = page.locator("#c");
  // Ningún plano es negro entero: un cuadro así es un fallo del dibujo (un solo píxel sin valor apaga todo el
  // resplandor). Se reconoce por el tamaño del JPEG y se vuelve a dibujar unas milésimas después.
  const BLACK_BYTES = 30000, NUDGE = 0.004;
  const frame = async (scene, t, file) => {
    for (let attempt = 0; attempt < 4; attempt += 1) {
      await page.evaluate(([s, time]) => window.draw(s, time), [scene, t + attempt * NUDGE]);
      const image = await canvas.screenshot({ type: "jpeg", quality: 95 });
      if (image.length > BLACK_BYTES) {
        if (attempt) console.log(`${scene} ${t.toFixed(3)} s salía negro: dibujado ${(attempt * NUDGE * 1000).toFixed(0)} ms después`);
        fs.writeFileSync(file, image);
        return;
      }
    }
    throw new Error(`El cuadro de «${scene}» en ${t.toFixed(3)} s sale negro.`);
  };
  const started = Date.now();
  if (mode === "prueba") {
    fs.mkdirSync(c, { recursive: true });
    for (const t of b.split(",").map(Number)) { await frame(a, t, path.join(c, `${a}_${t.toFixed(2)}.jpg`)); console.log("ok", a, t); }
  } else {
    const plan = JSON.parse(fs.readFileSync(a, "utf8"));
    for (const item of plan) {
      const folder = path.join(b, item.escena);
      fs.mkdirSync(folder, { recursive: true });
      for (let i = 0; i < item.cuadros; i += 1) await frame(item.escena, (item.desde_s || 0) + i / item.fps, path.join(folder, `${String(i).padStart(4, "0")}.jpg`));
      console.log(`${item.escena}: ${item.cuadros} cuadros · ${((Date.now() - started) / 1000).toFixed(0)} s`);
    }
  }
  await browser.close();
  server.close();
})().catch((error) => { console.error("FALLO", error.message.slice(0, 600)); process.exit(1); });
