"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { formatMoney, formatNumber, siteColor } from "./format";
import { Icon } from "./icons";
import NasaQuestions from "./nasa-questions";
import PipelinePanel, { STAGE_NAMES } from "./pipeline-panel";
import SiteVerdict from "./site-verdict";
import type { Assumptions, Module, Point, QuestionKey, ScreeningResult, SiteResult, Stage } from "./types";

const GeoMap = dynamic(() => import("./geo-map"), { ssr: false, loading: () => <div className="mapLoading">Preparando mapa NASA…</div> });
const TemporalChart = dynamic(() => import("./temporal-chart"), { ssr: false, loading: () => <div className="chartLoading">Preparando serie temporal…</div> });
const ComparisonChart = dynamic(() => import("./comparison-chart"), { ssr: false, loading: () => <div className="chartLoading">Preparando comparación…</div> });

const modules: Module[] = [
  { id: "climate", short: "Clima", name: "Inteligencia climática", icon: "climate", status: "Disponible vía Solar", ready: false, description: "Variables POWER y tendencias disponibles dentro del piloto solar." },
  { id: "solar", short: "Energía", name: "Energía renovable", icon: "solar", status: "Piloto funcional", ready: true, description: "Screening solar comparativo con observaciones NASA POWER." },
  { id: "hazards", short: "Amenazas", name: "Amenazas naturales", icon: "hazard", status: "Capas pendientes", ready: false, description: "Requiere integrar y validar capas oficiales de amenazas." },
  { id: "environment", short: "Ambiente", name: "Inteligencia ambiental", icon: "environment", status: "AppEEARS pendiente", ready: false, description: "Vegetación, agua y cobertura todavía no están conectadas." },
  { id: "social", short: "Territorio", name: "Dimensión social y arqueológica", icon: "social", status: "Fuentes pendientes", ready: false, description: "No se infiere patrimonio o contexto social desde satélites." },
  { id: "infrastructure", short: "Infraestructura", name: "Infraestructura", icon: "infrastructure", status: "Red pendiente", ready: false, description: "Corredores, red y capas territoriales aún deben validarse." },
  { id: "investment", short: "Inversión", name: "Inteligencia de inversión", icon: "investment", status: "Integrado en Solar", ready: false, description: "El VAN se calcula únicamente dentro del piloto solar y con supuestos explícitos." },
];

const initialSites: Point[] = [
  { label: "Moquegua", latitude: -17.193, longitude: -70.934 },
  { label: "Arequipa", latitude: -16.409, longitude: -71.537 },
];
const initialAssumptions: Assumptions = { capacity_mw: 20, performance_ratio: 0.8, initial_capex_usd: 18000000, annual_opex_usd: 360000, energy_price_usd_mwh: 55, mitigation_capex_usd: 0, discount_rate: 0.1, horizon_years: 20 };
const provenanceLabels: Record<string, string> = { REAL_DATA: "Observación original", CACHED_DATA: "Copia validada en caché", MODEL_ESTIMATE: "Cálculo derivado", USER_ASSUMPTION: "Supuesto editable", DATA_UNAVAILABLE: "Fuente pendiente" };
const variables = [
  { id: "ALLSKY_SFC_SW_DWN", short: "Radiación solar" },
  { id: "T2M", short: "Temperatura" },
  { id: "WS10M", short: "Viento" },
  { id: "PRECTOTCORR", short: "Precipitación" },
];

function getVariable(site: SiteResult, variable: string) { return site.variables.find((item) => item.variable === variable)!; }

