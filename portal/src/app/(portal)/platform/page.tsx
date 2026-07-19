"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, ArrowRight, AlertTriangle, Clock } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getPlatformOverview, getPlatformBilling, getPlatformReports } from "@/lib/api/platform";
import type { PlatformBillingRow } from "@/lib/api/types";

function fmtMoney(cents: number): string {
  return `$${(cents / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function daysLeft(iso: string | null): number | null {
  if (!iso) return null;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

const card = { background: "var(--surface)", border: "1px solid var(--border)" } as const;

function Kpi({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: boolean }) {
  return (
    <div className="rounded-xl p-4" style={accent ? { background: "rgba(37,99,235,0.06)", border: "1px solid var(--accent)" } : card}>
      <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{value}</p>
      {sub && <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{sub}</p>}
    </div>
  );
}

export default function PlatformOverviewPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const enabled = !!me?.is_platform_admin;
  const { data: overview } = useQuery({ queryKey: ["platform-overview"], queryFn: getPlatformOverview, enabled });
  const { data: billing } = useQuery({ queryKey: ["platform-billing"], queryFn: getPlatformBilling, enabled });
  const { data: reports } = useQuery({ queryKey: ["platform-reports"], queryFn: getPlatformReports, enabled });

  if (me && !me.is_platform_admin) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Platform administrator access required.</p>;
  }

  const trialsEndingSoon: PlatformBillingRow[] = (billing?.rows ?? [])
    .filter((r) => r.subscription_status === "trialing" && r.trial_ends_at !== null)
    .filter((r) => { const d = daysLeft(r.trial_ends_at); return d !== null && d <= 7; })
    .sort((a, b) => (daysLeft(a.trial_ends_at) ?? 0) - (daysLeft(b.trial_ends_at) ?? 0));
  const pastDue = (billing?.rows ?? []).filter((r) => r.subscription_status === "past_due" || r.subscription_status === "suspended");

  const maxSignups = Math.max(1, ...(reports?.signups_by_month ?? []).map((m) => m.count));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            <ShieldCheck size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Platform overview</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              The business at a glance — revenue, growth and risk
            </p>
          </div>
        </div>
        <Link href="/platform/organizations"
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: "var(--accent)" }}>
          Manage organizations <ArrowRight size={15} />
        </Link>
      </div>

      {/* Revenue KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi accent label="Monthly revenue (MRR)"
          value={billing?.mrr_cents != null ? fmtMoney(billing.mrr_cents) : "—"}
          sub={billing?.mrr_cents != null ? `${billing.active_subscriptions} active subscription${billing.active_subscriptions === 1 ? "" : "s"}` : "Set ASTRA_PRICE_PER_SEAT_CENTS to compute"} />
        <Kpi label="Annual run rate (ARR)" value={billing?.arr_cents != null ? fmtMoney(billing.arr_cents) : "—"} />
        <Kpi label="New sign-ups (30d)" value={overview?.signups_30d ?? "…"} sub={`${overview?.total_organizations ?? 0} organizations total`} />
        <Kpi label="Licenses sold" value={overview?.licenses_sold ?? "…"} />
      </div>

      {/* Fleet & risk KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <Kpi label="Devices" value={overview?.total_devices ?? "…"} />
        <Kpi label="Online now" value={overview?.online_devices ?? "…"} />
        <Kpi label="Users" value={overview?.total_users ?? "…"} />
        <Kpi label="Trials ending ≤7d" value={overview?.trials_ending_7d ?? "…"} />
        <Kpi label="Past due / suspended" value={(billing?.past_due ?? 0) + (billing?.suspended ?? 0)} />
        <Kpi label="Fixes awaiting approval" value={overview?.remediation_pending ?? "…"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Growth chart */}
        <div className="rounded-xl p-5" style={card}>
          <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Organization sign-ups — last 12 months</h2>
          <div className="flex items-end gap-1.5 h-32">
            {(reports?.signups_by_month ?? []).map((m) => (
              <div key={m.month} className="flex-1 flex flex-col items-center gap-1" title={`${m.month}: ${m.count}`}>
                <span className="text-[10px] tabular-nums" style={{ color: "var(--text-secondary)" }}>{m.count || ""}</span>
                <div className="w-full rounded-t"
                  style={{ height: `${Math.max(3, (m.count / maxSignups) * 100)}%`, background: "var(--accent)", opacity: m.count ? 1 : 0.15 }} />
                <span className="text-[9px]" style={{ color: "var(--text-secondary)" }}>{m.month.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Risk lists */}
        <div className="space-y-4">
          <div className="rounded-xl p-5" style={card}>
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
              <Clock size={14} style={{ color: "#f59e0b" }} /> Trials ending within 7 days
            </h2>
            {trialsEndingSoon.length === 0 && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>None — no conversions at risk.</p>}
            <ul className="space-y-2">
              {trialsEndingSoon.slice(0, 5).map((r) => (
                <li key={r.id} className="flex items-center justify-between text-sm">
                  <Link href={`/platform/${r.id}`} className="hover:underline font-medium" style={{ color: "var(--accent)" }}>{r.name}</Link>
                  <span style={{ color: "#f59e0b" }}>{daysLeft(r.trial_ends_at)}d left</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl p-5" style={card}>
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "var(--text-primary)" }}>
              <AlertTriangle size={14} style={{ color: "#ef4444" }} /> Past due & suspended
            </h2>
            {pastDue.length === 0 && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>None — all customers in good standing.</p>}
            <ul className="space-y-2">
              {pastDue.slice(0, 5).map((r) => (
                <li key={r.id} className="flex items-center justify-between text-sm">
                  <Link href={`/platform/${r.id}`} className="hover:underline font-medium" style={{ color: "var(--accent)" }}>{r.name}</Link>
                  <span className="capitalize" style={{ color: "#ef4444" }}>{r.subscription_status.replace("_", " ")}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
