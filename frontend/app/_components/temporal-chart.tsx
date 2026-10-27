"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatNumber } from "./format";

type TemporalPoint = { year: number } & Record<string, number>;
// `dash`: series de contraste (otra fuente para el mismo índice), punteadas y sin puntos para no competir con la principal.
type Series = { key: string; label: string; color: string; dash?: string };

function niceStep(raw: number) {
  const power = 10 ** Math.floor(Math.log10(raw));
  const scaled = raw / power;
  return (scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10) * power;
}

// Dominio legible sin exagerar: el tramo visible es al menos 1.6× el rango observado y 12 % del nivel medio,
// y una magnitud no negativa nunca baja de cero.
export function readableDomain(values: number[]) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const mid = (min + max) / 2;
  const span = Math.max((max - min) * 1.6, Math.abs(mid) * 0.12, 0.1);
  let low = mid - span / 2;
  const high = mid + span / 2;
  if (min >= 0 && low < 0) low = 0;
  const step = niceStep((high - low) / 5);
  const digits = Math.max(0, -Math.floor(Math.log10(step)));
  const start = Math.floor(low / step) * step;
  const end = Math.ceil(high / step) * step;
  const ticks: number[] = [];
  for (let tick = start; tick <= end + step / 2; tick += step) ticks.push(+tick.toFixed(digits));
  return { domain: [ticks[0], ticks[ticks.length - 1]] as [number, number], ticks, digits };
}

export default function TemporalChart({ data, series, unit }: { data: TemporalPoint[]; series: Series[]; unit: string }) {
  if (!data.length) {
    return (
      <div className="temporalEmpty" role="status">
        <svg viewBox="0 0 900 210" preserveAspectRatio="none" aria-hidden="true">
          {[30, 70, 110, 150, 190].map((y) => <line key={y} x1="44" y1={y} x2="884" y2={y} />)}
          {[120, 280, 440, 600, 760].map((x) => <line key={x} x1={x} y1="18" x2={x} y2="190" />)}
        </svg>
        <div><strong>Serie temporal aún no disponible</strong><span>Ejecute el análisis para graficar medias anuales reales de NASA POWER.</span></div>
      </div>
    );
  }

  const values = data.flatMap((point) => series.map((item) => point[item.key]).filter((value): value is number => typeof value === "number"));
  const axis = readableDomain(values);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 12, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#2e3136" strokeDasharray="2 3" vertical />
        <XAxis dataKey="year" stroke="#9aa4ae" tickLine={false} axisLine={{ stroke: "#3a3f44" }} minTickGap={24} />
        <YAxis stroke="#9aa4ae" tickLine={false} axisLine={false} width={44} domain={axis.domain} ticks={axis.ticks} allowDataOverflow={false} tickFormatter={(value) => Number(value).toFixed(axis.digits)} />
        <Tooltip
          labelFormatter={(value) => `Año ${value}`}
          formatter={(value, name) => [`${formatNumber(Number(value), 3)} ${unit}`, name]}
          contentStyle={{ background: "#101315", border: "1px solid #3a3f44", borderRadius: 2, fontFamily: "var(--font-data-mono)", fontSize: 11 }}
          cursor={{ stroke: "#38d9c3", strokeWidth: 1 }}
        />
        {series.map((item) => (
          <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={item.color} strokeWidth={item.dash ? 1.2 : 1.6} strokeDasharray={item.dash}
            strokeOpacity={item.dash ? 0.85 : 1} dot={item.dash ? false : { r: 2, fill: item.color, strokeWidth: 0 }} activeDot={{ r: item.dash ? 3 : 4, stroke: "#080c0d", strokeWidth: 2 }}
            isAnimationActive={false} connectNulls={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
