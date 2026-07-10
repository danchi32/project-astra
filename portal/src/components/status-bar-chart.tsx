"use client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

export interface BarDatum {
  name: string;
  value: number;
  color: string;
}

export function StatusBarChart({ data, height = 200 }: { data: BarDatum[]; height?: number }) {
  const filtered = data.filter((d) => d.value > 0);
  if (!filtered.length) {
    return (
      <div
        className="flex items-center justify-center text-xs"
        style={{ height, color: "var(--text-secondary)" }}
      >
        No data yet
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={filtered} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="name"
          tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={false}
          interval={0}
          angle={filtered.length > 5 ? -30 : 0}
          textAnchor={filtered.length > 5 ? "end" : "middle"}
          height={filtered.length > 5 ? 48 : 24}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: "var(--text-primary)" }}
          itemStyle={{ color: "var(--text-secondary)" }}
          cursor={{ fill: "var(--border)", opacity: 0.3 }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {filtered.map((d) => (
            <Cell key={d.name} fill={d.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
