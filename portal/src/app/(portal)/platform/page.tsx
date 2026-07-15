"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, BookOpen, Zap, Eye, Plus, X } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  listOrganizations, updateOrganization, deleteOrganization,
  setOrgDiscount, clearOrgDiscount, getPlatformOverview, createViewToken,
  createOrganizationAsAdmin,
} from "@/lib/api/platform";
import { enterViewAs } from "@/lib/viewAs";
import type { OrganizationAdmin, SubscriptionStatus } from "@/lib/api/types";

const STAT_LABELS: { key: string; label: string }[] = [
  { key: "total_organizations", label: "Organizations" },
  { key: "total_devices", label: "Devices" },
  { key: "online_devices", label: "Online now" },
  { key: "total_users", label: "Users" },
  { key: "licenses_sold", label: "Licenses sold" },
  { key: "trials_ending_7d", label: "Trials ending ≤7d" },
];

function fmtMoney(cents: number): string {
  return `$${(cents / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

const emptyOrgForm = { organization_name: "", admin_name: "", admin_email: "", admin_password: "" };

const STATUS_STYLE: Record<SubscriptionStatus, { label: string; color: string }> = {
  trialing: { label: "Trial", color: "#3b82f6" },
  active: { label: "Active", color: "#10b981" },
  past_due: { label: "Past due", color: "#f59e0b" },
  suspended: { label: "Suspended", color: "#ef4444" },
  canceled: { label: "Canceled", color: "#64748b" },
};

function trialInfo(o: OrganizationAdmin): string {
  if (o.subscription_status !== "trialing" || !o.trial_ends_at) return "—";
  const days = Math.ceil((new Date(o.trial_ends_at).getTime() - Date.now()) / 86_400_000);
  return days >= 0 ? `${days} day${days === 1 ? "" : "s"} left` : `ended ${-days}d ago`;
}

export default function PlatformPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: orgs, isLoading } = useQuery({
    queryKey: ["platform-orgs"],
    queryFn: listOrganizations,
    enabled: !!me?.is_platform_admin,
  });
  const { data: overview } = useQuery({
    queryKey: ["platform-overview"],
    queryFn: getPlatformOverview,
    enabled: !!me?.is_platform_admin,
  });

  const [showCreate, setShowCreate] = useState(false);
  const [orgForm, setOrgForm] = useState(emptyOrgForm);
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState("");
  const [createdNote, setCreatedNote] = useState("");

  async function viewAs(o: OrganizationAdmin) {
    const { access_token } = await createViewToken(o.id);
    queryClient.clear(); // drop this operator's own cached data before switching context
    enterViewAs(access_token, { id: o.id, name: o.name });
    router.push("/dashboard");
  }

  async function submitCreate(e: React.FormEvent) {
    e.preventDefault();
    if (orgForm.admin_password.length < 12) { setCreateErr("Initial password must be at least 12 characters."); return; }
    setCreating(true); setCreateErr("");
    try {
      await createOrganizationAsAdmin({
        organization_name: orgForm.organization_name.trim(),
        admin_name: orgForm.admin_name.trim(),
        admin_email: orgForm.admin_email.trim(),
        admin_password: orgForm.admin_password,
      });
      setCreatedNote(`Created “${orgForm.organization_name.trim()}”. Share the login email and password with the customer.`);
      setOrgForm(emptyOrgForm);
      setShowCreate(false);
      await queryClient.invalidateQueries({ queryKey: ["platform-orgs"] });
      await queryClient.invalidateQueries({ queryKey: ["platform-overview"] });
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setCreateErr(msg || "Couldn't create the organization. That email may already be registered.");
    } finally { setCreating(false); }
  }

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["platform-orgs"] });
  }
  async function setStatus(id: string, subscription_status: SubscriptionStatus) {
    await updateOrganization(id, { subscription_status });
    await refresh();
  }
  async function extendTrial(id: string, days: number) {
    await updateOrganization(id, { subscription_status: "trialing", extend_trial_days: days });
    await refresh();
  }
  async function removeOrg(id: string, name: string) {
    if (!confirm(`Delete "${name}" and ALL its data? This cannot be undone.`)) return;
    await deleteOrganization(id);
    await refresh();
  }
  async function editDiscount(o: OrganizationAdmin) {
    const input = prompt(`Discount % for "${o.name}" (1–100). Leave blank to remove.`, o.discount_percent ? String(o.discount_percent) : "");
    if (input === null) return;
    const trimmed = input.trim();
    if (trimmed === "") {
      if (o.discount_percent) await clearOrgDiscount(o.id);
    } else {
      const pct = Number(trimmed);
      if (!Number.isInteger(pct) || pct < 1 || pct > 100) { alert("Enter a whole number 1–100."); return; }
      await setOrgDiscount(o.id, pct);
    }
    await refresh();
  }

  if (me && !me.is_platform_admin) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Platform administrator access required.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            <ShieldCheck size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Platform</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              All organizations — subscriptions, trials and lifecycle
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { setShowCreate(true); setCreateErr(""); setCreatedNote(""); }}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
            style={{ background: "var(--accent)" }}>
            <Plus size={15} /> New organization
          </button>
          <Link href="/platform/fixes"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            <Zap size={15} /> Auto-fixes
          </Link>
          <Link href="/platform/knowledge"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            <BookOpen size={15} /> Global knowledge
          </Link>
        </div>
      </div>

      {createdNote && (
        <div className="rounded-lg px-4 py-3 text-sm" style={{ background: "rgba(16,185,129,0.1)", border: "1px solid #10b981", color: "var(--text-primary)" }}>
          {createdNote}
        </div>
      )}

      {/* Business KPIs */}
      {overview && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-xl p-4" style={{ background: "rgba(37,99,235,0.06)", border: "1px solid var(--accent)" }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Monthly revenue (MRR)</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
              {overview.mrr_cents != null ? fmtMoney(overview.mrr_cents) : "—"}
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
              {overview.mrr_cents != null ? `${overview.active_subscriptions} active subscription${overview.active_subscriptions === 1 ? "" : "s"}` : "Set a per-seat price to compute"}
            </p>
          </div>
          <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Active subscriptions</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{overview.active_subscriptions}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{overview.licenses_sold} licenses sold</p>
          </div>
          <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>New sign-ups (30d)</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{overview.signups_30d}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{overview.trials_ending_7d} trial{overview.trials_ending_7d === 1 ? "" : "s"} ending ≤7d</p>
          </div>
        </div>
      )}

      {/* Fleet / usage counts */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {STAT_LABELS.map(({ key, label }) => (
            <div key={key} className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
                {(overview as unknown as Record<string, number>)[key] ?? 0}
              </p>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={() => setShowCreate(false)}>
          <form onSubmit={submitCreate} onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-xl p-6 space-y-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>New organization</h2>
              <button type="button" onClick={() => setShowCreate(false)} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
            </div>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Creates the org + its first admin on a 14-day trial. Share the email and initial password with the customer.
            </p>
            {[
              { k: "organization_name", label: "Organization name", type: "text", ph: "Acme Corp" },
              { k: "admin_name", label: "Admin name", type: "text", ph: "Jane Admin" },
              { k: "admin_email", label: "Admin email", type: "email", ph: "admin@acme.com" },
              { k: "admin_password", label: "Initial password (min 12 chars)", type: "text", ph: "Share with the customer" },
            ].map(({ k, label, type, ph }) => (
              <div key={k}>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
                <input required type={type} placeholder={ph}
                  value={orgForm[k as keyof typeof orgForm]}
                  onChange={(e) => setOrgForm({ ...orgForm, [k]: e.target.value })}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
              </div>
            ))}
            {createErr && <p className="text-sm text-red-500">{createErr}</p>}
            <div className="flex gap-2">
              <button type="submit" disabled={creating}
                className="flex-1 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
                {creating ? "Creating…" : "Create organization"}
              </button>
              <button type="button" onClick={() => setShowCreate(false)}
                className="px-4 py-2 rounded-lg text-sm font-medium" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Organization", "Plan", "Status", "Trial", "Licenses", "Discount", "Users", "Devices", "Created", "Actions"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={10} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !orgs?.length && (
                <tr><td colSpan={10} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No organizations yet.</td></tr>
              )}
              {orgs?.map((o) => (
                <tr key={o.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/platform/${o.id}`} className="hover:underline" style={{ color: "var(--accent)" }}>{o.name}</Link>
                  </td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{o.plan}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: STATUS_STYLE[o.subscription_status].color, background: `${STATUS_STYLE[o.subscription_status].color}1a` }}>
                      {STATUS_STYLE[o.subscription_status].label}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{trialInfo(o)}</td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{o.license_count || "—"}</td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: o.discount_percent ? "#10b981" : "var(--text-secondary)" }}>
                    {o.discount_percent ? `${o.discount_percent}%` : "—"}
                  </td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{o.user_count}</td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{o.device_count}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{new Date(o.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      <button onClick={() => viewAs(o)} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg"
                        style={{ background: "rgba(124,58,237,0.1)", border: "1px solid #7c3aed", color: "#7c3aed" }}>
                        <Eye size={12} /> View
                      </button>
                      <button onClick={() => extendTrial(o.id, 14)} className="text-xs px-2 py-1 rounded-lg"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>+14d trial</button>
                      <button onClick={() => setStatus(o.id, "active")} className="text-xs px-2 py-1 rounded-lg"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#10b981" }}>Activate</button>
                      <button onClick={() => editDiscount(o)} className="text-xs px-2 py-1 rounded-lg"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>Discount</button>
                      {o.subscription_status === "suspended" ? (
                        <button onClick={() => setStatus(o.id, "active")} className="text-xs px-2 py-1 rounded-lg"
                          style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Unsuspend</button>
                      ) : (
                        <button onClick={() => setStatus(o.id, "suspended")} className="text-xs px-2 py-1 rounded-lg"
                          style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#f59e0b" }}>Suspend</button>
                      )}
                      <button onClick={() => removeOrg(o.id, o.name)} className="text-xs px-2 py-1 rounded-lg hover:bg-red-500/10"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#ef4444" }}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
