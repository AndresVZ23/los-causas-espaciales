"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { GeoJsonImportError, MAX_FILE_BYTES, kindOf, parseGeoJson, toFeatureCollection } from "./geojson-import";
import type { Position, StudyKind, StudyShape } from "./geojson-import";

// Respuesta de POST /api/v1/geospatial/inspect (medición geodésica WGS84 con PROJ/Geod y validación con Shapely).
export type GeometryInspection = {
  geometry_type: "Point" | "LineString" | "Polygon"; centroid: { latitude: number; longitude: number }; bounding_box: [number, number, number, number];
  length_km: number | null; area_km2: number | null; vertex_count: number; provenance: string; method: string; limitations: string[];
};
export type StudyGeometry = {
  id: string; name: string; kind: StudyKind; geometry: StudyShape; origin: string;
  status: "validando" | "valida" | "invalida"; inspection: GeometryInspection | null; error: string | null;
};
export type Draft = { kind: StudyKind; vertices: Position[] };

const COORDINATE_DIGITS = 6; // ~0,1 m: más precisión que la del clic sobre el mapa no aporta
const MIN_VERTICES: Record<StudyKind, number> = { segment: 2, polygon: 3 };
export const KIND_LABEL: Record<StudyKind, string> = { segment: "Corredor", polygon: "Polígono" };

function errorText(payload: unknown): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : String(item))).join(" · ");
  }
  return "La API no pudo validar la geometría.";
}

export function useStudyGeometries() {
  const [geometries, setGeometries] = useState<StudyGeometry[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "info" | "error"; lines: string[] } | null>(null);
  const counter = useRef(0);

  const inspect = useCallback(async (id: string, geometry: StudyShape) => {
    try {
      const response = await fetch("/api/geometry-inspect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ geometry }) });
      const payload = await response.json().catch(() => null);
      setGeometries((current) => current.map((item) => item.id !== id ? item : response.ok
        ? { ...item, status: "valida", inspection: payload as GeometryInspection, error: null }
        : { ...item, status: "invalida", inspection: null, error: errorText(payload) }));
    } catch {
      setGeometries((current) => current.map((item) => item.id === id ? { ...item, status: "invalida", error: "Sin conexión con la API de validación." } : item));
    }
  }, []);

  const add = useCallback((entries: { name: string; geometry: StudyShape; origin: string }[]) => {
    const created = entries.map((entry) => {
      counter.current += 1;
      return { id: `geom-${counter.current}`, name: entry.name, kind: kindOf(entry.geometry), geometry: entry.geometry, origin: entry.origin, status: "validando" as const, inspection: null, error: null };
    });
    setGeometries((current) => [...current, ...created]);
    setSelectedId(created[created.length - 1]?.id ?? null);
    created.forEach((item) => inspect(item.id, item.geometry));
  }, [inspect]);

  // Espejo síncrono del borrador: el doble clic del mapa llega antes de que React vuelva a renderizar.
  const draftRef = useRef<Draft | null>(null);
  const drawnCount = useRef<Record<StudyKind, number>>({ segment: 0, polygon: 0 });
  const updateDraft = useCallback((next: Draft | null) => { draftRef.current = next; setDraft(next); }, []);

  const startDraft = useCallback((kind: StudyKind) => { updateDraft({ kind, vertices: [] }); setNotice(null); }, [updateDraft]);
  const cancelDraft = useCallback(() => updateDraft(null), [updateDraft]);
  const addVertex = useCallback((longitude: number, latitude: number) => {
    const current = draftRef.current;
    if (!current) return;
    const vertex: Position = [+longitude.toFixed(COORDINATE_DIGITS), +latitude.toFixed(COORDINATE_DIGITS)];
    const last = current.vertices[current.vertices.length - 1];
    if (last && last[0] === vertex[0] && last[1] === vertex[1]) return; // el segundo clic de un doble clic
    updateDraft({ ...current, vertices: [...current.vertices, vertex] });
  }, [updateDraft]);
  const undoVertex = useCallback(() => {
    const current = draftRef.current;
    if (current) updateDraft({ ...current, vertices: current.vertices.slice(0, -1) });
  }, [updateDraft]);
  const canFinish = draft !== null && draft.vertices.length >= MIN_VERTICES[draft.kind];

  const finishDraft = useCallback(() => {
    const current = draftRef.current;
    if (!current || current.vertices.length < MIN_VERTICES[current.kind]) return;
    drawnCount.current[current.kind] += 1;
    const geometry: StudyShape = current.kind === "segment"
      ? { type: "LineString", coordinates: current.vertices }
      : { type: "Polygon", coordinates: [[...current.vertices, current.vertices[0]]] };
    add([{ name: `${KIND_LABEL[current.kind]} ${drawnCount.current[current.kind]}`, geometry, origin: "Dibujado en el mapa" }]);
    updateDraft(null);
  }, [add, updateDraft]);

  const importFile = useCallback(async (file: File) => {
    if (file.size > MAX_FILE_BYTES) { setNotice({ tone: "error", lines: [`«${file.name}» pesa más de 2 MB; simplifique la geometría antes de cargarla.`] }); return; }
    try {
      const { items, notes } = parseGeoJson(await file.text(), file.name);
      add(items.map((item) => ({ ...item, origin: `Archivo ${file.name}` })));
      setNotice({ tone: "info", lines: [`${items.length} geometría(s) cargada(s) de «${file.name}».`, ...notes] });
    } catch (error) {
      setNotice({ tone: "error", lines: [error instanceof GeoJsonImportError ? error.message : "No se pudo leer el archivo."] });
    }
  }, [add]);

  // Teclado: Escape cancela y Enter termina, mientras haya un borrador activo.
  const drafting = draft !== null;
  useEffect(() => {
    if (!drafting) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement) return;
      if (event.key === "Escape") cancelDraft();
      if (event.key === "Enter") finishDraft();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drafting, cancelDraft, finishDraft]);

  const remove = useCallback((id: string) => {
    setGeometries((current) => current.filter((item) => item.id !== id));
    setSelectedId((current) => (current === id ? null : current));
  }, []);
  const rename = useCallback((id: string, name: string) => setGeometries((current) => current.map((item) => item.id === id ? { ...item, name } : item)), []);

  const exportGeoJson = useCallback(() => {
    const valid = geometries.filter((item) => item.status === "valida" && item.inspection);
    if (!valid.length) return;
    const collection = toFeatureCollection(valid.map((item) => ({
      name: item.name, kind: item.kind, origin: item.origin, geometry: item.geometry,
      length_km: item.inspection!.length_km, area_km2: item.inspection!.area_km2,
    })));
    const url = URL.createObjectURL(new Blob([JSON.stringify(collection, null, 2)], { type: "application/geo+json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `geometrias-estudio-${new Date().toLocaleDateString("en-CA")}.geojson`; anchor.click();
    URL.revokeObjectURL(url);
  }, [geometries]);

  return {
    geometries, draft, selectedId, notice, canFinish,
    startDraft, cancelDraft, addVertex, undoVertex, finishDraft, importFile, remove, rename, select: setSelectedId, exportGeoJson,
    dismissNotice: () => setNotice(null),
  };
}

export type StudyGeometriesState = ReturnType<typeof useStudyGeometries>;
