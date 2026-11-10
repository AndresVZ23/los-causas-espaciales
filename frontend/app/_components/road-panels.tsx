"use client";

import { formatDay, formatMillions, formatNumber } from "./format";
import type { RoadAssumptions, RoadResult, RoadSegment, TerritorialEvidence } from "./types";

export const DEFAULT_ROAD_ASSUMPTIONS: RoadAssumptions = {
  baseline_interruption_days_per_year: 5, residual_interruption_fraction: 0.4, cost_per_interruption_day_usd: 200_000,
  mitigation_capex_usd_per_km: 120_000, annual_maintenance_usd_per_km: 3_000, discount_rate: 0.1, horizon_years: 15,
  heavy_rain_threshold_mm_day: 20, interruption_days_sensitivity: 0.4, cost_per_day_sensitivity: 0.3, capex_sensitivity: 0.25,
  maintenance_sensitivity: 0.25, residual_fraction_sensitivity: 0.15, discount_rate_sensitivity: 0.02,
};

// Supuestos visibles en la consola; los rangos de sensibilidad siguen con sus valores por defecto del backend.
const FIELDS: { key: keyof RoadAssumptions; label: string; step: number }[] = [
  { key: "baseline_interruption_days_per_year", label: "Días de interrupción/año", step: 1 },
  { key: "cost_per_interruption_day_usd", label: "Costo por día USD", step: 10_000 },
  { key: "residual_interruption_fraction", label: "Interrupción residual (fracción)", step: 0.05 },
  { key: "mitigation_capex_usd_per_km", label: "CAPEX mitigación USD/km", step: 10_000 },
  { key: "annual_maintenance_usd_per_km", label: "Mantenimiento USD/km·año", step: 500 },
  { key: "heavy_rain_threshold_mm_day", label: "Umbral lluvia fuerte mm/día", step: 5 },
  { key: "discount_rate", label: "Tasa de descuento", step: 0.01 },
  { key: "horizon_years", label: "Horizonte (años)", step: 1 },
];

const SOURCE_LABEL: Record<string, string> = {
  "cenepred-flood-risk": "Riesgo de inundación (CENEPRED)",
  "cenepred-mass-movement-risk": "Movimientos en masa (CENEPRED)",
  "sernanp-anp": "Áreas naturales protegidas (SERNANP)",
  "cultura-archaeology": "Patrimonio arqueológico (SIGDA)",
  "cultura-archaeology-declared": "Patrimonio declarado (SIGDA)",
  "ingemmet-geohazards": "Peligros geológicos (INGEMMET)",
};
export const sourceLabel = (id: string) => SOURCE_LABEL[id] ?? id;

export function RoadControls({ source, onSource, myCorridors, assumptions, onAssumption, open, onToggle }: {
  source: "pilot" | "mine"; onSource: (next: "pilot" | "mine") => void; myCorridors: number;
  assumptions: RoadAssumptions; onAssumption: (key: keyof RoadAssumptions, value: number) => void; open: boolean; onToggle: (open: boolean) => void;
}) {
  return (
    <section className="roadControls" aria-labelledby="corredor-title">
      <h3 id="corredor-title">Corredor a evaluar</h3>
      <label className="layerOption"><input type="radio" name="corredor" checked={source === "pilot"} onChange={() => onSource("pilot")} />
        <span>Piloto Moquegua–Ilo<small>OpenStreetMap (ODbL) · 5 tramos · ruta pública de screening</small></span></label>
      <label className="layerOption"><input type="radio" name="corredor" checked={source === "mine"} disabled={!myCorridors} onChange={() => onSource("mine")} />
        <span>Mis corredores ({myCorridors})<small>{myCorridors ? "Dibujados o cargados abajo; cada uno es un tramo" : "Dibuje o cargue un corredor abajo para habilitarlo"}</small></span></label>
      <details className="assumptionPanel" open={open} onToggle={(event) => onToggle(event.currentTarget.open)}>
        <summary>Supuestos viales <span>USER_ASSUMPTION</span></summary>
        <div className="assumptionFields">
          {FIELDS.map((field) => (
            <label key={field.key}>{field.label}
              <input type="number" step={field.step} value={assumptions[field.key]} onChange={(event) => onAssumption(field.key, +event.target.value)} />
            </label>
          ))}
        </div>
        <p className="assumptionGroup">La interrupción y su costo son supuestos: NASA mide la lluvia, no los cortes de vía.</p>
      </details>
    </section>
  );
}

const alerts = (segment: RoadSegment) => Object.entries(segment.territorial_intersections).filter(([, count]) => (count ?? 0) > 0);

