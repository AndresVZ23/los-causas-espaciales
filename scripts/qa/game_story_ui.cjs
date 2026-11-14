// Recorre la historia del modo jugador: prólogo de 2031, nota de la Luna, hoja del cuaderno en una misión,
// final malo (sin lugares a salvo) y final bueno (tres lugares a salvo, sembrados en el guardado local).
// Uso: node scripts/qa/game_story_ui.cjs <1440|390>   (QA_BASE_URL: por defecto http://localhost:3100)
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const BASE = process.env.QA_BASE_URL || "http://localhost:3100";
const OUT = path.join(__dirname, "..", "..", ".claude-qa", "jugar");
fs.mkdirSync(OUT, { recursive: true });
const width = process.argv[2] || "1440";
const viewport = width === "390" ? { width: 390, height: 844 } : { width: 1440, height: 900 };

(async () => {
  const browser = await chromium.launch({ channel: "chromium", args: ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11"] });
  const errors = [];
  const open = async (seed) => {
    const context = await browser.newContext({ viewport });
    if (seed) await context.addInitScript((value) => window.localStorage.setItem("lce-juego-v1", value), JSON.stringify(seed));
    const page = await context.newPage();
    page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text().slice(0, 200)); });
    page.on("pageerror", (err) => errors.push("pageerror: " + String(err).slice(0, 200)));
    await page.goto(`${BASE}/jugar`, { waitUntil: "networkidle", timeout: 120000 });
    await page.getByRole("button", { name: /Jugador/ }).click();
    await page.getByRole("radio", { name: /Mujer/ }).click();
    await page.locator(".gameName input").fill("Detective Andina");
    await page.locator(".gameCard .gameGo").click();
    return page;
  };
  const shot = (page, name) => page.screenshot({ path: path.join(OUT, `historia-${width}-${name}.png`) });
  const slides = async (page, prefix) => {
    const texts = [];
    for (let index = 0; index < 12; index += 1) {
      await page.waitForTimeout(index === 2 ? 9000 : 4200);          // la carta tarda más en escribirse
      texts.push(await page.locator(".gameStoryText").innerText().then((text) => text.replace(/\s+/g, " ")));
      await shot(page, `${prefix}-${index + 1}`);
      const button = page.locator(".gameStory .gameGo");
      const label = await button.innerText();
      await button.click();
      if (!/Continuar/.test(label)) { texts.push(`[botón final: ${label}]`); break; }
    }
    return texts;
  };
  const out = { width: +width };

  // 1 · Prólogo, Luna y final malo.
  let page = await open(null);
  await page.locator(".gameStory").waitFor({ timeout: 20000 });
  out.focoEnContinuar = await page.evaluate(() => document.activeElement?.innerText);
  out.overflowPrologo = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  out.prologo = await slides(page, "prologo");
  await page.locator(".gameCard.moon").waitFor({ timeout: 20000 });
  await page.waitForTimeout(2500);
  out.luna = await page.locator(".gameStoryNote").innerText();
  await shot(page, "luna");
  await page.locator(".gameCard .gameGo").click({ timeout: 90000 });
  await page.locator(".gameReturn").waitFor({ timeout: 40000 });
  out.regreso = await page.locator(".gameReturn").innerText().then((text) => text.replace(/\s+/g, " "));
  await page.waitForTimeout(2000);
  await shot(page, "menu");
  await page.locator(".gameReturn button").click();
  out.finalMalo = await slides(page, "final-malo");
  out.trasFinalMalo = await page.locator(".gameStory").count();

  // 2 · Hoja del cuaderno dentro de una misión, antes de jugar.
  await page.locator(".gameContinentList button").first().click();
  await page.locator(".gameMissionList button", { hasText: /Chosica/ }).click();
  await page.locator(".gamePage").waitFor({ timeout: 30000 });
  out.hoja = await page.locator(".gamePage").innerText().then((text) => text.replace(/\s+/g, " "));
  await page.locator(".gamePage").scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500);
  await shot(page, "hoja");
  // Responder mal el paso 1 y bien el 2 no importa: se responde mal a propósito para ver la hoja sin cambiar.
  await page.getByRole("button", { name: "Se está enfriando" }).click();
  await page.waitForTimeout(400);
  await page.locator(".gameStep button:not([disabled])").first().click().catch(() => undefined);
  await page.waitForTimeout(800);
  out.hojaPerdida = await page.locator(".gamePage").innerText().then((text) => text.replace(/\s+/g, " ").slice(0, 420)).catch(() => null);
  await page.locator(".gamePage").scrollIntoViewIfNeeded().catch(() => undefined);
  await shot(page, "hoja-perdida");
  out.guardado = await page.evaluate(() => JSON.parse(window.localStorage.getItem("lce-juego-v1") || "{}").story);
  await page.context().close();

  // 3 · Final bueno: tres lugares a salvo en el guardado.
  page = await open({ hero: { name: "Detective Andina", gender: "mujer" }, badges: {}, story: { chosica: "salvado", piura: "salvado", nazca: "salvado", derna: "perdido" } });
  await page.locator(".gameStory").waitFor({ timeout: 20000 });
  await page.locator(".gameStorySkip").click();
  await page.locator(".gameCard .gameGo").click({ timeout: 90000 });
  await page.locator(".gameReturn").waitFor({ timeout: 40000 });
  out.regresoBueno = await page.locator(".gameReturn").innerText().then((text) => text.replace(/\s+/g, " "));
  await page.locator(".gameReturn button").click();
  out.finalBueno = await slides(page, "final-bueno");
  out.errors = [...new Set(errors)].slice(0, 10);
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})().catch((error) => { console.log(JSON.stringify({ error: String(error).slice(0, 700) })); process.exit(1); });
