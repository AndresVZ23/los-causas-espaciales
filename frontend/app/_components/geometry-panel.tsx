"use client";

import { useRef } from "react";
import { formatNumber } from "./format";
import { KIND_LABEL } from "./use-study-geometries";
import type { StudyGeometriesState, StudyGeometry } from "./use-study-geometries";

function metrics(item: StudyGeometry) {
  const inspection = item.inspection;
  if (!inspection) return null;
  if (item.kind === "segment") return `${formatNumber(inspection.length_km ?? 0, 2)} km · ${inspection.vertex_count} vértices`;
  const area = inspection.area_km2 ?? 0;
  const areaText = area < 1 ? `${formatNumber(area * 100, 2)} ha` : `${formatNumber(area, 2)} km²`;
  return `${areaText} · perímetro ${formatNumber(inspection.length_km ?? 0, 2)} km · ${inspection.vertex_count} vértices`;
}

const STATUS_TEXT = { validando: "Validando", valida: "Válida", invalida: "Inválida" } as const;

export default function GeometryPanel({ state, hint }: { state: StudyGeometriesState; hint: string }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const { geometries, draft, selectedId, notice, canFinish } = state;
  const validCount = geometries.filter((item) => item.status === "valida").length;
  return (
    <section className="geometryPanel" aria-labelledby="geometrias-title">
      <div className="geometryHead">
        <h3 id="geometrias-title">Geometrías de estudio</h3>
        <span>WGS84 · lon, lat · USER_ASSUMPTION</span>
      </div>
      <p className="geometryHint">{hint}</p>
      {draft ? (
        <div className="drawBar" role="status" aria-live="polite">
          <p><b>{KIND_LABEL[draft.kind]}</b> · {draft.vertices.length} vértice(s). Haga clic en el mapa para agregar; doble clic o «Terminar» para cerrar.</p>
          <div>
            <button onClick={state.undoVertex} disabled={!draft.vertices.length}>Deshacer vértice</button>
            <button onClick={state.cancelDraft}>Cancelar</button>
            <button className="primary" onClick={state.finishDraft} disabled={!canFinish}>Terminar</button>
          </div>
        </div>
      ) : (
        <div className="geometryActions">
          <button onClick={() => state.startDraft("segment")}>Dibujar corredor</button>
          <button onClick={() => state.startDraft("polygon")}>Dibujar polígono</button>
          <button onClick={() => fileRef.current?.click()}>Cargar GeoJSON</button>
          <input ref={fileRef} type="file" accept=".geojson,.json,application/geo+json,application/json" hidden aria-label="Archivo GeoJSON"
                 onChange={(event) => { const file = event.target.files?.[0]; if (file) state.importFile(file); event.target.value = ""; }} />
          <button onClick={state.exportGeoJson} disabled={!validCount}>Exportar GeoJSON</button>
        </div>
      )}
      {notice && (
        <div className={`geometryNotice ${notice.tone}`} role={notice.tone === "error" ? "alert" : "status"}>
          {notice.lines.map((line) => <p key={line}>{line}</p>)}
          <button onClick={state.dismissNotice} aria-label="Cerrar aviso">×</button>
        </div>
      )}
      {geometries.length > 0 ? (
        <ul className="geometryList">
          {geometries.map((item) => (
            <li key={item.id} className={item.id === selectedId ? "selected" : undefined}>
              <button className="geometrySelect" onClick={() => state.select(item.id)} aria-pressed={item.id === selectedId} aria-label={`Ver ${item.name} en el mapa`}>
                <i className={item.kind} aria-hidden="true" />
              </button>
              <div>
                <label className="srOnly" htmlFor={`${item.id}-name`}>Nombre de la geometría</label>
                <input id={`${item.id}-name`} value={item.name} maxLength={60} onChange={(event) => state.rename(item.id, event.target.value)} />
                <small>{KIND_LABEL[item.kind]} · {item.origin}</small>
                {item.status === "valida" && <small className="figure">{metrics(item)}</small>}
                {item.status === "invalida" && <small className="invalid" role="alert">{item.error}</small>}
              </div>
              <span className={`geometryStatus ${item.status}`}>{STATUS_TEXT[item.status]}</span>
              <button className="geometryRemove" onClick={() => state.remove(item.id)} aria-label={`Quitar ${item.name}`}>Quitar</button>
            </li>
          ))}
        </ul>
      ) : !draft && <p className="geometryEmpty">Sin geometrías. Dibuje sobre el mapa o cargue un GeoJSON en WGS84 (longitud, latitud).</p>}
      {validCount > 0 && <p className="geometryMethod">Medición geodésica sobre el elipsoide WGS84 (PROJ/Geod) y validación topológica (Shapely), sin reparaciones automáticas.</p>}
    </section>
  );
}
