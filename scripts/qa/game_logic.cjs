// Comprobación de honestidad del modo jugador sobre TODAS las misiones, sin navegador.
//
// Carga las reglas reales del juego (frontend/app/_components/game/mission-logic.ts, transpilado al vuelo con el
// TypeScript del proyecto), pide las misiones a la API y revisa cada texto que el juego puede mostrar:
//   1. «pista falsa» solo donde se cumple la regla de la plataforma (ADR-036), recalculada aquí con los valores crudos:
//      índice en mm, hay contraste y el reanálisis supera al menos cinco veces a cada producto satelital;
//   2. «en un solo día» solo para la lluvia máxima de un día (RX1DAY);
//   3. «dos satélites» solo si hay dos productos de contraste;
//   4. ningún código interno en pantalla (sin_respaldo, solo_contraste, increasing…) ni «NaN», «undefined» o «null»;
//   5. donde el lugar «se calienta» o «se enfría» sin que la segunda fuente lo confirme, la respuesta correcta lo dice;
//   6. con datos faltantes las reglas no fallan ni muestran un cero inventado.
//
//   7. la historia TERRA 2045, las decisiones del paso 3 y la regla de los regresos (ADR-050), sin cifras inventadas.
//
//   node scripts/qa/game_logic.cjs                       # API en http://localhost:8000
//   $env:QA_API_URL = "http://127.0.0.1:8111"; node scripts/qa/game_logic.cjs
//   QA_OFFLINE=1 node scripts/qa/game_logic.cjs          # sin API: lee backend/data/missions/missions.json y omite el contrato
//
// Sale con código 1 si alguna regla falla. Imprime un resumen en JSON.
const fs = require("fs");
const path = require("path");
const Module = require("module");

