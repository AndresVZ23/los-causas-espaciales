// Presentación únicamente: la procedencia y el JSON exportado conservan las unidades originales de NASA POWER.
const DISPLAY_UNITS: Record<string, string> = {
  "kW-hr/m^2/day": "kWh/m²/día",
  "mm/day": "mm/día",
  C: "°C",
  "m/s": "m/s",
};
// Solo códigos inequívocos dentro de texto libre; "C" y "m/s" no se reemplazan en prosa.
const PROSE_UNITS = ["kW-hr/m^2/day", "mm/day"];

// Mismo orden que los marcadores del mapa: sitio principal en cian, comparador en blanco frío.
export const SITE_COLORS = ["#38d9c3", "#e8eaed"];
export function siteColor(index: number) { return SITE_COLORS[index % SITE_COLORS.length]; }

export function displayUnit(raw: string) { return DISPLAY_UNITS[raw] ?? raw; }
export function localizeUnits(text: string) { return PROSE_UNITS.reduce((acc, raw) => acc.replaceAll(raw, DISPLAY_UNITS[raw]), text); }

export function formatMoney(value: number) { return new Intl.NumberFormat("es-PE", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value); }
export function formatNumber(value: number, digits = 2) { return new Intl.NumberFormat("es-PE", { maximumFractionDigits: digits }).format(value); }
export function formatMillions(value: number) { return `${value < 0 ? "−" : ""}USD ${formatNumber(Math.abs(value) / 1e6, 2)} M`; }
export function formatPercent(fraction: number, digits = 1) { return `${formatNumber(fraction * 100, digits)} %`; }
