"use client";

import { formatMillions, formatNumber } from "./format";
import { TerritorialTable } from "./road-panels";
import TerritoryPicker from "./territory-picker";
import type { RealEstateAssumptions, RealEstateResult, RealEstateSite, TerritoryPick } from "./types";

export const DEFAULT_REAL_ESTATE_ASSUMPTIONS: RealEstateAssumptions = {
  developable_fraction: 0.55, floor_area_ratio: 1.0, sale_price_usd_m2: 850, construction_cost_usd_m2: 480, land_cost_usd_m2: 90,
  mitigation_cost_usd_m2_land: 12, selling_cost_fraction: 0.05, annual_absorption_fraction: 0.25, discount_rate: 0.12, horizon_years: 8,
  sale_price_sensitivity: 0.2, construction_cost_sensitivity: 0.2, land_cost_sensitivity: 0.25, mitigation_cost_sensitivity: 0.3,
  absorption_sensitivity: 0.1, discount_rate_sensitivity: 0.02,
};

// Áreas de ejemplo del contrato K3 (scripts/export_real_estate_contract.py): cuadrados de 0.003° (~330 m) en
// coordenadas públicas. Son ilustrativas: no representan lotes, predios ni ofertas reales.
const square = (west: number, south: number, size = 0.003): GeoJSON.Polygon => ({
  type: "Polygon", coordinates: [[[west, south], [west + size, south], [west + size, south + size], [west, south + size], [west, south]]],
});
export const EXAMPLE_PARCELS = [
  { id: "moquegua-area", label: "Área de ejemplo Moquegua", geometry: square(-70.92, -17.21) },
  { id: "samegua-area", label: "Área de ejemplo Samegua", geometry: square(-70.885, -17.19) },
  { id: "cerro-colorado-area", label: "Área de ejemplo Cerro Colorado", geometry: square(-71.585, -16.365) },
];

const FIELDS: { key: keyof RealEstateAssumptions; label: string; step: number }[] = [
  { key: "sale_price_usd_m2", label: "Precio de venta USD/m²", step: 25 },
  { key: "construction_cost_usd_m2", label: "Costo de construcción USD/m²", step: 25 },
  { key: "land_cost_usd_m2", label: "Costo del terreno USD/m²", step: 5 },
  { key: "developable_fraction", label: "Fracción urbanizable", step: 0.05 },
  { key: "floor_area_ratio", label: "Coeficiente de edificación", step: 0.1 },
  { key: "mitigation_cost_usd_m2_land", label: "Mitigación USD/m² de terreno", step: 1 },
  { key: "annual_absorption_fraction", label: "Absorción anual (fracción)", step: 0.05 },
  { key: "discount_rate", label: "Tasa de descuento", step: 0.01 },
  { key: "horizon_years", label: "Horizonte (años)", step: 1 },
];

export type ParcelSource = "ejemplo" | "mios" | "territorios";

export function RealEstateControls({ source, onSource, myParcels, territories, onAddTerritory, onRemoveTerritory, assumptions, onAssumption, open, onToggle }: {
  source: ParcelSource; onSource: (next: ParcelSource) => void; myParcels: number;
  territories: TerritoryPick[]; onAddTerritory: (pick: TerritoryPick) => void; onRemoveTerritory: (ubigeo: string) => void;
  assumptions: RealEstateAssumptions; onAssumption: (key: keyof RealEstateAssumptions, value: number) => void; open: boolean; onToggle: (open: boolean) => void;
}) {
  return (
    <section className="roadControls" aria-labelledby="terrenos-title">
      <h3 id="terrenos-title">Terrenos a comparar</h3>
      <label className="layerOption"><input type="radio" name="terrenos" checked={source === "ejemplo"} onChange={() => onSource("ejemplo")} />
        <span>Áreas de ejemplo (3)<small>Cuadrados ilustrativos de ~330 m en Moquegua, Samegua y Cerro Colorado; no son lotes reales</small></span></label>
      <label className="layerOption"><input type="radio" name="terrenos" checked={source === "mios"} disabled={!myParcels} onChange={() => onSource("mios")} />
        <span>Mis polígonos ({myParcels})<small>{myParcels ? "Dibujados o cargados abajo" : "Dibuje o cargue un polígono abajo para habilitarlo"}</small></span></label>
      <label className="layerOption"><input type="radio" name="terrenos" checked={source === "territorios"} onChange={() => onSource("territorios")} />
        <span>Territorios IGN ({territories.length})<small>Distritos, provincias o departamentos como áreas de análisis</small></span></label>
      {source === "territorios" && (
        <div className="territorySection">
          {territories.length > 0 && (
            <ul className="territoryChosen">
              {territories.map((item) => (
                <li key={item.ubigeo}><div><b>{item.name}</b><span>{item.context} · ubigeo {item.ubigeo}</span></div>
                  <button onClick={() => onRemoveTerritory(item.ubigeo)} aria-label={`Quitar ${item.name}`}>Quitar</button></li>
              ))}
            </ul>
          )}
          <TerritoryPicker onAdd={onAddTerritory} disabled={territories.length >= 12} chosen={territories.map((item) => item.ubigeo)} />
        </div>
      )}
      <details className="assumptionPanel" open={open} onToggle={(event) => onToggle(event.currentTarget.open)}>
        <summary>Supuestos inmobiliarios <span>USER_ASSUMPTION</span></summary>
        <div className="assumptionFields">
          {FIELDS.map((field) => (
            <label key={field.key}>{field.label}
              <input type="number" step={field.step} value={assumptions[field.key]} onChange={(event) => onAssumption(field.key, +event.target.value)} />
            </label>
          ))}
        </div>
        <p className="assumptionGroup">Precios, costos y absorción son supuestos del usuario; NASA y las capas oficiales no los informan.</p>
      </details>
    </section>
  );
}

