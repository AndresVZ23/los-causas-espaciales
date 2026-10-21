"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { Icon, type IconName } from "./icons";

const GeoMap = dynamic(() => import("./geo-map"), { ssr: false, loading: () => <div className="mapLoading">Preparando el mapa…</div> });
const ComparisonChart = dynamic(() => import("./comparison-chart"), { ssr: false, loading: () => <div className="chartLoading">Preparando la comparación…</div> });

type Point = { latitude: number; longitude: number; label: string };
type Assumptions = { capacity_mw: number; performance_ratio: number; initial_capex_usd: number; annual_opex_usd: number; energy_price_usd_mwh: number; mitigation_capex_usd: number; discount_rate: number; horizon_years: number };
type Trend = { direction: string; slope_per_year: number | null; p_value: number | null; confidence_interval: [number, number] | null; significant: boolean; autocorrelation_lag1: number | null; interpretation: string; limitations: string[] };
type VariableSummary = { variable: string; label: string; mean: number; minimum: number; maximum: number; unit: string; valid_observations: number; completeness_percent: number; annual_variability_percent: number | null; trend: Trend; adjusted_p_value: number | null; significant_after_bh: boolean; source: { dataset: string; version: string; downloaded_at: string; source_url: string; provenance: string; spatial_resolution: string } };
type SolarFinance = { specific_yield_kwh_kwp_year: number; annual_energy_mwh: number; annual_revenue_usd: number; npv_usd: number; formula: string; limitations: string[] };
type SiteResult = { location: Point; relative_solar_position: number; relative_position_text: string; variables: VariableSummary[]; finance: SolarFinance; opportunities: string[]; cautions: string[] };
type Stage = { step: number; key: string; name: string; status: string; summary: string; provenance: string[] };
type ScreeningResult = { analysis_id: string; generated_at: string; title: string; sector: string; period: string; pipeline: Stage[]; sites: SiteResult[]; comparative_findings: string[]; data_gaps: { dataset: string; status: string; impact: string; next_action: string }[]; assumptions: Assumptions; disclaimer: string };
type Module = { id: string; short: string; name: string; icon: IconName; status: string; ready: boolean; description: string };

const modules: Module[] = [
  { id: "climate", short: "Clima", name: "Inteligencia climática", icon: "climate", status: "Funcional", ready: true, description: "Variables POWER, cobertura y tendencias estadísticas." },
  { id: "solar", short: "Solar", name: "Energía renovable", icon: "solar", status: "Piloto funcional", ready: true, description: "Screening solar comparativo con escenario económico." },
  { id: "hazards", short: "Amenazas", name: "Amenazas naturales", icon: "hazard", status: "Capas pendientes", ready: false, description: "Requiere integrar capas oficiales verificadas." },
  { id: "environment", short: "Ambiente", name: "Inteligencia ambiental", icon: "environment", status: "AppEEARS pendiente", ready: false, description: "Vegetación, agua y cobertura aún no conectadas." },
  { id: "social", short: "Territorio", name: "Dimensión social y arqueológica", icon: "social", status: "Fuente pendiente", ready: false, description: "No se infiere patrimonio o información social desde satélites." },
  { id: "infrastructure", short: "Infraestructura", name: "Infraestructura", icon: "infrastructure", status: "Base geométrica", ready: false, description: "La validación de corredores requiere red y capas territoriales." },
  { id: "investment", short: "Inversión", name: "Inteligencia de inversión", icon: "investment", status: "Funcional en solar", ready: true, description: "VAN y energía condicionados a supuestos editables." },
];

const initialSites: Point[] = [
  { label: "Moquegua", latitude: -17.193, longitude: -70.934 },
  { label: "Arequipa", latitude: -16.409, longitude: -71.537 },
];
const initialAssumptions: Assumptions = { capacity_mw: 20, performance_ratio: 0.8, initial_capex_usd: 18000000, annual_opex_usd: 360000, energy_price_usd_mwh: 55, mitigation_capex_usd: 0, discount_rate: 0.1, horizon_years: 20 };
const pipelineNames = ["Selección", "Configuración", "Extracción", "Análisis", "Territorio", "Evaluación", "Economía", "Resultados", "Exportación"];
const provenanceLabels: Record<string, string> = { REAL_DATA: "Dato real", CACHED_DATA: "Dato real en caché", MODEL_ESTIMATE: "Estimación de modelo", USER_ASSUMPTION: "Supuesto del usuario", ILLUSTRATIVE_DEMO: "Demo ilustrativa", DATA_UNAVAILABLE: "Dato no disponible" };
const directionLabels: Record<string, string> = { increasing: "Creciente", decreasing: "Decreciente", no_trend: "Sin tendencia significativa", insufficient_evidence: "Evidencia insuficiente" };

