"use client";
import type { ReactNode } from "react";
import Link from "next/link";

/**
 * Reusable "hero insight card" shape used on the dashboard:
 * title -> muted subtitle -> dominant metric(s) -> chart/breakdown body -> action buttons.
 * Modeled on the Microsoft 365 admin center home cards: elevated white surface,
 * generous padding, rounded-2xl corners, soft shadow in light mode.
 */
export function InsightCard({
  title,
  subtitle,
  children,
  actions,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div
      className="rounded-2xl p-6 flex flex-col shadow-[0_1px_2px_rgba(15,23,42,0.04),0_8px_24px_rgba(15,23,42,0.06)] dark:shadow-none"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        {title}
      </h3>
      {subtitle && (
        <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
          {subtitle}
        </p>
      )}
      <div className="mt-4 flex-1">{children}</div>
      {actions && <div className="mt-5 pt-4 flex flex-wrap gap-2" style={{ borderTop: "1px solid var(--border)" }}>{actions}</div>}
    </div>
  );
}

/** The single dominant number a hero card leads with, e.g. "923". */
export function InsightMetric({ value, label }: { value: ReactNode; label?: string }) {
  return (
    <div className="mb-4">
      <p className="text-3xl font-bold tabular-nums leading-none" style={{ color: "var(--text-primary)" }}>
        {value}
      </p>
      {label && (
        <p className="text-xs mt-2 font-medium" style={{ color: "var(--text-secondary)" }}>
          {label}
        </p>
      )}
    </div>
  );
}

/** A row of small side-by-side stats, e.g. "Licensed users / Unlicensed users / Prompts used". */
export function InsightMiniStats({
  items,
}: {
  items: { label: string; value: ReactNode; accent?: string }[];
}) {
  return (
    <div className="grid gap-3 mb-4" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
      {items.map((it, i) => (
        <div key={i}>
          <p className="text-lg font-semibold tabular-nums" style={{ color: it.accent ?? "var(--text-primary)" }}>
            {it.value}
          </p>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
            {it.label}
          </p>
        </div>
      ))}
    </div>
  );
}

/** A single "Label — value/max" row with a colored horizontal progress bar beneath it. */
export function InsightProgressRow({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex items-center justify-between gap-2 text-xs mb-1.5">
        <span className="truncate" style={{ color: "var(--text-primary)" }}>{label}</span>
        <span className="shrink-0 tabular-nums" style={{ color: "var(--text-secondary)" }}>
          {value.toLocaleString()}/{max.toLocaleString()}
        </span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color, transition: "width 0.4s ease" }} />
      </div>
    </div>
  );
}

/** Outlined/ghost action button anchored at the bottom of a hero card. */
export function InsightButton({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="text-xs font-medium px-3.5 py-2 rounded-lg transition-colors hover:bg-blue-500/5"
      style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}
    >
      {children}
    </Link>
  );
}
