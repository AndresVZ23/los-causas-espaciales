"use client";

import * as maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { CONTINENTS, HEAT_LABEL, type Continent, type Hero, type Mission, type NasaLayer, type Stage } from "./game-types";
import { HeroAvatar } from "./hero-avatar";
import { Ship } from "./ship";
import { Hero3D } from "./hero-3d";
import { metersBetween, offset, type Checkpoint } from "./mission-logic";
import { Planet2045 } from "./planet-2045";

maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

// Lejos: la Tierra de NASA (Blue Marble). Cerca: la foto satelital Sentinel-2 sin nubes y el relieve en 3D.
const BLUE_MARBLE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg";
const SENTINEL = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg";
const TERRAIN = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
const LABELS_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const SENTINEL_CREDIT = "Sentinel-2 cloudless 2016 (s2maps.eu, EOX, CC BY 4.0) · contiene datos Copernicus Sentinel modificados";

function baseStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    projection: { type: "globe" },
    sky: { "atmosphere-blend": 0 } as maplibregl.SkySpecification,
    sources: {
      nasa: { type: "raster", tiles: [BLUE_MARBLE], tileSize: 256, maxzoom: 8, attribution: "NASA EOSDIS GIBS · Blue Marble" },
      sentinel: { type: "raster", tiles: [SENTINEL], tileSize: 256, minzoom: 5, maxzoom: 14, attribution: SENTINEL_CREDIT },
      terrain: { type: "raster-dem", tiles: [TERRAIN], tileSize: 256, maxzoom: 14, encoding: "terrarium", attribution: "Relieve: AWS Terrain Tiles (Mapzen)" },
    },
    layers: [
      { id: "space", type: "background", paint: { "background-color": "#0c1a3a" } },
      { id: "blue-marble", type: "raster", source: "nasa", paint: { "raster-saturation": 0.2, "raster-contrast": 0.08 } },
      { id: "sentinel", type: "raster", source: "sentinel", minzoom: 5, paint: { "raster-opacity": ["interpolate", ["linear"], ["zoom"], 5.5, 0, 7.5, 1] } },
    ],
  };
}

/** Solo los nombres de países, ciudades y aguas de OpenStreetMap, en español y legibles sobre la foto. */
function withLabels(base: maplibregl.StyleSpecification, streets: maplibregl.StyleSpecification): maplibregl.StyleSpecification {
  const labels = streets.layers
    .filter((layer) => layer.type === "symbol" && (layer.id.startsWith("label_") || layer.id.startsWith("water_name")))
    .map((layer) => ({ ...layer, layout: { ...(layer as maplibregl.SymbolLayerSpecification).layout, "text-field": ["coalesce", ["get", "name:es"], ["get", "name"]] },
      paint: { ...(layer as maplibregl.SymbolLayerSpecification).paint, "text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,.75)", "text-halo-width": 1.4 } }) as unknown as maplibregl.LayerSpecification);
  // Vista de cerca: relieve sombreado y agua con su tono. Sin edificios en bloque: Nikol pidió ver la foto real, sin cajas.
  const near: maplibregl.LayerSpecification[] = [
    { id: "relief", type: "hillshade", source: "relief", minzoom: 8, paint: { "hillshade-exaggeration": 0.45, "hillshade-shadow-color": "#2d241f", "hillshade-highlight-color": "#fffaf0", "hillshade-accent-color": "#4a3c33" } },
    { id: "water-tint", type: "fill", source: "openmaptiles", "source-layer": "water", minzoom: 8, paint: { "fill-color": "#5f7f9f", "fill-opacity": 0.38 } },
    // Calles y carreteras de OpenStreetMap sobre la foto, como un mapa híbrido: por donde camina el héroe.
    { id: "game-roads", type: "line", source: "openmaptiles", "source-layer": "transportation", minzoom: 9,
      filter: ["match", ["get", "class"], ["motorway", "trunk", "primary", "secondary", "tertiary", "minor", "service", "track"], true, false],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["match", ["get", "class"], ["motorway", "trunk"], "#ffcf6e", "primary", "#ffe6a3", "#ffffff"],
        "line-opacity": ["interpolate", ["linear"], ["zoom"], 9, 0.45, 14, 0.8],
        "line-width": ["interpolate", ["exponential", 1.6], ["zoom"], 9, ["match", ["get", "class"], ["motorway", "trunk"], 1.2, 0.4], 16, ["match", ["get", "class"], ["motorway", "trunk"], 9, "primary", 7, ["secondary", "tertiary"], 5, 2.5]] } },
    { id: "game-road-names", type: "symbol", source: "openmaptiles", "source-layer": "transportation_name", minzoom: 13.5,
      layout: { "symbol-placement": "line", "text-field": ["coalesce", ["get", "name:es"], ["get", "name"]], "text-font": ["Noto Sans Regular"], "text-size": 11 },
      paint: { "text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,.8)", "text-halo-width": 1.4 } },
  ] as maplibregl.LayerSpecification[];
  return { ...base, glyphs: streets.glyphs, sprite: streets.sprite,
    light: { anchor: "map", color: "#fff4e0", intensity: 0.35, position: [1.4, 210, 40] },
    sources: { ...base.sources, openmaptiles: streets.sources.openmaptiles, relief: { type: "raster-dem", tiles: [TERRAIN], tileSize: 256, maxzoom: 13, encoding: "terrarium" } },
    layers: [...base.layers, ...near, ...labels] };
}

