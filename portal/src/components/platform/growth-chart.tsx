"use client";
/**
 * New customer organizations per month.
 *
 * One series, so no legend — the panel title names it. Empty months are kept rather than
 * filtered out: a gap in acquisition is exactly what this chart is for.
 */
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonthCount } from "@/lib/api/types";
import { monthLabel, monthLabelLong } from "@/lib/utils";

function GrowthTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value?: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const count = payload[0]?.value ?? 0;
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
      }}
    >
      <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
        {label ? monthLabelLong(label) : ""}
      </p>
      <p style={{ color: "var(--text-secondary)" }}>
        {count} new organization{count === 1 ? "" : "s"}
      </p>
    </div>
  );
}

export function GrowthChart({ data, height = 150 }: { data: MonthCount[]; height?: number }) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center text-xs"
        style={{ height, color: "var(--text-secondary)" }}>
        No sign-up history yet.
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--chart-grid)" strokeDasharray="2 4" />
        <XAxis
          dataKey="month"
          tickFormatter={monthLabel}
          tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={44}
        />
        <Tooltip content={<GrowthTooltip />} cursor={{ fill: "var(--border)", opacity: 0.35 }} />
        <Bar dataKey="count" fill="var(--chart-series-1)" radius={[4, 4, 0, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}
