"use client";

import { useMemo, useState } from "react";
import styles from "./neural-dop.module.css";

type NodeStatus = "OPERATIVO" | "SIGUIENTE" | "PENDIENTE" | "BLOQUEADO" | "GATE";

type DopNode = {
  id: string;
  code: string;
  name: string;
  layer: string;
  status: NodeStatus;
  column: number;
  row: number;
  purpose: string;
  inputs: string[];
  output: string;
  acceptance: string;
  blocker?: string;
};

type DopEdge = { from: string; to: string; feedback?: boolean };

const nodes: DopNode[] = [
  { id: "solar", code: "00A", name: "Piloto solar", layer: "Base verificada", status: "OPERATIVO", column: 1, row: 2, purpose: "Conservar el caso extremo a extremo como patrón de integración y contrato público.", inputs: ["NASA POWER", "Supuestos financieros", "Geometrías WGS84"], output: "Screening trazable con serie anual, tendencias, VAN y exportación JSON.", acceptance: "13 pruebas, build, navegador desktop/mobile y procedencia aprobados." },
  { id: "qa-core", code: "00B", name: "QA científico", layer: "Base verificada", status: "OPERATIVO", column: 1, row: 4, purpose: "Aplicar puertas de datos, estadística, geoespacio, inversión y reproducibilidad a cada incremento.", inputs: ["Skills de dominio", "Casos controlados", "Fuentes primarias"], output: "Matriz de evidencia sin puertas aplicables en FALLÓ.", acceptance: "Auditor, validadores especializados y pruebas reproducibles en CI." },
  { id: "gpm", code: "01A", name: "GPM IMERG V07", layer: "Observación terrestre", status: "PENDIENTE", column: 2, row: 1, purpose: "Incorporar precipitación espacial de alta frecuencia con QA del producto.", inputs: ["Earthdata Login", "Short name y versión", "QA flags"], output: "Raster temporal validado con nodata, unidad, resolución y procedencia.", acceptance: "Consulta real contrastada con NASA y prueba de faltantes/error.", blocker: "Acceso Earthdata y selección final del producto aún no configurados." },
  { id: "dem", code: "01B", name: "DEM y pendiente", layer: "Observación terrestre", status: "SIGUIENTE", column: 2, row: 2, purpose: "Derivar elevación, pendiente y orientación para energía, corredores e inmuebles.", inputs: ["DEM NASA/Earthdata", "CRS y resolución", "Política nodata"], output: "Superficies de terreno y métricas por sitio, corredor o polígono.", acceptance: "Reproyección, unidades y muestreo contrastados con segunda implementación.", blocker: "Producto DEM y resolución de análisis deben decidirse y registrarse." },
  { id: "appeears", code: "01C", name: "AppEEARS", layer: "Observación terrestre", status: "PENDIENTE", column: 2, row: 3, purpose: "Extraer vegetación, agua y cobertura para la inteligencia ambiental.", inputs: ["Earthdata Login", "Productos versionados", "Escala y offset"], output: "Capas ambientales con QA y cobertura explícitas.", acceptance: "Extracción reproducible; QA flags, remuestreo y licencia documentados.", blocker: "Productos y credenciales Earthdata pendientes." },
  { id: "peru", code: "01D", name: "Capas oficiales Perú", layer: "Territorio", status: "PENDIENTE", column: 2, row: 4, purpose: "Integrar red, subestaciones, áreas protegidas, patrimonio, comunidades y predios.", inputs: ["MINEM/COES", "SERNANP/SENACE", "Cultura y fuentes sociales"], output: "Catálogo territorial con fecha, licencia, escala, cobertura y responsable.", acceptance: "Servicio oficial verificado; CRS, vigencia y limitaciones visibles.", blocker: "Endpoints, licencias y cobertura todavía deben verificarse fuente por fuente." },
  { id: "harmonize", code: "02A", name: "Armonización espacial", layer: "Motor geoespacial", status: "PENDIENTE", column: 3, row: 2, purpose: "Normalizar CRS, ejes, resolución, nodata y temporalidad sin degradación silenciosa.", inputs: ["Rasters NASA", "Vectores oficiales", "Metadatos de calidad"], output: "Capas comparables con transformaciones y tolerancias registradas.", acceptance: "Ninguna operación con CRS desconocido; casos límite y segunda implementación aprobados." },
  { id: "sampling", code: "02B", name: "Muestreo geométrico", layer: "Motor geoespacial", status: "PENDIENTE", column: 3, row: 3, purpose: "Extender el análisis de puntos a corredores y polígonos reales.", inputs: ["GeoJSON validado", "Capas armonizadas", "Regla de muestreo"], output: "Perfiles de corredor, estadísticas zonales y cobertura espacial.", acceptance: "Distancias/áreas geodésicas, densidad de muestra y nodata probados." },
  { id: "platform", code: "02C", name: "PostGIS y trabajos", layer: "Plataforma de datos", status: "PENDIENTE", column: 3, row: 4, purpose: "Persistir análisis grandes y ejecutar extracciones asíncronas auditables.", inputs: ["PostGIS", "Cola de trabajos", "Almacén de artefactos"], output: "Datasets, geometrías, ejecuciones y resultados versionados.", acceptance: "Idempotencia, reintentos, estados de error y restauración comprobados." },
  { id: "features", code: "03A", name: "Feature store", layer: "Preparación ML", status: "BLOQUEADO", column: 4, row: 1, purpose: "Convertir observaciones y territorio en variables reproducibles por fecha y geometría.", inputs: ["Capas armonizadas", "Agregaciones declaradas", "Procedencia completa"], output: "Dataset de características versionado, sin mezclar fuentes o períodos silenciosamente.", acceptance: "Esquema, unidades, linaje y pruebas de fuga aprobados.", blocker: "Depende de integrar y armonizar las fuentes faltantes." },
  { id: "labels", code: "03B", name: "Etiquetas reales", layer: "Preparación ML", status: "BLOQUEADO", column: 4, row: 2, purpose: "Definir un objetivo decisional medible a partir de resultados reales, no proxies inventados.", inputs: ["Decisión objetivo", "Resultados observados", "Criterio experto"], output: "Etiquetas con fecha, fuente, incertidumbre y política de revisión.", acceptance: "Definición pre-registrada, acuerdo experto y tamaño muestral suficiente.", blocker: "No existe todavía un corpus versionado de resultados reales de proyectos." },
  { id: "splits", code: "03C", name: "Partición sin fuga", layer: "Preparación ML", status: "BLOQUEADO", column: 4, row: 3, purpose: "Separar entrenamiento, validación y prueba por tiempo y espacio.", inputs: ["Features versionadas", "Etiquetas confiables", "Grupos espaciales"], output: "Splits congelados que representan generalización temporal y territorial.", acceptance: "Cero solapamiento causal; prueba externa reservada y documentada.", blocker: "Requiere features y etiquetas disponibles." },
  { id: "baseline", code: "03D", name: "Baselines simples", layer: "Preparación ML", status: "BLOQUEADO", column: 4, row: 4, purpose: "Establecer la referencia que cualquier red neuronal debe superar.", inputs: ["Splits congelados", "Métrica decisional", "Modelo lineal/árbol"], output: "Rendimiento, calibración y costo operacional reproducibles.", acceptance: "Validación fuera de muestra e intervalos por región/período.", blocker: "No se autoriza antes de congelar dataset, target y splits." },
  { id: "candidates", code: "04A", name: "Modelos candidatos", layer: "Investigación neuronal", status: "BLOQUEADO", column: 5, row: 2, purpose: "Comparar arquitecturas sólo cuando la estructura de datos lo justifique.", inputs: ["Baseline aprobado", "Series y grafos versionados", "Presupuesto computacional"], output: "Experimentos TCN/Transformer temporal o GNN, según evidencia.", acceptance: "Mejora material fuera de muestra frente al baseline con ablaciones.", blocker: "Arquitectura no debe elegirse antes de conocer datos, target y baseline." },
  { id: "assurance", code: "04B", name: "Incertidumbre y drift", layer: "Investigación neuronal", status: "BLOQUEADO", column: 5, row: 3, purpose: "Validar calibración, robustez, explicabilidad y degradación operativa.", inputs: ["Predicciones de prueba", "Subgrupos territoriales", "Escenarios adversos"], output: "Intervalos, calibración, atribuciones, drift y límites documentados.", acceptance: "Model card, pruebas de sensibilidad y umbrales de abstención aprobados.", blocker: "Depende de un candidato que supere el baseline." },
  { id: "human-gate", code: "05A", name: "Gate humano", layer: "Gobernanza", status: "GATE", column: 6, row: 2, purpose: "Autorizar, iterar o descartar el modelo sin automatizar una decisión de inversión.", inputs: ["Model card", "QA científico", "Revisión sectorial"], output: "Decisión firmada con alcance, responsable, vigencia y condiciones de uso.", acceptance: "Ciencia, negocio, riesgo y seguridad aprueban; existe ruta de apelación." },
  { id: "pilots", code: "05B", name: "Pilotos sectoriales", layer: "Producto", status: "PENDIENTE", column: 6, row: 3, purpose: "Desplegar energía ampliada, corredores viales e inmuebles como pilotos separados.", inputs: ["Gate humano", "Capas mínimas", "Casos reales"], output: "Comparativas sectoriales con brechas, mitigaciones y evidencia trazable.", acceptance: "Casos reales revisados por expertos; ninguna recomendación excede la evidencia." },
  { id: "delivery", code: "05C", name: "API, PDF y monitoreo", layer: "Producto", status: "PENDIENTE", column: 6, row: 4, purpose: "Entregar resultados reproducibles y vigilar calidad posterior al despliegue.", inputs: ["Resultados aprobados", "Artefactos versionados", "Umbrales de drift"], output: "API, JSON/PDF, auditoría, monitoreo y rollback.", acceptance: "Exportación reproducible, trazabilidad completa y alarmas probadas." },
];

