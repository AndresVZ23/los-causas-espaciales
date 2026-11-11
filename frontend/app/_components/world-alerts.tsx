"use client";

import { useEffect, useRef, useState } from "react";
import { formatDay } from "./format";
import type { AlertMarkerStyle } from "./geo-map";
import type { AlertLevel, WorldAlert, WorldAlertsResponse, WorldPlace } from "./types";
import { nearKm } from "./zone/use-zones";
import type { ZoneSummary } from "./zone/zone-data";

/** Una alerta «cae» en una zona si su punto está a menos de esta distancia del centro de la maqueta. */
const ZONE_REACH_KM = 40;

const LEVEL_LABEL: Record<AlertLevel, string> = { red: "Alerta roja", orange: "Alerta naranja", green: "Alerta verde", none: "Sin nivel" };

/** Alertas del mundo: se piden una sola vez, al abrir el panel. Si la consulta falla, el mensaje dice qué pasó. */
export function useWorldAlerts(enabled: boolean) {
  const [data, setData] = useState<WorldAlertsResponse | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!enabled || data) return;
    let cancelled = false;
    setError("");
    fetch("/api/world-alerts").then(async (response) => {
      const payload = await response.json();
      if (!response.ok || !Array.isArray(payload.alerts)) throw new Error();
      if (!cancelled) setData(payload as WorldAlertsResponse);
    }).catch(() => { if (!cancelled) setError("No se pudieron leer las alertas. Cierre y vuelva a abrir el panel para reintentar."); });
    return () => { cancelled = true; };
  }, [enabled, data]);
  return { data, error };
}

type Props = {
  open: boolean; onOpen: (open: boolean) => void; shown: boolean; onHide: () => void; data: WorldAlertsResponse | null; error: string;
  selected: string | null; onSelect: (alert: WorldAlert | null) => void; onAnalyze: (alert: WorldAlert, module: "hazards" | "climate") => void;
  markerStyle: AlertMarkerStyle; onMarkerStyle: (style: AlertMarkerStyle) => void;
  zones: ZoneSummary[]; selectedZone: string | null; onZone: (zone: ZoneSummary) => void; onEnterZone: (id: string) => void;
};