// Cielo con horizonte y bruma para la vista tipo dron dentro de una misión; en el espacio no se dibuja cielo.
const DAY_SKY = { "sky-color": "#6f9fd8", "horizon-color": "#e6edf3", "fog-color": "#dfe7ee", "sky-horizon-blend": 0.7, "horizon-fog-blend": 0.6, "fog-ground-blend": 0.15, "atmosphere-blend": 0 } as maplibregl.SkySpecification;
const SPACE_SKY = { "atmosphere-blend": 0 } as maplibregl.SkySpecification;

const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Escala de juego: en una ciudad todo está más cerca que en un paisaje. */
export function missionScale(mission: Mission) {
  const city = mission.scale !== "paisaje";
  // La foto Sentinel-2 tiene píxeles de 10 m: más allá del zoom 14 solo se estira y se ve borrosa.
  return { zoom: city ? 13.8 : 12.8, spread: city ? 1100 : 2600, reach: city ? 190 : 450, speed: city ? 300 : 650 };
}

/** Encuadre de cámara para cada momento del viaje. `panel` es el ancho que ocupa el panel lateral en pantalla. */
function frame(stage: Stage, continent: Continent | null, mission: Mission | null, panel: number, height: number) {
  // En pantallas angostas el panel ocupa la parte de abajo: el lugar se encuadra en la franja que queda arriba.
  const below = panel === 0 && (stage === "mision" || stage === "tierra") ? Math.round(height * (stage === "mision" ? 0.6 : 0.44)) : 0;
  const flat = { pitch: 0, bearing: 0 };
  if (stage === "mision" && mission) {
    return { center: [mission.longitude, mission.latitude] as [number, number], zoom: missionScale(mission).zoom, pitch: panel ? 72 : 58, bearing: 0,
      padding: { top: 0, bottom: below, left: 0, right: panel } };
  }
  // En la vista de continentes el panel está a la izquierda.
  if (stage === "tierra" && continent) {
    const found = CONTINENTS.find((item) => item.id === continent)!;
    return { ...flat, center: found.center, zoom: found.zoom - (below ? 0.6 : 0), padding: { top: 0, bottom: below, left: panel ? 346 : 0, right: 0 } };
  }
  if (stage === "tierra" || stage === "viaje") return { ...flat, center: [-40, 10] as [number, number], zoom: below ? 0.7 : 1.25, padding: { top: 0, bottom: below, left: panel ? 346 : 0, right: 0 } };
  // Desde la Luna: la Tierra pequeña y redonda, arriba, sobre el horizonte lunar.
  return { ...flat, center: [-60, 5] as [number, number], zoom: 0.35, padding: { top: 0, bottom: Math.round(height * 0.42), left: 0, right: 0 } };
}

