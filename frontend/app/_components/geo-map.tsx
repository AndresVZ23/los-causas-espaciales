"use client";

import * as maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";

maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

type Point = { latitude: number; longitude: number; label: string };

export default function GeoMap({ sites, onPick }: { sites: Point[]; onPick: (latitude: number, longitude: number) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const onPickRef = useRef(onPick);

  useEffect(() => { onPickRef.current = onPick; }, [onPick]);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm-dark", type: "raster", source: "osm", minzoom: 0, maxzoom: 19 }],
      },
      center: [-71.15, -16.8],
      zoom: 6,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
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
    if (sites.length > 1) {
      const bounds = new maplibregl.LngLatBounds();
      sites.forEach((site) => bounds.extend([site.longitude, site.latitude]));
      map.fitBounds(bounds, { padding: 96, maxZoom: 7, duration: 650 });
    }
  }, [sites]);

  return <div ref={container} className="geoMap" aria-label="Mapa interactivo con las ubicaciones configuradas" />;
}