const edges: DopEdge[] = [
  { from: "solar", to: "features" }, { from: "solar", to: "labels" },
  { from: "qa-core", to: "harmonize" }, { from: "qa-core", to: "splits" }, { from: "qa-core", to: "assurance" },
  { from: "gpm", to: "harmonize" }, { from: "dem", to: "harmonize" }, { from: "appeears", to: "harmonize" }, { from: "peru", to: "harmonize" },
  { from: "harmonize", to: "sampling" }, { from: "sampling", to: "platform" }, { from: "sampling", to: "features" }, { from: "platform", to: "features" }, { from: "platform", to: "labels" },
  { from: "features", to: "splits" }, { from: "labels", to: "splits" }, { from: "splits", to: "baseline" },
  { from: "baseline", to: "candidates" }, { from: "candidates", to: "assurance" }, { from: "assurance", to: "human-gate" },
  { from: "human-gate", to: "pilots" }, { from: "pilots", to: "delivery" }, { from: "human-gate", to: "labels", feedback: true },
];

const coordinates: Record<string, [number, number]> = Object.fromEntries(nodes.map((node) => [node.id, [100 + (node.column - 1) * 200, 80 + (node.row - 1) * 125]]));

function collectConnected(start: string, direction: "upstream" | "downstream") {
  const visited = new Set<string>();
  const queue = [start];
  while (queue.length) {
    const current = queue.shift()!;
    edges.forEach((edge) => {
      // The governance loop is shown in the DOP, but it must not turn every
      // node into a dependency when tracing the delivery path.
      if (edge.feedback) return;
      const candidate = direction === "downstream" && edge.from === current ? edge.to : direction === "upstream" && edge.to === current ? edge.from : null;
      if (candidate && !visited.has(candidate)) { visited.add(candidate); queue.push(candidate); }
    });
  }
  visited.delete(start);
  return visited;
}

