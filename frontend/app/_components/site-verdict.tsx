import { formatMillions, formatNumber, formatPercent, siteColor } from "./format";
import type { Assumptions, ScreeningResult, VariableSummary } from "./types";

const IRRADIANCE = "ALLSKY_SFC_SW_DWN";
const directionLabels: Record<string, string> = { increasing: "Creciente", decreasing: "Decreciente", no_trend: "Sin tendencia", insufficient_evidence: "Evidencia insuficiente" };

function irradiance(variables: VariableSummary[]) { return variables.find((item) => item.variable === IRRADIANCE)!; }

type Props = { result: ScreeningResult; staleAssumptions: boolean; onEditAssumptions: () => void; headingId: string };

export default function SiteVerdict({ result, staleAssumptions, onEditAssumptions, headingId }: Props) {
  const ranked = [...result.sites].sort((a, b) => a.relative_solar_position - b.relative_solar_position);
  const means = ranked.map((site) => irradiance(site.variables).mean);
  const unit = irradiance(ranked[0].variables).display_unit;
  const delta = means[0] - means[means.length - 1];
  const deltaShare = means[means.length - 1] > 0 ? delta / means[means.length - 1] : null;
  const used: Assumptions = result.assumptions;
  // Año en curso: no entra en la tendencia; se compara con la misma ventana del calendario en los años completos.
  const periods = ranked.map((site) => ({ label: site.location.label, period: irradiance(site.variables).current_period })).filter((item) => item.period);
  const first = periods[0]?.period;
  const currentLine = first
    ? `${first.year} hasta el ${new Date(`${first.through}T12:00:00`).toLocaleDateString("es-PE", { day: "numeric", month: "short" })}: ${periods.map(({ label, period }) => `${label} ${period!.anomaly_percent != null ? `${period!.anomaly_percent > 0 ? "+" : ""}${formatNumber(period!.anomaly_percent, 1)} %` : formatNumber(period!.anomaly, 2)}`).join(", ")} frente a ${first.baseline_years} en la misma ventana. El año en curso no entra en la tendencia.`
    : null;

  return (
    <section className="verdict" aria-labelledby={headingId}>
      <div className="verdictHead">
        <h2 id={headingId}>Lectura comparativa</h2>
        <span>Irradiancia media · {unit}</span>
      </div>
      <table className="verdictTable">
        <thead><tr><th scope="col">Orden</th><th scope="col">Sitio</th><th scope="col">Irradiancia</th><th scope="col" className="trendCell">Tendencia</th><th scope="col">VAN cond.</th></tr></thead>
        <tbody>
          {ranked.map((site) => {
            const solar = irradiance(site.variables);
            const trendLabel = directionLabels[solar.trend.direction] ?? solar.trend.direction;
            return (
              <tr key={site.location.label} className={site.relative_solar_position === 1 ? "lead" : undefined}>
                <td className="rank">{site.relative_solar_position}.º</td>
                <th scope="row"><i aria-hidden="true" style={{ background: siteColor(result.sites.indexOf(site)) }} />{site.location.label}<small>{formatNumber(solar.completeness_percent, 1)} % cobertura<span className="trendInline">{trendLabel}</span></small></th>
                <td className="figure">{formatNumber(solar.mean, 3)}</td>
                <td className="trendCell">{trendLabel}</td>
                <td className={`figure ${site.finance.npv_usd >= 0 ? "positive" : "negative"}`}>{formatMillions(site.finance.npv_usd)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {ranked.length > 1 && (
        <p className="verdictNote">
          Diferencia entre extremos: <b>{formatNumber(delta, 3)} {unit}{deltaShare !== null ? ` (${formatPercent(deltaShare)})` : ""}</b>. El orden solo considera irradiancia histórica; no es una recomendación de inversión.
        </p>
      )}
      {currentLine && <p className="verdictNote">{currentLine}</p>}
      <div className={`verdictAssumptions ${staleAssumptions ? "isStale" : ""}`}>
        <p>
          <span>{staleAssumptions ? "Supuestos editados · vuelva a ejecutar para recalcular el VAN" : "VAN calculado con USER_ASSUMPTION"}</span>
          <b>{formatNumber(used.capacity_mw, 1)} MW · PR {formatNumber(used.performance_ratio, 2)} · CAPEX {formatMillions(used.initial_capex_usd)} · {formatNumber(used.energy_price_usd_mwh, 1)} USD/MWh · tasa {formatPercent(used.discount_rate)} · {used.horizon_years} años</b>
        </p>
        <button type="button" onClick={onEditAssumptions}>Editar supuestos</button>
      </div>
    </section>
  );
}
