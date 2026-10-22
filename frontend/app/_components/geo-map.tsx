"use client";

import * as maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";

maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

type Point = { latitude: number; longitude: number; label: string };
export type TerrainOverlay = { url: string; bounds: [number, number, number, number] };

export default function GeoMap({ sites, onPick, terrainOverlay, showTerrain }: { sites: Point[]; onPick: (latitude: number, longitude: number) => void; terrainOverlay: TerrainOverlay | null; showTerrain: boolean }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const onPickRef = useRef(onPick);
  const sitesRef = useRef(sites);

  useEffect(() => { onPickRef.current = onPick; }, [onPick]);
  useEffect(() => { sitesRef.current = sites; }, [sites]);

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
        layers: [{ id: "nasa-blue-marble", type: "raster", source: "nasaGibs", minzoom: 0, maxzoom: 8, paint: { "raster-brightness-max": 0.76, "raster-contrast": 0.16, "raster-saturation": -0.04 } }],
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
    });
    map.on("click", (event) => onPickRef.current(+event.lngLat.lat.toFixed(5), +event.lngLat.lng.toFixed(5)));
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

  return <div ref={container} className="geoMap" aria-label={`Mapa interactivo con las ubicaciones configuradas${showTerrain ? " y vista previa NASADEM" : ""}`} />;
}
