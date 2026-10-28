"use client";

import { evidenceLabel, ExtremesTable } from "./climate-panels";
import { formatNumber } from "./format";
import type { BaselineComponent, BaselineLayer, BaselineResult, SubjectBaseline } from "./types";

export const BASELINE_HINT = "Dibuje o cargue polígonos o corredores; se suman a los sitios y territorios como áreas de estudio (hasta 4 en total).";
const COMPONENT_LABEL: Record<BaselineComponent, string> = { fisico: "Medio físico", biologico: "Medio biológico", sociocultural: "Medio sociocultural", amenazas: "Amenazas y riesgo" };
export type BaselineModule = "environment" | "social" | "hazards";
const MODULE_SOURCES: Record<BaselineModule, string> = {
  environment: "MODIS anual (vegetación y cobertura), relieve NASADEM y capas de ANA, MINAM y SERNANP, ordenados como la línea base de un EIA.",
  social: "Cultura (SIGDA): patrimonio registrado y declarado, CIRA, diagnósticos arqueológicos, Qhapaq Ñan, paisajes culturales y consulta previa.",
  hazards: "Lluvia y extremos ETCCDI desde 2001 cruzados con GPM IMERG y CHIRPS, relieve NASADEM, riesgo por distrito de CENEPRED, deslizamientos de NASA cruzados con CENEPRED y puntos críticos de la ANA.",
};
const signed = (value: number, digits: number) => `${value > 0 ? "+" : value < 0 ? "−" : ""}${formatNumber(Math.abs(value), digits)}`;
const withRecords = (item: SubjectBaseline) => item.layers.filter((layer) => layer.status === "READY" && (layer.intersection_count ?? 0) > 0);
const unanswered = (item: SubjectBaseline) => item.layers.filter((layer) => layer.status !== "READY").length;

export function BaselineOptions({ bufferKm, onBuffer, geometries, module }: { bufferKm: number; onBuffer: (km: number) => void; geometries: number; module: BaselineModule }) {
  return (
    <section className="roadControls" aria-labelledby="linea-base-title">
      <h3 id="linea-base-title">Áreas de estudio</h3>
      <p className="territoryHint">{MODULE_SOURCES[module]}</p>
      <div className="assumptionFields">
        <label>Radio de sitios y corredores (km)
          <input type="number" min={0.25} max={10} step={0.25} value={bufferKm} onChange={(event) => onBuffer(+event.target.value)} />
        </label>
        <p className="baselineCount"><span>Mis geometrías válidas</span><b>{geometries}</b></p>
      </div>
    </section>
  );
}

const HEADINGS: Record<BaselineResult["sector"], string> = { environment: "Lectura de la línea base", heritage: "Lectura patrimonial", hazards: "Lectura de amenazas" };
const NOTES: Record<BaselineResult["sector"], string> = {
  environment: "Indicadores satelitales indirectos para preparar la línea base; no sustituyen el trabajo de campo ni el EIA.",
  heritage: "Registros oficiales del Ministerio de Cultura. Cero registros no prueba ausencia de patrimonio; nada de esto es opinión legal.",
  hazards: "Lluvia en el punto representativo (NASA POWER, contrastes IMERG y CHIRPS), riesgo por distrito (CENEPRED) y deslizamientos (NASA frente a CENEPRED). No es un mapa de amenaza a escala de proyecto.",
};

