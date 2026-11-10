import { formatMillions, formatNumber, formatPercent, siteColor } from "./format";
import type { HydroAssumptions, HydroPoint, HydroResult, HydroSiteInput, HydroSiteResult } from "./types";

// Mismo orden de claves que el backend: la consola compara los supuestos vigentes con los del resultado.
export const DEFAULT_HYDRO_ASSUMPTIONS: HydroAssumptions = {
  design_exceedance_percent: 30, ecological_flow_fraction: 0.1, min_turbine_flow_fraction: 0.2, efficiency: 0.87, head_loss_fraction: 0.05,
  availability: 0.95, capex_usd_per_mw: 2500000, opex_fraction_of_capex: 0.025, energy_price_usd_mwh: 55, mitigation_capex_usd: 0,
  discount_rate: 0.1, horizon_years: 30, price_sensitivity: 0.2, capex_sensitivity: 0.2, opex_sensitivity: 0.2, discount_rate_sensitivity: 0.02,
};
// Machupicchu es una central en operación (represa y casa de máquinas según OpenStreetMap; 61 m³/s de diseño): sirve
// para comparar el modelo con su producción real. El Tambo alto es un tramo de ejemplo dentro de Moquegua.
export const HYDRO_SITES: HydroSiteInput[] = [
  { label: "Machupicchu (río Vilcanota)", intake: { latitude: -13.18291, longitude: -72.53356 }, powerhouse: { latitude: -13.17421, longitude: -72.56025 }, design_flow_m3s: 61 },
  { label: "Tambo alto (Moquegua)", intake: { latitude: -16.64468, longitude: -70.76477 }, powerhouse: { latitude: -16.68564, longitude: -70.77409 }, design_flow_m3s: null },
];
export const hydroTabs = [
  { id: "RIVER_DISCHARGE", short: "Caudal" },
  { id: "PRECTOTCORR", short: "Precipitación" },
  { id: "T2M", short: "Temperatura" },
];
export type HydroEnd = "intake" | "powerhouse";
export type HydroPick = { index: number; end: HydroEnd } | null;
const END_LABEL: Record<HydroEnd, string> = { intake: "Toma (sobre el río)", powerhouse: "Casa de máquinas (aguas abajo)" };
const MAX_SITES = 4;

type EditorProps = {
  sites: HydroSiteInput[]; onChange: (sites: HydroSiteInput[]) => void; picking: HydroPick; onPick: (pick: HydroPick) => void;
};

export function HydroSiteEditor({ sites, onChange, picking, onPick }: EditorProps) {
  const update = (index: number, patch: Partial<HydroSiteInput>) => onChange(sites.map((site, position) => (position === index ? { ...site, ...patch } : site)));
  const move = (index: number, end: HydroEnd, key: keyof HydroPoint, value: string) => update(index, { [end]: { ...sites[index][end], [key]: +value } });
  const add = () => {
    const last = sites[sites.length - 1] ?? HYDRO_SITES[0];
    onChange([...sites, { label: `Sitio ${sites.length + 1}`, intake: { ...last.intake }, powerhouse: { ...last.powerhouse }, design_flow_m3s: null }]);
  };
  return (
    <section className="hydroEditor" aria-label="Aprovechamientos hidroeléctricos">
      {sites.map((site, index) => (
        <div className="hydroSite" key={index}>
          <div className="hydroSiteHead">
            <span aria-hidden="true">{index + 1}</span>
            <label>Aprovechamiento<input value={site.label} onChange={(event) => update(index, { label: event.target.value })} /></label>
            {sites.length > 1 && <button type="button" onClick={() => { onPick(null); onChange(sites.filter((_, position) => position !== index)); }} aria-label={`Quitar ${site.label || `sitio ${index + 1}`}`}>Quitar</button>}
          </div>
          {(["intake", "powerhouse"] as HydroEnd[]).map((end) => {
            const active = picking?.index === index && picking.end === end;
            return (
              <fieldset className="hydroPoint" key={end}>
                <legend>{END_LABEL[end]}</legend>
                <label>Latitud<input type="number" step="0.0001" value={site[end].latitude} onChange={(event) => move(index, end, "latitude", event.target.value)} /></label>
                <label>Longitud<input type="number" step="0.0001" value={site[end].longitude} onChange={(event) => move(index, end, "longitude", event.target.value)} /></label>
                <button type="button" aria-pressed={active} onClick={() => onPick(active ? null : { index, end })}>{active ? "Haga clic en el mapa" : "Elegir en el mapa"}</button>
              </fieldset>
            );
          })}
          <label className="hydroDesign">Caudal de diseño m³/s (opcional; vacío = según la excedencia)
            <input type="number" step="0.5" min="0" value={site.design_flow_m3s ?? ""} placeholder="según la excedencia"
                   onChange={(event) => update(index, { design_flow_m3s: event.target.value === "" || +event.target.value <= 0 ? null : +event.target.value })} />
          </label>
        </div>
      ))}
      {sites.length < MAX_SITES && <button type="button" className="hydroAdd" onClick={add}>Agregar aprovechamiento</button>}
      <p className="territoryHint">La toma va sobre el río y la casa de máquinas aguas abajo: el salto es la diferencia de elevación entre ambas.
        La primera consulta de un río nuevo puede tardar 1–2 minutos; la segunda opinión del caudal puede llegar en la siguiente ejecución.</p>
    </section>
  );
}

