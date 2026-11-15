// Recorre la historia TERRA 2045 (ADR-050): prólogo, colonia lunar, menú de la Tierra con el estado del planeta, y los
// tres finales sembrando el guardado local: perdedor (regresar sin mejoras), intermedio (último regreso con mejora pero
// sin lo fundamental) y bueno (un lugar a salvo de cada peligro fundamental), más un regreso que no es final. Cada escena
// es una cinemática en video (frontend/public/cine/): anota cuál corre y la salta; sin video, lee las láminas de texto.
// Uso: node scripts/qa/game_story_ui.cjs <1440|390>   (QA_BASE_URL: por defecto http://localhost:3100)
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "jugar");
fs.mkdirSync(OUT, { recursive: true });
const width = process.argv[2] || "1440";
const viewport = width === "390" ? { width: 390, height: 844 } : { width: 1440, height: 900 };
const HERO = { name: "Ayelén", gender: "mujer" };

(async () => {
  const browser = await chromium.launch({ channel: "chromium", args: ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11"] });
  const errors = [];
  const open = async (seed) => {
    const context = await browser.newContext({ viewport });
    if (seed) await context.addInitScript((value) => window.localStorage.setItem("lce-juego-v1", value), JSON.stringify(seed));
    const page = await context.newPage();
    page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text().slice(0, 200)); });
    page.on("pageerror", (err) => errors.push("pageerror: " + String(err).slice(0, 200)));
    await page.goto(`${BASE}/`, { waitUntil: "networkidle", timeout: 120000 });
    await page.getByRole("button", { name: /Jugador/ }).click();
    await page.getByRole("radio", { name: /Mujer/ }).click();
    await page.locator(".gameName input").fill(HERO.name);
    await page.locator(".gameCard .gameGo").click();
    return page;
  };
  const shot = (page, name) => page.screenshot({ path: path.join(OUT, `terra-${width}-${name}.png`) });
  const slides = async (page, prefix) => {
    const texts = [];
    for (let index = 0; index < 14; index += 1) {
      await page.waitForTimeout(4200);
      texts.push(await page.locator(".gameStoryText").innerText().then((text) => text.replace(/\s+/g, " ")));
      await shot(page, `${prefix}-${index + 1}`);
      const button = page.locator(".gameStory .gameGo");
      const label = await button.innerText();
      await button.click();
      if (!/Continuar/.test(label)) { texts.push(`[botón final: ${label}]`); break; }
    }
    return texts;
  };
  // Cinemática en video (cine-scene.tsx): si está, anota cuál corre y la salta; si el video no está, el juego cae a la
  // historia en texto (prólogo, regreso, finales) o directo a la Tierra (viaje), y se devuelve { video: null }.
  const cine = async (page, prefix) => {
    const appeared = await page.locator(".gameCinePlayer").waitFor({ timeout: 8000 }).then(() => true, () => false);
    if (appeared) await page.waitForTimeout(2500);
    if (!appeared || !(await page.locator(".gameCinePlayer").count())) return { video: null };
    const video = await page.locator(".gameCineVideo").evaluate((element) => ({ src: element.currentSrc.replace(/^.*\/cine\//, ""), segundo: +element.currentTime.toFixed(1),
      pausado: element.paused, error: element.error ? element.error.code : null, subtitulos: element.textTracks.length }));
    await shot(page, `${prefix}-video`);
    await page.locator(".gameCineSkip").click();
    return { video };
  };
  const skipPrologue = async (page) => {
    const result = await cine(page, "prologo");
    if (!result.video) await page.locator(".gameStorySkip").click();
  };
  const toEarth = async (page) => {
    await page.locator(".gameCard.moon").waitFor({ timeout: 20000 });
    await page.locator(".gameCard .gameGo").click({ timeout: 90000 });
    const viaje = await cine(page, "viaje");
    await page.locator(".gameReturn").waitFor({ timeout: 40000 });
    return viaje;
  };
  const out = { width: +width };

  // 1 · Prólogo, colonia y final perdedor (regresar sin ningún lugar a salvo).
  let page = await open(null);
  out.prologo = await cine(page, "prologo");
  if (!out.prologo.video) out.prologo.texto = await slides(page, "prologo");
  await page.locator(".gameCard.moon").waitFor({ timeout: 20000 });
  out.colonia = await page.locator(".gameCard.moon").innerText().then((text) => text.replace(/\s+/g, " "));
  await shot(page, "colonia");
  out.viaje = await toEarth(page);
  out.menu = await page.locator(".gameReturn").innerText().then((text) => text.replace(/\s+/g, " "));
  await shot(page, "menu");
  await page.locator(".gameReturn button", { hasText: /Regresar a 2045/ }).click();
  out.confirmacion = await page.locator(".gameConfirm").innerText();
  await page.locator(".gameConfirm button", { hasText: /Sí, regresar/ }).click();
  out.finalPerdedor = { ...(await cine(page, "final-perdedor")), texto: await slides(page, "final-perdedor") };
  await page.context().close();

  // 1b · Regreso que no es final: un lugar a salvo nuevo desde el comienzo, regresos sin usar.
  page = await open({ hero: HERO, badges: {}, story: { chosica: "salvado" }, plans: { chosica: 4 }, returns: { used: 0, savedAtLast: 0 } });
  await skipPrologue(page);
  await toEarth(page);
  await page.locator(".gameReturn button", { hasText: /Regresar a 2045/ }).click();
  await page.locator(".gameConfirm button", { hasText: /Sí, regresar/ }).click();
  out.regreso = { ...(await cine(page, "regreso")), texto: await slides(page, "regreso") };
  await page.context().close();

  // 2 · Final intermedio: dos regresos usados, un lugar nuevo desde el último, sin lo fundamental.
  page = await open({ hero: HERO, badges: {}, story: { chosica: "salvado", piura: "salvado" }, plans: { chosica: 4, piura: 3 }, returns: { used: 2, savedAtLast: 1 } });
  await skipPrologue(page);
  await toEarth(page);
  await page.locator(".gameReturn button", { hasText: /Regresar a 2045/ }).click();
  await page.locator(".gameConfirm button", { hasText: /Sí, regresar/ }).click();
  out.finalIntermedio = { ...(await cine(page, "final-intermedio")), texto: await slides(page, "final-intermedio") };
  await page.context().close();

  // 3 · Final bueno: un lugar a salvo de cada peligro fundamental.
  page = await open({ hero: HERO, badges: {}, story: { chosica: "salvado", piura: "salvado", santiago: "salvado", taal: "salvado", huascaran: "salvado" }, plans: { chosica: 4, piura: 4, santiago: 3, taal: 4, huascaran: 4 } });
  await skipPrologue(page);
  await toEarth(page);
  out.menuCompleto = await page.locator(".gameReturn").innerText().then((text) => text.replace(/\s+/g, " "));
  await shot(page, "menu-completo");
  await page.locator(".gameReturn button.primary").click();
  out.finalBueno = { ...(await cine(page, "final-bueno")), texto: await slides(page, "final-bueno") };
  out.errors = [...new Set(errors)].slice(0, 10);
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})().catch((error) => { console.log(JSON.stringify({ error: String(error).slice(0, 700) })); process.exit(1); });
