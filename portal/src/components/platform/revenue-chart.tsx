"use client";
/**
 * Billed vs collected, by month.
 *
 * Two series on ONE axis because they are the same measure in the same currency at two
 * stages — what went out on invoices, and what actually arrived. The gap between them is
 * the point of the chart, which is why they share a scale rather than getting an axis each.
 */
import {
  Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { RevenueMonth } from "@/lib/api/types";
import { formatMinor, formatMinorCompact, monthLabel, monthLabelLong } from "@/lib/utils";

interface Props {
  data: RevenueMonth[];
  currency: string | null;
  height?: number;
}

function LegendSwatch({ color, shape, label }: {
  color: string; shape: "bar" | "line"; label: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="inline-block shrink-0 rounded-sm"
        style={{
          background: color,
          width: shape === "line" ? 14 : 9,
          height: shape === "line" ? 2 : 9,
        }}
      />
      {/* Ink token, not the series colour — the swatch carries identity, the text carries
          the words. */}
      <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</span>
    </span>
  );
}

function ChartTooltip({ active, payload, label, currency }: {
  active?: boolean;
  payload?: Array<{ dataKey?: string | number; value?: number }>;
  label?: string;
  currency: string | null;
}) {
  if (!active || !payload?.length) return null;
  const get = (key: string) =>
    payload.find((p) => p.dataKey === key)?.value ?? 0;
  const invoiced = get("invoiced_cents");
  const collected = get("collected_cents");
  const gap = invoiced - collected;

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
      }}
    >
      <p className="font-semibold mb-1.5" style={{ color: "var(--text-primary)" }}>
        {label ? monthLabelLong(label) : ""}
      </p>
      <div className="flex flex-col gap-1">
        <span className="flex items-center justify-between gap-4">
          <LegendSwatch color="var(--chart-series-1)" shape="bar" label="Invoiced" />
          <span className="tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>
            {formatMinor(invoiced, currency)}
          </span>
        </span>
        <span className="flex items-center justify-between gap-4">
          <LegendSwatch color="var(--chart-series-2)" shape="line" label="Collected" />
          <span className="tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>
            {formatMinor(collected, currency)}
          </span>
        </span>
        {gap > 0 && (
          <span
            className="flex items-center justify-between gap-4 pt-1 mt-0.5"
            style={{ borderTop: "1px solid var(--border)" }}
          >
            <span style={{ color: "var(--text-secondary)" }}>Uncollected</span>
            <span className="tabular-nums" style={{ color: "var(--health-warn)" }}>
              {formatMinor(gap, currency)}
            </span>
          </span>
        )}
      </div>
    </div>
  );
}

export function RevenueChart({ data, currency, height = 260 }: Props) {
  const hasMoney = data.some((d) => d.invoiced_cents > 0 || d.collected_cents > 0);

  if (!hasMoney) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-1 text-center"
        style={{ height, color: "var(--text-secondary)" }}
      >
        <p className="text-xs">No invoices recorded yet.</p>
        <p className="text-[11px]">
          The trend fills in as subscriptions bill — it reads invoices, not seat counts.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="flex items-center gap-4 mb-2">
        <LegendSwatch color="var(--chart-series-1)" shape="bar" label="Invoiced" />
        <LegendSwatch color="var(--chart-series-2)" shape="line" label="Collected" />
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid
            vertical={false}
            stroke="var(--chart-grid)"
            strokeDasharray="2 4"
          />
          <XAxis
            dataKey="month"
            tickFormatter={monthLabel}
            tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tickFormatter={(v: number) => formatMinorCompact(v, currency)}
            tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={58}
          />
          <Tooltip
            content={<ChartTooltip currency={currency} />}
            cursor={{ fill: "var(--border)", opacity: 0.35 }}
          />
          <Bar
            dataKey="invoiced_cents"
            name="Invoiced"
            fill="var(--chart-series-1)"
            radius={[4, 4, 0, 0]}
            maxBarSize={26}
          />
          <Line
            type="monotone"
            dataKey="collected_cents"
            name="Collected"
            stroke="var(--chart-series-2)"
            strokeWidth={2}
            dot={{ r: 3, fill: "var(--chart-series-2)", strokeWidth: 2, stroke: "var(--surface)" }}
            activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--surface)" }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}
