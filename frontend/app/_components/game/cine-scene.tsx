"use client";

// Cinemáticas de TERRA 2045 dentro del juego (ADR-050): prólogo, viaje a 2026, regreso a 2045, los tres finales y el
// tráiler. Son los videos que arma scripts/video/render.py (versión web/, copiada a frontend/public/cine/): voz,
// música y escenas, sin subtítulos quemados; los subtítulos van en un .vtt aparte para poder apagarlos o cambiarlos.
// Voz y subtítulos en español o en inglés (la preferencia queda guardada en este navegador). Siempre se puede saltar
// (botón o Escape) y pausar (clic sobre el video o Espacio). Si el video no está o no carga, avisa con
// `onUnavailable` y el juego muestra la historia en texto, como antes.

import { useCallback, useEffect, useRef, useState } from "react";

export type CineName = "trailer" | "prologo" | "viaje" | "regreso" | "final_bueno" | "final_intermedio" | "final_perdedor";
type Lang = "es" | "en";
type Pref = { lang: Lang; subs: boolean };

const PREF_KEY = "terra2045-cine";
const BASE = "/cine";

function readPref(): Pref {
  try {
    const value = JSON.parse(window.localStorage.getItem(PREF_KEY) ?? "{}") as Partial<Pref>;
    return { lang: value.lang === "en" ? "en" : "es", subs: value.subs !== false };
  } catch {
    return { lang: "es", subs: true };
  }
}

function writePref(pref: Pref) {
  try { window.localStorage.setItem(PREF_KEY, JSON.stringify(pref)); } catch { /* sin almacenamiento: no se recuerda */ }
}

export function CineScene({ name, label, skipLabel = "Saltar", onEnd, onUnavailable }: {
  name: CineName;
  /** Nombre de la cinemática para lectores de pantalla y la barra de controles. */
  label: string;
  skipLabel?: string;
  /** Al terminar el video o al saltarlo. */
  onEnd: () => void;
  /** El video no existe o no se puede reproducir: el juego cae a la historia en texto. */
  onUnavailable: () => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const box = useRef<HTMLElement>(null);
  const resumeAt = useRef(0);
  const ended = useRef(false);
  const [pref, setPref] = useState<Pref>(readPref);
  const [blocked, setBlocked] = useState(false);
  const [paused, setPaused] = useState(false);
  const [progress, setProgress] = useState(0);
  const [idle, setIdle] = useState(false);

  const finish = useCallback(() => {
    if (ended.current) return;
    ended.current = true;
    video.current?.pause();
    onEnd();
  }, [onEnd]);

  const play = useCallback(() => {
    const element = video.current;
    if (!element) return;
    // Sin un clic previo en el sitio, el navegador puede negar el sonido automático: se pide un clic para empezar.
    element.play().then(() => setBlocked(false)).catch(() => setBlocked(true));
  }, []);

  const toggle = useCallback(() => {
    const element = video.current;
    if (!element) return;
    if (element.paused) play(); else element.pause();
  }, [play]);

  // Subtítulos: el único track es el del idioma elegido; se muestra u oculta según la preferencia.
  const applyTracks = useCallback(() => {
    const element = video.current;
    if (!element) return;
    const tracks = element.textTracks;
    for (let index = 0; index < tracks.length; index += 1) tracks[index].mode = pref.subs ? "showing" : "hidden";
  }, [pref.subs]);
  useEffect(applyTracks, [applyTracks]);

  const choose = (next: Partial<Pref>) => {
    const value = { ...pref, ...next };
    if (next.lang && next.lang !== pref.lang) resumeAt.current = video.current?.currentTime ?? 0;
    setPref(value);
    writePref(value);
  };

  // Teclado: Escape salta; Espacio pausa o sigue (salvo sobre un botón, donde Espacio lo pulsa).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); finish(); }
      if (event.key === " " && !(event.target instanceof HTMLButtonElement)) { event.preventDefault(); toggle(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [finish, toggle]);

  // Los controles se esconden mientras el video corre y el mouse no se mueve.
  useEffect(() => {
    if (paused || blocked) { setIdle(false); return; }
    let timer = window.setTimeout(() => setIdle(true), 2600);
    const wake = () => { setIdle(false); window.clearTimeout(timer); timer = window.setTimeout(() => setIdle(true), 2600); };
    window.addEventListener("mousemove", wake);
    window.addEventListener("keydown", wake);
    return () => { window.clearTimeout(timer); window.removeEventListener("mousemove", wake); window.removeEventListener("keydown", wake); };
  }, [paused, blocked]);

  useEffect(() => { box.current?.focus(); }, []);

  const src = `${BASE}/${name}_${pref.lang}`;
  return (
    <section ref={box} tabIndex={-1} className={`gameCine${idle ? " idle" : ""}`} role="dialog" aria-modal="true" aria-label={label}>
      <video
        ref={video}
        key={src}
        className="gameCineVideo"
        src={`${src}.mp4`}
        autoPlay
        playsInline
        preload="auto"
        onLoadedMetadata={(event) => {
          applyTracks();
          if (resumeAt.current > 0) { event.currentTarget.currentTime = Math.min(resumeAt.current, event.currentTarget.duration - 0.5); resumeAt.current = 0; }
          play();
        }}
        onPlay={() => setPaused(false)}
        onPause={() => setPaused(true)}
        onTimeUpdate={(event) => { const { currentTime, duration } = event.currentTarget; if (duration) setProgress(currentTime / duration); }}
        onEnded={finish}
        onError={() => { if (pref.lang === "en") choose({ lang: "es" }); else onUnavailable(); }}
        onClick={toggle}
      >
        <track kind="subtitles" src={`${src}.vtt`} srcLang={pref.lang} label={pref.lang === "es" ? "Español" : "English"} default={pref.subs} />
      </video>

      {blocked && (
        <button type="button" className="gameCinePlay" onClick={play}>▶ Ver la cinemática</button>
      )}

      <div className="gameCineBar" aria-hidden><span style={{ width: `${(progress * 100).toFixed(2)}%` }} /></div>
      <div className="gameCineControls">
        <span className="gameCineLabel">{label}</span>
        <button type="button" onClick={toggle} aria-label={paused ? "Seguir" : "Pausar"}>{paused ? "▶ Seguir" : "❚❚ Pausa"}</button>
        <button type="button" aria-pressed={pref.subs} onClick={() => choose({ subs: !pref.subs })}>Subtítulos: {pref.subs ? "sí" : "no"}</button>
        <div className="gameCineLang" role="group" aria-label="Idioma de la voz y de los subtítulos">
          <button type="button" aria-pressed={pref.lang === "es"} onClick={() => choose({ lang: "es" })}>ES</button>
          <button type="button" aria-pressed={pref.lang === "en"} onClick={() => choose({ lang: "en" })}>EN</button>
        </div>
        <button type="button" className="gameCineSkip" onClick={finish}>{skipLabel} ⏭</button>
      </div>
    </section>
  );
}