function formatMoney(value: number) { return new Intl.NumberFormat("es-PE", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value); }
function formatNumber(value: number, digits = 2) { return new Intl.NumberFormat("es-PE", { maximumFractionDigits: digits }).format(value); }
function getVariable(site: SiteResult, variable: string) { return site.variables.find((item) => item.variable === variable)!; }

export default function Workspace() {
  const [activeModule, setActiveModule] = useState("solar");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [sites, setSites] = useState<Point[]>(initialSites);
  const [startDate, setStartDate] = useState("2001-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [assumptions, setAssumptions] = useState<Assumptions>(initialAssumptions);
  const [result, setResult] = useState<ScreeningResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const selectedModule = modules.find((module) => module.id === activeModule)!;
  const visiblePipeline: Stage[] = result?.pipeline ?? pipelineNames.map((name, index) => ({ step: index + 1, key: String(index), name, status: index < 2 ? "LISTO" : "PENDIENTE", summary: "", provenance: [] }));
  const chartData = useMemo(() => result?.sites.map((site) => ({ name: site.location.label, irradiancia: +getVariable(site, "ALLSKY_SFC_SW_DWN").mean.toFixed(3) })) ?? [], [result]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 820px)");
    const sync = () => setIsMobile(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!mobileNavOpen) return;
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileNavOpen(false);
        window.setTimeout(() => moreButtonRef.current?.focus(), 0);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobileNavOpen]);

  function updateSite(index: number, key: keyof Point, value: string) {
    setSites((current) => current.map((site, position) => position === index ? { ...site, [key]: key === "label" ? value : +value } : site));
  }
  function updateAssumption(key: keyof Assumptions, value: string) { setAssumptions((current) => ({ ...current, [key]: +value })); }
  function resetSites() { setSites(initialSites); }
  function selectModule(id: string) {
    if (id !== activeModule) {
      setResult(null);
      setError("");
    }
    setActiveModule(id);
    setMobileNavOpen(false);
  }
  async function runScreening() {
    setLoading(true); setError("");
    try {
      const response = await fetch("/api/solar-screening", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sites, start_date: startDate, end_date: endDate, assumptions }) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No fue posible ejecutar el screening. Revise la configuración e intente de nuevo.");
      setResult(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Ocurrió un error inesperado. Revise la API e intente de nuevo.");
    } finally { setLoading(false); }
  }
  function exportReport() {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `screening-solar-${result.analysis_id}.json`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <main className="appShell">
      <aside className={`moduleRail ${mobileNavOpen ? "isOpen" : ""}`} aria-label="Módulos de inteligencia" aria-hidden={isMobile && !mobileNavOpen} inert={isMobile && !mobileNavOpen ? true : undefined}>
        <a className="brandMark" href="#workspace" aria-label="Los Causas Espaciales, inicio">
          <span className="brandSymbol"><span /></span>
          <span><strong>Los Causas</strong><small>Espaciales</small></span>
        </a>
        <button ref={closeButtonRef} className="railClose" onClick={() => { setMobileNavOpen(false); window.setTimeout(() => moreButtonRef.current?.focus(), 0); }}>Cerrar módulos</button>
        <nav className="moduleNav">
          {modules.map((module) => (
            <button key={module.id} className={`moduleButton ${activeModule === module.id ? "active" : ""}`} onClick={() => selectModule(module.id)} aria-pressed={activeModule === module.id} title={`${module.name}: ${module.status}`}>
              <Icon name={module.icon} />
              <span><b>{module.short}</b><small>{module.status}</small></span>
            </button>
          ))}
        </nav>
        <a className="railUtility" href="/plan-operativo.html"><Icon name="info" /><span>Plan operativo</span></a>
      </aside>

      <div className="workspaceBody">
        <header className="topBar">
          <div className="workspaceTitle"><span>Earth Intelligence Workspace</span><strong>{selectedModule.name}</strong></div>
          <div className="topContext">
            <span className={`sourceState ${result ? "verified" : ""}`}><i />{result ? "Consulta NASA verificada" : "NASA POWER configurado"}</span>
            <span className="locationContext">Moquegua · Perú</span>
            {result && <span className="analysisId">{result.analysis_id}</span>}
          </div>
        </header>

        <section id="workspace" className="workbench" aria-labelledby="workspace-heading">
          <h1 id="workspace-heading" className="srOnly">Espacio de inteligencia terrestre</h1>
          <aside className="controlPane" aria-label="Configuración del análisis">
            <div className="paneHeading"><div><h2>Configurar análisis</h2><p>{selectedModule.description}</p></div><Icon name="settings" /></div>
            {!selectedModule.ready && <div className="pendingNotice" role="status"><strong>{selectedModule.status}</strong><p>Este módulo no ejecutará cálculos hasta integrar y validar su fuente oficial.</p></div>}
            <div className="controlGroup">
              <div className="groupTitle"><span>Ubicaciones</span><button onClick={resetSites}>Restablecer</button></div>
              {sites.map((site, index) => (
                <div className="siteFields" key={index}>
                  <label>Nombre<input value={site.label} onChange={(event) => updateSite(index, "label", event.target.value)} /></label>
                  <div className="splitFields">
                    <label>Latitud<input type="number" step="0.001" value={site.latitude} onChange={(event) => updateSite(index, "latitude", event.target.value)} /></label>
                    <label>Longitud<input type="number" step="0.001" value={site.longitude} onChange={(event) => updateSite(index, "longitude", event.target.value)} /></label>
                  </div>
                </div>
              ))}
              <p className="fieldHint">Seleccione el mapa para mover la primera ubicación.</p>
            </div>
            <div className="controlGroup">
              <span className="groupTitle">Período de observación</span>
              <div className="splitFields"><label>Desde<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label>Hasta<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label></div>
            </div>
            <div className="controlGroup">
              <span className="groupTitle">Variables NASA POWER</span>
              <div className="variableList"><span>Radiación solar</span><span>Temperatura</span><span>Viento</span><span>Precipitación</span></div>
            </div>
            <button className="runAnalysis" onClick={runScreening} disabled={loading || !selectedModule.ready}>{loading ? "Consultando NASA POWER…" : selectedModule.ready ? "Ejecutar análisis" : "Fuente pendiente"}</button>
            {error && <p className="errorMessage" role="alert">{error}</p>}
            <details className="assumptionPanel" open={activeModule === "investment"}>
              <summary>Supuestos financieros <span>USER_ASSUMPTION</span></summary>
              <div className="assumptionFields">
                <label>Capacidad (MW)<input type="number" value={assumptions.capacity_mw} onChange={(event) => updateAssumption("capacity_mw", event.target.value)} /></label>
                <label>Performance ratio<input type="number" step="0.01" value={assumptions.performance_ratio} onChange={(event) => updateAssumption("performance_ratio", event.target.value)} /></label>
                <label>CAPEX inicial (USD)<input type="number" value={assumptions.initial_capex_usd} onChange={(event) => updateAssumption("initial_capex_usd", event.target.value)} /></label>
                <label>OPEX anual (USD)<input type="number" value={assumptions.annual_opex_usd} onChange={(event) => updateAssumption("annual_opex_usd", event.target.value)} /></label>
                <label>Precio (USD/MWh)<input type="number" value={assumptions.energy_price_usd_mwh} onChange={(event) => updateAssumption("energy_price_usd_mwh", event.target.value)} /></label>
                <label>Tasa de descuento<input type="number" step="0.01" value={assumptions.discount_rate} onChange={(event) => updateAssumption("discount_rate", event.target.value)} /></label>
              </div>
            </details>
          </aside>

          <section className="mapStage" aria-label="Área de trabajo geoespacial">
            <div className="mapToolbar">
              <div><Icon name="map" /><span>Mapa de evaluación</span></div>
              <div className="mapMeta"><span>WGS84</span><span>Mapa base OpenStreetMap</span></div>
            </div>
            <div className="mapViewport">
              <GeoMap sites={sites} onPick={(latitude, longitude) => setSites((current) => [{ ...current[0], latitude, longitude }, ...current.slice(1)])} />
              <div className="mapLegend" aria-label="Leyenda de ubicaciones"><span><i className="siteOne" />Sitio principal</span><span><i className="siteTwo" />Comparador</span></div>
              <div className="coordinateReadout">{sites[0].latitude.toFixed(4)}°, {sites[0].longitude.toFixed(4)}° · WGS84</div>
            </div>
            <div className="sourceBand"><span>Variables activas</span><b>ALLSKY_SFC_SW_DWN</b><b>T2M</b><b>WS10M</b><b>PRECTOTCORR</b></div>
          </section>

          <aside className="insightPane" aria-label="Lectura y procedencia">
            <div className="paneHeading"><div><h2>Lectura actual</h2><p>{result ? `Resultado generado ${new Date(result.generated_at).toLocaleString("es-PE")}` : "Aún no se ha ejecutado una consulta."}</p></div><Icon name="layers" /></div>
            {result ? (
              <>
                <div className="leadMetric"><span>Irradiancia media · {result.sites[0].location.label}</span><strong>{formatNumber(getVariable(result.sites[0], "ALLSKY_SFC_SW_DWN").mean, 3)}</strong><small>{getVariable(result.sites[0], "ALLSKY_SFC_SW_DWN").unit}</small></div>
                <dl className="metricList">
                  <div><dt>Posición relativa</dt><dd>{result.sites[0].relative_solar_position} de {result.sites.length}</dd></div>
                  <div><dt>Tendencia</dt><dd>{directionLabels[getVariable(result.sites[0], "ALLSKY_SFC_SW_DWN").trend.direction]}</dd></div>
                  <div><dt>Cobertura</dt><dd>{formatNumber(getVariable(result.sites[0], "ALLSKY_SFC_SW_DWN").completeness_percent, 1)}%</dd></div>
                  <div><dt>VAN del escenario</dt><dd>{formatMoney(result.sites[0].finance.npv_usd)}</dd></div>
                </dl>
              </>
            ) : (
              <div className="emptyInsight"><span className="targetMark"><i /><i /></span><h3>Listo para consultar</h3><p>El análisis recuperará observaciones NASA, evaluará tendencias y separará evidencia, estimaciones y supuestos.</p></div>
            )}
            <div className="provenanceStack">
              <h3>Procedencia</h3>
              {Object.entries(provenanceLabels).filter(([code]) => code !== "ILLUSTRATIVE_DEMO").map(([code, label]) => <div key={code} className={`provenanceRow prov-${code.toLowerCase()}`}><i /><span>{label}</span><code>{code}</code></div>)}
            </div>
            <div className="honestyNote"><Icon name="info" /><p>Una fuente pendiente se muestra como brecha. Nunca se interpreta como ausencia de riesgo.</p></div>
          </aside>

          <div className={`pipelineStrip ${loading ? "isRunning" : ""}`} aria-label="Estado del pipeline" aria-live="polite">
            <div className="pipelineLabel"><span>Pipeline</span><b>{loading ? "Procesando" : result ? "Completado" : "Preparado"}</b></div>
            <ol>{visiblePipeline.map((stage, index) => <li key={stage.key} className={stage.status.toLowerCase().replaceAll("_", "-")}><span>{index + 1}</span><b>{stage.name}</b></li>)}</ol>
          </div>
        </section>

        <section className="evidenceSection" id="resultados" aria-labelledby="evidence-title">
          <div className="sectionHeader"><div><h2 id="evidence-title">Evidencia y decisión</h2><p>{result ? `${result.title} · período ${result.period}` : "Ejecute el análisis para habilitar resultados reproducibles."}</p></div>{result && <button className="exportAction" onClick={exportReport}><Icon name="download" />Exportar JSON</button>}</div>
          {!result ? (
            <div className="emptyEvidence">
              <div><h3>El flujo está preparado</h3><p>La plataforma consultará NASA POWER, calculará Mann–Kendall y pendiente de Sen, ajustará p-values y evaluará un escenario financiero con sus supuestos.</p></div>
              <ul><li>Comparación Moquegua–Arequipa</li><li>Cobertura y limitaciones por variable</li><li>VAN reproducible y condicionado</li><li>Brechas para la debida diligencia</li></ul>
            </div>
          ) : (
            <>
              <div className="findingsPanel"><h3>Lectura comparativa</h3>{result.comparative_findings.map((finding, index) => <p key={index}><span>{index + 1}</span>{finding}</p>)}</div>
              <div className="resultGrid">
                <article className="chartPanel"><div className="panelHeader"><div><h3>Irradiancia histórica media</h3><p>Comparación relativa con observaciones NASA POWER</p></div><span>kWh/m²/día</span></div><ComparisonChart data={chartData} /></article>
                <article className="decisionPanel"><h3>Escenario económico</h3>{result.sites.map((site) => <div className="decisionRow" key={site.location.label}><div><b>{site.location.label}</b><span>{formatNumber(site.finance.annual_energy_mwh, 0)} MWh/año</span></div><strong className={site.finance.npv_usd >= 0 ? "positive" : "negative"}>{formatMoney(site.finance.npv_usd)}</strong></div>)}<p>MODEL_ESTIMATE · cálculo condicionado a USER_ASSUMPTION</p></article>
              </div>
              <div className="siteResults">
                {result.sites.map((site) => (
                  <article className="siteResult" key={site.location.label}>
                    <div className="siteResultHeader">
                      <div><h3>{site.location.label}</h3><p>{site.relative_position_text}</p></div>
                      <span>Posición {site.relative_solar_position}</span>
                    </div>
                    <div className="tableScroll">
                      <table>
                        <thead><tr><th>Variable NASA</th><th>Media</th><th>Cobertura</th><th>Pendiente Sen</th><th>Evidencia BH</th></tr></thead>
                        <tbody>
                          {site.variables.map((variable) => (
                            <tr key={variable.variable}>
                              <th>{variable.label}<small>{variable.variable}</small></th>
                              <td>{formatNumber(variable.mean, 3)} {variable.unit}</td>
                              <td>{formatNumber(variable.completeness_percent, 1)}%</td>
                              <td>{variable.trend.slope_per_year?.toFixed(4) ?? "N/D"}</td>
                              <td>{variable.significant_after_bh ? "Significativa" : "Insuficiente"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </article>
                ))}
              </div>
              <div className="gapPanel"><div><h3>Brechas antes de invertir</h3><p>Definen el siguiente trabajo de debida diligencia; no representan riesgo cero.</p></div><div>{result.data_gaps.map((gap) => <article key={gap.dataset}><span>{provenanceLabels[gap.status]}</span><h4>{gap.dataset}</h4><p>{gap.impact}</p><b>Siguiente acción: {gap.next_action}</b></article>)}</div></div>
              <p className="disclaimer">{result.disclaimer}</p>
            </>
          )}
        </section>

        <section className="coverageSection" aria-labelledby="coverage-title">
          <div className="sectionHeader"><div><h2 id="coverage-title">Cobertura del producto</h2><p>Siete módulos, con capacidad y brechas declaradas sin ambigüedad.</p></div></div>
          <div className="moduleMatrix">{modules.map((module) => <button key={module.id} onClick={() => { selectModule(module.id); document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth" }); }}><Icon name={module.icon} /><span><b>{module.name}</b><small>{module.description}</small></span><em className={module.ready ? "ready" : "pending"}>{module.status}</em></button>)}</div>
        </section>

        <footer><div><strong>Los Causas Espaciales</strong><span>Inteligencia terrestre verificable para decisiones de inversión.</span></div><div><a href="/plan-operativo.html">Plan operativo</a><a href="http://localhost:8000/docs">OpenAPI · 8000</a><span>Aplicación · 3100</span></div></footer>
      </div>
      <nav className="mobileBottomNav" aria-label="Navegación principal móvil">
        {modules.filter((module) => ["climate", "solar", "hazards", "investment"].includes(module.id)).map((module) => (
          <button key={module.id} onClick={() => selectModule(module.id)} className={activeModule === module.id ? "active" : ""} aria-pressed={activeModule === module.id}>
            <Icon name={module.icon} /><span>{module.short}</span>
          </button>
        ))}
        <button ref={moreButtonRef} onClick={() => setMobileNavOpen(true)} aria-expanded={mobileNavOpen} aria-label={mobileNavOpen ? "Ocultar todos los módulos" : "Mostrar todos los módulos"}>
          <Icon name="menu" /><span>Más</span>
        </button>
      </nav>
    </main>
  );
}