export default function NeuralDop() {
  const [selectedId, setSelectedId] = useState("labels");
  const selected = nodes.find((node) => node.id === selectedId)!;
  const upstream = useMemo(() => collectConnected(selectedId, "upstream"), [selectedId]);
  const downstream = useMemo(() => collectConnected(selectedId, "downstream"), [selectedId]);
  const active = useMemo(() => new Set([selectedId, ...upstream, ...downstream]), [selectedId, upstream, downstream]);
  const counts = useMemo(() => ({ operative: nodes.filter((node) => node.status === "OPERATIVO").length, missing: nodes.filter((node) => ["SIGUIENTE", "PENDIENTE"].includes(node.status)).length, blocked: nodes.filter((node) => node.status === "BLOQUEADO").length }), []);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <a className={styles.brand} href="/"><strong>LOS CAUSAS<br />ESPACIALES</strong><span>INTELIGENCIA DE LA TIERRA<br />PARA DECISIONES REALES</span></a>
        <div className={styles.titleBlock}><span>DOP — SISTEMA NEURONAL</span><h1>Pipeline de construcción pendiente</h1><p>Red de dependencias para llegar desde el piloto verificado hasta modelos evaluables y pilotos sectoriales.</p></div>
        <nav className={styles.headerNav} aria-label="Navegación del DOP"><a href="/">Workspace</a><a href="/dop-neuronal.html">Tracker HTML</a><a href="/plan-operativo.html">Plan operativo</a></nav>
      </header>

      <section className={styles.statusBar} aria-label="Estado del programa">
        <div><span>BASE OPERATIVA</span><strong>{counts.operative}</strong><small>capacidades verificadas</small></div>
        <div><span>INTEGRACIONES</span><strong>{counts.missing}</strong><small>próximas o pendientes</small></div>
        <div><span>PRECONDICIONES ML</span><strong>{counts.blocked}</strong><small>bloqueadas por evidencia</small></div>
        <p><b>Regla de autorización</b> La red neuronal no se entrena hasta disponer de etiquetas reales, dataset versionado, splits sin fuga y un baseline reproducible.</p>
      </section>

      <section className={styles.networkSection} aria-labelledby="network-title">
        <div className={styles.sectionHeading}><div><span>DIAGRAMA DE OPERACIONES DEL PROCESO</span><h2 id="network-title">Red completa de dependencias</h2></div><div className={styles.legend} aria-label="Leyenda de estado"><span data-status="OPERATIVO">Operativo</span><span data-status="SIGUIENTE">Siguiente</span><span data-status="PENDIENTE">Pendiente</span><span data-status="BLOQUEADO">Bloqueado</span><span data-status="GATE">Gate</span></div></div>
        <p className={styles.instructions}>Seleccione un nodo para aislar sus dependencias ascendentes y el trabajo que desbloquea.</p>

        <div className={styles.network}>
          <svg className={styles.edges} viewBox="0 0 1200 580" preserveAspectRatio="none" aria-hidden="true">
            <defs><marker id="dop-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 8 4 0 8Z" /></marker></defs>
            {edges.map((edge) => {
              const [x1, y1] = coordinates[edge.from]; const [x2, y2] = coordinates[edge.to];
              const isActive = active.has(edge.from) && active.has(edge.to);
              const bend = Math.max(34, Math.abs(x2 - x1) * 0.42);
              return <path key={`${edge.from}-${edge.to}`} className={`${isActive ? styles.activeEdge : ""} ${edge.feedback ? styles.feedbackEdge : ""}`} d={`M ${x1 + 72} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2 - 72} ${y2}`} markerEnd="url(#dop-arrow)" />;
            })}
          </svg>

          <div className={styles.stageLabels} aria-hidden="true">{["BASE", "DATOS", "GEO", "DATASET", "MODELOS", "DECISIÓN"].map((label) => <span key={label}>{label}</span>)}</div>
          <div className={styles.nodeGrid}>
            {nodes.map((node) => {
              const relation = node.id === selectedId ? "selected" : upstream.has(node.id) ? "upstream" : downstream.has(node.id) ? "downstream" : "unrelated";
              return (
                <button key={node.id} type="button" className={styles.node} data-status={node.status} data-relation={relation} style={{ gridColumn: node.column, gridRow: node.row }} onClick={() => setSelectedId(node.id)} aria-pressed={node.id === selectedId} aria-label={`${node.name}, ${node.status}. ${node.purpose}`}>
                  <span>{node.code}</span><strong>{node.name}</strong><small>{node.status}</small>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className={styles.detail} aria-live="polite" aria-labelledby="detail-title">
        <div className={styles.detailIdentity}><span>{selected.code} · {selected.layer}</span><h2 id="detail-title">{selected.name}</h2><b data-status={selected.status}>{selected.status}</b></div>
        <div className={styles.detailPurpose}><span>OBJETIVO</span><p>{selected.purpose}</p>{selected.blocker && <p className={styles.blocker}><b>Bloqueo actual:</b> {selected.blocker}</p>}</div>
        <div><span>ENTRADAS</span><ul>{selected.inputs.map((input) => <li key={input}>{input}</li>)}</ul></div>
        <div><span>SALIDA VERIFICABLE</span><p>{selected.output}</p></div>
        <div><span>PUERTA DE ACEPTACIÓN</span><p>{selected.acceptance}</p></div>
      </section>

      <section className={styles.criticalPath} aria-labelledby="critical-title">
        <div><span>RUTA CRÍTICA RECOMENDADA</span><h2 id="critical-title">Del dato faltante a una decisión asistida</h2></div>
        <ol>{["DEM + fuentes oficiales", "Armonización espacial", "PostGIS y muestreo", "Etiquetas reales", "Splits sin fuga", "Baseline simple", "Candidato neuronal", "Gate humano"].map((step, index) => <li key={step}><span>{String(index + 1).padStart(2, "0")}</span><b>{step}</b></li>)}</ol>
      </section>

      <footer className={styles.footer}><div><strong>LOS CAUSAS ESPACIALES</strong><span>DOP de desarrollo · no representa un modelo entrenado.</span></div><div><a href="/">Aplicación · 3100</a><a href="http://localhost:8000/docs">OpenAPI · 8000</a></div></footer>
    </main>
  );
}
