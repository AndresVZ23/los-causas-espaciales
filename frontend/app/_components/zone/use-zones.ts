"use client";

import { useEffect, useState } from "react";
import type { ZoneSummary } from "./zone-data";

const TRIES = 4;

/**
 * Zonas que se pueden recorrer. Se piden al encender las alertas; si la API aún no responde se reintenta unas pocas
 * veces y, si sigue sin responder, el panel continúa sin esa sección.
 */
export function useZones(enabled: boolean): ZoneSummary[] {
  const [zones, setZones] = useState<ZoneSummary[] | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled || zones || attempt >= TRIES) return;
    let cancelled = false;
    let retry = 0;
    fetch("/api/zones").then(async (response) => {
      const payload = await response.json();
      if (!response.ok || !Array.isArray(payload)) throw new Error();
      if (!cancelled) setZones(payload as ZoneSummary[]);
    }).catch(() => { if (!cancelled) retry = window.setTimeout(() => setAttempt((value) => value + 1), 3000); });
    return () => { cancelled = true; window.clearTimeout(retry); };
  }, [enabled, zones, attempt]);
  return zones ?? EMPTY;
}
const EMPTY: ZoneSummary[] = [];

/** Distancia aproximada en kilómetros entre dos puntos cercanos (basta para saber si una alerta cae en una zona). */
export function nearKm(latA: number, lonA: number, latB: number, lonB: number): number {
  const dLat = (latA - latB) * 111.32;
  const dLon = (lonA - lonB) * 111.32 * Math.cos(((latA + latB) / 2) * (Math.PI / 180));
  return Math.hypot(dLat, dLon);
}