const alertCount = (site: RealEstateSite) => Object.values(site.territorial_intersections).reduce<number>((sum, count) => sum + (count ?? 0), 0);
const area = (km2: number) => (km2 < 1 ? `${formatNumber(km2 * 100, 1)} ha` : `${formatNumber(km2, 1)} km²`);

// El umbral de escala (200 ha) lo decide el backend K3 y llega como advertencia en `cautions`; aquí solo se muestra.
const SCALE_CAUTION = "escala territorial";

export function scoreVerdict(card: RealEstateResult["scorecard"], count: number, noun: string) {
  if (!card) return null;
  if (count < 2) return `Un solo ${noun}: el puntaje no compara; agregue otro para priorizar.`;
  return card.tie
    ? `Empate práctico (${formatNumber(card.margin ?? 0, 1)} puntos): compare los criterios uno por uno.`
    : `${card.leader} lidera por ${formatNumber(card.margin ?? 0, 1)} puntos.`;
}

export function RealEstateReading({ result, headingId }: { result: RealEstateResult; headingId: string }) {
  const card = result.scorecard;
  const oversized = result.sites
    .map((site) => ({ label: site.label, caution: site.cautions.find((text) => text.includes(SCALE_CAUTION)) }))
    .filter((item): item is { label: string; caution: string } => Boolean(item.caution));
  return (
    <section className="verdict" aria-labelledby={headingId}>
      <div className="verdictHead"><h2 id={headingId}>Lectura de terrenos</h2><span>{result.sites.length} terreno(s)</span></div>
      <table className="verdictTable climateTable">
        <thead><tr><th scope="col">Terreno</th><th scope="col">Área</th><th scope="col">Pendiente</th><th scope="col">VAN</th></tr></thead>
        <tbody>
          {result.sites.map((site) => (
            <tr key={site.subject_id}>
              <th scope="row">{site.label}<small>{alertCount(site) ? `${alertCount(site)} alertas territoriales` : "sin alertas devueltas"}</small></th>
              <td className="figure">{area(site.area_km2)}</td>
              <td className="figure">{site.terrain_slope_degrees == null ? "Sin dato" : `${formatNumber(site.terrain_slope_degrees, 1)}°`}</td>
              <td className={`figure ${site.finance.npv_usd >= 0 ? "positive" : "negative"}`}>{formatMillions(site.finance.npv_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="verdictNote">Pendiente NASADEM en el punto representativo. El VAN usa los supuestos del usuario; no es tasación ni factibilidad.</p>
      {oversized.map((item) => <p key={item.label} className="layerNotice"><b>{item.label}:</b> {item.caution}</p>)}
      {card && (
        <div className="verdictAssumptions climateExtremes">
          <p><span>Puntaje multicriterio</span><b>{scoreVerdict(card, result.sites.length, "terreno")}</b></p>
        </div>
      )}
    </section>
  );
}

export function RealEstateEvidence({ result }: { result: RealEstateResult }) {
  return (
    <>
      <div className="siteResults">
        <article className="siteResult">
          <div className="siteResultHeader"><div><h3>Terrenos</h3><p>Área geodésica, exposición a lluvia por celdas NASA POWER, relieve y escenario económico con supuestos del usuario.</p></div></div>
          <div className="tableScroll">
            <table>
              <thead><tr><th>Terreno</th><th>Área</th><th>Lluvia P99</th><th>Pendiente</th><th>Área vendible</th><th>Ingresos</th><th>Construcción</th><th>VAN</th></tr></thead>
              <tbody>{result.sites.map((site) => (
                <tr key={site.subject_id}>
                  <th>{site.label}<small>{result.site_sources.find((item) => item.subject === site.label)?.dataset ?? "—"}{site.spatial_exposure ? ` · ${site.spatial_exposure.mode === "POINT" ? "punto representativo" : `${site.spatial_exposure.cell_count} celdas`}` : ""}</small></th>
                  <td>{area(site.area_km2)}</td>
                  <td>{site.spatial_exposure?.p99_precipitation_mm_day == null ? "N/D" : `${formatNumber(site.spatial_exposure.p99_precipitation_mm_day, 1)} mm/día`}</td>
                  <td>{site.terrain_slope_degrees == null ? "Sin dato" : `${formatNumber(site.terrain_slope_degrees, 1)}°`}</td>
                  <td>{formatNumber(site.finance.saleable_floor_area_m2, 0)} m²</td>
                  <td>{formatMillions(site.finance.projected_revenue_usd)}</td>
                  <td>{formatMillions(site.finance.projected_construction_cost_usd)}</td>
                  <td className={site.finance.npv_usd >= 0 ? "positive" : "negative"}>{formatMillions(site.finance.npv_usd)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </article>
        <TerritorialTable evidence={result.territorial_evidence} scope="dentro de cada terreno" />
      </div>
      <div className="findingsPanel methodPanel">
        <h3>Terrenos y método</h3>
        {[...new Set([...result.site_sources.flatMap((item) => item.limitations), result.sites[0]?.finance.formula, result.sites[0]?.spatial_exposure?.method].filter(Boolean))].map((note, index) => <p key={index}><span>{index + 1}</span>{note}</p>)}
      </div>
    </>
  );
}
