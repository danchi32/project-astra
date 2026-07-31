"use client";
import Link from "next/link";
import {
  AlertTriangle, ArrowRight, CheckCircle2, ShieldCheck, RefreshCw, XCircle, Clock,
} from "lucide-react";
import type { DashboardAction, PatchState, TrendPoint } from "@/lib/api/types";
import type { ComplianceSummary } from "@/lib/api/compliance";
import type { FleetIssue } from "@/lib/api/fleet";

const SEVERITY: Record<string, { color: string; bg: string }> = {
  high: { color: "#ef4444", bg: "rgba(239,68,68,0.10)" },
  medium: { color: "#f59e0b", bg: "rgba(245,158,11,0.10)" },
  low: { color: "#64748b", bg: "rgba(100,116,139,0.10)" },
};

function Panel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl p-4 ${className}`}
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      {children}
    </div>
  );
}

/**
 * The decisions, above everything else.
 *
 * The dashboard used to open with counts — devices, online, average CPU. All true, none of
 * it answering the question people actually arrive with. These are the things a person can
 * do something about today, each linking to where that is done.
 */
export function NeedsYou({ actions }: { actions?: DashboardAction[] }) {
  // Undefined means still loading; an empty array means genuinely nothing to do, and those
  // deserve different words — "nothing needs you" while data is in flight would be a lie.
  if (!actions) {
    return <Panel><div className="h-14 animate-pulse rounded-lg" style={{ background: "var(--bg)" }} /></Panel>;
  }

  if (actions.length === 0) {
    return (
      <Panel>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg shrink-0" style={{ background: "rgba(16,185,129,0.12)", color: "#10b981" }}>
            <CheckCircle2 size={18} />
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Nothing needs you right now
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              No approvals waiting, no failing updates, every device reporting in.
            </p>
          </div>
        </div>
      </Panel>
    );
  }

  return (
    <Panel>
      <p className="text-xs font-medium uppercase tracking-wide mb-3" style={{ color: "var(--text-secondary)" }}>
        Needs you
      </p>
      <div className="flex flex-col gap-2">
        {actions.map((a) => {
          const s = SEVERITY[a.severity] ?? SEVERITY.low;
          return (
            <Link key={a.key} href={a.href}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors hover:bg-brand-500/5"
              style={{ border: "1px solid var(--border)", background: "var(--bg)" }}>
              <span className="p-1.5 rounded-lg shrink-0" style={{ background: s.bg, color: s.color }}>
                <AlertTriangle size={15} />
              </span>
              <span className="flex-1 min-w-0">
                <span className="block text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {a.title}
                </span>
                <span className="block text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                  {a.detail}
                </span>
              </span>
              <ArrowRight size={15} className="shrink-0" style={{ color: "var(--text-secondary)" }} />
            </Link>
          );
        })}
      </div>
    </Panel>
  );
}

/** A 14-day sparkline. Deliberately unlabelled and small — it exists to show a direction,
 *  and the number beside it carries the value. */
function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return null;
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const span = max - min || 1;
  const d = points
    .map((p, i) => `${(i / (points.length - 1)) * 100},${28 - ((p - min) / span) * 24}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="w-full h-8 mt-2" aria-hidden>
      <polyline points={d} fill="none" stroke="var(--accent)" strokeWidth="1.5"
        vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function CompliancePatchRow({
  compliance, patch, trend,
}: {
  compliance?: ComplianceSummary;
  patch?: PatchState;
  trend?: TrendPoint[];
}) {
  const worst = compliance?.checks
    ? [...compliance.checks].sort((a, b) => b.failed - a.failed).find((c) => c.failed > 0)
    : undefined;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <Panel>
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} style={{ color: "var(--accent)" }} />
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Compliance</p>
        </div>
        <p className="text-3xl font-semibold mt-2" style={{ color: "var(--text-primary)" }}>
          {compliance ? `${compliance.score}%` : "—"}
        </p>
        <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
          {compliance
            ? `${compliance.compliant} compliant · ${compliance.at_risk} at risk · ${compliance.non_compliant} failing`
            : "Scoring the fleet…"}
        </p>
        {/* The single check failing most often — the one fix that would move the score most. */}
        {worst && (
          <p className="text-xs mt-2 pt-2 border-t" style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}>
            Most common failure: <span style={{ color: "var(--text-primary)" }}>{worst.label}</span> on {worst.failed}
          </p>
        )}
        <Link href="/compliance" className="text-xs mt-2 inline-block" style={{ color: "var(--accent)" }}>
          Open compliance →
        </Link>
      </Panel>

      <Panel>
        <div className="flex items-center gap-2">
          <RefreshCw size={16} style={{ color: "var(--accent)" }} />
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Windows updates</p>
        </div>
        {/* Three states, never one number: only one of them is fixed by installing again. */}
        <div className="mt-3 flex flex-col gap-2">
          <PatchRow icon={<Clock size={13} />} color="#f59e0b"
            label="Pending" value={patch?.pending} sub={patch ? `on ${patch.devices_with_pending} device${patch.devices_with_pending === 1 ? "" : "s"}` : ""} />
          <PatchRow icon={<RefreshCw size={13} />} color="#3b82f6"
            label="Installed, needs restart" value={patch?.awaiting_restart}
            sub={patch ? `on ${patch.devices_awaiting_restart} device${patch.devices_awaiting_restart === 1 ? "" : "s"}` : ""} />
          <PatchRow icon={<XCircle size={13} />} color="#ef4444"
            label="Failed" value={patch?.failed} sub="Windows returned an error" />
        </div>
      </Panel>

      <Panel>
        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Reporting in</p>
        <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
          Devices that sent telemetry, last 14 days
        </p>
        <p className="text-3xl font-semibold mt-2" style={{ color: "var(--text-primary)" }}>
          {trend?.length ? trend[trend.length - 1].devices_reporting : "—"}
        </p>
        <Sparkline points={(trend ?? []).map((t) => t.devices_reporting)} />
        {trend && trend.length === 0 && (
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            No history yet — rollups build up one day at a time.
          </p>
        )}
      </Panel>
    </div>
  );
}

