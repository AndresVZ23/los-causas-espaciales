"use client";

import { formatNumber } from "./format";
import type { MapCell } from "./geo-map";
import type { ClimateResult } from "./types";

// Par divergente validado con el validador de dataviz sobre el fondo oscuro (también usado en el tornado).
const RISING = "#c8743e";
const FALLING = "#1f9e8e";
export const CELL_VARIABLES = [
  { id: "T2M", label: "Temperatura", unit: "°C/década" },
  { id: "PRECTOTCORR", label: "Precipitación", unit: "mm/día por década" },
] as const;
export type CellVariable = (typeof CELL_VARIABLES)[number]["id"];

/** Celdas de todos los territorios para una variable: color por signo, opacidad por magnitud; sin evidencia (BH), casi transparentes. */
export type CellLayer = { cells: MapCell[]; maxPerDecade: number; maxRise: number | null; maxFall: number | null };

export function cellsFor(result: ClimateResult | null, variable: CellVariable): CellLayer {
  const trends = (result?.sites ?? []).flatMap((site) => (site.cell_trends ?? []).filter((cell) => cell.variable === variable).map((cell) => ({ cell, site: site.location.label })));
  const significant = trends.filter(({ cell }) => cell.significant && cell.slope_per_year != null).map(({ cell }) => cell.slope_per_year! * 10);
  const rises = significant.filter((value) => value > 0);
  const falls = significant.filter((value) => value < 0);
  const maxPerDecade = Math.max(1e-9, ...significant.map(Math.abs));
  const unit = CELL_VARIABLES.find((item) => item.id === variable)!.unit;
  const cells = trends.map(({ cell, site }) => {
    const perDecade = (cell.slope_per_year ?? 0) * 10;
    const strength = Math.min(1, Math.abs(perDecade) / maxPerDecade);
    return {
      id: `${site}-${cell.cell_id}`, bounds: cell.bounds, significant: cell.significant,
      color: cell.significant ? (perDecade >= 0 ? RISING : FALLING) : "#818b94",
      opacity: cell.significant ? 0.2 + 0.45 * strength : 0.05,
      label: `${site} · celda ${cell.cell_id}: ${perDecade >= 0 ? "+" : "−"}${formatNumber(Math.abs(perDecade), 2)} ${unit} · `
        + (cell.significant ? `p BH ${formatNumber(cell.adjusted_p_value ?? 0, 3)}` : "sin evidencia tras BH"),
    };
  });
  return { cells, maxPerDecade, maxRise: rises.length ? Math.max(...rises) : null, maxFall: falls.length ? Math.min(...falls) : null };
}

export function CellTrendLegend({ variable, onVariable, layer }: { variable: CellVariable; onVariable: (next: CellVariable) => void; layer: CellLayer }) {
  const unit = CELL_VARIABLES.find((item) => item.id === variable)!.unit;
  const count = layer.cells.length;
  const withEvidence = layer.cells.filter((cell) => cell.significant).length;
  return (
    <div className="cellLegend">
      <div role="group" aria-label="Variable de la grilla de tendencias">
        {CELL_VARIABLES.map((item) => (
          <button key={item.id} className={variable === item.id ? "active" : ""} aria-pressed={variable === item.id} onClick={() => onVariable(item.id)}>{item.label}</button>
        ))}
      </div>
      <p><b>Tendencia por celda</b> · {withEvidence} de {count} celdas con evidencia · Hamed–Rao + BH entre celdas</p>
      <p className="cellScale">
        {layer.maxRise != null && <span><i style={{ background: RISING }} />sube hasta +{formatNumber(layer.maxRise, 2)}</span>}
        {layer.maxFall != null && <span><i style={{ background: FALLING }} />baja hasta −{formatNumber(Math.abs(layer.maxFall), 2)}</span>}
        <span><i className="cellNone" />sin evidencia</span>
      </p>
      <p>{withEvidence ? `${unit} · intensidad del color = magnitud` : "Ninguna celda tiene tendencia significativa: es evidencia insuficiente, no prueba de que no cambie."}</p>
    </div>
  );
}