export function BaselineReading({ result, headingId }: { result: BaselineResult; headingId: string }) {
  const environment = result.sector === "environment";
  const hazards = result.sector === "hazards";
  return (
    <section className="verdict" aria-labelledby={headingId}>
      <div className="verdictHead"><h2 id={headingId}>{HEADINGS[result.sector]}</h2><span>{result.baselines.length} área(s)</span></div>
      <table className="verdictTable climateTable baselineReading">
        <thead><tr><th scope="col">Área</th><th scope="col">Capas con registros</th>{environment && <th scope="col">Sin vegetación</th>}{hazards && <th scope="col">Lluvia máx. 1 día</th>}</tr></thead>
        <tbody>
          {result.baselines.map((item) => {
            const bare = item.vegetation.find((variable) => variable.variable === "VCF_BARE");
            const slope = bare?.trend.slope_per_year;
            const rx1 = item.extremes?.find((index) => index.variable === "RX1DAY");
            return (
              <tr key={item.subject}>
                <th scope="row">{item.subject}<small>{formatNumber(item.area_km2, item.area_km2 < 10 ? 2 : 0)} km² · {item.origin}</small></th>
                {/* Una capa que no respondió no cuenta como «sin registros»: se informa aparte. */}
                <td className="figure">{withRecords(item).length} de {item.layers.length - unanswered(item)}
                  {unanswered(item) > 0 && <small className="negative">{unanswered(item)} sin respuesta</small>}</td>
                {environment && <td className="figure">{bare ? `${formatNumber(bare.mean, 1)} %` : "N/D"}<small>{bare && slope != null ? `${signed(slope * 10, 1)} pts/década · ${evidenceLabel(bare).toLowerCase()}` : "sin serie"}</small></td>}
                {hazards && <td className="figure">{rx1 ? `${formatNumber(rx1.mean, 1)} mm` : "N/D"}<small>{rx1 ? `tendencia ${evidenceLabel(rx1).toLowerCase()}${rx1.atypical_years?.length ? ` · ${rx1.atypical_years.length} año(s) atípico(s)` : ""}` : "sin serie"}</small></td>}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="verdictNote">{NOTES[result.sector]}</p>
    </section>
  );
}

function LayerRows({ layers }: { layers: BaselineLayer[] }) {
  return (
    <tbody>{layers.map((layer) => (
      <tr key={layer.source_id}>
        <th>{layer.dataset}<small>{layer.organization}</small></th>
        <td className="figure">{layer.status !== "READY" || layer.intersection_count == null ? "No disponible" : `${layer.intersection_count}${layer.truncated ? "+" : ""}`}</td>
        <td>
          {layer.status !== "READY"
            ? <span className="layerMuted">{layer.limitations[0]}</span>
            : layer.highlights.length === 0
              ? <span className="layerMuted">Sin registros devueltos; no prueba ausencia.</span>
              : <ul className="layerHighlights">{layer.highlights.map((item) => (
                  <li key={`${item.label}-${item.detail}`}>
                    {item.link ? <a href={item.link} target="_blank" rel="noreferrer">{item.label}</a> : <b>{item.label}</b>}
                    {item.count > 1 && <em>×{item.count}</em>}
                    {item.detail && <small>{item.detail}</small>}
                  </li>
                ))}</ul>}
        </td>
      </tr>
    ))}</tbody>
  );
}

function AreaArticle({ item, components }: { item: SubjectBaseline; components: BaselineComponent[] }) {
  return (
    <article className="siteResult">
      <div className="siteResultHeader">
        <div><h3>{item.subject}</h3><p>{item.origin}{item.modis_window_km ? ` · ventana MODIS ±${item.modis_window_km} km · ${item.modis_pixels.MOD44B ?? 0} píxeles de 250 m` : ""}</p></div>
        <span>{formatNumber(item.area_km2, item.area_km2 < 10 ? 2 : 0)} km²</span>
      </div>
      {item.vegetation.length > 0 && (
        <div className="tableScroll">
          <table>
            <caption className="srOnly">Vegetación MODIS anual de {item.subject}</caption>
            <thead><tr><th>Indicador MODIS</th><th>Media</th><th>Pendiente Sen</th><th>Cambio en el período</th><th>p BH</th><th>Evidencia</th></tr></thead>
            <tbody>{item.vegetation.map((variable) => {
              const years = variable.annual_series.length > 1 ? variable.annual_series[variable.annual_series.length - 1].year - variable.annual_series[0].year : 0;
              const slope = variable.trend.slope_per_year;
              return (
                <tr key={variable.variable}>
                  <th>{variable.label}<small>{variable.source.dataset} · {variable.annual_series[0]?.year}–{variable.annual_series[variable.annual_series.length - 1]?.year}</small></th>
                  <td className="figure">{formatNumber(variable.mean, variable.unit === "percent_cover" ? 1 : 3)} {variable.display_unit}</td>
                  <td className="figure">{slope == null ? "N/D" : `${signed(slope, 3)}/año`}</td>
                  <td className="figure">{slope == null ? "N/D" : `${signed(slope * years, 1)}${variable.unit === "percent_cover" ? " pts" : ` ${variable.display_unit}`}`}</td>
                  <td className="figure">{variable.adjusted_p_value == null ? "N/D" : formatNumber(variable.adjusted_p_value, 3)}</td>
                  <td>{evidenceLabel(variable)}</td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      )}
      {item.land_cover && (
        <div className="tableScroll">
          <table className="compactTable">
            <caption className="srOnly">Cobertura del suelo MODIS de {item.subject}</caption>
            <thead><tr><th>Cobertura IGBP (MCD12Q1)</th><th>{item.land_cover.first_year}</th><th>{item.land_cover.last_year}</th></tr></thead>
            <tbody>{item.land_cover.classes.slice(0, 6).map((entry) => (
              <tr key={entry.code}><th>{entry.label}</th><td className="figure">{formatNumber(entry.first_percent, 1)} %</td><td className="figure">{formatNumber(entry.last_percent, 1)} %</td></tr>
            ))}</tbody>
          </table>
          <p className="verdictNote">Cambió de clase el {formatNumber(item.land_cover.changed_percent, 1)} % de {item.land_cover.pixels} píxeles de 500 m. {item.land_cover.limitations[0]}</p>
        </div>
      )}
      {item.land_cover_check && (
        <div className="tableScroll">
          <table className="compactTable">
            <caption className="srOnly">Contraste de cobertura MODIS y ESA WorldCover de {item.subject}</caption>
            <thead><tr><th>Contraste de cobertura {item.land_cover_check.year}</th><th>MOD44B</th><th>ESA WorldCover</th></tr></thead>
            <tbody>{item.land_cover_check.groups.map((group) => (
              <tr key={group.variable}>
                <th>{group.label}</th>
                <td className="figure">{group.modis_percent == null ? "N/D" : `${formatNumber(group.modis_percent, 1)} %`}</td>
                <td className="figure">{formatNumber(group.worldcover_percent, 1)} %</td>
              </tr>
            ))}</tbody>
          </table>
          <p className="verdictNote">
            WorldCover (Sentinel-1/2, 10 m) · {formatNumber(item.land_cover_check.pixels, 0)} píxeles en la ventana MODIS, sin el agua · {item.land_cover_check.provenance}. {item.land_cover_check.limitations[0]}
          </p>
        </div>
      )}
      {item.extremes && item.extremes.length > 0 && <>
        <ExtremesTable extremes={item.extremes} />
        {item.wet_day_p95_mm != null && <p className="verdictNote">P95 de los días húmedos: {formatNumber(item.wet_day_p95_mm, 1)} mm · serie NASA POWER en la celda del punto representativo.</p>}
      </>}
      {[...item.vegetation_notes, ...item.errors].map((note) => <p className="verdictNote" key={note}>{note}</p>)}
      {components.map((component) => {
        const layers = item.layers.filter((layer) => layer.component === component);
        return layers.length > 0 && (
          <div className="tableScroll" key={component}>
            <table className="baselineLayers">
              <caption className="srOnly">{COMPONENT_LABEL[component]} de {item.subject}</caption>
              <thead><tr><th>{COMPONENT_LABEL[component]}</th><th>Registros</th><th>Lo que registra la fuente</th></tr></thead>
              <LayerRows layers={layers} />
            </table>
          </div>
        );
      })}
    </article>
  );
}

export function BaselineEvidence({ result }: { result: BaselineResult }) {
  return (
    <>
      <div className="siteResults">
        {result.baselines.map((item) => <AreaArticle key={item.subject} item={item} components={result.components} />)}
      </div>
      <div className="findingsPanel methodPanel">
        <h3>Método</h3>
        {result.method_notes.map((note, index) => <p key={note}><span>{index + 1}</span>{note}</p>)}
      </div>
    </>
  );
}