interface Halo { x: number; y: number; r: number }
interface Screen { x: number; y: number }
const KEYS: Record<string, [number, number]> = { ArrowUp: [0, 1], KeyW: [0, 1], ArrowDown: [0, -1], KeyS: [0, -1], ArrowLeft: [-1, 0], KeyA: [-1, 0], ArrowRight: [1, 0], KeyD: [1, 0] };

export interface LiveAlert { id: string; kind: string; kind_label: string; level: string; title: string; place: string; started: string; updated: string; latitude: number; longitude: number; severity?: string; url?: string; also_seen_by?: string[] }

export function GameGlobe({ missions, stage, continent, mission, hero, panelWidth, completed, checkpoints, visited, vision, immersive, alerts, onAlert, onPick, onReach, planetHealth = null }: {
  missions: Mission[];
  stage: Stage;
  continent: Continent | null;
  mission: Mission | null;
  hero: Hero | null;
  panelWidth: number;
  completed: Set<string>;
  checkpoints: Checkpoint[];
  visited: Set<string>;
  /** Capa de NASA que se pinta sobre el globo y la fecha que se muestra. */
  vision: { layer: NasaLayer; date: string } | null;
  /** Dentro de una misión se muestra el mundo 3D (MissionWorld): el mapa solo acompaña de fondo. */
  immersive: boolean;
  /** Alertas reales de GDACS (cruzadas con NASA EONET) que se muestran como marcadores ⚠ en el globo. */
  alerts: LiveAlert[];
  onAlert: (alert: LiveAlert) => void;
  onPick: (mission: Mission) => void;
  /** Estado del planeta en 2045, de 0 (crisis) a 1 (sano): desde la Luna se dibuja la Tierra de 2045 (planet-2045.tsx). Nulo: el globo de siempre. */
  planetHealth?: number | null;
  onReach: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Map<string, { marker: maplibregl.Marker; element: HTMLButtonElement }>>(new Map());
  const [halo, setHalo] = useState<Halo | null>(null);
  const [planetReady, setPlanetReady] = useState(false);
  const show2045 = planetHealth != null && (stage === "luna" || stage === "viaje");
  useEffect(() => { if (!show2045) setPlanetReady(false); }, [show2045]);
  const onPickRef = useRef(onPick);
  const onReachRef = useRef(onReach);
  useEffect(() => { onPickRef.current = onPick; onReachRef.current = onReach; }, [onPick, onReach]);

  // Personaje en el lugar: posición real (longitud, latitud), hacia dónde mira y si está corriendo.
  const heroPos = useRef<[number, number] | null>(null);
  const [heroScreen, setHeroScreen] = useState<Screen | null>(null);
  const [pins, setPins] = useState<(Screen & { id: string })[]>([]);
  const [running, setRunning] = useState(false);
  const [facingLeft, setFacingLeft] = useState(false);
  const [heading, setHeading] = useState(0);
  const [use3d, setUse3d] = useState(true);
  // Llegada en nave: baja desde el globo, vuela rasante hacia el lugar, aterriza y el héroe sale.
  const [phase, setPhase] = useState<"off" | "descenso" | "vuelo" | "aterriza" | "suelo">("off");
  const landed = phase === "suelo";
  const phaseRef = useRef(phase);
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  const [ship, setShip] = useState<Screen | null>(null);
  const [speech, setSpeech] = useState<Checkpoint | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current, style: baseStyle(), center: [-60, 5], zoom: 0.35, minZoom: 0, maxZoom: 14.6, maxPitch: 80,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    // Nombres en español de OpenStreetMap (OpenFreeMap). Si no responde, el juego sigue sin nombres.
    fetch(LABELS_STYLE, { signal: AbortSignal.timeout(10_000) }).then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((streets: maplibregl.StyleSpecification) => { if (mapRef.current === map) map.setStyle(withLabels(baseStyle(), streets)); })
      .catch(() => { /* sin nombres */ });
    // Halo de atmósfera: sigue al globo mientras el planeta entero cabe en pantalla.
    const glow = () => {
      const zoom = map.getZoom();
      if (zoom > 3.2 || map.getPitch() > 5) { setHalo(null); return; }
      const center = map.project(map.getCenter());
      setHalo({ x: center.x, y: center.y, r: (512 * 2 ** zoom) / (2 * Math.PI) });
    };
    map.on("move", glow);
    map.on("load", glow);
    map.on("resize", glow);
    return () => { map.remove(); mapRef.current = null; markersRef.current.clear(); };
  }, []);

  // Visión del héroe: la capa de NASA va encima de la foto y debajo de los nombres. Al cambiar la fecha solo cambian las teselas.
  const visionRef = useRef(vision);
  useEffect(() => {
    visionRef.current = vision;
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const current = visionRef.current;
      const source = map.getSource("vision") as maplibregl.RasterTileSource | undefined;
      if (!current) {
        if (map.getLayer("vision")) map.removeLayer("vision");
        if (source) map.removeSource("vision");
        return;
      }
      const url = current.layer.tile_url.replace("{time}", current.date);
      if (source && (source as unknown as { _visionId?: string })._visionId === current.layer.id) { source.setTiles([url]); return; }
      if (map.getLayer("vision")) map.removeLayer("vision");
      if (source) map.removeSource("vision");
      map.addSource("vision", { type: "raster", tiles: [url], tileSize: 256, maxzoom: current.layer.max_zoom, attribution: "NASA EOSDIS GIBS" });
      (map.getSource("vision") as unknown as { _visionId?: string })._visionId = current.layer.id;
      const firstLabel = map.getStyle().layers.find((layer) => layer.type === "symbol")?.id;
      map.addLayer({ id: "vision", type: "raster", source: "vision", paint: { "raster-opacity": 0.88, "raster-fade-duration": 350 } }, firstLabel);
    };
    if (map.isStyleLoaded()) apply(); else map.once("idle", apply);
    // Si el estilo se recarga (llegan los nombres), la capa se vuelve a poner.
    const again = () => { if (visionRef.current && !map.getLayer("vision")) apply(); };
    map.on("styledata", again);
    return () => { map.off("styledata", again); };
  }, [vision]);

  // Alertas reales: marcadores ⚠ que laten, visibles solo con el planeta a la vista.
  const alertMarkers = useRef<Map<string, HTMLButtonElement>>(new Map());
  const onAlertRef = useRef(onAlert);
  useEffect(() => { onAlertRef.current = onAlert; }, [onAlert]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    for (const item of alerts) {
      if (alertMarkers.current.has(item.id)) continue;
      const element = document.createElement("button");
      element.type = "button";
      element.className = `gameLiveAlert level-${item.level}`;
      element.textContent = "⚠";
      element.setAttribute("aria-label", `Alerta real ${item.level === "red" ? "roja" : "naranja"}: ${item.kind_label} en ${item.place}`);
      element.addEventListener("click", (event) => { event.stopPropagation(); onAlertRef.current(item); });
      new maplibregl.Marker({ element }).setLngLat([item.longitude, item.latitude]).addTo(map);
      alertMarkers.current.set(item.id, element);
    }
  }, [alerts]);
  useEffect(() => {
    alertMarkers.current.forEach((element) => { element.hidden = stage !== "tierra"; });
  }, [stage, alerts]);

  // Marcadores de misión: botones accesibles, de color según lo que dicen los datos.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const existing = markersRef.current;
    for (const item of missions) {
      if (existing.has(item.id)) continue;
      const element = document.createElement("button");
      element.type = "button";
      element.className = `gameMarker heat-${item.heat}`;
      element.append(document.createElement("i"), Object.assign(document.createElement("span"), { textContent: item.name }));
      element.setAttribute("aria-label", `Misión ${item.name}, ${item.country}: ${HEAT_LABEL[item.heat]}`);
      element.addEventListener("click", (event) => { event.stopPropagation(); onPickRef.current(item); });
      existing.set(item.id, { marker: new maplibregl.Marker({ element }).setLngLat([item.longitude, item.latitude]).addTo(map), element });
    }
  }, [missions]);

  useEffect(() => {
    const visible = stage === "tierra";
    markersRef.current.forEach(({ element }, id) => {
      element.hidden = !visible;
      element.classList.toggle("compact", stage === "tierra" && !continent);
      element.classList.toggle("done", completed.has(id));
      element.tabIndex = visible ? 0 : -1;
    });
  }, [stage, completed, missions, continent]);

  // Cámara y relieve 3D (solo dentro de una misión).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const interactive = stage === "tierra" || stage === "mision";
    [map.dragPan, map.scrollZoom, map.touchZoomRotate, map.doubleClickZoom, map.dragRotate].forEach((handler) => (interactive ? handler.enable() : handler.disable()));
    map.keyboard.disable(); // las flechas mueven al personaje, no al mapa
    const target = frame(stage, continent, mission, panelWidth, map.getContainer().clientHeight);
    const duration = reduced() ? 0 : stage === "viaje" ? 2600 : stage === "mision" ? 4200 : 1800;
    const applyTerrain = () => {
      try { map.setTerrain(stage === "mision" ? { source: "terrain", exaggeration: mission?.scale === "paisaje" ? 1.6 : 1.2 } : null); } catch { /* sin relieve */ }
      try { map.setSky(stage === "mision" ? DAY_SKY : SPACE_SKY); } catch { /* sin cielo */ }
      // En el lugar, sin nombres amontonados: la escena queda limpia, como una toma de cine.
      for (const layer of map.getStyle().layers) {
        if (layer.type === "symbol" && !layer.id.startsWith("game-")) map.setLayoutProperty(layer.id, "visibility", stage === "mision" ? "none" : "visible");
      }
    };
    if (map.isStyleLoaded()) applyTerrain(); else map.once("idle", applyTerrain);
    map.stop();
    if (stage !== "mision" || !mission) { setPhase("off"); map.flyTo({ ...target, duration, essential: false }); return; }
    if (immersive) { setPhase("off"); map.flyTo({ ...target, pitch: 0, duration: reduced() ? 0 : 1500, essential: false }); return; }
    if (reduced()) { map.jumpTo(target); setPhase("suelo"); return; }
    // 1) la nave baja desde el globo hasta unos kilómetros al sur del lugar, casi a ras del suelo y mirando al horizonte;
    // 2) vuela rasante hacia el lugar; 3) aterriza. Si la persona mueve el mapa, la secuencia sigue desde donde quedó.
    let cancelled = false;
    let timer = 0;
    const scale = missionScale(mission);
    const approach = offset(mission.latitude, mission.longitude, 180, scale.spread * 5);
    setPhase("descenso");
    map.flyTo({ center: approach, zoom: scale.zoom - 0.5, pitch: target.pitch + 6, bearing: 0, padding: target.padding, duration: 4200, essential: false });
    map.once("moveend", () => {
      if (cancelled) return;
      setPhase("vuelo");
      map.easeTo({ ...target, pitch: target.pitch + 4, duration: 5200, easing: (t) => t, essential: false });
      map.once("moveend", () => {
        if (cancelled) return;
        setPhase("aterriza");
        map.easeTo({ pitch: target.pitch, duration: 1600, essential: false });
        timer = window.setTimeout(() => { if (!cancelled) setPhase("suelo"); }, 1700);
      });
    });
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [stage, continent, mission, panelWidth, immersive]);

  // Al entrar a una misión el héroe espera en la nave; al aterrizar baja junto a ella, al este del lugar.
  useEffect(() => {
    setSpeech(null);
    if (stage !== "mision" || !mission) { heroPos.current = null; setHeroScreen(null); setPins([]); setShip(null); return; }
    heroPos.current = offset(mission.latitude, mission.longitude, 120, missionScale(mission).spread * 0.2);
  }, [stage, mission]);

  // Proyección a pantalla del personaje y de los puntos de aviso, en cada cuadro que se mueve el mapa.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || stage !== "mision" || !mission) return;
    const scale = missionScale(mission);
    const spots = checkpoints.map((item) => ({ id: item.id, at: offset(mission.latitude, mission.longitude, item.bearing, scale.spread) }));
    const draw = () => {
      if (heroPos.current) { const p = map.project(heroPos.current); setHeroScreen({ x: p.x, y: p.y }); }
      // En vuelo la nave va fija delante de la cámara; aterrizada, queda en el centro del lugar.
      const flying = phaseRef.current === "descenso" || phaseRef.current === "vuelo";
      const at = flying ? map.project(map.getCenter()) : map.project([mission.longitude, mission.latitude]);
      setShip({ x: at.x, y: at.y + (flying ? 90 : 0) });
      setPins(spots.map((spot) => { const p = map.project(spot.at); return { id: spot.id, x: p.x, y: p.y }; }));
    };
    draw();
    map.on("move", draw);
    map.on("render", draw);
    return () => { map.off("move", draw); map.off("render", draw); };
  }, [stage, mission, checkpoints]);

  // Moverse: flechas o WASD, o un clic / toque en el suelo para correr hasta ahí. La cámara sigue al personaje.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || stage !== "mision" || !mission || !hero || !landed) return;
    const scale = missionScale(mission);
    const spots = checkpoints.map((item) => ({ item, at: offset(mission.latitude, mission.longitude, item.bearing, scale.spread) }));
    const held = new Set<string>();
    let target: [number, number] | null = null;
    let frameId = 0;
    let last = performance.now();
    let wasRunning = false;
    const onKey = (event: KeyboardEvent) => {
      if (!(event.code in KEYS) || (event.target as HTMLElement)?.closest?.("input, textarea")) return;
      event.preventDefault();
      if (event.type === "keydown") { held.add(event.code); target = null; } else held.delete(event.code);
    };
    const onClick = (event: maplibregl.MapMouseEvent) => { target = [event.lngLat.lng, event.lngLat.lat]; };
    const step = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      const pos = heroPos.current;
      if (pos) {
        let dx = 0, dy = 0;
        held.forEach((code) => { dx += KEYS[code][0]; dy += KEYS[code][1]; });
        if (!dx && !dy && target) {
          const gap = metersBetween(pos, target);
          if (gap < 4) target = null;
          else { dx = ((target[0] - pos[0]) * 111_320 * Math.cos((pos[1] * Math.PI) / 180)) / gap; dy = ((target[1] - pos[1]) * 110_540) / gap; }
        }
        const moving = dx !== 0 || dy !== 0;
        if (moving !== wasRunning) { setRunning(moving); wasRunning = moving; }
        if (moving) {
          const length = Math.hypot(dx, dy) || 1;
          const meters = scale.speed * dt;
          const next: [number, number] = [pos[0] + ((dx / length) * meters) / (111_320 * Math.cos((pos[1] * Math.PI) / 180)), pos[1] + ((dy / length) * meters) / 110_540];
          // No se aleja más allá de la zona de la misión.
          if (metersBetween(next, [mission.longitude, mission.latitude]) < scale.spread * 1.8) heroPos.current = next;
          else target = null;
          if (dx) setFacingLeft(dx < 0);
          setHeading(Math.atan2(dx, -dy));
          map.setCenter(heroPos.current!);
          const near = spots.find((spot) => metersBetween(heroPos.current!, spot.at) < scale.reach);
          if (near) { setSpeech(near.item); onReachRef.current(near.item.id); }
        }
      }
      frameId = requestAnimationFrame(step);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKey);
    map.on("click", onClick);
    frameId = requestAnimationFrame(step);
    return () => { cancelAnimationFrame(frameId); window.removeEventListener("keydown", onKey); window.removeEventListener("keyup", onKey); map.off("click", onClick); setRunning(false); };
  }, [stage, mission, hero, landed, checkpoints]);

  return (
    <>
      {halo && !(show2045 && planetReady) && <div className="gameHalo" aria-hidden style={{ left: halo.x, top: halo.y, width: halo.r * 3, height: halo.r * 3 }} />}
      {halo && show2045 && <Planet2045 x={halo.x} y={halo.y} r={halo.r} health={planetHealth ?? 0} onReady={setPlanetReady} />}
      <div ref={container} className={`gameGlobe${show2045 && planetReady ? " under2045" : ""}`} aria-label="La Tierra vista desde el espacio: imagen Blue Marble de NASA y, de cerca, foto satelital Sentinel-2 con relieve" role="region" />
      {halo && (
        // La órbita del cometa: el planeta mide 130 unidades de radio en este dibujo.
        <svg className="gameOrbit" aria-hidden viewBox="-195 -195 390 390" style={{ left: halo.x, top: halo.y, width: halo.r * 3, height: halo.r * 3 }}>
          <ellipse cx="0" cy="0" rx="182" ry="46" transform="rotate(-14)" />
          {!reduced() && (
            <g transform="rotate(-14)">
              <circle r="6" className="orbitComet"><animateMotion dur="10s" repeatCount="indefinite" path="M182 0 A182 46 0 1 1 -182 0 A182 46 0 1 1 182 0" /></circle>
            </g>
          )}
        </svg>
      )}
      {stage === "mision" && !immersive && pins.map((pin) => {
        const item = checkpoints.find((c) => c.id === pin.id);
        if (!item) return null;
        return (
          <div key={pin.id} className={`gamePin tone-${item.tone} ${visited.has(pin.id) ? "done" : ""}`} style={{ left: pin.x, top: pin.y }} aria-hidden>
            <span className="ring" /><span className="pole" />
            <b><em>{item.icon}</em>{item.quest}{visited.has(pin.id) ? " ✓" : ""}</b>
            {!visited.has(pin.id) && <span className="bang">!</span>}
          </div>
        );
      })}
      {stage === "mision" && !immersive && ship && phase !== "off" && (
        <div className={`gameShip ship-${phase}`} style={{ left: ship.x, top: ship.y }} aria-hidden>
          <span className="trail" />
          {!use3d && <Ship width={phase === "suelo" || phase === "aterriza" ? 110 : 170} />}
          {(phase === "aterriza" || phase === "suelo") && <span className="shipShadow" />}
          {phase === "aterriza" && <span className="shipDust" />}
        </div>
      )}
      {stage === "mision" && !immersive && mission && phase !== "off" && (
        <div className={`gameCine ${landed ? "out" : ""}`} aria-hidden={landed}>
          <span className="bar top" /><span className="bar bottom" />
          <div className="gameCineTitle" role={landed ? undefined : "status"}>
            <b>{mission.name}, {mission.country}</b>
            <small>{Math.abs(mission.latitude).toFixed(4)}° {mission.latitude < 0 ? "S" : "N"}   {Math.abs(mission.longitude).toFixed(4)}° {mission.longitude < 0 ? "O" : "E"}</small>
            {!landed && <em>{phase === "aterriza" ? "Aterrizando" : "En aproximación"}</em>}
          </div>
        </div>
      )}
      {stage === "mision" && !immersive && heroScreen && hero && landed && (
        <div className={`gameWalker ${landed ? "landed" : "landing"} ${running ? "running" : ""} ${facingLeft ? "left" : ""}`} style={{ left: heroScreen.x, top: heroScreen.y }}>
          {speech && (
            <div className={`gameSpeech tone-${speech.tone}`} role="status">
              <p className="ask"><span>{speech.icon}</span> «{speech.ask}»</p>
              <p className="answer"><b>{hero?.name ?? "Héroe"}:</b> {speech.message}</p>
              <span className="xp">+100 XP</span>
            </div>
          )}
          {!use3d && <span className="body"><HeroAvatar gender={hero.gender} size={50} /></span>}
          <span className="shadow" />
          {running && <span className="dust" />}
        </div>
      )}
      {stage === "mision" && !immersive && use3d && phase !== "off" && (
        <Hero3D onUnavailable={() => setUse3d(false)}
          state={{ hero: heroScreen, ship, phase, running, heading, gender: hero?.gender ?? "mujer", showHero: !!hero }} />
      )}
      {stage === "mision" && !immersive && hero && landed && !speech && (
        <p className="gameHint" role="note">Corre con las flechas (o W A S D), o toca el suelo para ir hasta ahí. Llega a cada «!» para avisar al pueblo.</p>
      )}
    </>
  );
}
