"use client";
/**
 * Shared furniture for the operator console.
 *
 * These exist so the console reads as one surface rather than a pile of cards: one panel
 * treatment, one KPI shape, one way of saying "healthy" or "at risk". Everything is themed
 * through CSS variables, so light and dark come from the same markup.
 */
import type { ReactNode } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, MinusCircle, type LucideIcon } from "lucide-react";
import type { HealthBand, SubscriptionStatus } from "@/lib/api/types";

/* ── surfaces ─────────────────────────────────────────────────────────────── */

export function Panel({
  children, className = "", padded = true,
}: { children: ReactNode; className?: string; padded?: boolean }) {
  return (
    <div
      className={`rounded-xl ${padded ? "p-5" : ""} ${className}`}
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      {children}
    </div>
  );
}

export function SectionHeading({
  title, description, action,
}: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-3 flex-wrap mb-3">
      <div>
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {title}
        </h2>
        {description && (
          <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}

/* ── KPI ──────────────────────────────────────────────────────────────────── */

/**
 * One headline figure.
 *
 * `hint` is for the thing the number does not say on its own — what it is derived from,
 * or why it is dashed out. A KPI showing "—" with no explanation reads as broken.
 */
export function Kpi({
  label, value, hint, tone = "default", icon: Icon, href,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "default" | "accent" | "good" | "warn" | "bad";
  icon?: LucideIcon;
  href?: string;
}) {
  const toneColor =
    tone === "accent" ? "var(--accent)"
      : tone === "good" ? "var(--health-good)"
        : tone === "warn" ? "var(--health-warn)"
          : tone === "bad" ? "var(--health-bad)"
            : "var(--text-primary)";

  const body = (
    <div
      className="rounded-xl p-4 h-full transition-colors"
      style={{
        background: "var(--surface)",
        border: `1px solid ${tone === "accent" ? "var(--accent)" : "var(--border)"}`,
      }}
    >
      <div className="flex items-center gap-1.5">
        {Icon && <Icon size={13} style={{ color: "var(--text-secondary)" }} />}
        <p
          className="text-[11px] font-medium uppercase tracking-wide"
          style={{ color: "var(--text-secondary)" }}
        >
          {label}
        </p>
      </div>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums" style={{ color: toneColor }}>
        {value}
      </p>
      {hint && (
        <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{hint}</p>
      )}
    </div>
  );

  return href ? <Link href={href} className="block h-full">{body}</Link> : body;
}

/* ── status ───────────────────────────────────────────────────────────────── */

const BAND: Record<HealthBand, { label: string; color: string; icon: LucideIcon }> = {
  healthy: { label: "Healthy", color: "var(--health-good)", icon: CheckCircle2 },
  watch: { label: "Watch", color: "var(--health-warn)", icon: MinusCircle },
  at_risk: { label: "At risk", color: "var(--health-bad)", icon: AlertTriangle },
};

/** A health band, always as icon + word + colour — never colour alone. */
export function HealthPill({ band, score }: { band: HealthBand; score?: number }) {
  const { label, color, icon: Icon } = BAND[band];
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap"
      style={{ color, background: `color-mix(in srgb, ${color} 12%, transparent)` }}
    >
      <Icon size={12} />
      {label}
      {score != null && <span className="tabular-nums opacity-70">{score}</span>}
    </span>
  );
}

const SUB_STATUS: Record<string, { label: string; color: string }> = {
  active: { label: "Active", color: "var(--health-good)" },
  trialing: { label: "Trial", color: "var(--accent)" },
  past_due: { label: "Past due", color: "var(--health-bad)" },
  suspended: { label: "Suspended", color: "var(--health-bad)" },
  canceled: { label: "Canceled", color: "var(--text-secondary)" },
};

export function StatusPill({ status }: { status: SubscriptionStatus }) {
  const s = SUB_STATUS[status] ?? { label: status, color: "var(--text-secondary)" };
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap"
      style={{ color: s.color, background: `color-mix(in srgb, ${s.color} 12%, transparent)` }}
    >
      {s.label}
    </span>
  );
}

/** A horizontal share bar — used where a percentage needs a shape as well as a number. */
export function Meter({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <span
      className="inline-block w-14 h-1.5 rounded-full overflow-hidden align-middle shrink-0"
      style={{ background: "var(--border)" }}
    >
      <span className="block h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
    </span>
  );
}

/* ── states ───────────────────────────────────────────────────────────────── */

export function EmptyNote({ icon: Icon, text }: { icon: LucideIcon; text: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <Icon size={22} style={{ color: "var(--text-secondary)" }} />
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{text}</p>
    </div>
  );
}

export function ErrorNote({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <AlertTriangle size={22} style={{ color: "var(--health-bad)" }} />
      <p className="text-xs" style={{ color: "var(--health-bad)" }}>{text}</p>
    </div>
  );
}

export function LoadingBlock({ height = 120 }: { height?: number }) {
  return (
    <div className="animate-pulse rounded-lg" style={{ height, background: "var(--bg)" }} />
  );
}
