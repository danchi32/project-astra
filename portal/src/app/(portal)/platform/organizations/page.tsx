"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { Building2, Eye, Plus, Search, X, Sparkles } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  listOrganizations, updateOrganization, deleteOrganization,
  setOrgDiscount, clearOrgDiscount, createViewToken, createOrganizationAsAdmin,
} from "@/lib/api/platform";
import { enterViewAs } from "@/lib/viewAs";
import type { OrganizationAdmin, SubscriptionStatus } from "@/lib/api/types";
import { PLAN_TIERS } from "@/lib/api/types";
import { Pagination } from "@/components/pagination";
import { ScrollPanel, pageShell, stickyHeadCell } from "@/components/scroll-panel";

const emptyOrgForm = { organization_name: "", admin_name: "", admin_email: "", admin_password: "" };

const STATUS_STYLE: Record<SubscriptionStatus, { label: string; color: string }> = {
  trialing: { label: "Trial", color: "#b246d4" },
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
  const [query, setQuery] = useState("");
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<(typeof FILTERS)[number]>("all");
  const [planFilter, setPlanFilter] = useState<string>("all");
  const [sort, setSort] = useState("created_at");
  const [desc, setDesc] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Debounced: a request per keystroke against a table of ten thousand organizations is
  // load nobody asked for, and the answer to "acm" is never the one anyone wanted.
  useEffect(() => {
    const t = setTimeout(() => { setQ(query.trim()); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [query]);
  useEffect(() => { setPage(1); }, [statusFilter, planFilter, sort, desc, pageSize]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["platform-orgs", q, statusFilter, planFilter, sort, desc, page, pageSize],
    queryFn: () => listOrganizations({
      q: q || undefined,
      subscription_status: statusFilter === "all" ? undefined : statusFilter,
      plan: planFilter === "all" ? undefined : planFilter,
      sort, desc, page, page_size: pageSize,
    }),
    enabled: !!me?.is_platform_admin,
    // Keeps the current page on screen while the next loads, so paging and typing don't
    // flash an empty table under the cursor.
    placeholderData: keepPreviousData,
  });
  const orgs = data?.items;
  const [drawerOrg, setDrawerOrg] = useState<OrganizationAdmin | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [orgForm, setOrgForm] = useState(emptyOrgForm);
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState("");
  const [createdNote, setCreatedNote] = useState("");

  // Searched, filtered and sorted by the database — the browser no longer sees the rows it
  // isn't showing.
  const filtered = orgs ?? [];

  async function viewAs(o: OrganizationAdmin) {
    const { access_token } = await createViewToken(o.id);
    queryClient.clear(); // drop this operator's own cached data before switching context
    enterViewAs(access_token, { id: o.id, name: o.name });
    router.push("/dashboard");
  }

  async function submitCreate(e: React.FormEvent) {
    e.preventDefault();
    if (orgForm.admin_password.length < 8) { setCreateErr("Initial password must be at least 8 characters."); return; }
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
    <div className={pageShell}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
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
            className="pl-8 pr-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 w-64"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setStatusFilter(f)}
              className="text-xs px-2.5 py-1.5 rounded-lg font-medium capitalize"
              style={statusFilter === f
                ? { background: "rgba(154,47,187,0.1)", border: "1px solid var(--accent)", color: "var(--accent)" }
                : { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
              {f === "all" ? "All" : STATUS_STYLE[f].label}
            </button>
          ))}
        </div>
        {/* Plan filter — the tier decides what the org can use, so it is the second thing
            an operator narrows by after status. */}
        <select value={planFilter} onChange={(e) => setPlanFilter(e.target.value)}
          className="px-2.5 py-1.5 rounded-lg text-xs font-medium outline-none"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          <option value="all">All plans</option>
          {PLAN_TIERS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>

        <select value={`${sort}:${desc ? "d" : "a"}`}
          onChange={(e) => { const [s, d] = e.target.value.split(":"); setSort(s); setDesc(d === "d"); }}
          className="px-2.5 py-1.5 rounded-lg text-xs font-medium outline-none"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          <option value="created_at:d">Newest first</option>
          <option value="created_at:a">Oldest first</option>
          <option value="name:a">Name A–Z</option>
          <option value="name:d">Name Z–A</option>
          <option value="updated_at:d">Recently updated</option>
        </select>

        <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}
          className="px-2.5 py-1.5 rounded-lg text-xs font-medium outline-none"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} per page</option>)}
        </select>
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
              { k: "admin_password", label: "Initial password (min 8 chars)", type: "text", ph: "Share with the customer" },
            ].map(({ k, label, type, ph }) => (
              <div key={k}>
                <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
                <input required type={type} placeholder={ph}
                  value={orgForm[k as keyof typeof orgForm]}
                  onChange={(e) => setOrgForm({ ...orgForm, [k]: e.target.value })}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
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

      {/* Seven columns, not ten. The rest moved into the drawer: an operator scanning the
          list is trying to FIND an account, and every extra column pushes the actions off
          the right edge and makes finding one harder, not easier. */}
      <ScrollPanel
        footer={<Pagination page={page} onPage={setPage} data={data} noun="organization" busy={isFetching} />}
      >
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr>
                {["Organization", "Plan", "Users", "Status", "Subscription", "Updated", ""].map((h, i) => (
                  <th key={h || i} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={stickyHeadCell}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={7} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !filtered.length && (
                <tr><td colSpan={7} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                  {q || statusFilter !== "all" || planFilter !== "all"
                    ? "No organizations match these filters."
                    : "No organizations yet."}
                </td></tr>
              )}
              {filtered.map((o) => (
                <tr key={o.id} className="hover:bg-brand-500/5 transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/platform/${o.id}`} className="hover:underline" style={{ color: "var(--accent)" }}>{o.name}</Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full capitalize"
                      style={{ color: "var(--accent)", background: "rgba(154,47,187,0.10)" }}>
                      {o.plan_tier}
                    </span>
                  </td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{o.user_count}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: STATUS_STYLE[o.subscription_status].color, background: `${STATUS_STYLE[o.subscription_status].color}1a` }}>
                      {STATUS_STYLE[o.subscription_status].label}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {o.subscription_status === "trialing"
                      ? trialInfo(o)
                      : o.license_count ? `${o.license_count} licence${o.license_count === 1 ? "" : "s"}` : "—"}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {new Date(o.updated_at ?? o.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => setDrawerOrg(o)}
                      className="text-xs px-2.5 py-1.5 rounded-lg"
                      style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                      Manage
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      </ScrollPanel>

      {/* Everything that used to be a column, plus every action. A drawer rather than a
          modal because an operator working down a list keeps their place behind it. */}
      {drawerOrg && (
        <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(0,0,0,0.4)" }}
          onClick={() => setDrawerOrg(null)}>
          <div className="w-full max-w-md h-full overflow-y-auto p-5"
            onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--surface)", borderLeft: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>{drawerOrg.name}</h2>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                  Created {new Date(drawerOrg.created_at).toLocaleDateString()}
                </p>
              </div>
              <button onClick={() => setDrawerOrg(null)} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              {[
                ["Plan", drawerOrg.plan_tier],
                ["Status", STATUS_STYLE[drawerOrg.subscription_status].label],
                ["Users", String(drawerOrg.user_count)],
                ["Devices", String(drawerOrg.device_count)],
                ["Licences", drawerOrg.license_count ? String(drawerOrg.license_count) : "—"],
                ["Discount", drawerOrg.discount_percent ? `${drawerOrg.discount_percent}%` : "—"],
                ["Trial", trialInfo(drawerOrg)],
                ["Billing rail", drawerOrg.billing_provider ?? "—"],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs" style={{ color: "var(--text-secondary)" }}>{k}</dt>
                  <dd className="capitalize" style={{ color: "var(--text-primary)" }}>{v}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-5 pt-4 border-t flex flex-wrap gap-2" style={{ borderColor: "var(--border)" }}>
              <button onClick={() => viewAs(drawerOrg)} className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg"
                style={{ background: "rgba(124,58,237,0.1)", border: "1px solid #7c3aed", color: "#7c3aed" }}>
                <Eye size={12} /> View as
              </button>
              <button onClick={() => toggleAiPro(drawerOrg)} className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg"
                style={drawerOrg.ai_pro
                  ? { background: "rgba(124,58,237,0.1)", border: "1px solid #7c3aed", color: "#7c3aed" }
                  : { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                <Sparkles size={12} /> {drawerOrg.ai_pro ? "Pro AI" : "Basic AI"}
              </button>
              <button onClick={() => extendTrial(drawerOrg.id, 14)} className="text-xs px-2.5 py-1.5 rounded-lg"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>+14d trial</button>
              <button onClick={() => setStatus(drawerOrg.id, "active")} className="text-xs px-2.5 py-1.5 rounded-lg"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#10b981" }}>Activate</button>
              <button onClick={() => editDiscount(drawerOrg)} className="text-xs px-2.5 py-1.5 rounded-lg"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>Discount</button>
              {drawerOrg.subscription_status === "suspended" ? (
                <button onClick={() => setStatus(drawerOrg.id, "active")} className="text-xs px-2.5 py-1.5 rounded-lg"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Unsuspend</button>
              ) : (
                <button onClick={() => setStatus(drawerOrg.id, "suspended")} className="text-xs px-2.5 py-1.5 rounded-lg"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#f59e0b" }}>Suspend</button>
              )}
              <Link href={`/platform/${drawerOrg.id}`} className="text-xs px-2.5 py-1.5 rounded-lg"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--accent)" }}>Full details →</Link>
              <button onClick={() => { removeOrg(drawerOrg.id, drawerOrg.name); setDrawerOrg(null); }}
                className="text-xs px-2.5 py-1.5 rounded-lg hover:bg-red-500/10"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#ef4444" }}>Delete</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
