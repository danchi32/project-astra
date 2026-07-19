"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CreditCard } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getPlatformBilling } from "@/lib/api/platform";
import type { SubscriptionStatus } from "@/lib/api/types";

const STATUS_COLOR: Record<SubscriptionStatus, string> = {
  trialing: "#3b82f6", active: "#10b981", past_due: "#f59e0b", suspended: "#ef4444", canceled: "#64748b",
};

function fmtMoney(cents: number | null): string {
  if (cents == null) return "—";
  return `$${(cents / 100).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

const card = { background: "var(--surface)", border: "1px solid var(--border)" } as const;

export default function PlatformBillingPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: billing, isLoading } = useQuery({
    queryKey: ["platform-billing"],
    queryFn: getPlatformBilling,
    enabled: !!me?.is_platform_admin,
  });

  if (me && !me.is_platform_admin) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Platform administrator access required.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <CreditCard size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Billing</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Revenue across every organization — subscriptions, providers and pricing
          </p>
        </div>
      </div>

      {billing && billing.price_per_seat_cents == null && (
        <div className="rounded-lg px-4 py-3 text-sm" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid #f59e0b", color: "var(--text-primary)" }}>
          No per-seat price configured — revenue shows as “—”. Set <code className="font-mono">ASTRA_PRICE_PER_SEAT_CENTS</code> on the backend to compute MRR/ARR.
        </div>
      )}

      {/* Revenue KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-xl p-4" style={{ background: "rgba(37,99,235,0.06)", border: "1px solid var(--accent)" }}>
          <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>MRR</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{fmtMoney(billing?.mrr_cents ?? null)}</p>
        </div>
        <div className="rounded-xl p-4" style={card}>
          <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>ARR</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{fmtMoney(billing?.arr_cents ?? null)}</p>
        </div>
        <div className="rounded-xl p-4" style={card}>
          <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>List price / seat / month</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{fmtMoney(billing?.price_per_seat_cents ?? null)}</p>
        </div>
        <div className="rounded-xl p-4" style={card}>
          <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Subscriptions</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{billing?.active_subscriptions ?? "…"}</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
            {billing ? `${billing.trialing} trialing · ${billing.past_due} past due · ${billing.canceled} canceled` : ""}
          </p>
        </div>
      </div>

      {/* Provider mix */}
      {billing && Object.keys(billing.by_provider).length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {Object.entries(billing.by_provider).map(([provider, stat]) => (
            <div key={provider} className="rounded-lg px-3 py-2 text-sm flex items-center gap-2" style={card}>
              <span className="font-medium capitalize" style={{ color: "var(--text-primary)" }}>{provider}</span>
              <span style={{ color: "var(--text-secondary)" }}>
                {stat.subscriptions} sub{stat.subscriptions === 1 ? "" : "s"}{stat.mrr_cents != null ? ` · ${fmtMoney(stat.mrr_cents)}/mo` : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Per-org economics */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Organization", "Status", "Provider", "Licenses", "Discount", "Seat price", "MRR", "Renews", "Trial ends"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={9} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {billing?.rows.map((r) => (
                <tr key={r.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/platform/${r.id}`} className="hover:underline" style={{ color: "var(--accent)" }}>{r.name}</Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full capitalize"
                      style={{ color: STATUS_COLOR[r.subscription_status], background: `${STATUS_COLOR[r.subscription_status]}1a` }}>
                      {r.subscription_status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{r.billing_provider ?? "—"}</td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{r.license_count || "—"}</td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: r.discount_percent ? "#10b981" : "var(--text-secondary)" }}>
                    {r.discount_percent ? `${r.discount_percent}%` : "—"}
                  </td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{fmtMoney(r.seat_price_cents)}</td>
                  <td className="px-4 py-3 tabular-nums font-medium" style={{ color: r.mrr_cents ? "var(--text-primary)" : "var(--text-secondary)" }}>
                    {fmtMoney(r.mrr_cents)}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {r.current_period_end ? new Date(r.current_period_end).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {r.trial_ends_at ? new Date(r.trial_ends_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
              {billing && billing.rows.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No organizations yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
