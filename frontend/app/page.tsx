"use client";
import * as maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Point = {
    latitude: number;
    longitude: number;
    label: string;
};
type Trend = {
    direction: string;
    slope_per_year: number | null;
    p_value: number | null;
    confidence_interval: [
        number,
        number
    ] | null;
    significant: boolean;
    autocorrelation_lag1: number | null;
    interpretation: string;
    limitations: string[];
};
type VariableSummary = {
    variable: string;
    label: string;
    mean: number;
    minimum: number;
    maximum: number;
    unit: string;
    valid_observations: number;
    completeness_percent: number;
    annual_variability_percent: number | null;
    trend: Trend;
    adjusted_p_value: number | null;
    significant_after_bh: boolean;
    source: {
        dataset: string;
        version: string;
        downloaded_at: string;
        source_url: string;
        provenance: string;
        spatial_resolution: string;
    };
};
type SolarFinance = {
    specific_yield_kwh_kwp_year: number;
    annual_energy_mwh: number;
    annual_revenue_usd: number;
    npv_usd: number;
    formula: string;
    limitations: string[];
};
type SiteResult = {
    location: Point;
    relative_solar_position: number;
    relative_position_text: string;
    variables: VariableSummary[];
    finance: SolarFinance;
    opportunities: string[];
    cautions: string[];
};
type Stage = {
    step: number;
    key: string;
    name: string;
    status: string;
    summary: string;
    provenance: string[];
};
type ScreeningResult = {
    analysis_id: string;
    generated_at: string;
    title: string;
    sector: string;
    period: string;
    pipeline: Stage[];
    sites: SiteResult[];
    comparative_findings: string[];
    data_gaps: {
        dataset: string;
        status: string;
        impact: string;
        next_action: string;
    }[];
    assumptions: Assumptions;
    disclaimer: string;
};
type Assumptions = {
    capacity_mw: number;
    performance_ratio: number;
    initial_capex_usd: number;
    annual_opex_usd: number;
    energy_price_usd_mwh: number;
    mitigation_capex_usd: number;
    discount_rate: number;
    horizon_years: number;
};
const initialSites: Point[] = [{ label: "Moquegua", latitude: -17.193, longitude: -70.934 }, { label: "Arequipa", latitude: -16.409, longitude: -71.537 }];
const initialAssumptions: Assumptions = { capacity_mw: 20, performance_ratio: .8, initial_capex_usd: 18000000, annual_opex_usd: 360000, energy_price_usd_mwh: 55, mitigation_capex_usd: 0, discount_rate: .1, horizon_years: 20 };
const pipelineNames = ["Selección", "Configuración", "Extracción", "Análisis", "Inteligencia territorial", "Evaluación", "Impacto económico", "Resultados", "Exportación"];
const provenanceLabels: Record<string, string> = { REAL_DATA: "Dato real", CACHED_DATA: "Dato real en caché", MODEL_ESTIMATE: "Estimación de modelo", USER_ASSUMPTION: "Supuesto del usuario", ILLUSTRATIVE_DEMO: "Demo ilustrativa", DATA_UNAVAILABLE: "Dato no disponible" };
const directionLabels: Record<string, string> = { increasing: "Creciente", decreasing: "Decreciente", no_trend: "Sin tendencia significativa", insufficient_evidence: "Evidencia insuficiente" };
function money(value: number) { return new Intl.NumberFormat("es-PE", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value); }
function number(value: number, digits = 2) { return new Intl.NumberFormat("es-PE", { maximumFractionDigits: digits }).format(value); }
function getVariable(site: SiteResult, variable: string) { return site.variables.find(item => item.variable === variable)!; }
export default function Home() {
    const mapContainer = useRef<HTMLDivElement>(null);
    const mapRef = useRef<maplibregl.Map | null>(null);
    const markersRef = useRef<maplibregl.Marker[]>([]);
    const [sites, setSites] = useState<Point[]>(initialSites);
    const [startDate, setStartDate] = useState("2001-01-01");
    const [endDate, setEndDate] = useState("2024-12-31");
    const [assumptions, setAssumptions] = useState<Assumptions>(initialAssumptions);
    const [result, setResult] = useState<ScreeningResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    useEffect(() => {
        if (!mapContainer.current)
            return;
        const map = new maplibregl.Map({
            container: mapContainer.current,
            style: "https://demotiles.maplibre.org/style.json",
            center: [-71.15, -16.8],
            zoom: 6,
        });
        map.addControl(new maplibregl.NavigationControl(), "top-right");
        map.on("click", event => setSites(current => [
            {
                ...current[0],
                latitude: +event.lngLat.lat.toFixed(5),
                longitude: +event.lngLat.lng.toFixed(5),
            },
            ...current.slice(1),
        ]));
        mapRef.current = map;
        return () => {
            markersRef.current.forEach(marker => marker.remove());
            map.remove();
            mapRef.current = null;
        };
    }, []);
    useEffect(() => { const map = mapRef.current; if (!map)
        return; markersRef.current.forEach(marker => marker.remove()); markersRef.current = sites.map((site, index) => new maplibregl.Marker({ color: index === 0 ? "#c7ff5e" : "#70d6ff" }).setLngLat([site.longitude, site.latitude]).setPopup(new maplibregl.Popup({ offset: 22 }).setText(site.label)).addTo(map)); if (sites.length > 1) {
        const bounds = new maplibregl.LngLatBounds();
        sites.forEach(site => bounds.extend([site.longitude, site.latitude]));
        map.fitBounds(bounds, { padding: 90, maxZoom: 8, duration: 700 });
    } }, [sites]);
    const visiblePipeline: Stage[] = result?.pipeline ?? pipelineNames.map((name, index) => ({ step: index + 1, key: String(index), name, status: index < 2 ? "LISTO" : "PENDIENTE", summary: index < 2 ? "Complete la configuración y ejecute el screening." : "Se activa después de ejecutar el análisis.", provenance: [] }));
    const chartData = useMemo(() => result?.sites.map(site => ({ name: site.location.label, irradiancia: +getVariable(site, "ALLSKY_SFC_SW_DWN").mean.toFixed(3), energia: +site.finance.annual_energy_mwh.toFixed(0) })) ?? [], [result]);
    function updateSite(index: number, key: keyof Point, value: string) { setSites(current => current.map((site, position) => position === index ? { ...site, [key]: key === "label" ? value : +value } : site)); }
    function updateAssumption(key: keyof Assumptions, value: string) { setAssumptions(current => ({ ...current, [key]: +value })); }
    async function runScreening() { setLoading(true); setError(""); setResult(null); try {
        const response = await fetch(`${API}/api/v1/projects/solar-screening`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sites, start_date: startDate, end_date: endDate, assumptions }) });
        const data = await response.json();
        if (!response.ok)
            throw new Error(typeof data.detail === "string" ? data.detail : "No fue posible ejecutar el screening.");
        setResult(data);
        setTimeout(() => document.getElementById("resultados")?.scrollIntoView({ behavior: "smooth" }), 100);
    }
    catch (cause) {
        setError(cause instanceof Error ? cause.message : "Ocurrió un error inesperado.");
    }
    finally {
        setLoading(false);
    } }
    function exportReport() { if (!result)
        return; const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `screening-solar-${result.analysis_id}.json`; anchor.style.display = "none"; document.body.appendChild(anchor); anchor.click(); anchor.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
    return <main>
  <header>
<a className="brand" href="#inicio">
<span className="orb">◉</span>
<span>
<b>LOS CAUSAS ESPACIALES</b>
<small>Inteligencia terrestre para inversiones más inteligentes</small>
</span>
</a>
<nav>
<a href="#pipeline">Pipeline</a>
<a href="#piloto">Piloto solar</a>
<a href="#resultados">Resultados</a>
<a href="#cobertura">Cobertura</a>
<a href="/plan-operativo.html">Plan operativo</a>
</nav>
<span className="systemStatus">● NASA POWER CONECTADO</span>
</header>

  <section id="inicio" className="hero">
<div className="heroCopy">
<p className="eyebrow">NASA SPACE APPS CHALLENGE 2026 · MOQUEGUA, PERÚ</p>
<h1>Del dato NASA<br />
<em>a una decisión trazable.</em>
</h1>
<p>Una plataforma de inteligencia territorial que responde qué está cambiando, dónde, cuánto, con qué evidencia y qué significa para una inversión real.</p>
<div className="heroActions">
<a className="primary" href="#piloto">Ejecutar el piloto funcional</a>
<a className="secondary" href="#pipeline">Ver cómo funciona</a>
</div>
</div>
<div className="heroProof">
<div>
<span>FUENTE OPERATIVA</span>
<strong>NASA POWER</strong>
<small>Consulta pública real + caché</small>
</div>
<div>
<span>PIPELINE</span>
<strong>9 pasos</strong>
<small>Selección → exportación</small>
</div>
<div>
<span>ESTADO DE PILOTOS</span>
<strong>1 / 3</strong>
<small>Solar funcional · vial y real estate pendientes</small>
</div>
</div>
</section>

  <section className="architecture">
<div>
<span>A</span>
<h3>Observación de la Tierra</h3>
<p>Extracción, metadatos, calidad y procedencia.</p>
<b>OPERATIVA</b>
</div>
<div>
<span>B</span>
<h3>Geoespacial y riesgo</h3>
<p>Tendencias, comparación y brechas territoriales.</p>
<b>PARCIAL</b>
</div>
<div>
<span>C</span>
<h3>Inteligencia de inversión</h3>
<p>Escenario económico y próximos estudios.</p>
<b>OPERATIVA EN SOLAR</b>
</div>
</section>

  <section id="pipeline" className="section pipelineSection">
<div className="sectionHeading">
<p className="eyebrow">PIPELINE DECIDIDO</p>
<h2>Un solo flujo para los siete módulos</h2>
<p>Cada etapa declara su estado y procedencia. Una capa no conectada aparece como pendiente; nunca se sustituye por datos inventados.</p>
</div>
<div className="pipelineGrid">{visiblePipeline.map(stage => <article key={stage.step} className={`pipelineStep status-${stage.status.toLowerCase().replace("_", "-")}`}>
<span className="stepNumber">{String(stage.step).padStart(2, "0")}</span>
<div>
<h3>{stage.name}</h3>
<b>{stage.status.replace("_", " ")}</b>
<p>{stage.summary}</p>
</div>
</article>)}</div>
</section>

  <section id="piloto" className="section pilotSection">
<div className="sectionHeading">
<p className="eyebrow">PILOTO FUNCIONAL A · ENERGÍA RENOVABLE</p>
<h2>Screening solar: Moquegua vs. Arequipa</h2>
<p>Cuatro variables NASA, evidencia estadística, comparación relativa y un escenario financiero condicionado a sus supuestos.</p>
</div>
<div className="pilotWorkspace">
<aside className="configPanel">
<div className="panelTitle">
<span>01</span>
<div>
<h3>Ubicaciones y período</h3>
<p>Haga clic en el mapa para mover la primera ubicación.</p>
</div>
</div>{sites.map((site, index) => <div className="siteEditor" key={index}>
<label>Nombre<input value={site.label} onChange={event => updateSite(index, "label", event.target.value)}/>
</label>
<div className="twoCols">
<label>Latitud<input type="number" step="0.001" value={site.latitude} onChange={event => updateSite(index, "latitude", event.target.value)}/>
</label>
<label>Longitud<input type="number" step="0.001" value={site.longitude} onChange={event => updateSite(index, "longitude", event.target.value)}/>
</label>
</div>
</div>)}<div className="twoCols">
<label>Desde<input type="date" value={startDate} onChange={event => setStartDate(event.target.value)}/>
</label>
<label>Hasta<input type="date" value={endDate} onChange={event => setEndDate(event.target.value)}/>
</label>
</div>
    <div className="panelTitle assumptionsTitle">
<span>02</span>
<div>
<h3>Supuestos financieros</h3>
<p>Todos son editables y se identifican como USER_ASSUMPTION.</p>
</div>
</div>
<div className="assumptionGrid">
<label>Capacidad (MW)<input type="number" value={assumptions.capacity_mw} onChange={event => updateAssumption("capacity_mw", event.target.value)}/>
</label>
<label>Performance ratio<input type="number" step="0.01" value={assumptions.performance_ratio} onChange={event => updateAssumption("performance_ratio", event.target.value)}/>
</label>
<label>CAPEX inicial (USD)<input type="number" value={assumptions.initial_capex_usd} onChange={event => updateAssumption("initial_capex_usd", event.target.value)}/>
</label>
<label>OPEX anual (USD)<input type="number" value={assumptions.annual_opex_usd} onChange={event => updateAssumption("annual_opex_usd", event.target.value)}/>
</label>
<label>Precio energía (USD/MWh)<input type="number" value={assumptions.energy_price_usd_mwh} onChange={event => updateAssumption("energy_price_usd_mwh", event.target.value)}/>
</label>
<label>Tasa de descuento<input type="number" step="0.01" value={assumptions.discount_rate} onChange={event => updateAssumption("discount_rate", event.target.value)}/>
</label>
<label>Horizonte (años)<input type="number" value={assumptions.horizon_years} onChange={event => updateAssumption("horizon_years", event.target.value)}/>
</label>
<label>CAPEX mitigación (USD)<input type="number" value={assumptions.mitigation_capex_usd} onChange={event => updateAssumption("mitigation_capex_usd", event.target.value)}/>
</label>
</div>
<button className="runButton" onClick={runScreening} disabled={loading}>{loading ? "Consultando NASA y ejecutando el pipeline…" : "Ejecutar screening solar"}</button>{error && <p className="errorBox">{error}</p>}</aside>
<div className="mapPanel">
<div className="mapHeader">
<span>MAPA DE UBICACIONES</span>
<div>
<i className="dot moquegua"/>Sitio 1 <i className="dot arequipa"/>Sitio 2</div>
</div>
<div ref={mapContainer} className="map"/>
<div className="sourceStrip">
<span>Variables</span>
<b>ALLSKY_SFC_SW_DWN</b>
<b>T2M</b>
<b>WS10M</b>
<b>PRECTOTCORR</b>
</div>
</div>
</div>
</section>

  {!result && <section className="section emptyResult">
<div>
<span>RESULTADO AÚN NO GENERADO</span>
<h2>Ejecute el piloto para convertir observaciones en una evaluación.</h2>
<p>La aplicación recuperará datos NASA reales, calculará tendencias y mostrará también aquello que todavía no puede responder.</p>
</div>
<div className="whatYouGet">
<b>El resultado incluirá</b>
<ul>
<li>Comparación solar Moquegua–Arequipa</li>
<li>Mann-Kendall, pendiente de Sen y p-value BH</li>
<li>Producción anual y VAN con supuestos explícitos</li>
<li>Brechas territoriales y próximos estudios</li>
<li>Reporte JSON reproducible</li>
</ul>
</div>
</section>}

  {result && <section id="resultados" className="section resultsSection">
<div className="resultHeader">
<div>
<p className="eyebrow">RESULTADO REPRODUCIBLE · {result.analysis_id}</p>
<h2>{result.title}</h2>
<p>Período {result.period} · generado {new Date(result.generated_at).toLocaleString("es-PE")}</p>
</div>
<button className="exportButton" onClick={exportReport}>Descargar reporte JSON</button>
</div>
<div className="provenanceLegend">
<span>Procedencia:</span>{Object.entries(provenanceLabels).map(([code, label]) => <b key={code} className={`prov prov-${code.toLowerCase()}`}>{label}</b>)}</div>
    <div className="findings">
<h3>Lectura comparativa</h3>{result.comparative_findings.map((finding, index) => <p key={index}>
<span>{index + 1}</span>{finding}</p>)}</div>
    <div className="chartGrid">
<div className="chartCard">
<h3>Irradiancia histórica media</h3>
<ResponsiveContainer width="100%" height={260}>
<BarChart data={chartData}>
<CartesianGrid stroke="#26364d" vertical={false}/>
<XAxis dataKey="name" stroke="#8c9ab0"/>
<YAxis stroke="#8c9ab0"/>
<Tooltip contentStyle={{ background: "#101928", border: "1px solid #33435c" }}/>
<Bar dataKey="irradiancia" fill="#c7ff5e" radius={[4, 4, 0, 0]}/>
</BarChart>
</ResponsiveContainer>
<small>NASA POWER · kWh/m²/día · comparación relativa</small>
</div>
<div className="chartCard">
<h3>Energía anual estimada</h3>
<ResponsiveContainer width="100%" height={260}>
<BarChart data={chartData}>
<CartesianGrid stroke="#26364d" vertical={false}/>
<XAxis dataKey="name" stroke="#8c9ab0"/>
<YAxis stroke="#8c9ab0"/>
<Tooltip contentStyle={{ background: "#101928", border: "1px solid #33435c" }}/>
<Bar dataKey="energia" fill="#70d6ff" radius={[4, 4, 0, 0]}/>
</BarChart>
</ResponsiveContainer>
<small>MODEL_ESTIMATE · MWh/año · condicionado a performance ratio</small>
</div>
</div>
    <div className="siteResults">{[...result.sites].sort((a, b) => a.relative_solar_position - b.relative_solar_position).map(site => { const solar = getVariable(site, "ALLSKY_SFC_SW_DWN"); return <article className="siteCard" key={site.location.label}>
<div className="siteCardHeader">
<div>
<span>POSICIÓN RELATIVA {site.relative_solar_position}</span>
<h3>{site.location.label}</h3>
<p>{site.relative_position_text}</p>
</div>
<b className="prov prov-real_data">{provenanceLabels[solar.source.provenance]}</b>
</div>
<div className="siteMetrics">
<div>
<span>Irradiancia media</span>
<strong>{number(solar.mean, 3)}</strong>
<small>{solar.unit}</small>
</div>
<div>
<span>Variabilidad anual</span>
<strong>{solar.annual_variability_percent === null ? "N/D" : `${number(solar.annual_variability_percent)}%`}</strong>
<small>coeficiente descriptivo</small>
</div>
<div>
<span>Tendencia</span>
<strong>{directionLabels[solar.trend.direction]}</strong>
<small>p BH {solar.adjusted_p_value?.toFixed(4) ?? "N/D"}</small>
</div>
<div>
<span>Producción estimada</span>
<strong>{number(site.finance.annual_energy_mwh, 0)}</strong>
<small>MWh/año</small>
</div>
<div>
<span>VAN del escenario</span>
<strong className={site.finance.npv_usd >= 0 ? "positive" : "negative"}>{money(site.finance.npv_usd)}</strong>
<small>supuestos del usuario</small>
</div>
</div>
<div className="variableTable">
<div className="variableRow tableHead">
<span>Variable NASA</span>
<span>Media</span>
<span>Cobertura</span>
<span>Pendiente Sen</span>
<span>Evidencia BH</span>
</div>{site.variables.map(variable => <div className="variableRow" key={variable.variable}>
<b>{variable.label}<small>{variable.variable}</small>
</b>
<span>{number(variable.mean, 3)} {variable.unit}</span>
<span>{number(variable.completeness_percent, 1)}%</span>
<span>{variable.trend.slope_per_year?.toFixed(4) ?? "N/D"}</span>
<span>{variable.significant_after_bh ? "Significativa" : "Insuficiente"}</span>
</div>)}</div>
<div className="evidenceColumns">
<div>
<h4>Oportunidades observadas</h4>{site.opportunities.map((item, index) => <p key={index}>+ {item}</p>)}</div>
<div>
<h4>Cautelas</h4>{site.cautions.map((item, index) => <p key={index}>! {item}</p>)}</div>
</div>
</article>; })}</div>
    <div className="gaps">
<div>
<p className="eyebrow">INTELIGENCIA TERRITORIAL · ESTADO PARCIAL</p>
<h3>Información que aún falta antes de invertir</h3>
<p>Estas brechas no se interpretan como riesgo cero. Definen el siguiente trabajo de debida diligencia.</p>
</div>
<div className="gapList">{result.data_gaps.map(gap => <article key={gap.dataset}>
<span>{provenanceLabels[gap.status]}</span>
<h4>{gap.dataset}</h4>
<p>{gap.impact}</p>
<b>Siguiente acción: {gap.next_action}</b>
</article>)}</div>
</div>
<p className="disclaimer">{result.disclaimer}</p>
</section>}

  <section id="cobertura" className="section coverageSection">
<div className="sectionHeading">
<p className="eyebrow">COBERTURA HONESTA DEL PRODUCTO</p>
<h2>Qué funciona y qué falta</h2>
</div>
<div className="coverageGrid">
<article className="active">
<span>01</span>
<h3>Inteligencia climática</h3>
<b>FUNCIONAL</b>
<p>Cuatro variables POWER, series, tendencias, anomalías estadísticas y cobertura.</p>
</article>
<article className="active">
<span>02</span>
<h3>Energía renovable</h3>
<b>PILOTO FUNCIONAL</b>
<p>Screening solar comparativo y escenario económico parametrizable.</p>
</article>
<article>
<span>03</span>
<h3>Amenazas naturales</h3>
<b>PENDIENTE DE CAPAS</b>
<p>No se muestran amenazas hasta integrar fuentes oficiales verificadas.</p>
</article>
<article>
<span>04</span>
<h3>Inteligencia ambiental</h3>
<b>PENDIENTE APPEEARS</b>
<p>Vegetación, cobertura, agua y ecosistemas aún no conectados.</p>
</article>
<article>
<span>05</span>
<h3>Dimensión social y arqueológica</h3>
<b>PENDIENTE OFICIAL</b>
<p>No se infiere información social o patrimonial desde satélites.</p>
</article>
<article>
<span>06</span>
<h3>Infraestructura</h3>
<b>BASE GEOMÉTRICA</b>
<p>Valida corredores; faltan muestreo, red y amenazas territoriales.</p>
</article>
<article className="active">
<span>07</span>
<h3>Inteligencia de inversión</h3>
<b>FUNCIONAL EN SOLAR</b>
<p>Comparación, energía, VAN, cautelas, brechas y exportación.</p>
</article>
</div>
<div className="nextPilots">
<article>
<span>CASO B</span>
<h3>Corredor vial peruano</h3>
<p>Próximo: definir corredor real, muestrear precipitación y conectar amenazas oficiales.</p>
</article>
<article>
<span>CASO C</span>
<h3>Desarrollo inmobiliario</h3>
<p>Próximo: integrar DEM, pendientes, amenazas y restricciones documentadas.</p>
</article>
</div>
</section>

  <footer>
<div>
<b>LOS CAUSAS ESPACIALES</b>
<p>Ciencia terrestre, inteligencia territorial y evaluación económica.</p>
</div>
<div>
<span>Aplicación</span>
<b>localhost:3100</b>
</div>
<div>
<span>API verificable</span>
<b>localhost:8000/docs</b>
</div>
</footer>
 </main>;
}
