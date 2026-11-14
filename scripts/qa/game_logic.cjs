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
//   node scripts/qa/game_logic.cjs                       # API en http://localhost:8000
//   $env:QA_API_URL = "http://127.0.0.1:8111"; node scripts/qa/game_logic.cjs
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

function loadLogic(name = "mission-logic.ts") {
  const ts = require(path.join(ROOT, "frontend", "node_modules", "typescript"));
  const file = path.join(ROOT, "frontend", "app", "_components", "game", name);
  const output = ts.transpileModule(fs.readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const loaded = new Module(file, module);
  loaded.filename = file;
  loaded.paths = Module._nodeModulePaths(path.dirname(file));
  loaded._compile(output, file);
  return loaded.exports;
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
  const response = await fetch(`${API}/api/v1/world/missions`);
  if (!response.ok) throw new Error(`La API respondió ${response.status} en ${API}`);
  const { missions } = await response.json();
  const failures = [];
  const fail = (mission, rule, detail) => failures.push({ mision: mission.name, regla: rule, detalle: detail.slice(0, 260) });
  const summary = { api: API, misiones: missions.length, conPistaFalsa: [], artefactosSegunLaRegla: [], calientaSinConfirmar: 0 };

  for (const mission of missions) {
    const real = artifacts(mission);
    if (real.length) summary.artefactosSegunLaRegla.push(mission.name);
    // El backend debe decir lo mismo que la regla recalculada aquí.
    for (const flag of mission.flagged_extremes || []) {
      if (flag.probable_artifact === undefined) { fail(mission, "contrato", "la API no envía probable_artifact"); break; }
      if (flag.probable_artifact !== real.includes(flag)) fail(mission, "contrato", `probable_artifact de ${flag.variable} ${flag.year} no coincide con la regla`);
    }
    if (mission.heat !== "sin_evidencia" && mission.heat_support == null) fail(mission, "contrato", "la API no envía heat_support en un lugar con evidencia");

    const all = texts(logic, mission);
    const joined = all.map(([, text]) => text).join(" \n ");
    const saysFalseClue = /pista falsa/i.test(joined);
    if (saysFalseClue) summary.conPistaFalsa.push(mission.name);
    if (saysFalseClue && !real.length) fail(mission, "pista falsa sin artefacto", all.find(([, text]) => /pista falsa|un modelo marca/i.test(text))[1]);
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

  // La historia (story.ts) es ficción declarada: no puede traer cifras. Solo se admiten los años de la historia (2031 y
  // 2026), el año en que empiezan las series (2001) y el conteo de lugares avisados a tiempo en el final.
  const story = loadLogic("story.ts");
  const plain = { name: "historia" };
  const noFigures = (where, lines, allowed = []) => {
    for (const line of lines) {
      const numbers = (line.match(/\d+(?:[.,]\d+)?/g) || []).filter((value) => !["2031", "2026", "2001", ...allowed].includes(value));
      if (numbers.length) fail(plain, "la historia trae una cifra", `${where}: ${line}`);
      if (RAW_CODES.test(line) || BROKEN.test(line)) fail(plain, "texto roto en la historia", `${where}: ${line}`);
    }
  };
  const flat = (slides) => slides.flatMap((slide) => [slide.kicker || "", ...slide.lines, ...(slide.letter || [])]);
  noFigures("prólogo", flat(story.PROLOGUE));
  if (!/historia/i.test(story.STORY_NOTICE) || !/no (es )?un pron[oó]stico/i.test(story.STORY_NOTICE)) fail(plain, "la historia no se declara como ficción", story.STORY_NOTICE);
  for (let saved = 0; saved <= story.STORY_GOAL + 1; saved += 1) {
    const ending = story.finale(saved);
    if (ending.good !== (saved >= story.STORY_GOAL)) fail(plain, "final equivocado", `con ${saved} lugares a salvo, final bueno = ${ending.good}`);
    noFigures(`final con ${saved}`, flat(ending.slides), [String(saved), String(story.STORY_GOAL)]);
  }
  for (const mission of missions) {
    for (const saved of [false, true]) {
      const page = story.missionPage(mission, saved);
      if (!Array.isArray(page) || !page.length) fail(mission, "misión sin hoja del cuaderno", `a salvo = ${saved}`);
      else noFigures(`hoja de ${mission.name}`, page);
    }
    if (story.missionPage(mission, true).join(" ") === story.missionPage(mission, false).join(" ")) fail(mission, "la hoja no cambia al salvar el lugar", mission.hazard || "sin peligro");
  }
  // Un lugar queda a salvo solo con todas las respuestas correctas y todo el pueblo avisado.
  const outcomes = [[true, true, true, "salvado"], [true, true, false, null], [false, true, true, "perdido"], [false, true, false, "perdido"], [true, false, true, null]];
  for (const [correct, finished, warned, expected] of outcomes) {
    if (story.missionOutcome(correct, finished, warned) !== expected) fail(plain, "resultado de misión equivocado", `${correct}/${finished}/${warned} → ${story.missionOutcome(correct, finished, warned)}`);
  }
  summary.historia = { laminasDelPrologo: story.PROLOGUE.length, lugaresParaElFinalBueno: story.STORY_GOAL };

  summary.fallos = failures.length;
  summary.porRegla = failures.reduce((count, item) => ({ ...count, [item.regla]: (count[item.regla] || 0) + 1 }), {});
  summary.detalle = failures.slice(0, 40);
  console.log(JSON.stringify(summary, null, 1));
  process.exit(failures.length ? 1 : 0);
})().catch((error) => { console.error(String(error)); process.exit(2); });
