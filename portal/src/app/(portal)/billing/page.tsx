"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard, Users, Monitor, RefreshCw, ExternalLink, AlertTriangle } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getBillingStatus, startCheckout, openBillingPortal, syncSeats } from "@/lib/api/billing";
import type { SubscriptionStatus } from "@/lib/api/types";

const STATUS_STYLE: Record<SubscriptionStatus, { label: string; color: string }> = {
  trialing: { label: "Trial", color: "#3b82f6" },
  active: { label: "Active", color: "#10b981" },
  past_due: { label: "Past due", color: "#f59e0b" },
  suspended: { label: "Suspended", color: "#ef4444" },
  canceled: { label: "Canceled", color: "#64748b" },
};

function fmtDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—";
}

export default function BillingPage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: status, isLoading } = useQuery({ queryKey: ["billing-status"], queryFn: getBillingStatus });

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const isAdmin = me?.role === "admin";

  // Surface the Stripe Checkout return (?checkout=success|cancelled) and refresh,
  // since the webhook that flips the subscription may land a moment later.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const outcome = params.get("checkout");
    if (outcome === "success") {
      setNotice("Payment received — activating your subscription. This can take a few seconds.");
      const t = setInterval(() => queryClient.invalidateQueries({ queryKey: ["billing-status"] }), 3000);
      setTimeout(() => clearInterval(t), 15000);
      window.history.replaceState({}, "", "/billing");
      return () => clearInterval(t);
    }
    if (outcome === "cancelled") {
      setNotice("Checkout cancelled — no charge was made.");
      window.history.replaceState({}, "", "/billing");
    }
  }, [queryClient]);

  async function redirect(fn: () => Promise<string>, key: string) {
    setBusy(key); setError("");
    try {
      window.location.href = await fn();
    } catch {
      setError("Couldn't reach Stripe. Please try again.");
      setBusy(null);
    }
  }

  async function doSync() {
    setBusy("sync"); setError("");
    try {
      const r = await syncSeats();
      setNotice(r.detail);
      await queryClient.invalidateQueries({ queryKey: ["billing-status"] });
    } catch {
      setError("Couldn't sync seats.");
    } finally { setBusy(null); }
  }

  const SeatIcon = status?.seat_type === "user" ? Users : Monitor;
  const card = { background: "var(--surface)", border: "1px solid var(--border)" } as const;

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <CreditCard size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Billing</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Your subscription, seats and payment method
          </p>
        </div>
      </div>

      {notice && (
        <div className="rounded-lg px-4 py-3 text-sm" style={{ background: "rgba(37,99,235,0.08)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          {notice}
        </div>
      )}
      {error && <p className="text-sm text-red-500">{error}</p>}

      {isLoading && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>}

      {status && !status.writable && (
        <div className="rounded-xl px-4 py-3 flex items-start gap-3" style={{ background: "rgba(245,158,11,0.1)", border: "1px solid #f59e0b" }}>
          <AlertTriangle size={18} style={{ color: "#f59e0b", marginTop: 2 }} />
          <div className="text-sm" style={{ color: "var(--text-primary)" }}>
            <p className="font-medium">Your account is read-only.</p>
            <p style={{ color: "var(--text-secondary)" }}>{status.read_only_reason}</p>
          </div>
        </div>
      )}

      {status && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-xl p-4" style={card}>
            <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Status</p>
            <div className="mt-2">
              <span className="text-sm font-medium px-2 py-0.5 rounded-full"
                style={{ color: STATUS_STYLE[status.subscription_status].color, background: `${STATUS_STYLE[status.subscription_status].color}1a` }}>
                {STATUS_STYLE[status.subscription_status].label}
              </span>
            </div>
            <p className="text-xs mt-2 capitalize" style={{ color: "var(--text-secondary)" }}>Plan: {status.plan}</p>
          </div>

          <div className="rounded-xl p-4" style={card}>
            <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Billable seats</p>
            <div className="mt-2 flex items-center gap-2">
              <SeatIcon size={18} style={{ color: "var(--accent)" }} />
              <span className="text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{status.seat_count}</span>
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>{status.seat_type}s</span>
            </div>
            <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>Charged per {status.seat_type}, updated at renewal</p>
          </div>

          <div className="rounded-xl p-4" style={card}>
            <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
              {status.subscription_status === "trialing" ? "Trial ends" : "Renews"}
            </p>
            <p className="mt-2 text-lg font-medium" style={{ color: "var(--text-primary)" }}>
              {status.subscription_status === "trialing" ? fmtDate(status.trial_ends_at) : fmtDate(status.current_period_end)}
            </p>
          </div>
        </div>
      )}

      {status && !status.billing_enabled && (
        <div className="rounded-xl px-4 py-3 text-sm" style={{ background: "var(--surface)", border: "1px dashed var(--border)", color: "var(--text-secondary)" }}>
          Online payments aren&apos;t enabled yet. Your account works normally on its trial —
          contact ASTRA to set up a subscription.
        </div>
      )}

      {status && status.billing_enabled && isAdmin && (
        <div className="flex flex-wrap gap-2">
          {!status.has_subscription ? (
            <button onClick={() => redirect(startCheckout, "checkout")} disabled={busy !== null || !status.unit_price_configured}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}>
              <CreditCard size={15} /> {busy === "checkout" ? "Redirecting…" : "Subscribe"}
            </button>
          ) : (
            <>
              <button onClick={() => redirect(openBillingPortal, "portal")} disabled={busy !== null}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                <ExternalLink size={15} /> {busy === "portal" ? "Opening…" : "Manage billing"}
              </button>
              <button onClick={doSync} disabled={busy !== null}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                <RefreshCw size={15} /> {busy === "sync" ? "Syncing…" : "Sync seats"}
              </button>
            </>
          )}
        </div>
      )}

      {status && status.billing_enabled && !isAdmin && (
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Only an organization admin can change billing.</p>
      )}
    </div>
  );
}
