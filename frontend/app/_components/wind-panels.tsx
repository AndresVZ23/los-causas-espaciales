import { formatMillions, formatNumber, formatPercent, siteColor } from "./format";
import type { Point, WindAssumptions, WindResult, WindSite } from "./types";

// Mismo orden de claves que el backend: la consola compara los supuestos vigentes con los del resultado.
export const DEFAULT_WIND_ASSUMPTIONS: WindAssumptions = {
  capacity_mw: 50, hub_height_m: 100, cut_in_ms: 3, rated_ms: 12, cut_out_ms: 25, losses: 0.15,
  initial_capex_usd: 65000000, annual_opex_usd: 1750000, energy_price_usd_mwh: 55, mitigation_capex_usd: 0, discount_rate: 0.1, horizon_years: 25,
  price_sensitivity: 0.2, capex_sensitivity: 0.2, opex_sensitivity: 0.2, losses_sensitivity: 0.05, discount_rate_sensitivity: 0.02,
};
// Marcona tiene parques eólicos en operación; Moquegua sirve de contraste de un sitio de poco viento.
export const WIND_SITES: Point[] = [
  { label: "Marcona", latitude: -15.36, longitude: -75.16 },
  { label: "Moquegua", latitude: -17.193, longitude: -70.934 },
];
export const windTabs = [
  { id: "WS50M", short: "Viento 50 m" },
  { id: "WS10M", short: "Viento 10 m" },
  { id: "T2M", short: "Temperatura" },
  { id: "PRECTOTCORR", short: "Precipitación" },
];

const atlasLevel = (site: WindSite) => site.resource.level_factor !== 1;

export type EnergyTech = "solar" | "wind" | "hydro";

export function EnergyTechControls({ tech, onTech }: { tech: EnergyTech; onTech: (tech: EnergyTech) => void }) {
  return (
    <section className="roadControls" aria-labelledby="tecnologia-title">
      <h3 id="tecnologia-title">Tecnología</h3>
      <label className="layerOption"><input type="radio" name="tecnologia" checked={tech === "solar"} onChange={() => onTech("solar")} />
        <span>Solar fotovoltaica<small>Irradiancia NASA POWER (CERES) cruzada con ERA5</small></span></label>
      <label className="layerOption"><input type="radio" name="tecnologia" checked={tech === "wind"} onChange={() => onTech("wind")} />
        <span>Eólica<small>Viento horario NASA POWER a 50 m, nivel del Atlas Eólico Global y contraste ERA5</small></span></label>
      <label className="layerOption"><input type="radio" name="tecnologia" checked={tech === "hydro"} onChange={() => onTech("hydro")} />
        <span>Hidroeléctrica de pasada<small>Caudal diario GloFAS cruzado con GEOGLOWS y salto NASADEM cruzado con Copernicus</small></span></label>
    </section>
  );
}

type ReadingProps = { result: WindResult; staleAssumptions: boolean; onEditAssumptions: () => void; headingId: string };

