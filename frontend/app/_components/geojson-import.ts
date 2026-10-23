// Lectura estricta de GeoJSON (RFC 7946: WGS84, longitud-latitud) para corredores y polígonos de estudio.
// Nunca repara en silencio: rechaza con un mensaje accionable o separa partes y lo declara en `notes`.

export type Position = [number, number];
export type StudyKind = "segment" | "polygon";
export type StudyShape = { type: "LineString"; coordinates: Position[] } | { type: "Polygon"; coordinates: Position[][] };
export type ParsedGeometry = { name: string; geometry: StudyShape };
export type ParseResult = { items: ParsedGeometry[]; notes: string[] };

export const MAX_FILE_BYTES = 2_000_000;
export const MAX_GEOMETRIES = 12;
export const MAX_VERTICES = 5_000;
const WGS84_CRS = /CRS84|EPSG:+4326|EPSG::4326/i;

export class GeoJsonImportError extends Error {}

export const kindOf = (shape: StudyShape): StudyKind => (shape.type === "LineString" ? "segment" : "polygon");

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json => typeof value === "object" && value !== null && !Array.isArray(value);

function position(raw: unknown, notes: Set<string>): Position {
  if (!Array.isArray(raw) || raw.length < 2 || !raw.every((value) => typeof value === "number" && Number.isFinite(value))) {
    throw new GeoJsonImportError("Hay una coordenada que no es un par numérico [longitud, latitud].");
  }
  if (raw.length > 2) notes.add("Se ignoró la altura (tercera coordenada): el análisis es planimétrico.");
  const [lon, lat] = raw as number[];
  if (Math.abs(lon) > 180 || Math.abs(lat) > 90) {
    throw new GeoJsonImportError("Coordenadas fuera del rango WGS84. ¿Están en un CRS proyectado (por ejemplo UTM)? Reproyecte a EPSG:4326 antes de cargar.");
  }
  return [lon, lat];
}

function line(raw: unknown, notes: Set<string>): Position[] {
  if (!Array.isArray(raw)) throw new GeoJsonImportError("Un LineString debe tener una lista de coordenadas.");
  const points = raw.map((item) => position(item, notes));
  if (points.length < 2) throw new GeoJsonImportError("Un corredor necesita al menos dos vértices.");
  return points;
}

function rings(raw: unknown, notes: Set<string>): Position[][] {
  if (!Array.isArray(raw) || raw.length === 0) throw new GeoJsonImportError("Un Polygon debe tener al menos un anillo.");
  return raw.map((ringRaw) => {
    const ring = line(ringRaw, notes);
    const [first, last] = [ring[0], ring[ring.length - 1]];
    if (ring.length < 4) throw new GeoJsonImportError("Cada anillo de polígono necesita al menos cuatro posiciones (tres vértices y el cierre).");
    if (first[0] !== last[0] || first[1] !== last[1]) throw new GeoJsonImportError("Hay un anillo abierto: la última posición debe repetir la primera (RFC 7946). No se cierra automáticamente.");
    return ring;
  });
}

function collect(geometry: unknown, name: string, out: ParsedGeometry[], notes: Set<string>) {
  if (!isObject(geometry)) throw new GeoJsonImportError("Se esperaba un objeto de geometría GeoJSON.");
  const { type, coordinates } = geometry;
  switch (type) {
    case "LineString": out.push({ name, geometry: { type, coordinates: line(coordinates, notes) } }); return;
    case "Polygon": out.push({ name, geometry: { type, coordinates: rings(coordinates, notes) } }); return;
    case "MultiLineString":
    case "MultiPolygon": {
      if (!Array.isArray(coordinates)) throw new GeoJsonImportError(`${type} sin coordenadas.`);
      const single = type === "MultiLineString" ? "LineString" : "Polygon";
      if (coordinates.length > 1) notes.add(`${name}: ${type} separado en ${coordinates.length} partes; cada parte se valida y mide por separado.`);
      coordinates.forEach((part, index) => collect({ type: single, coordinates: part }, coordinates.length > 1 ? `${name} · parte ${index + 1}` : name, out, notes));
      return;
    }
    case "GeometryCollection":
      (Array.isArray(geometry.geometries) ? geometry.geometries : []).forEach((item, index) => collect(item, `${name} · ${index + 1}`, out, notes));
      return;
    case "Point":
    case "MultiPoint":
      notes.add("Los puntos del archivo se ignoraron: los sitios se editan en la lista de ubicaciones.");
      return;
    default:
      throw new GeoJsonImportError(`Tipo de geometría no admitido: ${String(type)}.`);
  }
}

