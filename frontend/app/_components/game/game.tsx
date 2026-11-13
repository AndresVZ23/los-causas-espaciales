"use client";

// Modo jugador: un superhéroe que nace en la Luna, viaja a la Tierra en un cometa y resuelve misiones con datos reales
// de cada lugar (NASA POWER desde 2001, con su segunda fuente). El espectador recorre lo mismo sin jugar.

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { GameGlobe, type LiveAlert } from "./game-globe";
import { CONTINENTS, HEAT_LABEL, type Continent, type Gender, type Hero, type Mission, type MissionsPayload, type NasaLayer, type Role, type Stage } from "./game-types";
import { HeroModel } from "./hero-model";
import { missionCheckpoints } from "./mission-logic";
import { MissionPanel } from "./mission-panel";
import { MoonScene } from "./moon-scene";
import { MissionWorld } from "./mission-world";
import { lastDays, useNasaLayers, VisionBar } from "./vision-bar";
import "./game.css";

const STORE = "lce-juego-v1";
interface Saved { hero: Hero | null; badges: Record<string, string[]> }

function readSaved(): Saved {
  try {
    const raw = window.localStorage.getItem(STORE);
    if (raw) return JSON.parse(raw) as Saved;
  } catch { /* almacenamiento bloqueado: se juega sin guardar */ }
  return { hero: null, badges: {} };
}
function writeSaved(saved: Saved) {
  try { window.localStorage.setItem(STORE, JSON.stringify(saved)); } catch { /* sin almacenamiento */ }
}

function useMissions() {
  const [state, setState] = useState<{ data: MissionsPayload | null; error: string | null }>({ data: null, error: null });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/missions").then(async (response) => {
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail ?? "No se pudieron leer las misiones.");
      if (!cancelled) setState({ data: payload as MissionsPayload, error: null });
    }).catch((error: Error) => { if (!cancelled) setState({ data: null, error: error.message }); });
    return () => { cancelled = true; };
  }, [attempt]);
  return { ...state, retry: () => setAttempt((value) => value + 1) };
}

function usePanelWidth(active: boolean) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const update = () => setWidth(active && window.innerWidth > 820 ? 420 : 0);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [active]);
  return width;
}

