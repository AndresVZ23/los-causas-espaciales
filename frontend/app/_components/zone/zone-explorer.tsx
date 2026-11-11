"use client";

// «Entrar a la zona» (ADR-047): recorrido en primera persona por la maqueta en bloques de un lugar real. three.js se
// carga solo aquí. Lo que la plataforma sabe del lugar aparece como balizas; la misma información está en la lista del
// panel, que funciona con teclado y también si el equipo no puede iniciar los gráficos 3D.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PerspectiveCamera, WebGLRenderer } from "three";
import { formatDay, formatNumber } from "../format";
import { createPlayer, type Player } from "./zone-controls";
import { COVER, KIND, SLOPE_CLASSES, cellIndex, decodeGrid, heading, realElevation, type Zone, type ZoneBeacon, type ZoneGrid } from "./zone-data";
import { buildZoneScene, type BeaconPoint, type ZoneScene } from "./zone-scene";
import "./zone-explorer.css";

const NEAR = 9;
const SPOTS: [number, number][] = [[0, 6], [6, 0], [-6, 0], [0, -6], [4, 4], [-4, 4], [4, -4], [-4, -4]];
type Readout = { elevation: number; slope: number; cover: string; heading: string };
type Stage = { player: Player; scene: ZoneScene; grid: ZoneGrid };

function BeaconCard({ beacon, onClose }: { beacon: ZoneBeacon; onClose: () => void }) {
  const kind = KIND[beacon.kind];
  return (
    <article className="zoneCard" style={{ "--kind": kind.css } as React.CSSProperties} aria-live="polite">
      <header><span>{kind.label}</span><button onClick={onClose} aria-label="Cerrar la ficha">Cerrar</button></header>
      <h3>{beacon.title}</h3>
      <p>{beacon.body}</p>
      {beacon.figures.length > 0 && <dl>{beacon.figures.map((figure) => <div key={figure.label}><dt>{figure.label}</dt><dd>{figure.value}</dd></div>)}</dl>}
      <p className="zoneCardLine"><b>Segunda fuente</b>{beacon.second_source ?? "Este dato no tiene una segunda fuente conectada."}</p>
      <p className="zoneCardLine"><b>Qué mirar primero</b>{beacon.look_first}</p>
      <p className="zoneCardFoot">Fuentes: {beacon.sources.join("; ")}. {beacon.placement}</p>
    </article>
  );
}

