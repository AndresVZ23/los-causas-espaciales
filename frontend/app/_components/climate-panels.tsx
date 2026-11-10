import { formatNumber, siteColor } from "./format";
import type { Agreement, ClimateResult, ExtremeIndex, VariableSummary } from "./types";

const READING_ROWS = [
  { code: "T2M", label: "Temperatura" },
  { code: "PRECTOTCORR", label: "Precipitación" },
  { code: "WS10M", label: "Viento a 10 m" },
  { code: "ALLSKY_SFC_SW_DWN", label: "Radiación solar" },
];
const STRONG = 0.01;

const shortDate = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-PE", { day: "numeric", month: "short" });
const signed = (value: number, digits: number) => `${value > 0 ? "+" : value < 0 ? "−" : ""}${formatNumber(Math.abs(value), digits)}`;

export function evidenceLabel(item: { significant_after_bh: boolean; adjusted_p_value: number | null }) {
  if (!item.significant_after_bh || item.adjusted_p_value == null) return "Insuficiente";
  return item.adjusted_p_value < STRONG ? "Fuerte" : "Moderada";
}

function anomalyText(variable: VariableSummary | undefined) {
  const period = variable?.current_period;
  if (!period) return { main: "—", rank: "Sin año en curso", through: null };
  const main = period.anomaly_percent != null ? `${signed(period.anomaly_percent, 1)} %` : `${signed(period.anomaly, 2)} ${variable!.display_unit}`;
  return { main, rank: `${period.rank}.º de ${period.years_compared}`, through: `hasta ${shortDate(period.through)}` };
}