/** Botón y panel sobre el mapa. El nivel es el de GDACS; analizar un punto muestra su fondo climático, no el evento. */
export function WorldAlertsControl({ open, onOpen, shown, onHide, data, error, selected, onSelect, onAnalyze, markerStyle, onMarkerStyle, zones, selectedZone, onZone, onEnterZone }: Props) {
  const [onlyPeru, setOnlyPeru] = useState(false);
  // Foco: al abrir entra al panel (botón «Cerrar») y al cerrar vuelve al botón que lo abrió. El panel no es modal:
  // el mapa y el resto de la consola siguen disponibles.
  const toggleRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open && !wasOpen.current) closeRef.current?.focus();
    if (!open && wasOpen.current) toggleRef.current?.focus();
    wasOpen.current = open;
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") onOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open, onOpen]);

  const alerts = (data?.alerts ?? []).filter((alert) => !onlyPeru || alert.in_peru);
  const peruCount = (data?.alerts ?? []).filter((alert) => alert.in_peru).length;
  return (
    <div className="alertsControl">
      <button ref={toggleRef} className="layerToggle alertsToggle" aria-expanded={open} aria-controls="panel-alertas" onClick={() => onOpen(!open)}>
        <i aria-hidden="true" />Alertas en el mundo{data ? ` · ${data.alerts.length}` : ""}
      </button>
      {open && (
        <div className="layerPanel alertsPanel" id="panel-alertas" role="dialog" aria-label="Alertas en el mundo">
          <div className="layerPanelHead">
            <p className="layerPanelNote">Eventos de los últimos {data?.window_days ?? 60} días. El nivel lo asigna <b>GDACS</b>; <b>NASA EONET</b> es el segundo testigo.</p>
            <button ref={closeRef} onClick={() => onOpen(false)}>Cerrar</button>
          </div>
          <p className="layerPanelNote">Al cerrar, los marcadores siguen en el globo. {shown && <button className="alertsHide" onClick={onHide}>Quitar del mapa</button>}</p>
          {zones.length > 0 && (
            <div className="zonesList">
              <p className="layerPanelNote"><b>Zonas para recorrer.</b> Maquetas en bloques de lugares reales, con lo que la plataforma sabe de cada uno.</p>
              {zones.map((zone) => (
                <div key={zone.id} className={`zoneRow${zone.id === selectedZone ? " selected" : ""}`}>
                  <button className="zoneRowName" aria-pressed={zone.id === selectedZone} onClick={() => onZone(zone)}>
                    <i aria-hidden="true" /><span><b>{zone.name}, {zone.country}</b><small>{zone.tagline}</small></span>
                  </button>
                  <button className="zoneEnter" onClick={() => onEnterZone(zone.id)} aria-label={`Entrar a la zona ${zone.name}`}>Entrar</button>
                </div>
              ))}
            </div>
          )}
          {error && <p className="errorMessage" role="alert">{error}</p>}
          {!data && !error && <p className="layerPanelNote" role="status">Consultando GDACS y NASA EONET…</p>}
          {data && (
            <>
              <div className="alertsFilter" role="group" aria-label="Filtro de alertas">
                <button className={onlyPeru ? "" : "active"} aria-pressed={!onlyPeru} onClick={() => setOnlyPeru(false)}>Mundo · {data.alerts.length}</button>
                <button className={onlyPeru ? "active" : ""} aria-pressed={onlyPeru} onClick={() => setOnlyPeru(true)}>Perú · {peruCount}</button>
              </div>
              <div className="alertsFilter" role="group" aria-label="Estilo de los marcadores">
                <button className={markerStyle === "blocks" ? "active" : ""} aria-pressed={markerStyle === "blocks"} onClick={() => onMarkerStyle("blocks")}>Bloques</button>
                <button className={markerStyle === "pulses" ? "active" : ""} aria-pressed={markerStyle === "pulses"} onClick={() => onMarkerStyle("pulses")}>Pulsos</button>
              </div>
              {alerts.length === 0 && <p className="layerPanelNote">Sin eventos publicados en este filtro. No significa que no haya emergencias: solo que estas fuentes no listan ninguna.</p>}
              <ul className="alertsList">
                {alerts.map((alert) => {
                  const isOpen = alert.id === selected;
                  const zoneHere = isOpen ? zones.find((zone) => nearKm(alert.latitude, alert.longitude, zone.latitude, zone.longitude) < ZONE_REACH_KM) : undefined;
                  return (
                    <li key={alert.id} className={`level-${alert.level}${isOpen ? " selected" : ""}`}>
                      <button className="alertRow" aria-expanded={isOpen} onClick={() => onSelect(isOpen ? null : alert)}>
                        <i className={alert.current ? "live" : ""} aria-hidden="true" />
                        <span><b>{alert.title}</b><small>{alert.place}</small></span>
                        <em>{LEVEL_LABEL[alert.level]}<small>{formatDay(alert.updated)}{alert.current ? " · vigente" : ""}</small></em>
                      </button>
                      {isOpen && (
                        <div className="alertDetail">
                          <p>{alert.kind_label} · {alert.source} · del {formatDay(alert.started)} al {formatDay(alert.updated)}{alert.severity ? ` · ${alert.severity}` : ""}</p>
                          <p>{alert.also_seen_by.length ? `También en ${alert.also_seen_by.join(" y ")}: dos fuentes publican este evento.` : alert.source === "GDACS"
                            ? "NASA EONET no lista un evento equivalente cerca y en estas fechas." : "GDACS no publica una alerta naranja o roja equivalente."}</p>
                          <div className="alertActions">
                            {zoneHere && <button className="zoneEnter" onClick={() => onEnterZone(zoneHere.id)}>Entrar a la zona</button>}
                            <button onClick={() => onAnalyze(alert, "hazards")}>Analizar amenazas aquí</button>
                            <button onClick={() => onAnalyze(alert, "climate")}>Analizar clima aquí</button>
                            <a href={alert.url} target="_blank" rel="noreferrer">Ver en {alert.source}</a>
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
              <div className="alertsFoot">
                {data.sources.map((source) => (
                  <p key={source.name}><b>{source.name}</b> · {source.provenance}{source.downloaded_at ? ` · ${formatDay(source.downloaded_at)}` : ""}<span>{source.note}</span></p>
                ))}
                <details><summary>Cómo se arma esta lista</summary>{data.method.map((note) => <p key={note}>{note}</p>)}<p>{data.disclaimer}</p></details>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** Buscador de lugares del mundo: solo ubica un sitio; el análisis sigue saliendo de las fuentes de datos. */
export function PlaceSearch({ slots, onPick }: { slots: string[]; onPick: (place: WorldPlace, slot: number) => void }) {
  const [query, setQuery] = useState("");
  const [places, setPlaces] = useState<WorldPlace[] | null>(null);
  const [error, setError] = useState("");
  const [slot, setSlot] = useState(0);
  const target = Math.min(slot, Math.max(slots.length - 1, 0));

  useEffect(() => {
    const text = query.trim();
    if (text.length < 2) { setPlaces(null); setError(""); return; }
    // Cada consulta cancela la anterior: una respuesta lenta de un texto viejo no puede pisar los resultados del actual.
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(`/api/places?q=${encodeURIComponent(text)}`, { signal: controller.signal }).then(async (response) => {
        const payload = await response.json();
        if (controller.signal.aborted) return;
        if (!response.ok || !Array.isArray(payload.places)) throw new Error(typeof payload.detail === "string" ? payload.detail : "");
        setPlaces(payload.places); setError("");
      }).catch((exception: Error) => { if (controller.signal.aborted) return; setPlaces(null); setError(exception.message || "El buscador de lugares no respondió."); });
    }, 350);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [query]);

  return (
    <div className="placeSearch">
      <label htmlFor="buscar-lugar">Buscar un lugar del mundo</label>
      <div className="placeSearchRow">
        <input id="buscar-lugar" value={query} placeholder="Ciudad o región: Nairobi, Sevilla, Piura…" onChange={(event) => setQuery(event.target.value)} autoComplete="off" />
        {slots.length > 1 && (
          <select aria-label="Sitio que se reemplaza" value={target} onChange={(event) => setSlot(+event.target.value)}>
            {slots.map((label, index) => <option key={index} value={index}>Reemplaza: {label || `sitio ${index + 1}`}</option>)}
          </select>
        )}
      </div>
      {error && <p className="errorMessage" role="alert">{error}</p>}
      {places && places.length === 0 && <p className="territoryHint">Sin resultados para «{query.trim()}». Pruebe con otro nombre o escriba las coordenadas.</p>}
      {places && places.length > 0 && (
        <ul className="territoryResults" aria-label="Lugares encontrados">
          {places.map((place) => (
            <li key={`${place.name}-${place.latitude}-${place.longitude}`}>
              <button onClick={() => { onPick(place, target); setQuery(""); setPlaces(null); }}>
                <b>{place.name}</b><span>{place.detail || "Sin región publicada"} · {place.latitude.toFixed(3)}, {place.longitude.toFixed(3)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
