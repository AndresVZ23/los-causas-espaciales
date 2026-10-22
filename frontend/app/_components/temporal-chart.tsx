"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type TemporalPoint = { year: number } & Record<string, number>;
type Series = { key: string; label: string; color: string };

export default function TemporalChart({ data, series }: { data: TemporalPoint[]; series: Series[] }) {
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

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 12, right: 20, left: -8, bottom: 0 }}>
        <CartesianGrid stroke="#2e3136" strokeDasharray="2 3" vertical />
        <XAxis dataKey="year" stroke="#9aa4ae" tickLine={false} axisLine={{ stroke: "#3a3f44" }} minTickGap={24} />
        <YAxis stroke="#9aa4ae" tickLine={false} axisLine={false} width={42} tickFormatter={(value) => Number(value).toFixed(1)} />
        <Tooltip
          labelFormatter={(value) => `Año ${value}`}
          contentStyle={{ background: "#101315", border: "1px solid #3a3f44", borderRadius: 2, fontFamily: "var(--font-data-mono)" }}
          cursor={{ stroke: "#38d9c3", strokeWidth: 1 }}
        />
        {series.map((item) => (
          <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={item.color} strokeWidth={1.6} dot={{ r: 2, fill: item.color, strokeWidth: 0 }} activeDot={{ r: 4, stroke: "#080c0d", strokeWidth: 2 }} isAnimationActive={false} connectNulls={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