function PatchRow({ icon, color, label, value, sub }: {
  icon: React.ReactNode; color: string; label: string; value?: number; sub: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="p-1 rounded shrink-0" style={{ background: `${color}1a`, color }}>{icon}</span>
      <span className="text-sm font-medium tabular-nums w-8" style={{ color: "var(--text-primary)" }}>
        {value ?? "—"}
      </span>
      <span className="text-xs min-w-0" style={{ color: "var(--text-secondary)" }}>
        {label}{sub ? ` · ${sub}` : ""}
      </span>
    </div>
  );
}

/** The three issues affecting the most devices, already ranked by the fleet service. */
export function TopIssues({ issues }: { issues?: FleetIssue[] }) {
  if (!issues || issues.length === 0) return null;
  return (
    <Panel>
      <div className="flex items-center justify-between gap-3 mb-3">
        <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
          Affecting the most devices
        </p>
        <Link href="/fleet" className="text-xs" style={{ color: "var(--accent)" }}>All issues →</Link>
      </div>
      <div className="flex flex-col gap-2">
        {issues.map((i) => {
          const s = SEVERITY[i.severity] ?? SEVERITY.low;
          return (
            <Link key={i.key} href="/fleet"
              className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors hover:bg-brand-500/5"
              style={{ border: "1px solid var(--border)", background: "var(--bg)" }}>
              <span className="text-xs font-medium px-2 py-0.5 rounded-full shrink-0"
                style={{ color: s.color, background: s.bg }}>
                {i.affected.length}
              </span>
              <span className="flex-1 min-w-0">
                <span className="block text-sm truncate" style={{ color: "var(--text-primary)" }}>{i.title}</span>
              </span>
              {/* Says up front whether this one can be pushed, so the page doesn't imply a
                  one-click fix exists where it doesn't. */}
              <span className="text-xs shrink-0" style={{ color: i.fix_action_id ? "var(--accent)" : "var(--text-secondary)" }}>
                {i.fix_action_id ? "Fix all" : "Needs review"}
              </span>
            </Link>
          );
        })}
      </div>
    </Panel>
  );
}