export function RoadReading({ result, headingId }: { result: RoadResult; headingId: string }) {
  const card = result.scorecard;
  return (
    <section className="verdict" aria-labelledby={headingId}>
      <div className="verdictHead"><h2 id={headingId}>Lectura del corredor</h2><span>{result.corridor_source.name}</span></div>
      <table className="verdictTable climateTable">
        <thead><tr><th scope="col">Tramo</th><th scope="col">km</th><th scope="col">Lluvia fuerte</th><th scope="col">VAN</th></tr></thead>
        <tbody>
          {result.segments.map((segment) => (
            <tr key={segment.subject_id}>
              <th scope="row">{segment.label}<small>{alerts(segment).length ? `${alerts(segment).reduce((sum, [, count]) => sum + (count ?? 0), 0)} alertas territoriales` : "sin alertas devueltas"}</small></th>
              <td className="figure">{formatNumber(segment.length_km, 1)}</td>
              <td className="figure">{segment.heavy_rain_days_per_year == null ? "N/D" : `${formatNumber(segment.heavy_rain_days_per_year, 1)} d/año`}</td>
              <td className={`figure ${segment.finance.npv_usd >= 0 ? "positive" : "negative"}`}>{formatMillions(segment.finance.npv_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="verdictNote">Lluvia fuerte: días por año sobre el umbral elegido (NASA POWER). El VAN compara mitigar contra el costo de interrupción supuesto; no es factibilidad.</p>
      {card && (
        <div className="verdictAssumptions climateExtremes">
          <p><span>Puntaje multicriterio</span><b>{result.segments.length < 2
            ? "Un solo tramo: el puntaje no compara; agregue otro corredor para priorizar."
            : card.tie
              ? `Empate práctico entre tramos (${formatNumber(card.margin ?? 0, 1)} puntos): priorice con los criterios uno por uno.`
              : `${card.leader} lidera por ${formatNumber(card.margin ?? 0, 1)} puntos.`}</b></p>
        </div>
      )}
    </section>
  );
}

/** Objetos devueltos por cada capa oficial por sujeto; «No disponible» si la capa no respondió. Compartida por los pilotos. */
export function TerritorialTable({ evidence, scope }: { evidence: TerritorialEvidence[]; scope: string }) {
  const sourceIds = [...new Set(evidence.flatMap((item) => item.sources.map((source) => source.source_id)))];
  // Capas cuyo servicio no respondió hoy: se muestran desde su última copia válida, marcadas en la celda y explicadas al pie.
  const staleNotes = sourceIds.flatMap((id) => {
    const stale = evidence.flatMap((item) => item.sources).find((source) => source.source_id === id && source.status === "READY" && source.stale_note);
    return stale?.stale_note ? [{ id, note: stale.stale_note }] : [];
  });
  return (
    <article className="siteResult">
      <div className="siteResultHeader"><div><h3>Capas territoriales oficiales</h3><p>Objetos devueltos por cada servicio {scope}. Cero no prueba ausencia de riesgo o restricción.</p></div></div>
      <div className="tableScroll">
        <table>
          <thead><tr><th>Capa</th>{evidence.map((item) => <th key={item.subject}>{item.subject}</th>)}</tr></thead>
          <tbody>{sourceIds.map((id) => (
            <tr key={id}>
              <th>{sourceLabel(id)}</th>
              {evidence.map((item) => {
                const source = item.sources.find((entry) => entry.source_id === id);
                const ready = source && source.status === "READY" && source.intersection_count != null;
                return <td key={item.subject}>{ready ? source.intersection_count : "No disponible"}{ready && source.stale_note && <small className="staleTag">copia del {formatDay(source.downloaded_at)}</small>}</td>;
              })}
            </tr>
          ))}</tbody>
        </table>
      </div>
      {staleNotes.length > 0 && (
        <div className="staleNotes">{staleNotes.map((item) => <p key={item.id}><b>{sourceLabel(item.id)}.</b> {item.note}</p>)}</div>
      )}
    </article>
  );
}

export function RoadEvidence({ result }: { result: RoadResult }) {
  return (
    <>
      <div className="siteResults">
        <article className="siteResult">
          <div className="siteResultHeader">
            <div><h3>Tramos del corredor</h3><p>{result.corridor_source.name} · {result.corridor_source.source} · {result.corridor_source.license}</p></div>
            <span>{formatNumber(result.segments.reduce((sum, segment) => sum + segment.length_km, 0), 1)} km</span>
          </div>
          <div className="tableScroll">
            <table>
              <thead><tr><th>Tramo</th><th>Longitud</th><th>Lluvia fuerte</th><th>Máx. diario (celdas)</th><th>Pendiente</th><th>Días evitados/año</th><th>CAPEX</th><th>VAN</th></tr></thead>
              <tbody>{result.segments.map((segment) => (
                <tr key={segment.subject_id}>
                  <th>{segment.label}<small>{segment.spatial_exposure ? `${segment.spatial_exposure.cell_count} celdas · cobertura ${formatNumber(segment.spatial_exposure.spatial_coverage_percent, 1)} %` : "sin muestreo espacial"}</small></th>
                  <td>{formatNumber(segment.length_km, 1)} km</td>
                  <td>{segment.heavy_rain_days_per_year == null ? "N/D" : `${formatNumber(segment.heavy_rain_days_per_year, 2)} d/año`}<small>{segment.heavy_rain_years} años</small></td>
                  <td>{segment.spatial_exposure?.rx1day_mm == null ? "N/D" : `${formatNumber(segment.spatial_exposure.rx1day_mm, 1)} mm`}</td>
                  <td>{segment.terrain_slope_degrees == null ? "Sin dato" : `${formatNumber(segment.terrain_slope_degrees, 1)}°`}</td>
                  <td>{formatNumber(segment.finance.avoided_interruption_days_per_year, 1)}</td>
                  <td>{formatMillions(segment.finance.mitigation_capex_usd)}</td>
                  <td className={segment.finance.npv_usd >= 0 ? "positive" : "negative"}>{formatMillions(segment.finance.npv_usd)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </article>
        <TerritorialTable evidence={result.territorial_evidence} scope="dentro del corredor" />
      </div>
      <div className="findingsPanel methodPanel">
        <h3>Corredor y método</h3>
        {[...result.corridor_source.limitations, result.segments[0]?.finance.formula, result.segments[0]?.spatial_exposure?.method].filter(Boolean).map((note, index) => <p key={index}><span>{index + 1}</span>{note}</p>)}
      </div>
    </>
  );
}
