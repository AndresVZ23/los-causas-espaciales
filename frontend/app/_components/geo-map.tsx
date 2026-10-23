"use client";

import * as maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import type { StudyShape } from "./geojson-import";
import type { VisualLayerState } from "./types";
import type { Draft } from "./use-study-geometries";

const VISUAL_SOURCE = "visual-gibs";
const VISUAL_LAYER = "visual-gibs-layer";

maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

type Point = { latitude: number; longitude: number; label: string };
export type TerrainOverlay = { url: string; bounds: [number, number, number, number] };
// Geometrías de estudio (corredores y polígonos) y el borrador en curso; coordenadas GeoJSON longitud-latitud.
export type MapGeometry = { id: string; name: string; geometry: StudyShape; valid: boolean };
export type MapDrawing = { draft: Draft | null; onVertex: (longitude: number, latitude: number) => void; onFinish: () => void };
// Territorios oficiales elegidos y la grilla de tendencias por celda (color y opacidad ya calculados por la consola).
export type MapTerritory = { id: string; label: string; geometry: GeoJSON.Geometry };
export type MapCell = { id: string; bounds: [number, number, number, number]; color: string; opacity: number; significant: boolean; label: string };

const STUDY_COLOR = "#b49cff"; // distinto de los sitios (cian y blanco) y de los colores de estado
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function whenReady(map: maplibregl.Map, run: () => void) {
  if (map.isStyleLoaded()) run();
  else map.once("load", run);
}

function draftFeatures(draft: Draft | null): GeoJSON.FeatureCollection {
  if (!draft || !draft.vertices.length) return EMPTY;
  const path = draft.kind === "polygon" && draft.vertices.length > 2 ? [...draft.vertices, draft.vertices[0]] : draft.vertices;
  return {
    type: "FeatureCollection",
    features: [
      ...(path.length > 1 ? [{ type: "Feature" as const, properties: {}, geometry: { type: "LineString" as const, coordinates: path } }] : []),
      ...draft.vertices.map((vertex) => ({ type: "Feature" as const, properties: {}, geometry: { type: "Point" as const, coordinates: vertex } })),
    ],
  };
}

function cellFeatures(cells: MapCell[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: cells.map((cell) => {
      const [west, south, east, north] = cell.bounds;
      return {
        type: "Feature", properties: { color: cell.color, opacity: cell.opacity, significant: cell.significant, label: cell.label },
        geometry: { type: "Polygon", coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]] },
      };
    }),
  };
}

