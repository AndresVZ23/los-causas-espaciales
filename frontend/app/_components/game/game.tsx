"use client";

// TERRA 2045 · El último viaje (ADR-050): desde la colonia lunar de 2045, el Proyecto Génesis envía al viajero a 2026
// para resolver misiones con datos reales de cada lugar (NASA POWER desde 2001, con su segunda fuente). Tiene tres
// regresos; el planeta cambia con su avance. El espectador recorre lo mismo sin jugar. Es la portada del sitio.

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GameGlobe, type LiveAlert } from "./game-globe";
import { CONTINENTS, HEAT_LABEL, type Continent, type Gender, type Hero, type Mission, type MissionsPayload, type NasaLayer, type Role, type Stage } from "./game-types";
import { HeroModel } from "./hero-model";
import { heatSupport, heatSupportPhrase, heatUnconfirmed, missionCheckpoints } from "./mission-logic";
import { MissionPanel } from "./mission-panel";
import { MoonScene } from "./moon-scene";
import { MissionWorld } from "./mission-world";
import { companionLine, finale, finaleSummary, nikolBrief, nikolMessage, PROLOGUE, returnSlides, returnSummary, rulesText, savedCount, STORY_TAGLINE, STORY_TITLE, type Outcome, type StorySlide } from "./story";
import { FUNDAMENTAL, MAX_RETURNS, NO_RETURNS, PLANET_NOTICE, TIERS, judgeReturn, missingHazards, newSince, planetPercent, planetTier, type Ending, type ReturnCause, type Returns } from "./planet";
import { StoryScene } from "./story-scene";
import { CineScene } from "./cine-scene";
import { lastDays, useNasaLayers, VisionBar } from "./vision-bar";
import "./game.css";

const STORE = "lce-juego-v1";
/**
 * `story`: cómo quedó la hoja del cuaderno de cada lugar jugado. `plans`: calidad del mejor plan por lugar (0 a 4).
 * `returns`: regresos usados y lugares a salvo en el último. `ended`: final ya visto. Un guardado anterior no los trae.
 */
interface Saved { hero: Hero | null; badges: Record<string, string[]>; story?: Record<string, Outcome>; plans?: Record<string, number>; returns?: Returns; ended?: Ending | null }

/**
 * Lo que se ve encima de todo: el prólogo, el viaje a 2026, un regreso que no es final, un final o el tráiler.
 * Cada uno es una cinemática en video (cine-scene.tsx). `phase`: «video» mientras corre; «resumen» después, con lo que
 * cambió en la partida (regresos y finales); «texto» si el video no está: la historia en láminas de texto, como antes.
 */
type Phase = "video" | "resumen" | "texto";
type Scene = ({ kind: "prologo" } | { kind: "viaje" } | { kind: "trailer" }
  | { kind: "regreso"; slides: StorySlide[]; summary: StorySlide }
  | { kind: "final"; ending: Ending; slides: StorySlide[]; summary: StorySlide }) & { phase?: Phase };