export function ClimateReading({ result, headingId }: { result: ClimateResult; headingId: string }) {
  const sites = result.sites;
  const anyPeriod = sites.flatMap((site) => site.variables).find((item) => item.current_period)?.current_period;
  const extremeCodes = new Set(sites[0]?.extremes.map((item) => item.variable));
  const extremeFindings = result.trend_findings.filter((item) => extremeCodes.has(item.variable));
  const atypical = sites.flatMap((site) => site.extremes.flatMap((item) => (item.atypical_years ?? []).map((year) =>
    `${item.variable} ${site.location.label} ${year.year}: ${formatNumber(year.value, 1)} ${item.display_unit}`
    + (atypicalChecks(year).length ? ` (${atypicalChecks(year).map((check) => `${check.source} ${formatNumber(check.value, 1)}`).join(" · ")})` : ""))));
  const satelliteChecked = sites.some((site) => site.extremes.some((item) => (item.atypical_years ?? []).some((year) => atypicalChecks(year).length)));
  return (
    <section className="verdict" aria-labelledby={headingId}>
      <div className="verdictHead">
        <h2 id={headingId}>Lectura climática</h2>
        <span>{anyPeriod ? `${anyPeriod.year} frente a ${anyPeriod.baseline_years}` : "Año en curso"}</span>
      </div>
      <table className="verdictTable climateTable">
        <thead><tr><th scope="col">Variable</th>{sites.map((site, index) => <th scope="col" key={site.location.label}><i aria-hidden="true" style={{ background: siteColor(index) }} />{site.location.label}</th>)}</tr></thead>
        <tbody>
          {READING_ROWS.map((row) => (
            <tr key={row.code}>
              <th scope="row">{row.label}</th>
              {sites.map((site) => {
                const text = anomalyText(site.variables.find((item) => item.variable === row.code));
                return <td key={site.location.label} className="figure">{text.main}<small><span>{text.rank}</span>{text.through && <> · <span>{text.through}</span></>}</small></td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="verdictNote">
        Año en curso frente a la misma ventana del calendario en los años completos; el puesto ordena de mayor a menor. El año en curso no entra en la tendencia.
      </p>
      <div className="verdictAssumptions climateExtremes">
        <p>
          <span>Extremos de lluvia con tendencia significativa</span>
          <b>{extremeFindings.length
            ? extremeFindings.map((item) => `${item.label} · ${item.site} ${signed(item.slope_per_year, 2)} ${item.unit}/año (${item.adjusted_p_value < STRONG ? "fuerte" : "moderada"})`).join(" · ")
            : "Ningún índice ETCCDI conserva significancia tras Benjamini–Hochberg."}</b>
        </p>
      </div>
      {atypical.length > 0 && (
        <div className="verdictAssumptions climateExtremes">
          <p><span>Valores atípicos de NASA POWER</span><b>{atypical.join(" · ")}. {satelliteChecked ? "GPM IMERG y CHIRPS sirven de contraste independiente; falta el de estaciones." : "Sin contraste satelital ni de estaciones."} No cambian la prueba de Mann–Kendall, que usa rangos.</b></p>
        </div>
      )}
    </section>
  );
}

const AGREEMENT_TEXT: Record<Exclude<Agreement, "solo_contraste">, string> = {
  coincide: "Coincide",
  contradice: "Contradice",
  sin_respaldo: "Sin respaldo",
  sin_tendencia: "Sin tendencia",
};
// Contrastes independientes de la serie principal (NASA POWER · MERRA-2), en el orden en que se muestran.
export const CHECK_SOURCES = [{ key: "IMERG", label: "GPM IMERG", dash: "5 3" }, { key: "CHIRPS", label: "CHIRPS", dash: "1 3" }];
// Contraste de temperatura y radiación (ERA5): no es columna de la tabla de extremos, solo línea en el gráfico anual.
export const SERIES_SOURCES = [...CHECK_SOURCES, { key: "ERA5", label: "ERA5", dash: "8 3 2 3" }, { key: "GEOGLOWS", label: "GEOGLOWS", dash: "5 3" }];
export const shortSource = (source: string) => SERIES_SOURCES.find((item) => source.includes(item.key))?.key ?? source;
export const checksOf = (item: ExtremeIndex) => item.counterchecks?.length ? item.counterchecks : item.countercheck ? [item.countercheck] : [];

/** Valor de cada contraste en un año atípico; los resultados anteriores a CHIRPS solo traen el de IMERG. */
function atypicalChecks(year: NonNullable<ExtremeIndex["atypical_years"]>[number]) {
  const values = Object.entries(year.countercheck_values ?? {}).map(([source, value]) => ({ source: shortSource(source), value }));
  if (!values.length && year.countercheck_value != null) values.push({ source: "IMERG", value: year.countercheck_value });
  return values;
}

function CountercheckCell({ item, source }: { item: ExtremeIndex; source: string }) {
  const check = checksOf(item).find((candidate) => shortSource(candidate.source) === source);
  if (!check) return <td>N/D</td>;
  const slope = check.slope_per_year == null ? "N/D" : `${signed(check.slope_per_year, 3)} ${item.display_unit}/año`;
  return (
    <td className={`agreement ${check.agreement}`}>
      {check.agreement === "solo_contraste" ? `Solo ${source}` : AGREEMENT_TEXT[check.agreement]}
      <small>{slope} · p BH {check.adjusted_p_value == null ? "N/D" : formatNumber(check.adjusted_p_value, 3)}</small>
    </td>
  );
}

function ExtremeRow({ item }: { item: ExtremeIndex }) {
  const trend = item.trend;
  const years = item.annual_series.length > 1 ? item.annual_series[item.annual_series.length - 1].year - item.annual_series[0].year : 0;
  return (
    <tr>
      <th>
        {item.label}<small>{item.variable} · {item.description}</small>
        {item.atypical_years?.map((atypical) => {
          const checks = atypicalChecks(atypical);
          return (
            <small className="atypical" key={atypical.year}>
              Año atípico {atypical.year}: MERRA-2 {formatNumber(atypical.value, 1)} {item.display_unit} (z robusto {formatNumber(atypical.robust_z, 0)})
              {checks.length ? checks.map((check) => ` · ${check.source} ${formatNumber(check.value, 1)}`).join("") + ` ${item.display_unit}` : " · sin contraste satelital"}
            </small>
          );
        })}
      </th>
      <td>{formatNumber(item.mean, 1)} {item.display_unit}</td>
      <td>{trend.slope_per_year == null ? "N/D" : `${signed(trend.slope_per_year, 3)} ${item.display_unit}/año`}</td>
      <td>{trend.slope_per_year == null ? "N/D" : `${signed(trend.slope_per_year * years, 1)} ${item.display_unit}`}</td>
      <td>{item.adjusted_p_value == null ? "N/D" : formatNumber(item.adjusted_p_value, 3)}</td>
      <td>{evidenceLabel(item)}</td>
      {CHECK_SOURCES.map((source) => <CountercheckCell key={source.key} item={item} source={source.key} />)}
    </tr>
  );
}

/** Índices ETCCDI (NASA POWER · MERRA-2) con años atípicos y contraste GPM IMERG y CHIRPS; la usan Clima y Amenazas. */
export function ExtremesTable({ extremes }: { extremes: ExtremeIndex[] }) {
  return (
    <div className="tableScroll">
      <table>
        <thead><tr><th>Índice</th><th>Media anual</th><th>Pendiente Sen</th><th>Cambio en el período</th><th>p BH</th><th>Evidencia</th>{CHECK_SOURCES.map((source) => <th key={source.key}>Contraste {source.label}</th>)}</tr></thead>
        <tbody>{extremes.map((item) => <ExtremeRow key={item.variable} item={item} />)}</tbody>
      </table>
    </div>
  );
}

export function ClimateEvidence({ result }: { result: ClimateResult }) {
  return (
    <>
      <div className="siteResults">
        {result.sites.map((site) => (
          <article className="siteResult" key={site.location.label}>
            <div className="siteResultHeader">
              <div>
                <h3>{site.location.label}</h3>
                <p>Extremos de precipitación ETCCDI · {site.extremes[0]?.valid_years ?? 0} años completos{site.extremes[0]?.discarded_years ? ` · ${site.extremes[0].discarded_years} año(s) incompleto(s) fuera` : ""}</p>
                {site.territory && (
                  <p className="territoryScale">{site.territory.mode === "REGIONAL"
                    ? `Promedio por área de ${site.territory.cells} celdas NASA POWER (${site.territory.grid_degrees ? `${site.territory.grid_degrees[0]}° × ${site.territory.grid_degrees[1]}°` : "grilla nativa"}) · cobertura ${formatNumber(site.territory.coverage_percent, 1)} % · ${formatNumber(site.territory.area_km2, 0)} km²`
                    : `Menor que una celda NASA POWER: se analiza como punto representativo · ${formatNumber(site.territory.area_km2, 0)} km²`} · {site.territory.source}</p>
                )}
              </div>
              <span>P95 de días húmedos: {site.wet_day_p95_mm == null ? "N/D" : `${formatNumber(site.wet_day_p95_mm, 1)} mm`}</span>
            </div>
            <ExtremesTable extremes={site.extremes} />
          </article>
        ))}
      </div>
      <div className="findingsPanel methodPanel">
        <h3>Método</h3>
        {result.method_notes.map((note, index) => <p key={note}><span>{index + 1}</span>{note}</p>)}
        <p><span>{result.method_notes.length + 1}</span>Tendencia: Mann–Kendall con corrección de Hamed–Rao y pendiente de Sen; Benjamini–Hochberg por índice entre sitios. Evidencia fuerte si p BH &lt; 0.01; moderada si p BH &lt; 0.05.</p>
      </div>
    </>
  );
}
