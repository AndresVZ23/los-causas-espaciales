"use client";

import { useEffect, useState } from "react";
import { formatNumber } from "./format";
import type { TerritoryLevel, TerritoryPick, TerritorySummary } from "./types";

const LEVEL_LABEL: Record<TerritoryLevel, string> = { department: "Departamento", province: "Provincia", district: "Distrito" };
const context = (item: TerritorySummary) => [LEVEL_LABEL[item.level], item.province, item.department].filter((part, index, all) => part && all.indexOf(part) === index && part !== item.name).join(" · ");

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`/api/territories/${path}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "No se pudo consultar el catálogo territorial.");
  return payload as T;
}

export default function TerritoryPicker({ onAdd, disabled, chosen }: { onAdd: (pick: TerritoryPick) => void; disabled: boolean; chosen: string[] }) {
  const [mode, setMode] = useState<"buscar" | "niveles">("buscar");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TerritorySummary[]>([]);
  const [departments, setDepartments] = useState<TerritorySummary[]>([]);
  const [provinces, setProvinces] = useState<TerritorySummary[]>([]);
  const [districts, setDistricts] = useState<TerritorySummary[]>([]);
  const [selection, setSelection] = useState<{ department?: string; province?: string; district?: string }>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Búsqueda con espera corta: no consulta en cada tecla.
  useEffect(() => {
    if (mode !== "buscar" || query.trim().length < 2) { setResults([]); return; }
    const timer = window.setTimeout(() => {
      getJson<{ results: TerritorySummary[] }>(`search?q=${encodeURIComponent(query.trim())}&limit=8`)
        .then((payload) => { setResults(payload.results); setError(""); })
        .catch((exception: Error) => setError(exception.message));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query, mode]);

  useEffect(() => {
    if (mode !== "niveles" || departments.length) return;
    getJson<{ children: TerritorySummary[] }>("hierarchy").then((payload) => setDepartments(payload.children)).catch((exception: Error) => setError(exception.message));
  }, [mode, departments.length]);

  async function chooseDepartment(ubigeo: string) {
    setSelection({ department: ubigeo }); setProvinces([]); setDistricts([]);
    if (ubigeo) setProvinces((await getJson<{ children: TerritorySummary[] }>(`hierarchy?parent_ubigeo=${ubigeo}`)).children);
  }
  async function chooseProvince(ubigeo: string) {
    setSelection((current) => ({ department: current.department, province: ubigeo })); setDistricts([]);
    if (ubigeo) setDistricts((await getJson<{ children: TerritorySummary[] }>(`hierarchy?parent_ubigeo=${ubigeo}`)).children);
  }

  async function add(item: TerritorySummary) {
    setBusy(true); setError("");
    try {
      const geometry = await getJson<{ feature: { geometry: GeoJSON.Geometry } }>(`${item.level}/${item.ubigeo}/geometry`);
      onAdd({ level: item.level, ubigeo: item.ubigeo, name: item.name, context: context(item), geometry: geometry.feature.geometry });
      setQuery(""); setResults([]);
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "No se pudo cargar el límite.");
    } finally {
      setBusy(false);
    }
  }

  const levelPick = [...districts, ...provinces, ...departments].find((item) => item.ubigeo === (selection.district || selection.province || selection.department));
  return (
    <div className="territoryPicker">
      <div className="territoryModes" role="group" aria-label="Forma de elegir el territorio">
        <button className={mode === "buscar" ? "active" : ""} aria-pressed={mode === "buscar"} onClick={() => setMode("buscar")}>Buscar</button>
        <button className={mode === "niveles" ? "active" : ""} aria-pressed={mode === "niveles"} onClick={() => setMode("niveles")}>Por niveles</button>
      </div>
      {mode === "buscar" ? (
        <>
          <label className="srOnly" htmlFor="buscar-territorio">Buscar departamento, provincia o distrito</label>
          <input id="buscar-territorio" className="territorySearch" value={query} placeholder="Departamento, provincia, distrito o ubigeo" onChange={(event) => setQuery(event.target.value)} />
          {results.length > 0 && (
            <ul className="territoryResults" role="listbox" aria-label="Territorios encontrados">
              {results.map((item) => (
                <li key={`${item.level}-${item.ubigeo}`}>
                  <button disabled={disabled || busy || chosen.includes(item.ubigeo)} onClick={() => add(item)}>
                    <b>{item.name}</b><span>{context(item)} · {item.ubigeo} · {formatNumber(item.area_sqkm, 0)} km²</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <div className="territoryLevels">
          {/* Etiquetas explícitas: si el select va dentro de la etiqueta, su nombre accesible arrastra el texto de la opción. */}
          <div className="territoryField">
            <label htmlFor="nivel-departamento">Departamento</label>
            <select id="nivel-departamento" value={selection.department ?? ""} onChange={(event) => chooseDepartment(event.target.value)}>
              <option value="">Elegir…</option>{departments.map((item) => <option key={item.ubigeo} value={item.ubigeo}>{item.name}</option>)}
            </select>
          </div>
          <div className="territoryField">
            <label htmlFor="nivel-provincia">Provincia</label>
            <select id="nivel-provincia" value={selection.province ?? ""} disabled={!provinces.length} onChange={(event) => chooseProvince(event.target.value)}>
              <option value="">Todo el departamento</option>{provinces.map((item) => <option key={item.ubigeo} value={item.ubigeo}>{item.name}</option>)}
            </select>
          </div>
          <div className="territoryField">
            <label htmlFor="nivel-distrito">Distrito</label>
            <select id="nivel-distrito" value={selection.district ?? ""} disabled={!districts.length} onChange={(event) => setSelection((current) => ({ ...current, district: event.target.value || undefined }))}>
              <option value="">Toda la provincia</option>{districts.map((item) => <option key={item.ubigeo} value={item.ubigeo}>{item.name}</option>)}
            </select>
          </div>
          <button className="territoryAdd" disabled={!levelPick || disabled || busy || chosen.includes(levelPick.ubigeo)} onClick={() => levelPick && add(levelPick)}>
            {levelPick ? `Agregar ${levelPick.name}` : "Elija un territorio"}
          </button>
        </div>
      )}
      {disabled && <p className="territoryHint">Máximo 4 sujetos entre sitios y territorios: quite uno para agregar otro.</p>}
      {error && <p className="errorMessage" role="alert">{error}</p>}
    </div>
  );
}