type ReadingProps = { result: HydroResult; staleAssumptions: boolean; onEditAssumptions: () => void; headingId: string };

export function HydroReading({ result, staleAssumptions, onEditAssumptions, headingId }: ReadingProps) {
  const ranked = [...result.sites].sort((a, b) => a.relative_position - b.relative_position);
  const used = result.assumptions;
  const moved = ranked.filter((site) => site.resource.cell.moved).map((site) => site.location.label);
  return (
    <section className="verdict" aria-labelledby={headingId}>
      <div className="verdictHead">
        <h2 id={headingId}>Lectura comparativa</h2>
        <span>Central de pasada · energía anual</span>
      </div>
      <table className="verdictTable">
        <thead><tr><th scope="col">Orden</th><th scope="col">Sitio</th><th scope="col">Potencia</th><th scope="col" className="trendCell">Energía</th><th scope="col">VAN cond.</th></tr></thead>
        <tbody>
          {ranked.map((site) => (
            <tr key={site.location.label} className={site.relative_position === 1 ? "lead" : undefined}>
              <td className="rank">{site.relative_position}.º</td>
              <th scope="row"><i aria-hidden="true" style={{ background: siteColor(result.sites.indexOf(site)) }} />{site.location.label}
                <small>{formatNumber(site.resource.mean_flow_m3s, 1)} m³/s · salto {formatNumber(site.head.gross_head_m, 0)} m<span className="trendInline">{formatNumber(site.finance.annual_energy_mwh / 1000, 0)} GWh/año</span></small></th>
              <td className="figure">{formatNumber(site.resource.capacity_mw, 1)} MW</td>
              <td className="trendCell">{formatNumber(site.finance.annual_energy_mwh / 1000, 0)} GWh · FP {formatPercent(site.finance.plant_factor_net, 0)}</td>
              <td className={`figure ${site.finance.npv_usd >= 0 ? "positive" : "negative"}`}>{formatMillions(site.finance.npv_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="verdictNote">Caudal diario de GloFAS en la toma y salto de {ranked.every((site) => site.head.source === "NASADEM") ? "NASADEM" : "los modelos de elevación"};
        GEOGLOWS y Copernicus son la segunda opinión. No es un aforo ni una topografía.</p>
      {moved.length > 0 && <p className="layerNotice"><b>{moved.join(", ")}:</b> el cauce del modelo no pasa por la celda de la toma; se usó la celda vecina. Verifique que es su río.</p>}
      <div className={`verdictAssumptions ${staleAssumptions ? "isStale" : ""}`}>
        <p>
          <span>{staleAssumptions ? "Supuestos editados · vuelva a ejecutar para recalcular el VAN" : "VAN calculado con USER_ASSUMPTION"}</span>
          <b>Excedencia {formatNumber(used.design_exceedance_percent, 0)} % · ecológico {formatPercent(used.ecological_flow_fraction, 0)} · CAPEX {formatMillions(used.capex_usd_per_mw)}/MW · {formatNumber(used.energy_price_usd_mwh, 1)} USD/MWh · tasa {formatPercent(used.discount_rate)} · {used.horizon_years} años</b>
        </p>
        <button type="button" onClick={onEditAssumptions}>Editar supuestos</button>
      </div>
    </section>
  );
}

type FieldsProps = { assumptions: HydroAssumptions; onChange: (key: keyof HydroAssumptions, value: number) => void };

export function HydroAssumptionFields({ assumptions, onChange }: FieldsProps) {
  const field = (key: keyof HydroAssumptions, label: string, step = "1", min?: string, max?: string) => (
    <label>{label}<input type="number" step={step} min={min} max={max} value={assumptions[key]} onChange={(event) => onChange(key, +event.target.value)} /></label>
  );
  return <>
    <p className="assumptionGroup">Central de pasada · el caudal de diseño sale de la curva de duración</p>
    <div className="assumptionFields">
      {field("design_exceedance_percent", "Excedencia diseño %", "5", "5", "95")}
      {field("ecological_flow_fraction", "Caudal ecológico (fracción)", "0.01", "0", "0.5")}
      {field("min_turbine_flow_fraction", "Mínimo técnico (fracción)", "0.05", "0", "0.9")}
      {field("efficiency", "Eficiencia", "0.01", "0.31", "0.95")}
      {field("head_loss_fraction", "Pérdidas de carga", "0.01", "0", "0.49")}
      {field("availability", "Disponibilidad", "0.01", "0.31", "1")}
    </div>
    <p className="assumptionGroup">Finanzas</p>
    <div className="assumptionFields">
      {field("capex_usd_per_mw", "CAPEX USD/MW", "50000", "1")}
      {field("opex_fraction_of_capex", "OPEX (fracción CAPEX)", "0.005", "0", "0.2")}
      {field("energy_price_usd_mwh", "Precio USD/MWh")}
      {field("discount_rate", "Tasa descuento", "0.01")}
      {field("horizon_years", "Horizonte años", "1", "1", "50")}
    </div>
    <p className="assumptionGroup">Rangos de sensibilidad (±) · caudal y salto se mueven con la segunda fuente</p>
    <div className="assumptionFields">
      {field("price_sensitivity", "Precio ± (fracción)", "0.05", "0", "0.95")}
      {field("capex_sensitivity", "CAPEX ± (fracción)", "0.05", "0", "0.95")}
      {field("opex_sensitivity", "OPEX ± (fracción)", "0.05", "0", "0.95")}
      {field("discount_rate_sensitivity", "Tasa ± (puntos)", "0.005", "0", "0.45")}
    </div>
  </>;
}

const signedPercent = (value: number | null, digits = 0) => (value == null ? "N/D" : `${value > 0 ? "+" : ""}${formatNumber(value, digits)} %`);
const VERDICT_TEXT: Record<string, string> = { coinciden: "coinciden", intermedio: "diferencia intermedia", difieren: "difieren", no_comparable: "no ubican el mismo río" };

/** Curva de duración: caudal del río igualado o excedido cada porcentaje del tiempo, con el caudal de diseño y el estiaje. */
function DurationCurve({ site, color }: { site: HydroSiteResult; color: string }) {
  const resource = site.resource;
  const points = resource.flow_duration;
  const width = 520, height = 190, left = 44, right = 12, top = 12, bottom = 30;
  const top5 = points[0]?.flow_m3s ?? 1;
  const limit = Math.max(top5, resource.design_flow_m3s + resource.ecological_flow_m3s) * 1.05 || 1;
  const x = (percent: number) => left + (percent / 100) * (width - left - right);
  const y = (flow: number) => top + (1 - Math.min(flow, limit) / limit) * (height - top - bottom);
  const path = points.map((point, index) => `${index ? "L" : "M"}${x(point.exceedance_percent).toFixed(1)},${y(point.flow_m3s).toFixed(1)}`).join(" ");
  // La central toma agua mientras el río supere el ecológico; con el de diseño más el ecológico trabaja a plena carga.
  const full = resource.design_flow_m3s + resource.ecological_flow_m3s;
  const ticks = [0, limit / 2, limit];
  return (
    <figure className="durationCurve">
      <svg viewBox={`0 0 ${width} ${height}`} role="img"
           aria-label={`Curva de duración del caudal en ${site.location.label}: de ${formatNumber(top5, 1)} m³/s excedidos el 5 % del tiempo a ${formatNumber(resource.firm_flow_m3s, 1)} m³/s excedidos el 95 %. Plena carga con ${formatNumber(full, 1)} m³/s.`}>
        {ticks.map((tick) => <g key={tick}><line className="curveGrid" x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} /><text className="curveTick" x={left - 6} y={y(tick) + 3} textAnchor="end">{formatNumber(tick, tick < 10 ? 1 : 0)}</text></g>)}
        {[5, 25, 50, 75, 95].map((percent) => <text key={percent} className="curveTick" x={x(percent)} y={height - 12} textAnchor="middle">{percent} %</text>)}
        {full > 0 && full < limit && <>
          <line className="curveDesign" x1={left} x2={width - right} y1={y(full)} y2={y(full)} />
          <text className="curveLabel" x={width - right - 4} y={y(full) - 5} textAnchor="end">plena carga · {formatNumber(full, 1)} m³/s</text>
        </>}
        {resource.ecological_flow_m3s > 0 && <line className="curveEco" x1={left} x2={width - right} y1={y(resource.ecological_flow_m3s)} y2={y(resource.ecological_flow_m3s)} />}
        <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
        {points.map((point) => <circle key={point.exceedance_percent} cx={x(point.exceedance_percent)} cy={y(point.flow_m3s)} r="2.5" fill={color} />)}
      </svg>
      <figcaption>Curva de duración del río · m³/s igualados o excedidos (% del tiempo) · {resource.period}. Línea punteada: plena carga (diseño + ecológico); línea fina: caudal ecológico.</figcaption>
    </figure>
  );
}

export function HydroEvidence({ result }: { result: HydroResult }) {
  const first = result.sites[0];
  return (
    <div className="siteResults">
      {result.sites.map((site, index) => {
        const { resource: r, head, flow_check: check, finance } = site;
        const factors = r.annual_plant_factors.map((item) => item.value);
        const second = check
          ? check.verdict === "no_comparable"
            ? `${formatNumber(check.mean_m3s, 2)} m³/s · no ubica el mismo río`
            : `${formatNumber(check.mean_m3s, 1)} m³/s (${signedPercent(check.gap_percent)}) · ${VERDICT_TEXT[check.verdict]}`
          : "Sin respuesta en esta ejecución";
        return (
          <article className="siteResult" key={site.location.label}>
            <div className="siteResultHeader"><div><h3>{site.location.label}</h3><p>{site.relative_position_text}</p></div><span>{site.relative_position}.º de {result.sites.length}</span></div>
            <div className="tableScroll">
              <table className="compactTable">
                <thead><tr><th>Dato físico</th><th>Caso base</th><th>Segunda fuente</th></tr></thead>
                <tbody>
                  <tr><th>Caudal medio<small>{check ? check.period : r.period} · celda a {formatNumber(r.cell.distance_km, 1)} km de la toma{r.cell.moved ? " (vecina)" : ""}</small></th>
                    <td>{formatNumber(check ? check.primary_mean_m3s : r.mean_flow_m3s, 1)} m³/s<small>GloFAS</small></td><td>{second}<small>GEOGLOWS{check ? ` · río n.º ${check.river_id}` : ""}</small></td></tr>
                  <tr><th>Salto bruto<small>toma {formatNumber(head.intake_elevation_m, 0)} m · casa de máquinas {formatNumber(head.powerhouse_elevation_m, 0)} m · {formatNumber(head.conduction_km, 1)} km</small></th>
                    <td>{formatNumber(head.gross_head_m, 0)} m<small>{head.source.split(" (")[0]}</small></td>
                    <td>{head.second_gross_head_m == null ? "Sin contraste" : `${formatNumber(head.second_gross_head_m, 0)} m (${signedPercent(head.gap_percent, 1)})`}<small>{head.second_source ? head.second_source.split(" (")[0] : "un solo modelo de elevación"}</small></td></tr>
                  <tr><th>Factor de planta<small>antes de la disponibilidad</small></th><td>{formatPercent(r.plant_factor)}</td>
                    <td>{check?.plant_factor_at_second == null ? "N/D" : formatPercent(check.plant_factor_at_second)}<small>{check?.plant_factor_at_second == null ? "" : "con el caudal de GEOGLOWS"}</small></td></tr>
                  <tr><th>Central de pasada</th><td colSpan={2}><b>{formatNumber(r.capacity_mw, 1)} MW</b> · diseño {formatNumber(r.design_flow_m3s, 1)} m³/s · ecológico {formatNumber(r.ecological_flow_m3s, 1)} m³/s · estiaje (95 %) {formatNumber(r.firm_flow_m3s, 1)} m³/s<small>{r.design_basis}</small></td></tr>
                  <tr><th>Resultado del caso base</th><td colSpan={2}><b>{formatNumber(finance.annual_energy_mwh, 0)} MWh/año</b> · factor de planta neto {formatPercent(finance.plant_factor_net)} · CAPEX {formatMillions(finance.initial_capex_usd)} · VAN <span className={finance.npv_usd >= 0 ? "positive" : "negative"}>{formatMillions(finance.npv_usd)}</span></td></tr>
                  {factors.length > 1 && <tr><th>Factor de planta por año<small>{r.period}</small></th><td colSpan={2}>de {formatPercent(Math.min(...factors))} (año seco) a {formatPercent(Math.max(...factors))} (año húmedo)</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="hydroDetail">
              <DurationCurve site={site} color={siteColor(index)} />
              <div className="siteNotes">
                {[...site.opportunities, ...site.cautions].map((note, noteIndex) => <p key={noteIndex}>{note}</p>)}
              </div>
            </div>
            <div className="tableScroll">
              <table>
                <thead><tr><th>Variable</th><th>Media</th><th>Cobertura</th><th>Pendiente Sen</th><th>Evidencia BH</th></tr></thead>
                <tbody>{site.variables.map((variable) => (
                  <tr key={variable.variable}>
                    <th>{variable.label}<small>{variable.variable === "RIVER_DISCHARGE" ? "GloFAS" : `NASA POWER · ${variable.variable}`}</small></th>
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
        <h3>Método hidroeléctrico</h3>
        {result.method_validation?.map((note) => <p key={note} className="methodValidation"><span>real</span>{note}</p>)}
        {[first?.finance.formula,
          "Caudal: GloFAS v4 diario en la celda del cauce más cercana a la toma. Si la celda de la toma lleva menos del 20 % del máximo de sus vecinas, se usa la más cercana con al menos el 50 %, y se declara.",
          "Segunda opinión del caudal: el río de mayor caudal medio que GEOGLOWS devuelve en una malla de ±4.4 km alrededor de la toma. Coinciden bajo 25 %; difieren desde 50 %.",
          "Salto: elevación de la toma menos la de la casa de máquinas en NASADEM, contrastada con Copernicus GLO-30. Coinciden bajo 5 %; difieren desde 10 %.",
          ...(first?.finance.limitations ?? []), ...(result.sites.find((site) => site.flow_check)?.flow_check?.limitations.slice(0, 1) ?? [])]
          .filter(Boolean).map((note, index) => <p key={index}><span>{index + 1}</span>{note}</p>)}
      </div>
    </div>
  );
}