const ROOT = path.join(__dirname, "..", "..");
const API = (process.env.QA_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const ARTIFACT_RATIO = 5;   // el mismo valor que backend/app/orchestration/discoveries.py; aquí se recalcula aparte a propósito
const RAW_CODES = /\b(sin_respaldo|solo_contraste|sin_tendencia|sin_evidencia|sin_segunda_fuente|una_fuente|no_trend|increasing|decreasing|probable_artifact|heat_support)\b/;
const BROKEN = /\b(NaN|undefined|null)\b/;

function typescript() {
  try { return require(path.join(ROOT, "frontend", "node_modules", "typescript")); } catch { return require("typescript"); }
}

function loadLogic(name = "mission-logic.ts") {
  const ts = typescript();
  // Los módulos del juego se importan entre sí (story.ts usa planet.ts): se transpila cada .ts al cargarlo.
  if (!Module._extensions[".ts"]) {
    Module._extensions[".ts"] = (mod, filename) => {
      const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
      mod._compile(code, filename);
    };
  }
  return require(path.join(ROOT, "frontend", "app", "_components", "game", name));
}

/** Todas las cadenas de un valor (reto, puntos de aviso, etiquetas), con su ruta para ubicar el fallo. */
function strings(value, trail = "", out = []) {
  if (typeof value === "string") out.push([trail, value]);
  else if (Array.isArray(value)) value.forEach((item, index) => strings(item, `${trail}[${index}]`, out));
  else if (value && typeof value === "object") Object.entries(value).forEach(([key, item]) => strings(item, trail ? `${trail}.${key}` : key, out));
  return out;
}

/** La regla de la plataforma, recalculada aquí con los valores crudos de la misión. */
function artifacts(mission) {
  const unitOf = Object.fromEntries((mission.extremes || []).map((item) => [item.variable, item.unit]));
  return (mission.flagged_extremes || []).filter((flag) => {
    const others = Object.values(flag.countercheck_values || {}).filter((value) => value != null);
    return unitOf[flag.variable] === "mm" && flag.value != null && others.length > 0 && others.every((value) => value * ARTIFACT_RATIO < flag.value);
  });
}

function texts(logic, mission) {
  return strings({
    pasos: logic.missionSteps ? logic.missionSteps(mission) : [logic.detectiveQuestion(mission), logic.heroChallenge(mission)],
    puntos: logic.missionCheckpoints ? logic.missionCheckpoints(mission) : [],
    etiquetas: logic.missionTags ? logic.missionTags(mission) : [],
    temperatura: logic.temperatureSentence(mission),
    segunda: ["temperature", "rain", "sun"].map((key) => logic.secondSourceSentence(mission[key])),
  });
}

(async () => {
  const logic = loadLogic();
  const offline = process.env.QA_OFFLINE === "1";
  let missions;
  if (offline) {
    missions = JSON.parse(fs.readFileSync(path.join(ROOT, "backend", "data", "missions", "missions.json"), "utf8")).missions;
  } else {
    const response = await fetch(`${API}/api/v1/world/missions`);
    if (!response.ok) throw new Error(`La API respondió ${response.status} en ${API}`);
    missions = (await response.json()).missions;
  }
  const failures = [];
  const fail = (mission, rule, detail) => failures.push({ mision: mission.name, regla: rule, detalle: detail.slice(0, 260) });
  const summary = { api: offline ? "archivo (sin API)" : API, misiones: missions.length, conPistaFalsa: [], artefactosSegunLaRegla: [], calientaSinConfirmar: 0 };

  for (const mission of missions) {
    const real = artifacts(mission);
    if (real.length) summary.artefactosSegunLaRegla.push(mission.name);
    // El backend debe decir lo mismo que la regla recalculada aquí.
    for (const flag of offline ? [] : mission.flagged_extremes || []) {
      if (flag.probable_artifact === undefined) { fail(mission, "contrato", "la API no envía probable_artifact"); break; }
      if (flag.probable_artifact !== real.includes(flag)) fail(mission, "contrato", `probable_artifact de ${flag.variable} ${flag.year} no coincide con la regla`);
    }
    if (!offline && mission.heat !== "sin_evidencia" && mission.heat_support == null) fail(mission, "contrato", "la API no envía heat_support en un lugar con evidencia");

    const all = texts(logic, mission);
    const joined = all.map(([, text]) => text).join(" \n ");
    const saysFalseClue = /pista falsa/i.test(joined);
    if (saysFalseClue) summary.conPistaFalsa.push(mission.name);
    if (!offline && saysFalseClue && !real.length) fail(mission, "pista falsa sin artefacto", all.find(([, text]) => /pista falsa|un modelo marca/i.test(text))[1]);
    for (const [trail, text] of all) {
      if (RAW_CODES.test(text)) fail(mission, "código interno en pantalla", `${trail}: ${text}`);
      if (BROKEN.test(text)) fail(mission, "texto roto", `${trail}: ${text}`);
      if (/en un solo d[ií]a/i.test(text) && saysFalseClue && real.length && !real.some((flag) => flag.variable === "RX1DAY")) fail(mission, "«en un solo día» con otro índice", `${trail}: ${text}`);
      const sources = Math.max(0, ...real.map((flag) => Object.values(flag.countercheck_values).filter((value) => value != null).length));
      if (/dos sat[eé]lites|dos productos/i.test(text) && sources < 2) fail(mission, "«dos satélites» con un solo contraste", `${trail}: ${text}`);
    }
    if (mission.heat !== "sin_evidencia" && mission.heat_support && mission.heat_support !== "confirmada") {
      summary.calientaSinConfirmar += 1;
      const correct = (logic.detectiveQuestion(mission).options.find((option) => option.correct) || {}).feedback || "";
      const context = `${correct} ${logic.temperatureSentence(mission)} ${logic.secondSourceSentence(mission.temperature) || ""}`;
      if (!/ERA5|segunda fuente|una sola fuente|solo NASA POWER/i.test(context)) fail(mission, "calentamiento sin decir el respaldo", correct);
    }
  }

  // Datos faltantes: una misión sin medias ni pendientes no debe fallar ni mostrar un cero inventado.
  const blank = JSON.parse(JSON.stringify(missions[0]));
  for (const key of ["temperature", "rain", "sun"]) if (blank[key]) Object.assign(blank[key], { mean: null, slope_per_year: null, p_value_adjusted: null, confidence_interval: null });
  try {
    for (const [trail, text] of texts(logic, blank)) {
      if (BROKEN.test(text)) fail(blank, "texto roto con datos faltantes", `${trail}: ${text}`);
      if (/(^|[^\d.,])0([.,]0+)? ?(%|°C|mm)/.test(text)) fail(blank, "cero inventado con datos faltantes", `${trail}: ${text}`);
    }
    const empty = { ...blank, temperature: null, rain: null, sun: null, flagged_extremes: [], extremes: [] };
    texts(logic, empty);
  } catch (error) {
    fail(blank, "las reglas fallan con datos faltantes", String(error));
  }

  // La historia (story.ts) es ficción declarada: no puede traer cifras. Solo se admiten los años de la historia (2045 y
  // 2026), el año en que empiezan las series (2001) y los conteos del juego (lugares a salvo, regresos).
  const story = loadLogic("story.ts");
  const planet = loadLogic("planet.ts");
  const decisions = loadLogic("decisions.ts");
  const plain = { name: "historia" };
  const noFigures = (where, lines, allowed = []) => {
    for (const line of lines) {
      const numbers = (line.match(/\d+(?:[.,]\d+)?/g) || []).filter((value) => !["2045", "2026", "2001", ...allowed].includes(value));
      if (numbers.length) fail(plain, "la historia trae una cifra", `${where}: ${line}`);
      if (RAW_CODES.test(line) || BROKEN.test(line)) fail(plain, "texto roto en la historia", `${where}: ${line}`);
    }
  };
  const flat = (slides) => slides.flatMap((slide) => [slide.kicker || "", ...slide.lines, ...(slide.letter || [])]);
  noFigures("prólogo", flat(story.PROLOGUE));
  noFigures("reglas", [story.rulesText()], [String(planet.MAX_RETURNS)]);
  if (!/historia/i.test(story.STORY_NOTICE) || !/no (es )?un pron[oó]stico/i.test(story.STORY_NOTICE)) fail(plain, "la historia no se declara como ficción", story.STORY_NOTICE);
  const missingSets = [planet.FUNDAMENTAL, planet.FUNDAMENTAL.slice(0, 2), planet.FUNDAMENTAL.slice(4)];
  for (const ending of ["bueno", "intermedio", "perdedor"]) {
    for (let saved = 0; saved <= 8; saved += 1) {
      for (const gaps of missingSets) {
        const result = story.finale(ending, saved, ending === "bueno" ? [] : gaps);
        if (result.good !== (ending === "bueno")) fail(plain, "final equivocado", `${ending} con ${saved}`);
        noFigures(`final ${ending} con ${saved}`, flat(result.slides), [String(saved)]);
        if (ending === "intermedio" && !flat(result.slides).join(" ").includes(gaps[0].label.toLowerCase())) fail(plain, "el final intermedio no nombra lo que faltó", gaps[0].label);
      }
    }
  }
  for (const cause of ["emergencia", "voluntario"]) for (let used = 1; used < planet.MAX_RETURNS; used += 1) for (let tier = 0; tier <= 4; tier += 1) for (const gained of [1, 2, 5]) {
    noFigures(`regreso ${used}`, flat(story.returnSlides({ cause, used, tier, gained })), [String(used), String(planet.MAX_RETURNS), String(planet.MAX_RETURNS - used)]);
  }
  for (let saved = 0; saved <= 3; saved += 1) for (const gaps of missingSets) noFigures("transmisión", [story.nikolMessage(saved, gaps, false), story.nikolMessage(saved, [], true)]);
  for (const mission of missions) {
    for (const saved of [false, true]) {
      const page = story.missionPage(mission, saved);
      if (!Array.isArray(page) || !page.length) fail(mission, "misión sin hoja del cuaderno", `a salvo = ${saved}`);
      else noFigures(`hoja de ${mission.name}`, page);
    }
    if (story.missionPage(mission, true).join(" ") === story.missionPage(mission, false).join(" ")) fail(mission, "la hoja no cambia al salvar el lugar", mission.hazard || "sin peligro");
    const voice = story.companionLine(mission);
    if (mission.country === "Perú" && !voice) fail(mission, "misión del Perú sin Christian", mission.name);
    noFigures(`voz de ${mission.name}`, [voice ? voice.text : "", story.nikolBrief(mission)]);
    if (!decisions.decisionSet(mission).measures.length) fail(mission, "misión sin decisiones", mission.name);
  }
  // Un lugar queda a salvo solo con todas las respuestas correctas, un plan confirmado y todo el pueblo avisado.
  const outcomes = [[true, true, true, "salvado"], [true, true, false, null], [false, true, true, "perdido"], [false, true, false, "perdido"], [true, false, true, null]];
  for (const [correct, finished, warned, expected] of outcomes) {
    if (story.missionOutcome(correct, finished, warned) !== expected) fail(plain, "resultado de misión equivocado", `${correct}/${finished}/${warned} → ${story.missionOutcome(correct, finished, warned)}`);
  }

  // Regla de los regresos (planet.ts).
  const judge = (used, savedAtLast, saved, fundamentals) => JSON.stringify(planet.judgeReturn({ used, savedAtLast }, saved, fundamentals));
  const cases = [
    [[0, 0, 0, false], { kind: "final", ending: "perdedor" }],
    [[0, 0, 1, false], { kind: "volver", used: 1, savedAtLast: 1 }],
    [[1, 1, 1, false], { kind: "final", ending: "perdedor" }],
    [[1, 1, 3, false], { kind: "volver", used: 2, savedAtLast: 3 }],
    [[2, 3, 4, false], { kind: "final", ending: "intermedio" }],
    [[2, 3, 3, false], { kind: "final", ending: "perdedor" }],
    [[2, 3, 5, true], { kind: "final", ending: "bueno" }],
    [[0, 0, 5, true], { kind: "final", ending: "bueno" }],
  ];
  for (const [args, expected] of cases) if (judge(...args) !== JSON.stringify(expected)) fail(plain, "regla del regreso equivocada", `${args.join("/")} → ${judge(...args)}`);
  // Lo fundamental: un lugar a salvo por peligro. Se arma con las misiones reales y se comprueba el porcentaje.
  const oneEach = Object.fromEntries(planet.FUNDAMENTAL.map((item) => [missions.find((mission) => mission.hazard === item.id)?.id, "salvado"]).filter(([id]) => id));
  if (Object.keys(oneEach).length !== planet.FUNDAMENTAL.length) fail(plain, "falta una misión de algún peligro fundamental", Object.keys(oneEach).join(","));
  if (!planet.fundamentalsDone(missions, oneEach)) fail(plain, "lo fundamental no se completa con uno de cada peligro", Object.keys(oneEach).join(","));
  const best = planet.planetPercent(missions, { story: oneEach, plans: Object.fromEntries(Object.keys(oneEach).map((id) => [id, 4])) });
  const worst = planet.planetPercent(missions, { story: {}, plans: {} });
  if (worst !== 0 || best < 81) fail(plain, "porcentaje del planeta fuera de lo esperado", `vacío ${worst}, cinco perfectos ${best}`);

  // Decisiones: sin cifras, sin una única respuesta correcta y sin planes imposibles.
  const decisionSummary = {};
  for (const set of decisions.allDecisionSets()) {
    noFigures(`título de decisiones ${set.key}`, [set.title], ["3"]);
    noFigures(`decisiones ${set.key}`, [set.situation, set.indifference, ...set.measures.flatMap((item) => [item.text, item.benefit, item.limit])]);
    const plans = [];
    const walk = (index, chosen) => {
      if (index === set.measures.length) { if (chosen.length && decisions.spent(set, chosen) <= set.budget) plans.push(chosen); return; }
      walk(index + 1, chosen);
      walk(index + 1, [...chosen, set.measures[index].id]);
    };
    walk(0, []);
    const results = plans.map((chosen) => decisions.evaluatePlan(set, chosen));
    const top = results.filter((result) => result.quality === 4).length;
    if (top < 2) fail(plain, "decisiones con una sola respuesta perfecta", `${set.key}: ${top}`);
    if (!results.some((result) => result.weak)) fail(plain, "decisiones sin ningún plan débil", set.key);
    decisionSummary[set.key] = { planes: plans.length, perfectos: top, debiles: results.filter((result) => result.weak).length };
  }
  summary.historia = { laminasDelPrologo: story.PROLOGUE.length, regresos: planet.MAX_RETURNS, fundamentales: planet.FUNDAMENTAL.length, planetaCincoPerfectos: best };
  summary.decisiones = decisionSummary;

  summary.fallos = failures.length;
  summary.porRegla = failures.reduce((count, item) => ({ ...count, [item.regla]: (count[item.regla] || 0) + 1 }), {});
  summary.detalle = failures.slice(0, 40);
  console.log(JSON.stringify(summary, null, 1));
  process.exit(failures.length ? 1 : 0);
})().catch((error) => { console.error(String(error)); process.exit(2); });