function featureName(feature: Json, fallback: string): string {
  const properties = isObject(feature.properties) ? feature.properties : {};
  const value = properties.name ?? properties.nombre ?? properties.NAME ?? properties.Nombre;
  return typeof value === "string" && value.trim() ? value.trim().slice(0, 60) : fallback;
}

// Orden de ejes invertido: con todas las posiciones en el rango del Perú leído como (latitud, longitud).
function looksSwappedForPeru(items: ParsedGeometry[]): boolean {
  const positions = items.flatMap((item) => (item.geometry.type === "LineString" ? item.geometry.coordinates : item.geometry.coordinates.flat()));
  return positions.length > 0 && positions.every(([x, y]) => x >= -19 && x <= 0.5 && y >= -82 && y <= -68);
}

export function parseGeoJson(text: string, fileName: string): ParseResult {
  let data: unknown;
  try { data = JSON.parse(text); } catch { throw new GeoJsonImportError("El archivo no es JSON válido."); }
  if (!isObject(data)) throw new GeoJsonImportError("El archivo no contiene un objeto GeoJSON.");
  const notes = new Set<string>();
  if (data.crs !== undefined) {
    const crsName = isObject(data.crs) && isObject(data.crs.properties) ? String(data.crs.properties.name ?? "") : "";
    if (!WGS84_CRS.test(crsName)) throw new GeoJsonImportError(`El archivo declara el CRS «${crsName || "desconocido"}». Reproyecte a WGS84 (EPSG:4326, longitud-latitud) antes de cargar.`);
    notes.add("El miembro «crs» es heredado (RFC 7946 lo eliminó); declaraba WGS84 y se ignoró.");
  }
  const base = fileName.replace(/\.(geo)?json$/i, "") || "Geometría";
  const items: ParsedGeometry[] = [];
  if (data.type === "FeatureCollection") {
    const features = Array.isArray(data.features) ? data.features : [];
    features.forEach((feature, index) => {
      if (!isObject(feature)) throw new GeoJsonImportError("Hay un elemento de «features» que no es un Feature.");
      if (feature.geometry === null) { notes.add("Se ignoró un Feature sin geometría."); return; }
      collect(feature.geometry, featureName(feature, `${base} ${index + 1}`), items, notes);
    });
  } else if (data.type === "Feature") {
    collect(data.geometry, featureName(data, base), items, notes);
  } else {
    collect(data, base, items, notes);
  }
  if (items.length === 0) throw new GeoJsonImportError("El archivo no contiene corredores (LineString) ni polígonos (Polygon).");
  if (items.length > MAX_GEOMETRIES) throw new GeoJsonImportError(`El archivo trae ${items.length} geometrías; el máximo por carga es ${MAX_GEOMETRIES}.`);
  const tooDense = items.find((item) => (item.geometry.type === "LineString" ? item.geometry.coordinates.length : item.geometry.coordinates.flat().length) > MAX_VERTICES);
  if (tooDense) throw new GeoJsonImportError(`«${tooDense.name}» tiene más de ${MAX_VERTICES.toLocaleString("es-PE")} vértices; simplifíquelo antes de cargar.`);
  if (looksSwappedForPeru(items)) throw new GeoJsonImportError("Las coordenadas parecen estar en orden latitud, longitud. GeoJSON exige longitud, latitud (RFC 7946).");
  return { items, notes: [...notes] };
}

export function toFeatureCollection(entries: { name: string; kind: StudyKind; origin: string; geometry: StudyShape; length_km: number | null; area_km2: number | null }[]) {
  return {
    type: "FeatureCollection" as const,
    features: entries.map(({ geometry, ...properties }) => ({ type: "Feature" as const, properties: { ...properties, reference_system: "WGS84 · longitud, latitud (RFC 7946)", provenance: "USER_ASSUMPTION" }, geometry })),
  };
}
