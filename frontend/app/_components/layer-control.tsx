"use client";

import { useEffect, useState } from "react";
import type { MapLayer, VisualLayerState } from "./types";

const formatDate = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-PE", { day: "numeric", month: "short", year: "numeric" });

export function LayerControl({ value, onChange }: { value: VisualLayerState | null; onChange: (next: VisualLayerState | null) => void }) {
  const [layers, setLayers] = useState<MapLayer[] | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    fetch("/api/map-layers").then((response) => response.json()).then((payload) => {
      if (!Array.isArray(payload.layers)) throw new Error();
      setLayers(payload.layers);
    }).catch(() => setError("Catálogo de capas no disponible."));
  }, []);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);

  const groups = [...new Set((layers ?? []).map((layer) => layer.group))];
  const choose = (layer: MapLayer | null) => onChange(layer ? { layer, date: layer.latest_date ?? "default", opacity: value?.opacity ?? 0.75 } : null);

  return (
    <div className="layerControl">
      <button className="layerToggle" aria-expanded={open} aria-controls="panel-capas" onClick={() => setOpen((current) => !current)}>
        Capas{value ? ` · ${value.layer.label}` : ""}
      </button>
      {open && (
        <div className="layerPanel" id="panel-capas" role="dialog" aria-label="Capas visuales del mapa">
          <div className="layerPanelHead">
            <p className="layerPanelNote">Capas visuales NASA GIBS: muestran qué se ve en una fecha y <b>no entran en el cálculo</b>.</p>
            <button onClick={() => setOpen(false)}>Cerrar</button>
          </div>
          {error && <p className="errorMessage" role="alert">{error}</p>}
          {!layers && !error && <p className="layerPanelNote">Leyendo el catálogo de NASA…</p>}
          {layers && (
            <fieldset>
              <legend className="srOnly">Capa visual</legend>
              <label className="layerOption"><input type="radio" name="capa" checked={!value} onChange={() => choose(null)} /><span>Solo mapa base (Blue Marble)</span></label>
              {groups.map((group) => (
                <div key={group} className="layerGroup">
                  <span>{group}</span>
                  {layers.filter((layer) => layer.group === group).map((layer) => (
                    <label key={layer.id} className="layerOption">
                      <input type="radio" name="capa" checked={value?.layer.id === layer.id} onChange={() => choose(layer)} />
                      <span>{layer.label}<small>{layer.latest_date ? `al ${formatDate(layer.latest_date)}` : "fecha sin verificar"}{layer.notice ? " · serie detenida" : ""}</small></span>
                    </label>
                  ))}
                </div>
              ))}
            </fieldset>
          )}
          {value && (
            <div className="layerSettings">
              <p>{value.layer.description}</p>
              {value.layer.notice && <p className="layerNotice">{value.layer.notice}</p>}
              <label>Fecha
                <input type="date" value={value.date === "default" ? "" : value.date} min={value.layer.first_date ?? undefined} max={value.layer.latest_date ?? undefined}
                       disabled={!value.layer.latest_date} onChange={(event) => event.target.value && onChange({ ...value, date: event.target.value })} />
              </label>
              {value.layer.period_days && value.layer.period_days > 1 && <small>Compuesto de {value.layer.period_days} días: GIBS muestra el compuesto que contiene la fecha.</small>}
              <label>Opacidad
                <input type="range" min={0.2} max={1} step={0.05} value={value.opacity} onChange={(event) => onChange({ ...value, opacity: +event.target.value })} />
              </label>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function LayerLegend({ value }: { value: VisualLayerState }) {
  return (
    <div className="layerLegend">
      <p><b>{value.layer.label}</b> · {value.date === "default" ? "fecha más reciente" : formatDate(value.date)} · {value.layer.source} · visual, no entra en el cálculo</p>
      {/* eslint-disable-next-line @next/next/no-img-element -- leyenda SVG oficial de GIBS, sin optimización posible */}
      {value.layer.legend_url && <img src={value.layer.legend_url} alt={`Leyenda de ${value.layer.label}`} loading="lazy" />}
    </div>
  );
}