export default function Game() {
  const { data, error, retry } = useMissions();
  const missions = useMemo(() => data?.missions ?? [], [data]);
  const [role, setRole] = useState<Role | null>(null);
  const [stage, setStage] = useState<Stage>("inicio");
  const [hero, setHero] = useState<Hero | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftGender, setDraftGender] = useState<Gender | null>(null);
  const [continent, setContinent] = useState<Continent | null>(null);
  const [mission, setMission] = useState<Mission | null>(null);
  const [badges, setBadges] = useState<Record<string, string[]>>({});
  const [visited, setVisited] = useState<Set<string>>(new Set());
  const nasaLayers = useNasaLayers();
  // Alertas reales de GDACS (la misma fuente del botón «Alertas en el mundo» de la consola).
  const [liveAlerts, setLiveAlerts] = useState<LiveAlert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<LiveAlert | null>(null);
  useEffect(() => {
    fetch("/api/world-alerts").then((r) => (r.ok ? r.json() : Promise.reject())).then((payload: { alerts: LiveAlert[] }) => setLiveAlerts(payload.alerts ?? [])).catch(() => { /* sin alertas */ });
  }, []);
  const ALERT_HAZARD: Record<string, string> = { flood: "inundacion", tropical_cyclone: "inundacion", volcano: "erupcion", wildfire: "calor", drought: "calor", earthquake: "huaico" };
  const nearestMission = (alert: LiveAlert) => {
    const hazard = ALERT_HAZARD[alert.kind];
    const distance = (m: Mission) => Math.hypot(m.latitude - alert.latitude, (m.longitude - alert.longitude) * Math.cos((alert.latitude * Math.PI) / 180));
    const sameKind = missions.filter((m) => m.hazard === hazard);
    return [...(sameKind.length ? sameKind : missions)].sort((a, b) => distance(a) - distance(b))[0];
  };
  const [visionLayer, setVisionLayer] = useState<NasaLayer | null>(null);
  const [visionDate, setVisionDate] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  // Mundo 3D de la misión; si su terreno no carga, la misión sigue sobre el mapa.
  const [worldFailed, setWorldFailed] = useState(false);
  const immersive = stage === "mision" && !!mission && !worldFailed;
  const pickVision = (layer: NasaLayer | null) => { setPlaying(false); setVisionLayer(layer); setVisionDate(layer?.latest_date ?? null); };
  // Animación: recorre los últimos 7 días de una capa diaria y se detiene en el más reciente.
  useEffect(() => {
    if (!playing || !visionLayer?.latest_date) return;
    const days = lastDays(visionLayer.latest_date, 7);
    let index = 0;
    setVisionDate(days[0]);
    const timer = window.setInterval(() => {
      index += 1;
      if (index >= days.length) { setPlaying(false); return; }
      setVisionDate(days[index]);
    }, 1400);
    return () => window.clearInterval(timer);
  }, [playing, visionLayer]);
  const vision = useMemo(() => (visionLayer && visionDate && stage === "tierra" ? { layer: visionLayer, date: visionDate } : null), [visionLayer, visionDate, stage]);
  const checkpoints = useMemo(() => (mission ? missionCheckpoints(mission) : []), [mission]);
  const reach = useCallback((id: string) => setVisited((prev) => (prev.has(id) ? prev : new Set(prev).add(id))), []);

  useEffect(() => {
    const saved = readSaved();
    setBadges(saved.badges);
    if (saved.hero) { setDraftName(saved.hero.name); setDraftGender(saved.hero.gender); }
  }, []);

  const panelWidth = usePanelWidth(stage === "mision" || stage === "tierra");
  const completed = useMemo(() => new Set(Object.keys(badges)), [badges]);
  const totalBadges = Object.values(badges).reduce((sum, list) => sum + list.length, 0);

  const startJourney = () => {
    if (!draftGender || !draftName.trim()) return;
    const next = { name: draftName.trim().slice(0, 24), gender: draftGender };
    setHero(next);
    writeSaved({ hero: next, badges });
    setStage("luna");
  };
  const jump = () => {
    setStage("viaje");
    window.setTimeout(() => setStage("tierra"), window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 2700);
  };
  const pick = useCallback((item: Mission) => { setContinent(item.continent); setMission(item); setVisited(new Set()); setWorldFailed(false); setStage("mision"); }, []);
  const complete = (list: string[]) => {
    if (!mission || role !== "jugador") return;
    const next = { ...badges, [mission.id]: list };
    setBadges(next);
    writeSaved({ hero, badges: next });
  };
  // Ordenar por temperatura promedio real (NASA POWER desde 2001): los más fríos o los más calientes del planeta o del continente.
  const [order, setOrder] = useState<"todos" | "frios" | "calientes">("todos");
  const pool = continent ? missions.filter((item) => item.continent === continent) : missions;
  const withMean = pool.filter((item) => item.temperature?.mean != null);
  const inContinent = order === "todos" ? (continent ? pool : [])
    : [...withMean].sort((a, b) => (order === "frios" ? 1 : -1) * ((a.temperature!.mean as number) - (b.temperature!.mean as number))).slice(0, continent ? undefined : 10);

  return (
    <main className={`gameShell stage-${stage}`}>
      <div className="gameStars" aria-hidden />
      <GameGlobe missions={missions} stage={stage} continent={continent} mission={mission} hero={role === "jugador" ? hero : null}
        panelWidth={panelWidth} completed={completed} checkpoints={checkpoints} visited={visited} vision={vision} immersive={immersive}
        alerts={liveAlerts} onAlert={setSelectedAlert} onPick={pick} onReach={reach} />
      {immersive && mission && (
        <MissionWorld key={mission.id} mission={mission} hero={role === "jugador" ? hero : null} checkpoints={checkpoints} visited={visited}
          panelRight={panelWidth} panelBottom={panelWidth ? 0 : Math.round((typeof window !== "undefined" ? window.innerHeight : 800) * 0.6)}
          onReach={reach} onUnavailable={() => setWorldFailed(true)} onLeave={() => { setMission(null); setStage("tierra"); }} />
      )}

      {(stage === "luna" || stage === "viaje") && <MoonScene leaving={stage === "viaje"} />}

      {stage === "luna" && role === "jugador" && hero && (
        <div className="gameOnMoon"><HeroModel gender={hero.gender} size={130} pose="wave" label={`${hero.name} en la Luna`} /></div>
      )}


      <header className="gameHud">
        <Link href="/" className="gameBrand">Los Causas Espaciales</Link>
        {role === "jugador" && hero && stage !== "inicio" && stage !== "avatar" && (
          <p className="gameHeroTag"><i className={`gameHeroDot ${hero.gender}`} aria-hidden /> <b>{hero.name}</b> · {totalBadges} insignias · {completed.size}/{missions.length} misiones</p>
        )}
        {role === "espectador" && <p className="gameHeroTag">Modo espectador</p>}
      </header>

      {stage === "inicio" && (
        <section className="gameCard" aria-labelledby="start-title">
          <p className="gameEyebrow">NASA Space Apps 2026 · Detectives de la Tierra</p>
          <h1 id="start-title">La Tierra necesita detectives</h1>
          <p>Mira cómo cambió el clima de lugares reales desde 2001, con datos satelitales de NASA comprobados con una segunda fuente. ¿Cómo quieres entrar?</p>
          <div className="gameChoices">
            <button type="button" className="primary" onClick={() => { setRole("jugador"); setStage("avatar"); }}>
              <b>Jugador</b><span>Crea tu superhéroe, salta desde la Luna y resuelve misiones.</span>
            </button>
            <button type="button" onClick={() => { setRole("espectador"); setStage("tierra"); }}>
              <b>Espectador</b><span>Recorre el planeta y mira los datos de cada lugar, sin jugar.</span>
            </button>
          </div>
          <Link href="/" className="gameLink">Ir a la consola técnica para inversionistas →</Link>
        </section>
      )}

      {stage === "avatar" && (
        <section className="gameCard" aria-labelledby="avatar-title">
          <p className="gameEyebrow">Paso 1 de 1</p>
          <h1 id="avatar-title">Crea a tu superhéroe</h1>
          <div className="gameAvatars" role="radiogroup" aria-label="Figura del superhéroe">
            {(["mujer", "hombre"] as Gender[]).map((gender) => (
              <button key={gender} type="button" role="radio" aria-checked={draftGender === gender} className={draftGender === gender ? "on" : ""} onClick={() => setDraftGender(gender)}>
                <HeroModel gender={gender} size={110} /><span>{gender === "mujer" ? "Mujer" : "Hombre"}</span>
              </button>
            ))}
          </div>
          <label className="gameName">
            <span>¿Cómo se llama tu superhéroe?</span>
            <input value={draftName} maxLength={24} onChange={(event) => setDraftName(event.target.value)} placeholder="Por ejemplo: Guardiana Andina"
              onKeyDown={(event) => { if (event.key === "Enter") startJourney(); }} />
          </label>
          <button type="button" className="gameGo" disabled={!draftGender || !draftName.trim()} onClick={startJourney}>Ir a la Luna</button>
          {(!draftGender || !draftName.trim()) && <p className="gameMuted">Elige una figura y escribe un nombre para continuar.</p>}
        </section>
      )}

      {stage === "luna" && hero && (
        <section className="gameCard moon" aria-labelledby="moon-title">
          <h1 id="moon-title">Hola, {hero.name}</h1>
          <p>Estás en la Luna con tu nave y la bandera del Perú. Desde aquí ves que la Tierra está en peligro: hay {missions.length || "varios"} lugares que necesitan ayuda. En rojo, los que se calientan; en azul, los que se enfrían; en gris, donde los datos aún no alcanzan para saberlo.</p>
          <button type="button" className="gameGo" onClick={jump} disabled={!missions.length}>🚀 Despegar hacia la Tierra</button>
          {!missions.length && <p className="gameMuted">{error ? "Las misiones no están disponibles todavía." : "Cargando las misiones…"}</p>}
        </section>
      )}

      {stage === "viaje" && <p className="gameTravel" role="status">Tu nave vuela hacia la Tierra…</p>}

      {stage === "tierra" && (
        <section className="gameContinents" aria-labelledby="continent-title">
          <h2 id="continent-title">{continent ? `${continent}: elige una misión` : "¿A qué continente quieres ir?"}</h2>
          <div className="gameContinentList">
            {CONTINENTS.map((item) => (
              <button key={item.id} type="button" aria-pressed={continent === item.id} onClick={() => setContinent(item.id)}>
                {item.id}<small>{missions.filter((m) => m.continent === item.id).length}</small>
              </button>
            ))}
          </div>
          <div className="gameOrder" role="group" aria-label="Ordenar lugares por temperatura">
            <button type="button" aria-pressed={order === "frios"} onClick={() => setOrder(order === "frios" ? "todos" : "frios")}>❄️ Más fríos</button>
            <button type="button" aria-pressed={order === "calientes"} onClick={() => setOrder(order === "calientes" ? "todos" : "calientes")}>🔥 Más calientes</button>
          </div>
          {order !== "todos" && <p className="gameMuted">Temperatura media del aire desde 2001 (NASA POWER){continent ? ` en ${continent}` : ", los 10 del planeta"}.</p>}
          {inContinent.length > 0 && (
            <ul className="gameMissionList">
              {inContinent.map((item) => (
                <li key={item.id}>
                  <button type="button" onClick={() => pick(item)} className={`heat-${item.heat}`}>
                    <i /><span><b>{item.name}</b><small>{item.country} · {item.temperature?.mean != null ? `${item.temperature.mean.toFixed(1)} °C promedio · ` : ""}{HEAT_LABEL[item.heat]}</small></span>{completed.has(item.id) && <em>✓</em>}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="gameLegend"><span className="heat-calienta"><i />Se calienta</span><span className="heat-enfria"><i />Se enfría</span><span className="heat-sin_evidencia"><i />Sin evidencia suficiente</span></p>
          {error && <p className="gameError" role="alert">{error} <button type="button" onClick={retry}>Reintentar</button></p>}
        </section>
      )}

      {stage === "tierra" && selectedAlert && (
        <section className="gameAlertInfo" role="dialog" aria-labelledby="alert-title">
          <p className={`badge level-${selectedAlert.level}`}>⚠ Alerta real {selectedAlert.level === "red" ? "roja" : "naranja"} · GDACS</p>
          <h2 id="alert-title">{selectedAlert.kind_label}: {selectedAlert.place}</h2>
          {selectedAlert.severity && <p>{selectedAlert.severity}</p>}
          <p className="gameMuted">Desde {selectedAlert.started} · actualizada {selectedAlert.updated}{selectedAlert.also_seen_by?.length ? ` · también la ve ${selectedAlert.also_seen_by.join(", ")}` : ""}</p>
          {(() => { const m = nearestMission(selectedAlert); return m ? <button type="button" className="gameGo" onClick={() => { setSelectedAlert(null); pick(m); }}>Jugar una misión parecida: {m.name}</button> : null; })()}
          {selectedAlert.url && <a href={selectedAlert.url} target="_blank" rel="noreferrer">Ver el reporte en GDACS ↗</a>}
          <small>Es una alerta real e informativa, no un sistema de alerta temprana: sigue siempre a las autoridades locales.</small>
          <button type="button" className="gameBack" onClick={() => setSelectedAlert(null)}>Cerrar</button>
        </section>
      )}

      {stage === "tierra" && (
        <VisionBar layers={nasaLayers} active={visionLayer} date={visionDate} playing={playing} onPick={pickVision} onPlay={() => setPlaying((value) => !value)} />
      )}

      {stage === "mision" && mission && (
        <MissionPanel key={mission.id} mission={mission} role={role ?? "espectador"} heroName={hero?.name ?? ""} done={completed.has(mission.id)}
          checkpoints={checkpoints} visited={visited}
          onComplete={complete} onBack={() => { setMission(null); setStage("tierra"); }} />
      )}

      {stage !== "inicio" && stage !== "avatar" && data && (
        <p className="gameFoot">Misiones construidas el {new Date(data.built_at).toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })} con la API de la plataforma. Imagen: NASA Blue Marble{stage === "luna" || stage === "viaje" ? " · Luna: NASA Scientific Visualization Studio (LRO, cámara LROC y altímetro LOLA)" : ""}.</p>
      )}
    </main>
  );
}