export default function ZoneExplorer({ zoneId, onExit }: { zoneId: string; onExit: () => void }) {
  const [zone, setZone] = useState<Zone | null>(null);
  const [error, setError] = useState("");
  const [noGraphics, setNoGraphics] = useState(false);
  const [started, setStarted] = useState(false);
  const [locked, setLocked] = useState(false);
  const [flying, setFlying] = useState(true);
  const [slopeView, setSlopeView] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [readout, setReadout] = useState<Readout | null>(null);
  const [touch, setTouch] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const stageRef = useRef<Stage | null>(null);
  const exitRef = useRef<HTMLButtonElement | null>(null);
  const pinnedRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setZone(null); setError("");
    fetch(`/api/zones/${zoneId}`).then(async (response) => {
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "");
      if (!cancelled) setZone(payload as Zone);
    }).catch((exception: Error) => { if (!cancelled) setError(exception.message || "No se pudo leer la maqueta de la zona. Salga y vuelva a entrar para reintentar."); });
    return () => { cancelled = true; };
  }, [zoneId]);

  useEffect(() => {
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    setTouch(coarse);
    if (window.innerWidth < 760) setPanelOpen(false);
    exitRef.current?.focus();
  }, []);

  const grid = useMemo(() => {
    if (!zone) return null;
    try { return decodeGrid(zone); } catch { return null; }
  }, [zone]);
  const present = useMemo(() => {
    if (!grid) return [];
    const seen = new Set<number>(grid.cover);
    return Object.entries(COVER).filter(([code]) => seen.has(+code)).map(([code, item]) => ({ code: +code, ...item }));
  }, [grid]);

  // Escena, jugador y bucle de dibujo. Todo se libera al salir.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!zone || !grid || !canvas) return;
    let renderer: WebGLRenderer;
    try { renderer = new WebGLRenderer({ canvas, antialias: true, powerPreference: "low-power" }); } catch { setNoGraphics(true); return; }
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    const camera = new PerspectiveCamera(70, 1, 0.1, 600);
    const scene = buildZoneScene(zone, grid, still);
    const player = createPlayer(camera, canvas, grid, { onLock: setLocked, onFly: setFlying });
    // Arranque en el aire, desde el sur, con toda la maqueta a la vista.
    const peak = grid.heights.reduce((highest, value) => Math.max(highest, value), 0);
    player.place(grid.size / 2, grid.size * 0.94, { flying: true, height: peak + 34 });
    player.lookAt(grid.size / 2, peak * 0.4, grid.size * 0.45);
    stageRef.current = { player, scene, grid };

    const resize = () => {
      const width = canvas.clientWidth || 1, height = canvas.clientHeight || 1;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    let frame = 0, last = performance.now(), sinceHud = 1, near: string | null = null, lastKey = "";
    const closest = (x: number, z: number): BeaconPoint | null => {
      let best: BeaconPoint | null = null, distance = NEAR;
      for (const beacon of scene.beacons) { const d = Math.hypot(beacon.x - x, beacon.z - z); if (d < distance) { best = beacon; distance = d; } }
      return best;
    };
    const step = (now: number) => {
      // En un equipo lento el cuadro dura más: el movimiento se calcula en pasos cortos para que el recorrido no vaya en
      // cámara lenta ni atraviese bloques.
      const seconds = Math.min((now - last) / 1000, 0.3);
      last = now;
      const moves = Math.max(1, Math.ceil(seconds / 0.025));
      for (let move = 0; move < moves; move += 1) player.update(seconds / moves);
      scene.animate(now / 1000);
      renderer.render(scene.scene, camera);
      sinceHud += seconds;
      if (sinceHud > 0.15) {
        sinceHud = 0;
        const state = player.state();
        const index = cellIndex(grid, state.x, state.z);
        const next: Readout = { elevation: Math.round(realElevation(zone, grid.heights[index])), slope: grid.slope[index], cover: (COVER[grid.cover[index]] ?? COVER[0]).label, heading: heading(state.yaw) };
        const key = `${next.elevation}|${next.slope}|${next.cover}|${next.heading}`;
        if (key !== lastKey) { lastKey = key; setReadout(next); }
        // Altura sobre el suelo, en bloques: la usa la prueba de navegador para saber cuándo el jugador ya pisa tierra.
        canvas.dataset.height = (state.feet - grid.solid[index]).toFixed(1);
        // La baliza elegida en la lista manda mientras el jugador siga cerca de ella, aunque haya otra aún más cerca.
        const chosen = scene.beacons.find((beacon) => beacon.id === pinnedRef.current);
        if (chosen && Math.hypot(chosen.x - state.x, chosen.z - state.z) > NEAR + 3) pinnedRef.current = null;
        const found = pinnedRef.current ?? closest(state.x, state.z)?.id ?? null;
        if (found !== near) { near = found; setOpenId(found); }
      }
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    canvas.dataset.ready = "true";
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      player.dispose();
      scene.dispose();
      renderer.dispose();
      stageRef.current = null;
      delete canvas.dataset.ready;
    };
  }, [zone, grid]);

  useEffect(() => { stageRef.current?.scene.setSlopeView(slopeView); }, [slopeView]);

  const goTo = useCallback((beacon: ZoneBeacon) => {
    const stage = stageRef.current;
    setStarted(true);
    if (!stage) { setOpenId(beacon.id); return; }
    const point = stage.scene.beacons.find((item) => item.id === beacon.id);
    if (!point) return;
    const { grid: cells, player } = stage;
    // Se llega al punto vecino de altura más parecida a la de la baliza: nunca sobre un árbol ni detrás de un muro.
    const inside = SPOTS.map(([dx, dz]) => [point.x + dx, point.z + dz]).filter(([x, z]) => x > 1 && z > 1 && x < cells.size - 1 && z < cells.size - 1);
    const [x, z] = inside.sort((a, b) => Math.abs(cells.solid[cellIndex(cells, a[0], a[1])] - point.y) - Math.abs(cells.solid[cellIndex(cells, b[0], b[1])] - point.y))[0] ?? [point.x, point.z];
    pinnedRef.current = beacon.id;
    player.place(x, z, { flying: false });
    player.lookAt(point.x, point.y + 3.8, point.z);
    setOpenId(beacon.id);
    if (window.innerWidth < 760) setPanelOpen(false);
  }, []);

  // Con el mouse capturado no se puede hacer clic en los paneles: los números llevan a cada baliza y P cambia la vista.
  useEffect(() => {
    if (!zone) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return;
      const digit = /^Digit([1-9])$/.exec(event.code);
      if (digit && zone.beacons[+digit[1] - 1]) goTo(zone.beacons[+digit[1] - 1]);
      else if (event.code === "KeyP") setSlopeView((value) => !value);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [zone, goTo]);

  const start = () => { setStarted(true); if (!touch) stageRef.current?.player.capture(); };
  const toggleFly = () => stageRef.current?.player.setFlying(!flying);
  const hold = (direction: -1 | 1) => ({
    onPointerDown: () => stageRef.current?.player.setLift(direction), onPointerUp: () => stageRef.current?.player.setLift(0),
    onPointerLeave: () => stageRef.current?.player.setLift(0), onPointerCancel: () => stageRef.current?.player.setLift(0),
  });
  const open = zone?.beacons.find((beacon) => beacon.id === openId) ?? null;
  const ready = Boolean(zone && grid && !noGraphics);

  return (
    <div className={`zoneScreen${ready ? "" : " isPlain"}`} role="dialog" aria-modal="true" aria-label={zone ? `Recorrido por ${zone.name}` : "Recorrido por la zona"}>
      {ready && <canvas ref={canvasRef} className="zoneCanvas" aria-label="Maqueta en bloques de la zona. La misma información está en la lista de hallazgos." onClick={() => { if (started && !touch) stageRef.current?.player.capture(); }} />}

      <div className="zoneBar">
        <button ref={exitRef} className="zoneExit" onClick={onExit}>Salir al mapa</button>
        <div className="zoneTitle">
          <h2>{zone ? `${zone.name}, ${zone.country}` : "Abriendo la zona…"}</h2>
          {zone && <p>{zone.tagline}</p>}
        </div>
        {ready && (
          <div className="zoneTools">
            <button aria-pressed={slopeView} className={slopeView ? "active" : ""} onClick={() => setSlopeView((value) => !value)}>Pendientes</button>
            <button aria-pressed={flying} className={flying ? "active" : ""} onClick={toggleFly}>{flying ? "Volando" : "Caminando"}</button>
            {/* En pantalla angosta la lista y la ficha ocupan el mismo sitio: al abrir la lista se cierra la ficha. */}
            <button aria-expanded={panelOpen} aria-controls="zona-hallazgos" onClick={() => { if (!panelOpen && window.innerWidth < 760) setOpenId(null); setPanelOpen((value) => !value); }}>Hallazgos · {zone?.beacons.length}</button>
          </div>
        )}
      </div>

      {error && <p className="zoneMessage errorMessage" role="alert">{error}</p>}
      {!zone && !error && <p className="zoneMessage" role="status">Leyendo el relieve y la cobertura del lugar…</p>}
      {zone && !grid && <p className="zoneMessage errorMessage" role="alert">La maqueta llegó incompleta. Salga y vuelva a entrar.</p>}
      {noGraphics && <p className="zoneMessage" role="status">Este equipo no pudo iniciar los gráficos 3D. Lo que la plataforma sabe del lugar está completo en la lista de hallazgos.</p>}

      {zone && (panelOpen || !ready) && (
        <aside className="zonePanel" id="zona-hallazgos" aria-label="Hallazgos de la zona">
          <h3>Qué sabe la plataforma de este lugar</h3>
          <ul className="zoneBeacons">
            {zone.beacons.map((beacon) => (
              <li key={beacon.id}>
                <button className={beacon.id === openId ? "active" : ""} style={{ "--kind": KIND[beacon.kind].css } as React.CSSProperties} onClick={() => goTo(beacon)}>
                  <i aria-hidden="true" /><span><b>{beacon.title}</b><small>{KIND[beacon.kind].label}{ready ? ` · tecla ${zone.beacons.indexOf(beacon) + 1}` : ""}</small></span>
                </button>
              </li>
            ))}
          </ul>
          <h3>{slopeView ? "Pendiente real del terreno" : "Material de cada bloque"}</h3>
          <ul className="zoneLegend">
            {(slopeView ? SLOPE_CLASSES.map((item) => ({ code: item.from, label: item.label, color: item.color })) : present).map((item) => (
              <li key={item.code}><i style={{ background: `#${item.color.toString(16).padStart(6, "0")}` }} aria-hidden="true" />{item.label}</li>
            ))}
          </ul>
          <details>
            <summary>Sobre esta maqueta</summary>
            {zone.notes.map((note) => <p key={note}>{note}</p>)}
            {zone.sources.map((source) => <p key={source.name}><b>{source.name}</b> — {source.use} {source.license} <a href={source.url} target="_blank" rel="noreferrer">Ver la fuente</a></p>)}
            {zone.paths.map((path) => <p key={path.label}><b>{path.label}</b> — línea amarilla. {path.source}</p>)}
            <p>Construida el {formatDay(zone.built_at)} · {zone.size_km} × {zone.size_km} km · {formatNumber(zone.min_elevation_m, 0)} a {formatNumber(zone.max_elevation_m, 0)} m s. n. m.</p>
          </details>
        </aside>
      )}

      {ready && readout && (
        <p className="zoneReadout" aria-hidden="true">
          <b>{formatNumber(readout.elevation, 0)} m</b><span>altitud real</span><b>{readout.slope}°</b><span>pendiente</span><b>{readout.cover}</b><span>bajo sus pies</span><b>{readout.heading}</b><span>rumbo</span>
        </p>
      )}

      {open && <BeaconCard beacon={open} onClose={() => { pinnedRef.current = null; setOpenId(null); }} />}

      {ready && !started && zone && (
        <div className="zoneIntro">
          <h3>Está sobre {zone.name}</h3>
          <p>Cada bloque son {formatNumber(zone.cell_m, 0)} m de terreno real, con el relieve exagerado ×{formatNumber(zone.vertical_exaggeration, 1)} para que se lea. Las columnas de luz marcan lo que la plataforma encontró aquí.</p>
          {touch
            ? <ul><li><b>Lado izquierdo</b>arrastre para moverse</li><li><b>Lado derecho</b>arrastre para mirar</li><li><b>Caminando</b>baja al suelo</li></ul>
            : <ul><li><b>W A S D</b>moverse</li><li><b>Mouse</b>mirar</li><li><b>F</b>volar o caminar</li><li><b>Espacio</b>saltar o subir</li><li><b>Q</b>bajar al volar</li><li><b>Mayús</b>ir más rápido</li>
                <li><b>1 a {zone.beacons.length}</b>ir a una baliza</li><li><b>P</b>ver pendientes</li><li><b>Esc</b>soltar el mouse</li></ul>}
          <button className="zoneStart" onClick={start}>Empezar el recorrido</button>
        </div>
      )}
      {ready && started && !touch && <p className="zoneHint">{locked ? "Esc suelta el mouse para usar los botones" : "Clic en la escena para mirar con el mouse; también puede arrastrar"}</p>}

      {ready && touch && started && (
        <div className="zonePad">
          {flying ? <><button {...hold(1)}>Subir</button><button {...hold(-1)}>Bajar</button></> : <button onClick={() => stageRef.current?.player.jump()}>Saltar</button>}
        </div>
      )}
    </div>
  );
}
