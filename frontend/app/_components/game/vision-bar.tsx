"use client";

import { useEffect, useState } from "react";
import { VISIONS, type NasaLayer } from "./game-types";

const dateText = (iso: string) => new Date(`${iso}T12:00:00Z`).toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

/** Las fechas de los últimos días de una capa diaria, de la más antigua a la más reciente. */
export function lastDays(latest: string, count: number): string[] {
  const end = new Date(`${latest}T12:00:00Z`);
  return Array.from({ length: count }, (_, i) => new Date(end.getTime() - (count - 1 - i) * 86_400_000).toISOString().slice(0, 10));
}

/** Catálogo de capas de NASA (el mismo de la consola). Si no llega, la barra no se muestra. */
export function useNasaLayers(): NasaLayer[] {
  const [layers, setLayers] = useState<NasaLayer[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/map-layers").then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { layers: NasaLayer[] }) => { if (!cancelled) setLayers(payload.layers.filter((layer) => layer.latest_date && !layer.notice?.startsWith("Serie detenida"))); })
      .catch(() => { /* sin visiones */ });
    return () => { cancelled = true; };
  }, []);
  return layers;
}

export function VisionBar({ layers, active, date, playing, onPick, onPlay }: {
  layers: NasaLayer[];
  active: NasaLayer | null;
  date: string | null;
  playing: boolean;
  onPick: (layer: NasaLayer | null) => void;
  onPlay: () => void;
}) {
  const available = VISIONS.map((vision) => ({ vision, layer: layers.find((layer) => layer.id === vision.id) })).filter((item) => item.layer);
  if (!available.length) return null;
  const hint = active ? VISIONS.find((vision) => vision.id === active.id)?.hint : null;
  return (
    <section className="gameVision" aria-label="Visión del héroe: capas reales de NASA">
      <p className="gameVisionTitle">Visión del héroe <small>datos reales de NASA</small></p>
      <div className="gameVisionChips">
        {available.map(({ vision, layer }) => (
          <button key={vision.id} type="button" aria-pressed={active?.id === vision.id} onClick={() => onPick(active?.id === vision.id ? null : layer!)}>{vision.name}</button>
        ))}
      </div>
      {active && date && (
        <div className="gameVisionInfo" role="status">
          <p><b>{active.label}</b> · dato del {dateText(date)}</p>
          {hint && <p>{hint}</p>}
          {active.legend_url && <img src={active.legend_url} alt={`Leyenda de ${active.label}`} />}
          {active.period_days === 1 && (
            <button type="button" className="gameVisionPlay" onClick={onPlay}>{playing ? "❚❚ Pausar" : "▶ Ver los últimos 7 días"}</button>
          )}
          {active.notice && <small className="gameVisionNotice">Aviso del catálogo: {active.notice}</small>}
          <small>NASA GIBS · {active.description} Es una imagen para mirar: no entra en los cálculos.</small>
        </div>
      )}
    </section>
  );
}