export function WindReading({ result, staleAssumptions, onEditAssumptions, headingId }: ReadingProps) {
  const ranked = [...result.sites].sort((a, b) => a.relative_position - b.relative_position);
  const used = result.assumptions;
  const withAtlas = ranked.filter(atlasLevel).length;
  return (
    <section className="verdict" aria-labelledby={headingId}>
      <div className="verdictHead">
        <h2 id={headingId}>Lectura comparativa</h2>
        <span>Viento al buje · {formatNumber(used.hub_height_m, 0)} m</span>
      </div>
      <table className="verdictTable">
        <thead><tr><th scope="col">Orden</th><th scope="col">Sitio</th><th scope="col">Viento</th><th scope="col" className="trendCell">Factor de planta</th><th scope="col">VAN cond.</th></tr></thead>
        <tbody>
          {ranked.map((site) => (
            <tr key={site.location.label} className={site.relative_position === 1 ? "lead" : undefined}>
              <td className="rank">{site.relative_position}.º</td>
              <th scope="row"><i aria-hidden="true" style={{ background: siteColor(result.sites.indexOf(site)) }} />{site.location.label}
                <small>{atlasLevel(site) ? "nivel del atlas" : "nivel NASA POWER"}<span className="trendInline">FP {formatPercent(site.finance.capacity_factor_net)}</span></small></th>
              <td className="figure">{formatNumber(site.resource.mean_speed_hub_used, 2)} m/s</td>
              <td className="trendCell">{formatPercent(site.finance.capacity_factor_net)} neto</td>
              <td className={`figure ${site.finance.npv_usd >= 0 ? "positive" : "negative"}`}>{formatMillions(site.finance.npv_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="verdictNote">
        {withAtlas === ranked.length
          ? "Nivel medio del Atlas Eólico Global (250 m) con la forma hora a hora y la variación entre años de NASA POWER; el nivel propio de NASA POWER queda como escenario adverso."
          : withAtlas === 0 ? "El Atlas Eólico Global no respondió: la energía usa el nivel de la celda de NASA POWER, que en costa y relieve complejo puede subestimar el viento."
          : "Algunos sitios no tienen atlas y usan el nivel de NASA POWER: la comparación entre ellos mezcla fuentes de nivel."}
      </p>
      <div className={`verdictAssumptions ${staleAssumptions ? "isStale" : ""}`}>
        <p>
          <span>{staleAssumptions ? "Supuestos editados · vuelva a ejecutar para recalcular el VAN" : "VAN calculado con USER_ASSUMPTION"}</span>
          <b>{formatNumber(used.capacity_mw, 1)} MW · buje {formatNumber(used.hub_height_m, 0)} m · pérdidas {formatPercent(used.losses, 0)} · CAPEX {formatMillions(used.initial_capex_usd)} · {formatNumber(used.energy_price_usd_mwh, 1)} USD/MWh · tasa {formatPercent(used.discount_rate)} · {used.horizon_years} años</b>
        </p>
        <button type="button" onClick={onEditAssumptions}>Editar supuestos</button>
      </div>
    </section>
  );
}

type FieldsProps = { assumptions: WindAssumptions; onChange: (key: keyof WindAssumptions, value: number) => void };

export function WindAssumptionFields({ assumptions, onChange }: FieldsProps) {
  const field = (key: keyof WindAssumptions, label: string, step = "1", min?: string, max?: string) => (
    <label>{label}<input type="number" step={step} min={min} max={max} value={assumptions[key]} onChange={(event) => onChange(key, +event.target.value)} /></label>
  );
  return <>
    <div className="assumptionFields">
      {field("capacity_mw", "Capacidad MW")}
      {field("hub_height_m", "Altura del buje m", "5", "40", "200")}
      {field("initial_capex_usd", "CAPEX USD")}
      {field("energy_price_usd_mwh", "Precio USD/MWh")}
      {field("annual_opex_usd", "OPEX anual USD")}
      {field("losses", "Pérdidas (fracción)", "0.01", "0", "0.59")}
      {field("discount_rate", "Tasa descuento", "0.01")}
      {field("horizon_years", "Horizonte años", "1", "1", "50")}
    </div>
    <p className="assumptionGroup">Curva de potencia genérica (m/s) · reemplazar por la del fabricante</p>
    <div className="assumptionFields">
      {field("cut_in_ms", "Arranque", "0.5", "0.5", "10")}
      {field("rated_ms", "Nominal", "0.5", "1", "25")}
      {field("cut_out_ms", "Parada", "0.5", "5", "40")}
    </div>
    <p className="assumptionGroup">Rangos de sensibilidad (±) · el del recurso sale de los años observados y del atlas</p>
    <div className="assumptionFields">
      {field("price_sensitivity", "Precio ± (fracción)", "0.05", "0", "0.95")}
      {field("capex_sensitivity", "CAPEX ± (fracción)", "0.05", "0", "0.95")}
      {field("opex_sensitivity", "OPEX ± (fracción)", "0.05", "0", "0.95")}
      {field("losses_sensitivity", "Pérdidas ± (puntos)", "0.01", "0", "0.45")}
      {field("discount_rate_sensitivity", "Tasa ± (puntos)", "0.005", "0", "0.45")}
    </div>
  </>;
}

const pct = (value: number | null) => (value == null ? "N/D" : `${value > 0 ? "+" : ""}${formatNumber(value, 0)} %`);

export function WindEvidence({ result }: { result: WindResult }) {
  return (
    <div className="siteResults">
      {result.sites.map((site) => {
        const { resource: r, atlas_check: atlas, finance } = site;
        const factors = r.annual_capacity_factors.map((item) => item.value);
        return (
          <article className="siteResult" key={site.location.label}>
            <div className="siteResultHeader"><div><h3>{site.location.label}</h3><p>{site.relative_position_text}</p></div><span>{site.relative_position}.º de {result.sites.length}</span></div>
            <div className="tableScroll">
              <table className="compactTable">
                <thead><tr><th>Recurso</th><th>NASA POWER</th><th>Atlas Eólico Global</th></tr></thead>
                <tbody>
                  <tr><th>Viento a 50 m<small>{r.years} · {formatNumber(r.hours, 0)} h</small></th><td>{formatNumber(r.mean_speed_50m, 2)} m/s</td><td>{atlas?.speed_50m == null ? "N/D" : `${formatNumber(atlas.speed_50m, 2)} m/s (${pct(atlas.gap_percent_50m)})`}</td></tr>
                  <tr><th>Viento al buje ({formatNumber(r.hub_height_m, 0)} m)<small>cizalladura α {formatNumber(r.shear_exponent, 3)}</small></th><td>{formatNumber(r.mean_speed_hub, 2)} m/s</td><td>{atlas?.speed_hub == null ? "N/D" : `${formatNumber(atlas.speed_hub, 2)} m/s (${pct(atlas.gap_percent_hub)})`}</td></tr>
                  <tr><th>Factor de planta bruto<small>curva genérica · ρ {formatNumber(r.air_density_kg_m3, 3)} kg/m³</small></th><td>{formatPercent(r.capacity_factor_gross_nasa_level)}</td><td>{atlas?.capacity_factor_gross_at_atlas == null ? "N/D" : formatPercent(atlas.capacity_factor_gross_at_atlas)}</td></tr>
                  <tr><th>Usado en el caso base</th><td colSpan={2}><b>{atlasLevel(site) ? "Nivel del atlas con la forma horaria de NASA POWER" : "Nivel de NASA POWER"}</b> · {formatPercent(finance.capacity_factor_net)} neto · {formatNumber(finance.annual_energy_mwh, 0)} MWh/año · VAN <span className={finance.npv_usd >= 0 ? "positive" : "negative"}>{formatMillions(finance.npv_usd)}</span></td></tr>
                  {factors.length > 1 && <tr><th>Factor bruto por año<small>{r.years}</small></th><td colSpan={2}>de {formatPercent(Math.min(...factors))} a {formatPercent(Math.max(...factors))}</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="siteNotes">
              {[...site.opportunities, ...site.cautions, r.density_basis + "."].map((note, index) => <p key={index}>{note}</p>)}
            </div>
            <div className="tableScroll">
              <table>
                <thead><tr><th>Variable NASA</th><th>Media</th><th>Cobertura</th><th>Pendiente Sen</th><th>Evidencia BH</th></tr></thead>
                <tbody>{site.variables.map((variable) => (
                  <tr key={variable.variable}>
                    <th>{variable.label}<small>{variable.variable}</small></th>
                    <td>{formatNumber(variable.mean, 3)} {variable.display_unit}</td>
                    <td>{formatNumber(variable.completeness_percent, 1)}%</td>
                    <td>{variable.trend.slope_per_year == null ? "N/D" : `${variable.trend.slope_per_year.toFixed(4)} ${variable.display_unit}/año`}</td>
                    <td>{variable.significant_after_bh ? "Significativa" : "Insuficiente"}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </article>
        );
      })}
      <div className="findingsPanel methodPanel">
        <h3>Método eólico</h3>
        {result.method_validation?.map((note) => <p key={note} className="methodValidation"><span>real</span>{note}</p>)}
        {[result.sites[0]?.finance.formula, "Cizalladura por sitio: ln(v50 / v10) / ln 5 con las medias horarias; el atlas usa su propia cizalladura entre 50 y 100 m.",
          ...(result.sites[0]?.finance.limitations ?? []),
          ...(result.sites.find((site) => site.atlas_check)?.atlas_check?.limitations ?? [])].filter(Boolean).map((note, index) => <p key={index}><span>{index + 1}</span>{note}</p>)}
      </div>
    </div>
  );
}
