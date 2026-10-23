// Las unidades de presentación llegan del backend (`display_unit`); aquí solo se formatean cifras.

// Mismo orden que los marcadores del mapa: sitio principal en cian, comparador en blanco frío; 3.º y 4.º sujeto
// (territorios) en ámbar y lavanda. Separación para daltonismo validada (ΔE ≥ 9.4 entre vecinos); la serie se
// nombra siempre junto a su color, así que la identidad no depende solo del color.
export const SITE_COLORS = ["#38d9c3", "#e8eaed", "#e09040", "#9d8cff"];
export function siteColor(index: number) { return SITE_COLORS[index % SITE_COLORS.length]; }

export function formatMoney(value: number) { return new Intl.NumberFormat("es-PE", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value); }
export function formatNumber(value: number, digits = 2) { return new Intl.NumberFormat("es-PE", { maximumFractionDigits: digits }).format(value); }
export function formatMillions(value: number) { return `${value < 0 ? "−" : ""}USD ${formatNumber(Math.abs(value) / 1e6, 2)} M`; }
export function formatPercent(fraction: number, digits = 1) { return `${formatNumber(fraction * 100, digits)} %`; }
export function formatDuration(ms: number) { return ms >= 1000 ? `${formatNumber(ms / 1000, 2)} s` : `${formatNumber(ms, 0)} ms`; }
