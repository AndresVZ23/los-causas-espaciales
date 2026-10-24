// Viewports de la regresión visual: escritorio, tableta y móvil. QA_VIEWPORTS="1440,390" limita la corrida.
const ALL = {
  1440: { width: 1440, height: 900 },
  768: { width: 768, height: 1024 },
  390: { width: 390, height: 844 },
};

const VIEWPORTS = (process.env.QA_VIEWPORTS || "1440,768,390")
  .split(",")
  .map((tag) => tag.trim())
  .filter((tag) => ALL[tag])
  .map((tag) => ({ tag, viewport: ALL[tag] }));

// Mismo corte que styles.css (@media max-width: 900px): por debajo, menú inferior y riel desplegable.
const isCompact = (viewport) => viewport.width <= 900;

async function runAll(run, ...extra) {
  const results = [];
  for (const { tag, viewport } of VIEWPORTS) results.push(await run(viewport, tag, ...extra));
  return results;
}

module.exports = { VIEWPORTS, isCompact, runAll };
