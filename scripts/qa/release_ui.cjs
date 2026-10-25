// Puerta visual de cierre (RELEASE_2026-11-07.md) en 1440/768/390: recortes de texto en controles,
// navegación por teclado (foco visible y nunca en elementos ocultos) y estados de carga y error simulados.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { isCompact, runAll } = require("./viewports.cjs");

const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "cierre");
fs.mkdirSync(OUT, { recursive: true });
const MODULES = ["Clima", "Energía", "Amenazas", "Ambiente", "Territorio", "Infraestructura", "Inversión"];

async function openModule(page, viewport, name) {
  if (isCompact(viewport)) {
    const bottom = page.locator(".mobileBottomNav button", { hasText: name });
    if (await bottom.count()) return bottom.first().click();
    await page.getByRole("button", { name: /Más/ }).click();
  }
  await page.locator(".moduleNav button", { hasText: name }).first().click();
}

// Texto que no cabe en su caja sin un mecanismo declarado (scroll propio o elipsis).
const clipped = (page) => page.evaluate(() => {
  // Solo cuenta como mecanismo un ancestro que de verdad se desplaza en horizontal.
  const scrolls = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const s = getComputedStyle(p); if (["auto", "scroll"].includes(s.overflowX) && p.scrollWidth > p.clientWidth + 1) return true; } return false; };
  return [...document.querySelectorAll("button, a, label, input, select, th, td, h1, h2, h3, h4, p, b, small, span, em, strong")]
    .filter((el) => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (s.display === "inline" || s.display === "none" || s.visibility === "hidden" || r.width === 0 || el.clientWidth === 0) return false;
      if (s.textOverflow === "ellipsis" || scrolls(el) || el.closest("[aria-hidden='true'], .srOnly, .maplibregl-map")) return false;
      if (el.matches("input, select")) return false;
      return el.scrollWidth > el.clientWidth + 1;
    })
    .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).split(" ").filter(Boolean)[0] || ""} "${(el.innerText || el.value || "").trim().slice(0, 40)}" ${el.scrollWidth}>${el.clientWidth}`)
    .slice(0, 15);
});

async function keyboard(page, steps) {
  await page.locator("body").click({ position: { x: 2, y: 2 } });
  const visited = [];
  const problems = [];
  for (let i = 0; i < steps; i++) {
    await page.keyboard.press("Tab");
    await page.waitForTimeout(150); // los bordes de foco tienen transición
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      let hidden = r.width === 0 || r.height === 0 || s.visibility === "hidden";
      for (let p = el; p && !hidden; p = p.parentElement) {
        const ps = getComputedStyle(p);
        if (ps.visibility === "hidden" || ps.display === "none" || p.inert) hidden = true;
      }
      // Fuera de la pantalla en horizontal (riel desplegable cerrado) no se arregla con scroll.
      if (r.right <= 0 || r.left >= window.innerWidth) hidden = true;
      // Indicador visible: contorno, sombra o borde en el color de acento (campos de la barra de filtros).
      // En un campo de fecha, el Tab también pasa por el ícono del calendario (sombra nativa): su anillo vive en
      // ::-webkit-calendar-picker-indicator:focus-visible y el anfitrión deja de coincidir con :focus.
      if (el.type === "date" && !el.matches(":focus")) return { tag: "input", name: "calendario", hidden, ring: true, style: "" };
      const ring = s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0 || s.boxShadow !== "none" || s.borderColor.includes("56, 217, 195");
      const name = (el.getAttribute("aria-label") || el.innerText || el.value || el.getAttribute("title") || "").trim().replace(/\s+/g, " ").slice(0, 40);
      return { tag: el.tagName.toLowerCase(), name, hidden, ring, style: `${s.outlineStyle}/${s.boxShadow}/${s.borderColor}` };
    });
    if (!info) continue;
    visited.push(`${info.tag}:${info.name}`);
    if (info.hidden) problems.push(`oculto ${info.tag} "${info.name}"`);
    else if (!info.ring) problems.push(`sin anillo ${info.tag} "${info.name}" (${info.style})`);
  }
  return { reached: visited.length, unnamed: visited.filter((v) => v.endsWith(":")).length, problems: [...new Set(problems)].slice(0, 12), first: visited.slice(0, 6) };
}

async function run(viewport, tag) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.goto(BASE, { waitUntil: "networkidle" });
  const out = { tag, clipped: {}, overflow: {} };
  for (const name of MODULES) {
    await openModule(page, viewport, name);
    await page.waitForTimeout(400);
    out.clipped[name] = await clipped(page);
    out.overflow[name] = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  }
  out.keyboard = await keyboard(page, 45);

  // Carga y error: la API de clima responde tarde y luego con 503; la interfaz debe decirlo sin inventar datos.
  await openModule(page, viewport, "Clima");
  await page.route("**/api/climate-screening", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "La consulta a NASA POWER falló: prueba de caída simulada." }) });
  });
  const button = page.locator("button.runAnalysis");
  await button.scrollIntoViewIfNeeded();
  await button.click();
  await page.waitForTimeout(800);
  out.loading = { button: (await button.innerText()).trim(), busy: await button.getAttribute("aria-busy"), status: await page.locator(".systemLine b").first().innerText().catch(() => "(oculta en compacto)") };
  const alert = page.locator(".errorMessage[role='alert']").first();
  await alert.waitFor({ timeout: 15000 });
  out.error = { alert: (await alert.innerText()).trim().slice(0, 160), status: await page.locator(".systemLine b").first().innerText().catch(() => "(oculta en compacto)"), verdicts: await page.locator(".verdict").count() };
  await alert.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(OUT, `error-${tag}.png`) });
  await page.unroute("**/api/climate-screening");
  out.errors = errors.filter((text) => !text.includes("503"));
  await browser.close();
  return out;
}

(async () => {
  const results = await runAll(run);
  console.log(JSON.stringify(results, null, 1));
})();
