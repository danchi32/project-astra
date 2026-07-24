"use client";

interface GaugeProps {
  label: string;
  value: number; // 0-100
  unit?: string;
}

function gaugeColor(v: number) {
  if (v >= 90) return "#ef4444";
  if (v >= 75) return "#f59e0b";
  return "#b246d4";
}

export function Gauge({ label, value, unit = "%" }: GaugeProps) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const offset = circ - (value / 100) * circ;
  const color = gaugeColor(value);

  return (
    <div
      className="flex flex-col items-center gap-2 p-5 rounded-xl"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="var(--border)" strokeWidth="8" />
        <circle
          cx="48" cy="48" r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 48 48)"
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
        <text x="48" y="52" textAnchor="middle" fontSize="18" fontWeight="700" fill="var(--text-primary)">
          {Math.round(value)}{unit}
        </text>
      </svg>
      <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
        {label}
      </p>
    </div>
  );
}