export default function Workspace() {
  const [activeModule, setActiveModule] = useState("solar");
  const [activeVariable, setActiveVariable] = useState("ALLSKY_SFC_SW_DWN");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [sites, setSites] = useState<Point[]>(initialSites);
  const [startDate, setStartDate] = useState("2001-01-01");
  // "Hasta" es siempre hoy (fecha local): se fija al montar para no desalinear el HTML prerenderizado con el navegador.
  const [endDate, setEndDate] = useState("");
  useEffect(() => { setEndDate(new Date().toLocaleDateString("en-CA")); }, []);
  const [assumptions, setAssumptions] = useState<Assumptions>(initialAssumptions);
  const [result, setResult] = useState<ScreeningResult | null>(null);
  const [terrainVisible, setTerrainVisible] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);
  const [selectedStep, setSelectedStep] = useState(1);
  const [exportedAt, setExportedAt] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");
  const assumptionPanelRef = useRef<HTMLDetailsElement>(null);
  const mobileVerdictRef = useRef<HTMLDivElement>(null);

  const selectedModule = modules.find((module) => module.id === activeModule)!;
  // El relieve llega dentro del mismo resultado: una sola ejecución, una sola procedencia.
  const terrain = result?.terrain ?? null;
  const terrainError = result && !terrain ? result.pipeline.find((stage) => stage.key === "territorial")?.evidence?.find((item) => item.label === "NASADEM")?.value ?? "NASADEM no respondió." : "";
  const visiblePipeline: Stage[] = useMemo(() => {
    if (!result) return STAGE_NAMES.map((name, index) => ({ step: index + 1, key: String(index), name, status: index < 2 ? "LISTO" : "PENDIENTE", summary: "", provenance: [] }));
    if (!exportedAt) return result.pipeline;
    return result.pipeline.map((stage) => stage.key === "export"
      ? { ...stage, status: "COMPLETADO", summary: `Descargado: ${exportedAt}.` }
      : stage);
  }, [result, exportedAt]);
  const comparisonData = useMemo(() => result?.sites.map((site) => ({ name: site.location.label, irradiancia: +getVariable(site, "ALLSKY_SFC_SW_DWN").mean.toFixed(3) })) ?? [], [result]);
  const selectedVariable = result ? getVariable(result.sites[0], activeVariable) : null;
  const selectedUnit = selectedVariable?.display_unit ?? "Media anual";
  // Cada producto NASA se publica con su propia latencia: se muestra la fecha más antigua entre sitios, por grupo.
  const dataThrough = useMemo(() => {
    if (!result) return null;
    const latest = (codes: string[]) => result.sites.flatMap((site) => site.variables.filter((v) => codes.includes(v.variable) && v.last_valid_date).map((v) => v.last_valid_date as string)).sort()[0];
    const fmt = (iso?: string) => iso ? new Date(`${iso}T12:00:00`).toLocaleDateString("es-PE", { day: "numeric", month: "short", year: "numeric" }) : null;
    const meteo = fmt(latest(["T2M", "PRECTOTCORR", "WS10M"]));
    const solar = fmt(latest(["ALLSKY_SFC_SW_DWN"]));
    return [meteo && `Datos NASA hasta ${meteo}`, solar && solar !== meteo && `radiación hasta ${solar}`].filter(Boolean).join(" · ");
  }, [result]);
  const staleAssumptions = result !== null && JSON.stringify(result.assumptions) !== JSON.stringify(assumptions);
  const selectedSources = useMemo(() => result?.sites.map((site) => ({ site: site.location.label, ...getVariable(site, activeVariable).source })) ?? [], [result, activeVariable]);
  const terrainOverlay = useMemo(() => {
    const granule = terrain?.sites[0]?.granules.find((item) => item.short_name === "NASADEM_HGT" && item.preview_url);
    return granule?.preview_url
      ? { url: `/api/terrain-preview?url=${encodeURIComponent(granule.preview_url)}`, bounds: granule.bounding_box }
      : null;
  }, [terrain]);
  const sourceSummary = selectedSources.length > 0
    ? `${selectedSources.map((source) => `${source.site} ${source.provenance}`).join(" · ")} · ${selectedSources[0].dataset} ${selectedSources[0].version} · descarga ${selectedSources[0].downloaded_at.slice(0, 10)} · ${selectedSources[0].spatial_resolution}`
    : "SIN DATOS · la cuadrícula no representa observaciones";
  const temporalSeries = useMemo(() => {
    if (!result) return [];
    const years = new Set<number>();
    result.sites.forEach((site) => getVariable(site, activeVariable).annual_series.forEach((item) => years.add(item.year)));
    return [...years].sort().map((year) => {
      const point: { year: number } & Record<string, number> = { year };
      result.sites.forEach((site, index) => {
        const value = getVariable(site, activeVariable).annual_series.find((item) => item.year === year)?.value;
        if (value !== undefined) point[`site${index}`] = value;
      });
      return point;
    });
  }, [result, activeVariable]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 900px)");
    const sync = () => setIsMobile(media.matches);
    sync(); media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!mobileNavOpen) return;
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setMobileNavOpen(false); window.setTimeout(() => moreButtonRef.current?.focus(), 0); }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobileNavOpen]);

  function updateSite(index: number, key: keyof Point, value: string) {
    setSites((current) => current.map((site, position) => position === index ? { ...site, [key]: key === "label" ? value : +value } : site));
  }
  function updateAssumption(key: keyof Assumptions, value: string) { setAssumptions((current) => ({ ...current, [key]: +value })); }
  function selectModule(id: string) { if (id !== activeModule) { setResult(null); setError(""); setExportedAt(null); setSelectedStep(1); } setActiveModule(id); setMobileNavOpen(false); if (id === "investment") setAssumptionsOpen(true); }
  function goToStage(step: number) {
    setSelectedStep(step);
    window.setTimeout(() => document.getElementById("stage-inspector")?.scrollIntoView({ block: "nearest", behavior: "smooth" }), 0);
  }
  function goToQuestion(key: QuestionKey) {
    const target = document.getElementById(`pregunta-${key}`);
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
    target?.focus({ preventScroll: true });
  }
  function openAssumptions() {
    setAssumptionsOpen(true);
    window.setTimeout(() => {
      assumptionPanelRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      assumptionPanelRef.current?.querySelector("input")?.focus({ preventScroll: true });
    }, 0);
  }

  async function runScreening() {
    setLoading(true); setError(""); setExportedAt(null); setPdfError("");
    try {
      const response = await fetch("/api/solar-screening", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sites, start_date: startDate, end_date: endDate, assumptions }) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No fue posible ejecutar el screening. Revise la configuración e intente nuevamente.");
      const outcome = data as ScreeningResult;
      setResult(outcome);
      // El inspector abre en la primera etapa con salvedades; si no hay, en Análisis, donde nacen las respuestas NASA.
      setSelectedStep(outcome.pipeline.find((stage) => !["COMPLETADO", "LISTO"].includes(stage.status))?.step ?? 4);
      if (isMobile) window.setTimeout(() => mobileVerdictRef.current?.scrollIntoView({ block: "start" }), 0);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Ocurrió un error inesperado. Revise la API e intente nuevamente.");
    } finally { setLoading(false); }
  }

  function exportReport() {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `screening-solar-${result.analysis_id}.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    markExported("reporte JSON");
  }

  function markExported(format: string) {
    const time = new Intl.DateTimeFormat("es-PE", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date());
    setExportedAt((current) => `${current ? `${current}; ` : ""}${format} a las ${time}`);
  }

  async function exportPdf() {
    if (!result) return;
    setPdfLoading(true); setPdfError("");
    try {
      const response = await fetch("/api/report-pdf", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(result) });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(typeof data.detail === "string" ? data.detail : "No fue posible generar el PDF ejecutivo.");
      }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `reporte-ejecutivo-${result.sector}-${result.analysis_id}.pdf`; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      markExported("PDF ejecutivo");
    } catch (cause) {
      setPdfError(cause instanceof Error ? cause.message : "No fue posible generar el PDF ejecutivo.");
    } finally { setPdfLoading(false); }
  }

  return (
    <main className="appShell">
      <header className="consoleHeader">
        <div className="brandPlate">
          <h1 className="wordmark"><a href="#workspace" aria-label="Los Causas Espaciales, ir al espacio de trabajo">Los Causas Espaciales</a></h1>
          <span className="tagline">Inteligencia de la Tierra para decisiones reales</span>
        </div>
        <section className="utilityPlate" aria-label="Contexto de análisis">
          <div className="filterStrip">
            <label><span>Región</span><b>Sur del Perú</b></label>
            <label><span>Fuente analítica</span><b>NASA POWER · Daily</b></label>
            <label><span>Desde</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
            <label><span>Hasta</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
          </div>
          <div className="systemLine"><b><i />NASA POWER operativo</b><small>{dataThrough ?? "Datos hasta hoy · se actualizan en cada consulta"}</small><small>{result ? `ID ${result.analysis_id}` : "Sin ejecución"}</small></div>
        </section>
        <div className="provenanceStrip" role="list" aria-label="Clave de procedencia">
          <span className="provenanceTitle" aria-hidden="true">Procedencia</span>
          {Object.entries(provenanceLabels).map(([code, label]) => <span role="listitem" key={code} className={`prov-${code.toLowerCase()}`}><i /><b>{code}</b><small>{label}</small></span>)}
        </div>
      </header>

      <section id="workspace" className="consoleGrid" aria-label="Mesa de inteligencia terrestre">
        {result && isMobile && (
          <div className="mobileVerdict" ref={mobileVerdictRef}>
            <SiteVerdict result={result} staleAssumptions={staleAssumptions} onEditAssumptions={openAssumptions} headingId="lectura-movil" />
          </div>
        )}
        <aside className={`moduleRail ${mobileNavOpen ? "isOpen" : ""}`} aria-label="Módulos de inteligencia" aria-hidden={isMobile && !mobileNavOpen} inert={isMobile && !mobileNavOpen ? true : undefined}>
          <div className="railTitle"><span>NAVEGACIÓN</span><button ref={closeButtonRef} onClick={() => { setMobileNavOpen(false); window.setTimeout(() => moreButtonRef.current?.focus(), 0); }}>Cerrar</button></div>
          <nav className="moduleNav">
            {modules.map((module) => (
              <button key={module.id} className={activeModule === module.id ? "active" : ""} onClick={() => selectModule(module.id)} aria-pressed={activeModule === module.id} title={`${module.name}: ${module.status}`}>
                <Icon name={module.icon} /><span>{module.short}</span><i className={module.ready ? "ready" : "pending"} />
              </button>
            ))}
          </nav>
          <div className="mapKey">
            <span>LEYENDA DE MAPA</span>
            <p><i className="keyLine" />Eje entre ubicaciones</p><p><i className="keyPrimary" />Sitio principal</p><p><i className="keySecondary" />Comparador</p><p><i className="keyImagery" />NASA Blue Marble</p>
            <div className="scaleBar"><i /><span>0</span><span>100 km</span></div>
          </div>        </aside>

        <section className="mapStage" aria-label="Mapa de evaluación">
          <div className="panelCaption"><span>MAPA — OBSERVACIÓN TERRESTRE</span><b>WGS84 · EPSG:4326</b></div>
          <div className={`mapViewport ${loading ? "isAcquiring" : ""}`}>
            <GeoMap sites={sites} terrainOverlay={terrainOverlay} showTerrain={terrainVisible} onPick={(latitude, longitude) => setSites((current) => [{ ...current[0], latitude, longitude }, ...current.slice(1)])} />
            {loading && <div className="acquisitionLine" aria-hidden="true" />}
            <div className="mapCoordinates"><b>{sites[0].latitude.toFixed(4)}°</b><b>{sites[0].longitude.toFixed(4)}°</b><span>WGS84</span></div>
            <div className="mapSource">NASA GIBS · BLUE MARBLE · MAPA BASE ESTÁTICO</div>
          </div>
        </section>

        <aside className="controlPane" aria-label="Configuración y lectura">
          <div className="panelCaption"><span>CONFIGURACIÓN — {selectedModule.short.toUpperCase()}</span><b>{selectedModule.status}</b></div>
          <div className="controlContent">
            <details className="mobileContext">
              <summary>Contexto de análisis <span>{result ? "FUENTE VERIFICADA" : "PREPARADO"}</span></summary>
              <div className="mobileContextGrid">
                <p><span>Región</span><b>Sur del Perú</b></p><p><span>Fuente</span><b>NASA POWER · Daily</b></p>
                <label><span>Desde</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
                <label><span>Hasta</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
                <p className="mobileProvenance"><span>Procedencia efectiva</span><b>{sourceSummary}</b></p>
              </div>
            </details>
            <div className="siteEditor">
              {sites.map((site, index) => (
                <div className="siteRow" key={index}>
                  <span>{index + 1}</span>
                  <label>Ubicación<input value={site.label} onChange={(event) => updateSite(index, "label", event.target.value)} /></label>
                  <label>Latitud<input type="number" step="0.001" value={site.latitude} onChange={(event) => updateSite(index, "latitude", event.target.value)} /></label>
                  <label>Longitud<input type="number" step="0.001" value={site.longitude} onChange={(event) => updateSite(index, "longitude", event.target.value)} /></label>
                </div>
              ))}
            </div>
            <div className="actionRow"><button onClick={() => setSites(initialSites)}>Restablecer</button><button className="runAnalysis" onClick={runScreening} disabled={loading || !selectedModule.ready || !endDate}>{loading ? "Consultando NASA…" : selectedModule.ready ? "Ejecutar análisis" : "Módulo pendiente"}</button></div>
            {error && <p className="errorMessage" role="alert">{error}</p>}
            {result ? (
              !isMobile && <SiteVerdict result={result} staleAssumptions={staleAssumptions} onEditAssumptions={openAssumptions} headingId="lectura-escritorio" />
            ) : (
              <div className="emptyReading"><span><i /><i /></span><div><strong>LISTO PARA CONSULTAR</strong><p>{selectedModule.description}</p></div></div>
            )}
            <section className="terrainReadout" aria-label="Relieve NASADEM" aria-busy={loading}>
              <div className="terrainHeading">
                <div><strong>Relieve NASADEM</strong><span>HGT + pendiente y orientación · 1 arc-second</span></div>
                {terrainOverlay && <button type="button" aria-pressed={terrainVisible} onClick={() => setTerrainVisible((current) => !current)}>{terrainVisible ? "Ocultar capa" : "Mostrar capa"}</button>}
              </div>
              {loading && <p className="terrainState">Localizando gránulos oficiales en NASA CMR…</p>}
              {!loading && terrainError && <p className="terrainState terrainStateError" role="alert">{terrainError} Ejecute nuevamente para reintentar.</p>}
              {!loading && terrain && <div className="terrainSites">
                {terrain.sites.map((site) => <div className="terrainSite" key={`${site.location.latitude}-${site.location.longitude}`}>
                  <span><b>{site.location.label}</b><small>{site.granules[0]?.tile_id} · {site.provenance}</small></span>
                  {site.status === "READY" || site.status === "PARTIAL" ? <dl>
                    <div><dt>Elevación</dt><dd>{site.metrics.elevation_m === null ? "N/D" : `${formatNumber(site.metrics.elevation_m, 0)} m`}</dd></div>
                    <div><dt>Pendiente</dt><dd>{site.metrics.slope_degrees === null ? "N/D" : `${formatNumber(site.metrics.slope_degrees, 2)}°`}</dd></div>
                    <div><dt>Orientación</dt><dd>{site.metrics.aspect_degrees === null ? "N/D" : `${site.metrics.aspect_cardinal} · ${formatNumber(site.metrics.aspect_degrees, 1)}°`}</dd></div>
                  </dl> : site.status === "PENDING"
                    ? <p className="terrainPending"><b>Descargando tesela</b><span>NASADEM se descarga en segundo plano; vuelva a ejecutar en unos minutos.</span></p>
                    : <p><b>Metadatos verificados</b><span>Raster protegido: configure Earthdata Login para calcular métricas.</span></p>}
                </div>)}
                <p className="terrainProvenance">
                  <a href={terrain.sites[0]?.granules.find((item) => item.short_name === "NASADEM_HGT")?.doi_url} target="_blank" rel="noreferrer">NASADEM_HGT.001</a>
                  <a href={terrain.sites[0]?.granules.find((item) => item.short_name === "NASADEM_SC")?.doi_url} target="_blank" rel="noreferrer">NASADEM_SC.001</a>
                  <span>{terrain.crs} · {terrain.spatial_resolution}</span>
                </p>
              </div>}
              {!loading && !terrain && !terrainError && <p className="terrainState">Se consultará junto con el análisis solar; no se muestran métricas sin una respuesta oficial.</p>}
            </section>
            <details className="assumptionPanel" ref={assumptionPanelRef} open={assumptionsOpen} onToggle={(event) => setAssumptionsOpen(event.currentTarget.open)}>
              <summary>Supuestos financieros <span>USER_ASSUMPTION</span></summary>
              <div className="assumptionFields">
                <label>Capacidad MW<input type="number" value={assumptions.capacity_mw} onChange={(event) => updateAssumption("capacity_mw", event.target.value)} /></label>
                <label>Performance ratio<input type="number" step="0.01" value={assumptions.performance_ratio} onChange={(event) => updateAssumption("performance_ratio", event.target.value)} /></label>
                <label>CAPEX USD<input type="number" value={assumptions.initial_capex_usd} onChange={(event) => updateAssumption("initial_capex_usd", event.target.value)} /></label>
                <label>Precio USD/MWh<input type="number" value={assumptions.energy_price_usd_mwh} onChange={(event) => updateAssumption("energy_price_usd_mwh", event.target.value)} /></label>
                <label>OPEX anual USD<input type="number" value={assumptions.annual_opex_usd} onChange={(event) => updateAssumption("annual_opex_usd", event.target.value)} /></label>
                <label>Tasa descuento<input type="number" step="0.01" value={assumptions.discount_rate} onChange={(event) => updateAssumption("discount_rate", event.target.value)} /></label>
              </div>
            </details>
          </div>
        </aside>

        <section className="trendPanel" aria-label="Serie temporal anual">
          <div className="trendHeader">
            <span>Serie temporal anual</span>
            <div role="group" aria-label="Variable NASA POWER">{variables.map((variable) => <button key={variable.id} className={activeVariable === variable.id ? "active" : ""} aria-pressed={activeVariable === variable.id} onClick={() => setActiveVariable(variable.id)}>{variable.short}</button>)}</div>
            <p className="seriesKey">{(result?.sites ?? []).map((site, index) => <span key={site.location.label}><i style={{ background: siteColor(index) }} />{site.location.label}</span>)}<b>{selectedUnit}</b></p>
          </div>
          <div className="trendChart"><TemporalChart unit={selectedUnit} data={temporalSeries} series={(result?.sites ?? []).map((site, index) => ({ key: `site${index}`, label: site.location.label, color: siteColor(index) }))} /></div>
          <div className="chartFoot"><span title={result ? `${sourceSummary} · ${result.period}` : sourceSummary}>{result ? `${sourceSummary} · ${result.period}` : sourceSummary}</span><span>Media anual de observaciones diarias válidas · eje vertical ajustado al rango observado</span></div>
        </section>

        <PipelinePanel stages={visiblePipeline} running={loading} hasResult={result !== null} selectedStep={selectedStep} onSelect={setSelectedStep} onQuestion={goToQuestion} />
      </section>

      <section className="evidenceSection" id="resultados" aria-labelledby="evidence-title">
        <div className="sectionHeader"><div><h2 id="evidence-title">Evidencia y decisión</h2><p>{result ? `${result.title} · período ${result.period}` : "Ejecute el análisis para habilitar resultados reproducibles."}</p></div>{result && <div className="exportActions">
          <button className="exportAction primaryExport" onClick={exportPdf} disabled={pdfLoading} aria-busy={pdfLoading}><Icon name="download" />{pdfLoading ? "Generando PDF…" : "PDF ejecutivo"}</button>
          <button className="exportAction" onClick={exportReport}><Icon name="download" />Exportar JSON</button>
        </div>}</div>
        {pdfError && <p className="errorMessage" role="alert">{pdfError}</p>}
        {!result ? <div className="emptyEvidence"><div><h3>El flujo está preparado</h3><p>NASA POWER, Mann–Kendall, pendiente de Sen, ajuste BH y VAN condicionado se ejecutan únicamente al solicitar el análisis.</p></div><ul><li>Comparación Moquegua–Arequipa</li><li>Cobertura y limitaciones por variable</li><li>Supuestos financieros explícitos</li><li>Brechas para debida diligencia</li></ul></div> : <>
          <NasaQuestions questions={result.nasa_questions} onGoToStage={goToStage} />
          <div className="findingsPanel"><h3>Lectura comparativa</h3>{result.comparative_findings.map((finding, index) => <p key={index}><span>{index + 1}</span>{finding}</p>)}</div>
          <div className="resultGrid">
            <article className="chartPanel"><div className="panelHeader"><div><h3>Irradiancia histórica media</h3><p>Comparación relativa con observaciones NASA POWER</p></div><span>kWh/m²/día</span></div><ComparisonChart data={comparisonData} /></article>
            <article className="decisionPanel"><h3>Escenario económico</h3>{result.sites.map((site) => <div className="decisionRow" key={site.location.label}><div><b>{site.location.label}</b><span>{formatNumber(site.finance.annual_energy_mwh, 0)} MWh/año</span></div><strong className={site.finance.npv_usd >= 0 ? "positive" : "negative"}>{formatMoney(site.finance.npv_usd)}</strong></div>)}<p>MODEL_ESTIMATE · condicionado a USER_ASSUMPTION</p></article>
          </div>
          <div className="siteResults">
            {result.sites.map((site) => (
              <article className="siteResult" key={site.location.label}>
                <div className="siteResultHeader"><div><h3>{site.location.label}</h3><p>{site.relative_position_text}</p></div><span>{site.relative_solar_position}.º de {result.sites.length}</span></div>
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
            ))}
          </div>
          <div className="gapPanel"><div><h3>Brechas antes de invertir</h3><p>Definen el siguiente trabajo; no representan riesgo cero.</p></div><div>{result.data_gaps.map((gap) => <article key={gap.dataset}><span>{provenanceLabels[gap.status]}</span><h4>{gap.dataset}</h4><p>{gap.impact}</p><b>Siguiente acción: {gap.next_action}</b></article>)}</div></div><p className="disclaimer">{result.disclaimer}</p>
        </>}
      </section>

      <section className="coverageSection" aria-labelledby="coverage-title">
        <div className="sectionHeader"><div><h2 id="coverage-title">Siete módulos, estados honestos</h2><p>Una capacidad pendiente permanece identificada como pendiente.</p></div></div>
        <div className="moduleMatrix">{modules.map((module) => <button key={module.id} onClick={() => { selectModule(module.id); document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth" }); }}><Icon name={module.icon} /><span><b>{module.name}</b><small>{module.description}</small></span><em className={module.ready ? "ready" : "pending"}>{module.status}</em></button>)}</div>
      </section>
      <footer><div><strong>LOS CAUSAS ESPACIALES</strong><span>Inteligencia terrestre verificable para decisiones reales.</span></div><div><a href="http://localhost:8000/docs">OpenAPI · 8000</a><span>Aplicación · 3100</span></div></footer>

      <nav className="mobileBottomNav" aria-label="Navegación principal móvil">
        {modules.filter((module) => ["solar", "climate", "hazards", "investment"].includes(module.id)).map((module) => <button key={module.id} onClick={() => selectModule(module.id)} className={activeModule === module.id ? "active" : ""} aria-pressed={activeModule === module.id}><Icon name={module.icon} /><span>{module.short}</span></button>)}
        <button ref={moreButtonRef} onClick={() => setMobileNavOpen(true)} aria-expanded={mobileNavOpen}><Icon name="menu" /><span>Más</span></button>
      </nav>
    </main>
  );
}
