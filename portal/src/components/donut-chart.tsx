"use client";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

export interface DonutDatum {
  name: string;
  value: number;
  color: string;
}

export function DonutChart({ data, height = 180 }: { data: DonutDatum[]; height?: number }) {
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
      <PieChart>
        <Pie
          data={filtered}
          dataKey="value"
          nameKey="name"
          innerRadius="58%"
          outerRadius="90%"
          paddingAngle={2}
          strokeWidth={0}
        >
          {filtered.map((d) => (
            <Cell key={d.name} fill={d.color} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: "var(--text-primary)" }}
          itemStyle={{ color: "var(--text-secondary)" }}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, color: "var(--text-secondary)" }}
          formatter={(value) => <span style={{ color: "var(--text-secondary)" }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
