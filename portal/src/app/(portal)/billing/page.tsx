"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard, Users, Monitor, ExternalLink, AlertTriangle, Tag } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getBillingStatus, startCheckout, openBillingPortal, setLicenses, cancelSubscription } from "@/lib/api/billing";
import type { BillingProvider, BillingStatus, SubscriptionStatus } from "@/lib/api/types";

const PROVIDER_LABEL: Record<BillingProvider, string> = {
  razorpay: "India — UPI / cards / netbanking",
  paddle: "International — card (tax included)",
  paypal: "PayPal",
};

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
  const [qty, setQty] = useState<number>(1);
  const [provider, setProvider] = useState<BillingProvider | "">("");

  const isAdmin = me?.role === "admin";

  // Default the rail to the first one the server offers.
  useEffect(() => {
    if (status?.providers?.length && !provider) setProvider(status.providers[0]);
  }, [status, provider]);

  async function cancel() {
    if (!confirm("Cancel your subscription? Access continues until the end of the paid period.")) return;
    setBusy("cancel"); setError("");
    try {
      await cancelSubscription();
      setNotice("Subscription cancelled — you keep access until the current period ends.");
      await queryClient.invalidateQueries({ queryKey: ["billing-status"] });
    } catch {
      setError("Couldn't cancel. Please try again or contact support.");
    } finally { setBusy(null); }
  }

  // Keep the license quantity input sensible: at least the seats already in use.
  useEffect(() => {
    if (status) setQty(Math.max(1, status.licenses || status.seats_used || 1));
  }, [status]);

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
      setError("Couldn't reach the payment provider. Please try again.");
      setBusy(null);
    }
  }

  async function updateLicenses() {
    setBusy("licenses"); setError("");
    try {
      const r = await setLicenses(qty);
      setNotice(r.detail);
      await queryClient.invalidateQueries({ queryKey: ["billing-status"] });
    } catch (e) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || "Couldn't update licenses.");
    } finally { setBusy(null); }
  }

  const SeatIcon = status?.seat_type === "user" ? Users : Monitor;
  const card = { background: "var(--surface)", border: "1px solid var(--border)" } as const;
  const minQty = Math.max(1, status?.seats_used ?? 1);

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <CreditCard size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Billing</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Licenses, subscription and payment method
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
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium px-2 py-0.5 rounded-full"
                style={{ color: STATUS_STYLE[status.subscription_status].color, background: `${STATUS_STYLE[status.subscription_status].color}1a` }}>
                {STATUS_STYLE[status.subscription_status].label}
              </span>
              {status.discount_percent ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
                  style={{ color: "#10b981", background: "rgba(16,185,129,0.1)" }}>
                  <Tag size={11} /> {status.discount_percent}% off
                </span>
              ) : null}
            </div>
            <p className="text-xs mt-2 capitalize" style={{ color: "var(--text-secondary)" }}>Plan: {status.plan}</p>
          </div>

          <div className="rounded-xl p-4" style={card}>
            <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Licenses used</p>
            <div className="mt-2 flex items-center gap-2">
              <SeatIcon size={18} style={{ color: "var(--accent)" }} />
              <span className="text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
                {status.seats_used}
              </span>
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                / {status.licenses || "∞"} {status.seat_type}s
              </span>
            </div>
            <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>
              {status.licenses > 0 ? "Enrollment is capped at your license count" : "No cap while on trial"}
            </p>
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
        <div className="rounded-xl p-4 space-y-3" style={card}>
          {!status.has_subscription ? (
            <>
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Subscribe</p>

              {status.providers.length > 1 && (
                <div>
                  <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Payment method</label>
                  <select value={provider} onChange={(e) => setProvider(e.target.value as BillingProvider)}
                    className="w-full mt-1 max-w-sm px-3 py-2 rounded-lg text-sm outline-none"
                    style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    {status.providers.map((p) => (
                      <option key={p} value={p}>{PROVIDER_LABEL[p]}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex items-center gap-3 flex-wrap">
                <label className="text-sm" style={{ color: "var(--text-secondary)" }}>Licenses</label>
                <input type="number" min={minQty} value={qty}
                  onChange={(e) => setQty(Math.max(minQty, Number(e.target.value) || minQty))}
                  className="w-24 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                <button onClick={() => redirect(() => startCheckout(qty, (provider || status.providers[0]) as BillingProvider), "checkout")}
                  disabled={busy !== null || status.providers.length === 0}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                  style={{ background: "var(--accent)" }}>
                  <CreditCard size={15} /> {busy === "checkout" ? "Redirecting…" : `Subscribe for ${qty} ${status.seat_type}${qty === 1 ? "" : "s"}`}
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Manage subscription</p>
              <div className="flex items-center gap-3 flex-wrap">
                <label className="text-sm" style={{ color: "var(--text-secondary)" }}>Licenses</label>
                <input type="number" min={minQty} value={qty}
                  onChange={(e) => setQty(Math.max(minQty, Number(e.target.value) || minQty))}
                  className="w-24 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                <button onClick={updateLicenses} disabled={busy !== null || qty === status.licenses}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                  style={{ background: "var(--accent)" }}>
                  {busy === "licenses" ? "Updating…" : "Update licenses"}
                </button>
                {status.billing_provider === "paddle" && (
                  <button onClick={() => redirect(openBillingPortal, "portal")} disabled={busy !== null}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                    style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    <ExternalLink size={15} /> {busy === "portal" ? "Opening…" : "Manage billing"}
                  </button>
                )}
                <button onClick={cancel} disabled={busy !== null}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                  style={{ background: "var(--bg)", border: "1px solid #ef4444", color: "#ef4444" }}>
                  {busy === "cancel" ? "Cancelling…" : "Cancel subscription"}
                </button>
              </div>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Minimum {minQty} (seats currently in use). License changes are prorated by your provider.
              </p>
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