export default function GeoMap({ sites, onPick, terrainOverlay, showTerrain, geometries = [], selectedGeometry = null, drawing = null, visualLayer = null, territories = [], cells = [] }: {
  sites: Point[]; onPick: (latitude: number, longitude: number) => void; terrainOverlay: TerrainOverlay | null; showTerrain: boolean;
  geometries?: MapGeometry[]; selectedGeometry?: string | null; drawing?: MapDrawing | null; visualLayer?: VisualLayerState | null;
  territories?: MapTerritory[]; cells?: MapCell[];
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const onPickRef = useRef(onPick);
  const sitesRef = useRef(sites);
  const drawingRef = useRef(drawing);

  useEffect(() => { onPickRef.current = onPick; }, [onPick]);
  useEffect(() => { sitesRef.current = sites; }, [sites]);
  useEffect(() => { drawingRef.current = drawing; }, [drawing]);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {
          nasaGibs: {
            type: "raster",
            tiles: ["https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg"],
            tileSize: 256,
            maxzoom: 8,
            attribution: "NASA EOSDIS GIBS · Blue Marble",
          },
        },
        // Sin tope de zoom en la capa: la fuente llega a 8 y MapLibre amplía esa tesela al acercarse a terrenos pequeños.
        layers: [{ id: "nasa-blue-marble", type: "raster", source: "nasaGibs", minzoom: 0, paint: { "raster-brightness-max": 0.76, "raster-contrast": 0.16, "raster-saturation": -0.04 } }],
      },
      center: [-71.15, -16.8],
      zoom: 6,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      map.addSource("comparison-axis", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: sitesRef.current.map((site) => [site.longitude, site.latitude]) },
        },
      });
      map.addLayer({ id: "comparison-axis-line", type: "line", source: "comparison-axis", paint: { "line-color": "#38d9c3", "line-width": 1.5, "line-dasharray": [2, 2] } });
      map.addSource("cells", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "cells-fill", type: "fill", source: "cells", paint: { "fill-color": ["get", "color"], "fill-opacity": ["get", "opacity"] } });
      map.addLayer({ id: "cells-line", type: "line", source: "cells",
        paint: { "line-color": ["case", ["get", "significant"], ["get", "color"], "#818b94"], "line-width": 1, "line-opacity": 0.8, "line-dasharray": [2, 2] } });
      map.addSource("territories", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "territories-fill", type: "fill", source: "territories", paint: { "fill-color": "#e8eaed", "fill-opacity": 0.05 } });
      map.addLayer({ id: "territories-line", type: "line", source: "territories", paint: { "line-color": "#e8eaed", "line-width": 1.6 } });
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
      map.on("mousemove", "cells-fill", (event) => {
        const label = event.features?.[0]?.properties?.label;
        if (label) popup.setLngLat(event.lngLat).setText(String(label)).addTo(map);
      });
      map.on("mouseleave", "cells-fill", () => popup.remove());
      map.addSource("study", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "study-fill", type: "fill", source: "study", filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": STUDY_COLOR, "fill-opacity": ["case", ["get", "selected"], 0.28, 0.14] } });
      map.addLayer({ id: "study-line", type: "line", source: "study",
        paint: { "line-color": ["case", ["get", "valid"], STUDY_COLOR, "#ee7180"], "line-width": ["case", ["get", "selected"], 3.5, 2] } });
      map.addSource("draft", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "draft-line", type: "line", source: "draft", filter: ["==", ["geometry-type"], "LineString"], paint: { "line-color": STUDY_COLOR, "line-width": 2, "line-dasharray": [1.5, 1.5] } });
      map.addLayer({ id: "draft-vertex", type: "circle", source: "draft", filter: ["==", ["geometry-type"], "Point"],
        paint: { "circle-radius": 5, "circle-color": STUDY_COLOR, "circle-stroke-color": "#080c0d", "circle-stroke-width": 2 } });
    });
    // En modo dibujo el clic agrega vértices; fuera de él, mueve el sitio principal como antes.
    map.on("click", (event) => {
      const active = drawingRef.current;
      if (active?.draft) active.onVertex(event.lngLat.lng, event.lngLat.lat);
      else onPickRef.current(+event.lngLat.lat.toFixed(5), +event.lngLat.lng.toFixed(5));
    });
    map.on("dblclick", (event) => {
      if (!drawingRef.current?.draft) return;
      event.preventDefault(); // sin zoom: el doble clic termina la geometría
      drawingRef.current.onFinish();
    });
    mapRef.current = map;
    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = sites.map((site, index) =>
      new maplibregl.Marker({ color: index === 0 ? "#38d9c7" : "#f2f2f3" })
        .setLngLat([site.longitude, site.latitude])
        .setPopup(new maplibregl.Popup({ offset: 22 }).setText(site.label))
        .addTo(map),
    );
    const comparisonSource = map.getSource("comparison-axis") as maplibregl.GeoJSONSource | undefined;
    comparisonSource?.setData({
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: sites.map((site) => [site.longitude, site.latitude]) },
    });
    if (sites.length > 1) {
      const bounds = new maplibregl.LngLatBounds();
      sites.forEach((site) => bounds.extend([site.longitude, site.latitude]));
      map.fitBounds(bounds, { padding: 96, maxZoom: 7, duration: 650 });
    }
  }, [sites]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    whenReady(map, () => {
      (map.getSource("study") as maplibregl.GeoJSONSource | undefined)?.setData({
        type: "FeatureCollection",
        features: geometries.map((item) => ({ type: "Feature", properties: { name: item.name, valid: item.valid, selected: item.id === selectedGeometry }, geometry: item.geometry })),
      });
    });
  }, [geometries, selectedGeometry]);

  useEffect(() => {
    const map = mapRef.current;
    const target = geometries.find((item) => item.id === selectedGeometry);
    if (!map || !target) return;
    const bounds = new maplibregl.LngLatBounds();
    (target.geometry.type === "LineString" ? target.geometry.coordinates : target.geometry.coordinates.flat()).forEach((vertex) => bounds.extend(vertex));
    map.fitBounds(bounds, { padding: 72, maxZoom: 11, duration: 650 });
    // Solo al cambiar la selección: renombrar o revalidar no debe mover el mapa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedGeometry]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const draft = drawing?.draft ?? null;
    whenReady(map, () => (map.getSource("draft") as maplibregl.GeoJSONSource | undefined)?.setData(draftFeatures(draft)));
    map.getCanvas().style.cursor = draft ? "crosshair" : "";
  }, [drawing?.draft]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    whenReady(map, () => {
      (map.getSource("territories") as maplibregl.GeoJSONSource | undefined)?.setData({
        type: "FeatureCollection", features: territories.map((item) => ({ type: "Feature", properties: { label: item.label }, geometry: item.geometry })),
      });
    });
    if (!territories.length) return;
    // Encuadra los territorios y los sitios juntos al cambiar la selección.
    const bounds = new maplibregl.LngLatBounds();
    const walk = (coordinates: unknown): void => {
      if (Array.isArray(coordinates) && typeof coordinates[0] === "number") bounds.extend(coordinates as [number, number]);
      else if (Array.isArray(coordinates)) coordinates.forEach(walk);
    };
    territories.forEach((item) => "coordinates" in item.geometry && walk(item.geometry.coordinates));
    sitesRef.current.forEach((site) => bounds.extend([site.longitude, site.latitude]));
    map.fitBounds(bounds, { padding: 60, maxZoom: 9, duration: 650 });
  }, [territories]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    whenReady(map, () => (map.getSource("cells") as maplibregl.GeoJSONSource | undefined)?.setData(cellFeatures(cells)));
  }, [cells]);

  // Capa visual GIBS: sobre el mapa base y bajo todo lo demás. Cambiar solo la opacidad no recarga teselas.
  const visualUrl = visualLayer ? visualLayer.layer.tile_url.replace("{time}", visualLayer.date) : null;
  const visualZoom = visualLayer?.layer.max_zoom ?? null;
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    whenReady(map, () => {
      if (map.getLayer(VISUAL_LAYER)) map.removeLayer(VISUAL_LAYER);
      if (map.getSource(VISUAL_SOURCE)) map.removeSource(VISUAL_SOURCE);
      if (!visualUrl || visualZoom == null) return;
      map.addSource(VISUAL_SOURCE, { type: "raster", tiles: [visualUrl], tileSize: 256, maxzoom: visualZoom, attribution: "NASA EOSDIS GIBS" });
      const above = ["nasadem-preview-layer", "comparison-axis-line"].find((id) => map.getLayer(id));
      map.addLayer({ id: VISUAL_LAYER, type: "raster", source: VISUAL_SOURCE, paint: { "raster-opacity": visualLayer?.opacity ?? 0.75 } }, above);
    });
    // La opacidad se aplica en su propio efecto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visualUrl, visualZoom]);
  const visualOpacity = visualLayer?.opacity ?? null;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || visualOpacity == null) return;
    whenReady(map, () => { if (map.getLayer(VISUAL_LAYER)) map.setPaintProperty(VISUAL_LAYER, "raster-opacity", visualOpacity); });
  }, [visualOpacity]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const sourceId = "nasadem-preview";
    const layerId = "nasadem-preview-layer";
    const syncOverlay = () => {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      if (!terrainOverlay || !showTerrain) return;
      const [west, south, east, north] = terrainOverlay.bounds;
      map.addSource(sourceId, {
        type: "image",
        url: terrainOverlay.url,
        coordinates: [[west, north], [east, north], [east, south], [west, south]],
      });
      map.addLayer({
        id: layerId,
        type: "raster",
        source: sourceId,
        paint: { "raster-opacity": 0.58, "raster-contrast": 0.22, "raster-saturation": -0.35 },
      }, map.getLayer("comparison-axis-line") ? "comparison-axis-line" : undefined);
    };
    if (map.loaded()) syncOverlay();
    else map.once("load", syncOverlay);
    return () => {
      if (!map.getStyle()) return;
      if (map.getLayer(layerId)) map.removeLayer(layerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    };
  }, [terrainOverlay, showTerrain]);

  const described = [geometries.length ? `${geometries.length} geometría(s) de estudio` : "", showTerrain ? "vista previa NASADEM" : ""].filter(Boolean).join(" y ");
  return <div ref={container} className="geoMap" aria-label={`Mapa interactivo con las ubicaciones configuradas${described ? ` y ${described}` : ""}${drawing?.draft ? ". Modo dibujo activo" : ""}`} />;
}
