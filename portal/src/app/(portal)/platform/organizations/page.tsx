"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Eye, Plus, Search, X, Sparkles } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  listOrganizations, updateOrganization, deleteOrganization,
  setOrgDiscount, clearOrgDiscount, createViewToken, createOrganizationAsAdmin,
} from "@/lib/api/platform";
import { enterViewAs } from "@/lib/viewAs";
import type { OrganizationAdmin, SubscriptionStatus } from "@/lib/api/types";

const emptyOrgForm = { organization_name: "", admin_name: "", admin_email: "", admin_password: "" };

const STATUS_STYLE: Record<SubscriptionStatus, { label: string; color: string }> = {
  trialing: { label: "Trial", color: "#3b82f6" },
  active: { label: "Active", color: "#10b981" },
  past_due: { label: "Past due", color: "#f59e0b" },
  suspended: { label: "Suspended", color: "#ef4444" },
  canceled: { label: "Canceled", color: "#64748b" },
};

const FILTERS: ("all" | SubscriptionStatus)[] = ["all", "trialing", "active", "past_due", "suspended", "canceled"];

function trialInfo(o: OrganizationAdmin): string {
  if (o.subscription_status !== "trialing" || !o.trial_ends_at) return "—";
  const days = Math.ceil((new Date(o.trial_ends_at).getTime() - Date.now()) / 86_400_000);
  return days >= 0 ? `${days} day${days === 1 ? "" : "s"} left` : `ended ${-days}d ago`;
}

export default function PlatformOrganizationsPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: orgs, isLoading } = useQuery({
    queryKey: ["platform-orgs"],
    queryFn: listOrganizations,
    enabled: !!me?.is_platform_admin,
  });

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<(typeof FILTERS)[number]>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [orgForm, setOrgForm] = useState(emptyOrgForm);
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState("");
  const [createdNote, setCreatedNote] = useState("");

  const filtered = useMemo(() => {
    let rows = orgs ?? [];
    if (statusFilter !== "all") rows = rows.filter((o) => o.subscription_status === statusFilter);
    const q = query.trim().toLowerCase();
    if (q) rows = rows.filter((o) => o.name.toLowerCase().includes(q));
    return rows;
  }, [orgs, query, statusFilter]);

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
  async function toggleAiPro(o: OrganizationAdmin) {
    await updateOrganization(o.id, { ai_pro: !o.ai_pro });
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
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            <Building2 size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Organizations</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Every customer — subscriptions, trials and lifecycle
            </p>
          </div>
        </div>
        <button onClick={() => { setShowCreate(true); setCreateErr(""); setCreatedNote(""); }}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
          style={{ background: "var(--accent)" }}>
          <Plus size={15} /> New organization
        </button>
      </div>

      {createdNote && (
        <div className="rounded-lg px-4 py-3 text-sm" style={{ background: "rgba(16,185,129,0.1)", border: "1px solid #10b981", color: "var(--text-primary)" }}>
          {createdNote}
        </div>
      )}

      {/* Search + status filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search organizations…"
            className="pl-8 pr-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 w-64"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setStatusFilter(f)}
              className="text-xs px-2.5 py-1.5 rounded-lg font-medium capitalize"
              style={statusFilter === f
                ? { background: "rgba(37,99,235,0.1)", border: "1px solid var(--accent)", color: "var(--accent)" }
                : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
              {f === "all" ? "All" : STATUS_STYLE[f].label}
            </button>
          ))}
        </div>
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {filtered.length} of {orgs?.length ?? 0}
        </span>
      </div>

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
              {!isLoading && !filtered.length && (
                <tr><td colSpan={10} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                  {orgs?.length ? "No organizations match." : "No organizations yet."}
                </td></tr>
              )}
              {filtered.map((o) => (
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
                      <button onClick={() => toggleAiPro(o)} title={o.ai_pro ? "Pro AI enabled — click to downgrade" : "Enable Pro AI (real Claude)"}
                        className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg"
                        style={o.ai_pro
                          ? { background: "rgba(124,58,237,0.1)", border: "1px solid #7c3aed", color: "#7c3aed" }
                          : { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                        <Sparkles size={12} /> {o.ai_pro ? "Pro AI" : "Basic AI"}
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