const ENDING_LABEL: Record<Ending, string> = { bueno: "Final: un nuevo comienzo", intermedio: "Final: un futuro a medias", perdedor: "Final: un futuro perdido" };

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
      // Una respuesta que no es JSON (p. ej. una página de error) no debe mostrarse como «Unexpected token…».
      const payload = await response.json().catch(() => null);
      if (!response.ok || !Array.isArray(payload?.missions)) throw new Error(typeof payload?.detail === "string" ? payload.detail : "No se pudieron leer las misiones.");
      if (!cancelled) setState({ data: payload as MissionsPayload, error: null });
    }).catch((error: Error) => { if (!cancelled) setState({ data: null, error: error.name === "TypeError" ? "No se pudo conectar con la plataforma para leer las misiones." : error.message }); });
    return () => { cancelled = true; };
  }, [attempt]);
  // Al reintentar se borra el error para que se vea «Cargando…» y no el mensaje anterior.
  return { ...state, retry: () => { setState({ data: null, error: null }); setAttempt((value) => value + 1); } };
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
  // Cuadro de la alerta real: recibe el foco al abrirse, cierra con Escape y devuelve el foco a quien lo abrió (el «⚠» del globo).
  const alertRef = useRef<HTMLElement>(null);
  const alertOpener = useRef<HTMLElement | null>(null);
  const alertOpen = stage === "tierra" && !!selectedAlert;
  const closeAlert = useCallback(() => {
    setSelectedAlert(null);
    const opener = alertOpener.current;
    alertOpener.current = null;
    if (opener?.isConnected) opener.focus();
  }, []);
  useEffect(() => {
    if (!alertOpen) return;
    const active = document.activeElement;
    // Si el foco ya está dentro del cuadro (se eligió otra alerta con él abierto), se conserva quien lo abrió primero.
    if (!alertRef.current?.contains(active)) alertOpener.current = active instanceof HTMLElement && active !== document.body ? active : null;
    alertRef.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") closeAlert(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [alertOpen, selectedAlert, closeAlert]);
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

  // Historia: el prólogo de 2045 se ve al crear al héroe; los regresos y los finales se abren al volver a 2045.
  // Son una capa sobre la pantalla.
  const [scene, setScene] = useState<Scene | null>(null);
  const [story, setStory] = useState<Record<string, Outcome>>({});
  const [plans, setPlans] = useState<Record<string, number>>({});
  const [returns, setReturns] = useState<Returns>(NO_RETURNS);
  const [ended, setEnded] = useState<Ending | null>(null);
  const savedPlaces = savedCount(story);
  // Estado del planeta (gamificación declarada, planet.ts) y peligros fundamentales que faltan.
  const percent = useMemo(() => planetPercent(missions, { story, plans }), [missions, story, plans]);
  const tier = planetTier(percent);
  const missing = useMemo(() => missingHazards(missions, story), [missions, story]);
  const fundamentals = missions.length > 0 && missing.length === 0;
  const gained = newSince(returns, savedPlaces);
  // Mala decisión en el panel: el mundo 3D descuenta la salud.
  const [damage, setDamage] = useState<{ id: number; amount: number } | null>(null);
  const hurt = useCallback((amount: number) => setDamage((current) => ({ id: (current?.id ?? 0) + 1, amount })), []);
  const [confirmReturn, setConfirmReturn] = useState(false);

  useEffect(() => {
    const saved = readSaved();
    setBadges(saved.badges);
    setStory(saved.story ?? {});
    setPlans(saved.plans ?? {});
    setReturns(saved.returns ?? NO_RETURNS);
    setEnded(saved.ended ?? null);
    if (saved.hero) { setDraftName(saved.hero.name); setDraftGender(saved.hero.gender); }
  }, []);

  const panelWidth = usePanelWidth(stage === "mision" || stage === "tierra");
  // Una misión cuenta como completada solo si dejó al menos una insignia (un guardado antiguo puede traer listas vacías).
  const completed = useMemo(() => new Set(Object.keys(badges).filter((id) => badges[id]?.length)), [badges]);
  const totalBadges = Object.values(badges).reduce((sum, list) => sum + list.length, 0);
  // Conteos del texto de la Luna, calculados de las misiones: nada se da por hecho.
  const tally = useMemo(() => {
    const warm = missions.filter((item) => item.heat === "calienta");
    return {
      warm: warm.length, warmConfirmed: warm.filter((item) => heatSupport(item) === "confirmada").length,
      cool: missions.filter((item) => item.heat === "enfria").length, unknown: missions.filter((item) => item.heat === "sin_evidencia").length,
    };
  }, [missions]);
  // Rango real de fechas de los análisis (analysis.generated_at); built_at es solo cuándo se escribió el archivo.
  const analysisDays = useMemo(() => {
    const stamps = missions.map((item) => item.analysis.generated_at).filter((value): value is string => !!value).sort();
    const day = (iso: string) => new Date(iso).toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
    if (!stamps.length) return null;
    const [first, last] = [day(stamps[0]), day(stamps[stamps.length - 1])];
    return { text: first === last ? `el ${first}` : `entre el ${first} y el ${last}`, undated: missions.length - stamps.length };
  }, [missions]);

  const startJourney = () => {
    if (!draftGender || !draftName.trim()) return;
    const next = { name: draftName.trim().slice(0, 24), gender: draftGender };
    setHero(next);
    // Después de un final que no es el bueno, crear al viajero empieza una partida nueva.
    if (ended && ended !== "bueno") {
      setStory({}); setPlans({}); setReturns(NO_RETURNS); setEnded(null);
      writeSaved({ ...readSaved(), hero: next, badges, story: {}, plans: {}, returns: NO_RETURNS, ended: null });
    } else {
      writeSaved({ ...readSaved(), hero: next, badges, story });
    }
    // El jugador ve primero el prólogo; al terminarlo (o saltarlo) llega a la colonia lunar.
    setScene({ kind: "prologo" });
  };
  const toMoon = () => { setScene(null); setStage("luna"); };
  // Hoja del cuaderno de la misión en curso. Un lugar que ya quedó a salvo no vuelve a perderse por repetir y fallar.
  const settle = useCallback((id: string, outcome: Outcome) => {
    setStory((current) => {
      if (current[id] === outcome || current[id] === "salvado") return current;
      const next = { ...current, [id]: outcome };
      writeSaved({ ...readSaved(), story: next });
      return next;
    });
  }, []);
  // Viaje a 2026: la cinemática «El viaje» sobre la Luna que se aleja; si el video no está, solo la animación.
  const jump = () => {
    setConfirmReturn(false);
    setStage("viaje");
    setScene({ kind: "viaje" });
  };
  const land = () => { setScene(null); setStage("tierra"); };
  const landLater = () => {
    setScene(null);
    window.setTimeout(() => setStage("tierra"), window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 2700);
  };
  // Fin (o salto) de una cinemática: cada escena sigue a su manera.
  const endCine = () => {
    if (!scene) return;
    if (scene.kind === "prologo") toMoon();
    else if (scene.kind === "viaje") land();
    else if (scene.kind === "trailer") setScene(null);
    else setScene({ ...scene, phase: "resumen" });
  };
  const cineMissing = () => {
    if (!scene) return;
    if (scene.kind === "viaje") landLater();
    else if (scene.kind === "trailer") setScene(null);
    else setScene({ ...scene, phase: "texto" });
  };
  // Plan del paso 3: se guarda la mejor calidad de cada lugar (suma al estado del planeta).
  const notePlan = useCallback((id: string, quality: number) => {
    setPlans((current) => {
      if ((current[id] ?? -1) >= quality) return current;
      const next = { ...current, [id]: quality };
      writeSaved({ ...readSaved(), plans: next });
      return next;
    });
  }, []);
  // Regreso a 2045 (planet.ts): por salud en cero («emergencia») o porque el jugador lo pide. Decide si hay energía
  // para volver a 2026 o si llega un final. Los lugares a salvo se leen del guardado para no depender de un estado viejo.
  const goBack = useCallback((cause: ReturnCause) => {
    const current = readSaved();
    const currentStory = current.story ?? {};
    const currentReturns = current.returns ?? NO_RETURNS;
    const saved = savedCount(currentStory);
    const lacking = missingHazards(missions, currentStory);
    const verdict = judgeReturn(currentReturns, saved, missions.length > 0 && lacking.length === 0);
    setConfirmReturn(false);
    setMission(null);
    setStage("luna");
    if (verdict.kind === "volver") {
      const next = { used: verdict.used, savedAtLast: verdict.savedAtLast };
      setReturns(next);
      writeSaved({ ...current, returns: next });
      const nowTier = planetTier(planetPercent(missions, { story: currentStory, plans: current.plans ?? {} }));
      const facts = { cause, used: next.used, tier: nowTier, gained: saved - currentReturns.savedAtLast };
      setScene({ kind: "regreso", slides: returnSlides(facts), summary: returnSummary(facts) });
    } else {
      setEnded(verdict.ending);
      writeSaved({ ...current, ended: verdict.ending });
      setScene({ kind: "final", ending: verdict.ending, slides: finale(verdict.ending, saved, lacking).slides, summary: finaleSummary(verdict.ending, saved, lacking) });
    }
  }, [missions]);
  // Nueva partida: se borra la historia (hojas, planes, regresos y final), no el héroe ni las insignias.
  const newGame = () => {
    setStory({}); setPlans({}); setReturns(NO_RETURNS); setEnded(null);
    writeSaved({ ...readSaved(), story: {}, plans: {}, returns: NO_RETURNS, ended: null });
    setScene({ kind: "prologo" });
  };
  // El mundo 3D no simula un evento para el aire: allí el reto es la contaminación cotidiana (ADR-050).
  const worldMission = useMemo(() => (mission?.hazard === "aire" ? { ...mission, hazard: null } : mission), [mission]);
  const pick = useCallback((item: Mission) => { setContinent(item.continent); setMission(item); setVisited(new Set()); setWorldFailed(false); setStage("mision"); }, []);
  const complete = (list: string[]) => {
    if (!mission || role !== "jugador") return;
    // Nunca se pierde una insignia ganada: las nuevas se suman a las guardadas. Repetir y fallar no borra nada,
    // y sin ninguna insignia no se guarda la misión (no cuenta como completada).
    const kept = badges[mission.id] ?? [];
    const merged = [...kept, ...list.filter((badge) => !kept.includes(badge))];
    if (merged.length === kept.length) return;
    const next = { ...badges, [mission.id]: merged };
    setBadges(next);
    writeSaved({ ...readSaved(), hero, badges: next, story });
  };
  // Ordenar por temperatura promedio real (NASA POWER desde 2001): los más fríos o los más calientes del planeta o del continente.
  const [order, setOrder] = useState<"todos" | "frios" | "calientes">("todos");
  const pool = continent ? missions.filter((item) => item.continent === continent) : missions;
  const withMean = pool.filter((item) => item.temperature?.mean != null);
  const inContinent = order === "todos" ? (continent ? pool : [])
    : [...withMean].sort((a, b) => (order === "frios" ? 1 : -1) * ((a.temperature!.mean as number) - (b.temperature!.mean as number))).slice(0, continent ? undefined : 10);

  return (
    <main className={`gameShell stage-${stage}${role === "jugador" ? ` planet-t${tier}` : ""}`}>
      <div className="gameStars" aria-hidden />
      <GameGlobe missions={missions} stage={stage} continent={continent} mission={mission} hero={role === "jugador" ? hero : null}
        panelWidth={panelWidth} completed={completed} checkpoints={checkpoints} visited={visited} vision={vision} immersive={immersive}
        alerts={liveAlerts} onAlert={setSelectedAlert} onPick={pick} onReach={reach}
        planetHealth={role === "jugador" && hero ? percent / 100 : null} />
      {/* La clave del mundo es distinta de la del panel (son hermanos): con la misma, React no desmontaba el mundo al salir y quedaba vivo detrás del globo. */}
      {immersive && mission && worldMission && (
        <MissionWorld key={`mundo-${mission.id}`} mission={worldMission} hero={role === "jugador" ? hero : null} checkpoints={checkpoints} visited={visited}
          panelRight={panelWidth} panelBottom={panelWidth ? 0 : Math.round((typeof window !== "undefined" ? window.innerHeight : 800) * 0.6)}
          onReach={reach} onUnavailable={() => setWorldFailed(true)} onLeave={() => { setMission(null); setStage("tierra"); }}
          damage={role === "jugador" ? damage : null} onCollapse={role === "jugador" ? () => goBack("emergencia") : undefined} />
      )}

      {(stage === "luna" || stage === "viaje") && <MoonScene leaving={stage === "viaje"} />}

      {stage === "luna" && role === "jugador" && hero && (
        <div className="gameOnMoon"><HeroModel gender={hero.gender} size={130} pose="wave" label={`${hero.name} en la Luna`} /></div>
      )}


      <header className="gameHud">
        <Link href="/plataforma" className="gameBrand">Los Causas Espaciales</Link>
        {role === "jugador" && hero && stage !== "inicio" && stage !== "avatar" && (
          <p className="gameHeroTag"><i className={`gameHeroDot ${hero.gender}`} aria-hidden /> <b>{hero.name}</b> · {totalBadges} insignias · {completed.size}/{missions.length} misiones · Planeta: {TIERS[tier].label} · Regresos {returns.used}/{MAX_RETURNS}</p>
        )}
        {role === "espectador" && <p className="gameHeroTag">Modo espectador</p>}
      </header>

      {stage === "inicio" && (
        <section className="gameCard" aria-labelledby="start-title">
          <p className="gameEyebrow">NASA Space Apps 2026 · Los Causas Espaciales</p>
          <h1 id="start-title">{STORY_TITLE}</h1>
          <p className="gameTagline">{STORY_TAGLINE}</p>
          <p>Año 2045. La humanidad perdió la Tierra y vive en la Luna. Una sola persona puede viajar a 2026 para cambiar lo que viene, con datos satelitales reales de NASA contrastados con una segunda fuente. ¿Cómo quieres entrar?</p>
          <div className="gameChoices">
            <button type="button" className="primary" onClick={() => { setRole("jugador"); setStage("avatar"); }}>
              <b>Jugador</b><span>Crea a tu viajero, viaja a 2026 y cambia el futuro, misión por misión.</span>
            </button>
            <button type="button" onClick={() => { setRole("espectador"); setStage("tierra"); }}>
              <b>Espectador</b><span>Recorre el planeta y mira los datos de cada lugar, sin jugar.</span>
            </button>
          </div>
          {ended && role === null && <p className="gameMuted">Tu última partida terminó con el final {ended}. Al entrar como jugador puedes empezar una nueva.</p>}
          <div className="gameStartLinks">
            <button type="button" className="gameTrailer" onClick={() => setScene({ kind: "trailer" })}>▶ Ver el tráiler</button>
            <Link href="/plataforma" className="gameLink">Ir a la plataforma Los Causas Espaciales →</Link>
          </div>
        </section>
      )}

      {stage === "avatar" && (
        <section className="gameCard" aria-labelledby="avatar-title">
          <p className="gameEyebrow">Paso 1 de 1</p>
          <h1 id="avatar-title">Crea a tu viajero</h1>
          <div className="gameAvatars" role="radiogroup" aria-label="Figura del viajero">
            {(["mujer", "hombre"] as Gender[]).map((gender) => (
              <button key={gender} type="button" role="radio" aria-checked={draftGender === gender} className={draftGender === gender ? "on" : ""} onClick={() => setDraftGender(gender)}>
                <HeroModel gender={gender} size={110} /><span>{gender === "mujer" ? "Mujer" : "Hombre"}</span>
              </button>
            ))}
          </div>
          <label className="gameName">
            <span>¿Cómo se llama tu viajero?</span>
            <input value={draftName} maxLength={24} onChange={(event) => setDraftName(event.target.value)} placeholder="Por ejemplo: Ayelén"
              onKeyDown={(event) => { if (event.key === "Enter") startJourney(); }} />
          </label>
          <button type="button" className="gameGo" disabled={!draftGender || !draftName.trim()} onClick={startJourney}>Ir a la colonia lunar</button>
          {(!draftGender || !draftName.trim()) && <p className="gameMuted">Elige una figura y escribe un nombre para continuar.</p>}
        </section>
      )}

      {stage === "luna" && hero && (
        <section className="gameCard moon" aria-labelledby="moon-title">
          <p className="gameEyebrow">Año 2045 · Colonia lunar New Horizon</p>
          <h1 id="moon-title">{returns.used === 0 ? `Hola, ${hero.name}` : `Bienvenido de vuelta, ${hero.name}`}</h1>
          {/* Conteos calculados de las misiones: no todos los lugares «necesitan ayuda»; en varios los datos no alcanzan para afirmar nada. */}
          {missions.length ? (
            <p>Desde la colonia ves {missions.length} lugares de la Tierra para investigar. En {tally.warm || "ninguno"} la temperatura sube con evidencia estadística{tally.warm > 0 && <> (en {tally.warmConfirmed || "ninguno"} de ellos coinciden dos fuentes)</>}; en {tally.cool || "ninguno"} baja; y en {tally.unknown || "ninguno"} los datos no alcanzan para afirmarlo. En rojo, los que se calientan; en azul, los que se enfrían; en gris, donde los datos aún no alcanzan. Punto relleno: dos fuentes coinciden.</p>
          ) : <p>Desde la colonia se ven los lugares de la Tierra que vas a investigar.</p>}
          {role === "jugador" && (
            <>
              <p className="gameStoryNote">{rulesText()}</p>
              <p className="gameStoryNote">Estado del planeta en 2045: <b>{TIERS[tier].label}</b> ({percent} %). Regresos usados: {returns.used} de {MAX_RETURNS}. <small>{PLANET_NOTICE}</small></p>
            </>
          )}
          {ended && ended !== "bueno" ? (
            <button type="button" className="gameGo" onClick={newGame}>Empezar una nueva partida</button>
          ) : (
            <button type="button" className="gameGo" onClick={jump} disabled={!missions.length}>⏳ Activar Génesis: viajar a 2026</button>
          )}
          {!missions.length && (error
            ? <p className="gameError" role="alert">No se pudieron cargar las misiones: {error} <button type="button" onClick={retry}>Reintentar</button></p>
            : <p className="gameMuted" role="status">Cargando las misiones…</p>)}
        </section>
      )}

      {stage === "viaje" && <p className="gameTravel" role="status">Génesis te envía a 2026…</p>}

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
              {/* «Se calienta» y «se enfría» van con su respaldo; punto hueco si la segunda fuente no lo confirma. */}
              {inContinent.map((item) => (
                <li key={item.id}>
                  <button type="button" onClick={() => pick(item)} className={`heat-${item.heat}${heatUnconfirmed(item) ? " hollow" : ""}`}>
                    <i /><span><b>{item.name}</b><small>{item.country} · {item.temperature?.mean != null ? `${item.temperature.mean.toFixed(1)} °C promedio · ` : ""}{HEAT_LABEL[item.heat]}{heatSupportPhrase(item) && ` (${heatSupportPhrase(item)})`}</small></span>{completed.has(item.id) && <em>✓</em>}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="gameLegend"><span className="heat-calienta"><i />Se calienta</span><span className="heat-enfria"><i />Se enfría</span><span className="heat-sin_evidencia"><i />Sin evidencia suficiente</span><span className="fill"><i />Relleno: dos fuentes coinciden</span><span className="fill hollow"><i />Hueco: la segunda fuente no lo confirma</span></p>
          {error && <p className="gameError" role="alert">{error} <button type="button" onClick={retry}>Reintentar</button></p>}
          {/* TERRA 2045: transmisión de la doctora Nikol, estado del planeta, misiones fundamentales y regresos. */}
          {role === "jugador" && (
            <div className="gameReturn">
              <p className="gameRadio"><b>Dra. Nikol · transmisión desde 2045</b>{nikolMessage(savedPlaces, missing, fundamentals)}</p>
              <div className="gamePlanet" aria-label={`Estado del planeta: ${TIERS[tier].label}, ${percent} por ciento`}>
                <p><b>Estado del planeta en 2045</b><span>{TIERS[tier].label} · {percent} %</span></p>
                <i aria-hidden><em style={{ width: `${percent}%` }} /></i>
                <small>{PLANET_NOTICE}</small>
              </div>
              <ul className="gameFundamentals" aria-label="Misiones fundamentales">
                {FUNDAMENTAL.map((item) => {
                  const done = !missing.some((gap) => gap.id === item.id);
                  return <li key={item.id} className={done ? "done" : ""}><span aria-hidden>{done ? "✓" : item.icon}</span>{item.label}</li>;
                })}
              </ul>
              <p><b>Regresos</b>{returns.used} de {MAX_RETURNS} usados · {savedPlaces === 1 ? "1 lugar a salvo" : `${savedPlaces} lugares a salvo`} · {gained === 1 ? "1 nuevo desde el último regreso" : `${gained} nuevos desde el último regreso`}.</p>
              {fundamentals ? (
                <button type="button" className="primary" onClick={() => goBack("voluntario")}>Regreso final a 2045</button>
              ) : !confirmReturn ? (
                <button type="button" onClick={() => setConfirmReturn(true)}>Regresar a 2045</button>
              ) : (
                <div className="gameConfirm" role="group" aria-label="Confirmar el regreso">
                  <p>{gained === 0 ? "No salvaste ningún lugar nuevo desde el último regreso: si regresas ahora, será el final." : returns.used + 1 >= MAX_RETURNS ? "Es tu último regreso: sin las misiones fundamentales, verás el final intermedio." : "Usarás un regreso. Como el futuro mejoró, podrás volver a 2026."}</p>
                  <button type="button" onClick={() => goBack("voluntario")}>Sí, regresar</button>
                  <button type="button" onClick={() => setConfirmReturn(false)}>Seguir en 2026</button>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {stage === "tierra" && selectedAlert && (
        <section className="gameAlertInfo" role="dialog" aria-modal="false" aria-labelledby="alert-title" tabIndex={-1} ref={alertRef}>
          <p className={`badge level-${selectedAlert.level}`}>⚠ Alerta real {selectedAlert.level === "red" ? "roja" : "naranja"} · GDACS</p>
          <h2 id="alert-title">{selectedAlert.kind_label}: {selectedAlert.place}</h2>
          {selectedAlert.severity && <p>{selectedAlert.severity}</p>}
          <p className="gameMuted">Desde {selectedAlert.started} · actualizada {selectedAlert.updated}{selectedAlert.also_seen_by?.length ? ` · también la ve ${selectedAlert.also_seen_by.join(", ")}` : ""}</p>
          {(() => { const m = nearestMission(selectedAlert); return m ? <button type="button" className="gameGo" onClick={() => { setSelectedAlert(null); pick(m); }}>Jugar una misión parecida: {m.name}</button> : null; })()}
          {selectedAlert.url && <a href={selectedAlert.url} target="_blank" rel="noreferrer">Ver el reporte en GDACS ↗</a>}
          <small>Es una alerta real e informativa, no un sistema de alerta temprana: sigue siempre a las autoridades locales.</small>
          <button type="button" className="gameBack" onClick={closeAlert}>Cerrar</button>
        </section>
      )}

      {stage === "tierra" && (
        <VisionBar layers={nasaLayers} active={visionLayer} date={visionDate} playing={playing} onPick={pickVision} onPlay={() => setPlaying((value) => !value)} />
      )}

      {stage === "mision" && mission && (
        <MissionPanel key={mission.id} mission={mission} role={role ?? "espectador"} heroName={hero?.name ?? ""} done={completed.has(mission.id)}
          checkpoints={checkpoints} visited={visited} pageSaved={story[mission.id] === "salvado"} onOutcome={settle}
          onPlan={notePlan} onHurt={hurt} briefing={companionLine(mission) ? undefined : nikolBrief(mission)}
          onComplete={complete} onBack={() => { setMission(null); setStage("tierra"); }} />
      )}

      {scene && (scene.phase ?? "video") === "video" && (
        <CineScene key={scene.kind === "final" ? `final_${scene.ending}` : scene.kind}
          name={scene.kind === "final" ? `final_${scene.ending}` : scene.kind}
          label={scene.kind === "prologo" ? "Prólogo: año 2045" : scene.kind === "viaje" ? "El viaje a 2026" : scene.kind === "regreso" ? "Regreso a 2045" : scene.kind === "trailer" ? "Tráiler" : ENDING_LABEL[scene.ending]}
          skipLabel={scene.kind === "trailer" ? "Cerrar" : "Saltar"}
          onEnd={endCine} onUnavailable={cineMissing} />
      )}
      {scene?.kind === "prologo" && scene.phase === "texto" && (
        <StoryScene slides={PROLOGUE} tone="perdido" label="Prólogo: año 2045" doneLabel="Ir a la colonia" onDone={toMoon} onSkip={toMoon} />
      )}
      {scene?.kind === "regreso" && (scene.phase === "texto" || scene.phase === "resumen") && (
        <StoryScene slides={scene.phase === "resumen" ? [scene.summary] : scene.slides} tone="perdido" label="Regreso a 2045" doneLabel="Volver a la colonia"
          onDone={() => setScene(null)} onSkip={() => setScene(null)} />
      )}
      {scene?.kind === "final" && (scene.phase === "texto" || scene.phase === "resumen") && (
        <StoryScene slides={scene.phase === "resumen" ? [scene.summary] : scene.slides} tone={scene.ending === "bueno" ? "salvado" : "perdido"}
          label={ENDING_LABEL[scene.ending]}
          doneLabel={scene.ending === "bueno" ? "Seguir explorando la Tierra" : "Empezar una nueva partida"}
          onDone={() => { setScene(null); if (scene.ending === "bueno") setStage("tierra"); else newGame(); }}
          onSkip={() => setScene(null)}
          link={{ href: "/plataforma", label: "Abrir la plataforma Los Causas Espaciales" }} />
      )}

      {stage !== "inicio" && stage !== "avatar" && data && (
        <p className="gameFoot">{analysisDays ? `Análisis de las misiones generados ${analysisDays.text} (UTC)${analysisDays.undated ? `; ${analysisDays.undated} sin fecha` : ""}` : "Análisis de las misiones sin fecha registrada"}, con la API de la plataforma. Imagen: NASA Blue Marble{stage === "luna" || stage === "viaje" ? " · Luna: NASA Scientific Visualization Studio (LRO, cámara LROC y altímetro LOLA)" : ""}.</p>
      )}
    </main>
  );
}
