"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function ComparisonChart({ data }: { data: { name: string; irradiancia: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 4 }}>
        <CartesianGrid stroke="#2e3136" vertical={false} />
        <XAxis dataKey="name" stroke="#9aa4ae" tickLine={false} axisLine={false} />
        <YAxis stroke="#9aa4ae" tickLine={false} axisLine={false} />
        <Tooltip formatter={(value) => [`${value} kWh/m²/día`, "Irradiancia media"]} contentStyle={{ background: "#141618", border: "1px solid #35393e", borderRadius: 2 }} cursor={{ fill: "#202326" }} />
        <Bar dataKey="irradiancia" name="Irradiancia media" fill="#38d9c3" />
      </BarChart>
    </ResponsiveContainer>
  );
}
