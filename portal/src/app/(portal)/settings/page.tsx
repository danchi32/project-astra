"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Settings as SettingsIcon, User as UserIcon, Palette, Building2, ShieldCheck,
  Check, Minus, Monitor, Sun, Moon,
} from "lucide-react";
import { getMe, updateProfile, changePassword } from "@/lib/api/auth";
import { getOrgSettings, updateOrgSettings, getPermissionMatrix } from "@/lib/api/settings";
import { getTheme, setTheme, type Theme } from "@/lib/theme";
import type { OrganizationSettingsInput, UserRole } from "@/lib/api/types";

type Tab = "profile" | "preferences" | "organization" | "permissions";

const ROLE_STYLE: Record<UserRole, { color: string; bg: string }> = {
  admin: { color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  technician: { color: "#3b82f6", bg: "rgba(59,130,246,0.1)" },
  user: { color: "#64748b", bg: "rgba(100,116,139,0.1)" },
};

function Panel({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl p-5 space-y-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div>
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h2>
        {description && <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>{description}</p>}
      </div>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

const inputStyle = {
  background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)",
} as const;

function Toggle({ on, onChange, disabled }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={on} disabled={disabled}
      onClick={() => onChange(!on)}
      className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50"
      style={{ background: on ? "var(--accent)" : "var(--border)" }}>
      <span className="inline-block h-4 w-4 rounded-full bg-white transition-transform"
        style={{ transform: on ? "translateX(24px)" : "translateX(4px)" }} />
    </button>
  );
}

/* ── Profile ─────────────────────────────────────────────────────────────── */

function ProfileTab() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameMsg, setNameMsg] = useState("");

  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [pwBusy, setPwBusy] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => { if (me) setName(me.full_name); }, [me]);

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    setSavingName(true); setNameMsg("");
    try {
      await updateProfile(name.trim());
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      setNameMsg("Saved");
    } catch { setNameMsg("Couldn't save"); }
    finally { setSavingName(false); }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwMsg(null);
    if (pw.next !== pw.confirm) { setPwMsg({ ok: false, text: "New passwords don't match" }); return; }
    setPwBusy(true);
    try {
      await changePassword(pw.current, pw.next);
      setPw({ current: "", next: "", confirm: "" });
      setPwMsg({ ok: true, text: "Password changed. Other sessions were signed out." });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setPwMsg({ ok: false, text: detail ?? "Couldn't change password" });
    } finally { setPwBusy(false); }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <Panel title="Your profile" description="Update how your name appears across ASTRA.">
        <form onSubmit={saveName} className="space-y-4">
          <Field label="Full name">
            <input value={name} onChange={(e) => setName(e.target.value)} required
              className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Email">
              <input value={me?.email ?? ""} disabled
                className="w-full px-3 py-2 rounded-lg text-sm outline-none opacity-70" style={inputStyle} />
            </Field>
            <Field label="Role">
              <div>
                {me && (
                  <span className="text-xs font-medium px-2 py-1 rounded-full capitalize"
                    style={{ color: ROLE_STYLE[me.role].color, background: ROLE_STYLE[me.role].bg }}>{me.role}</span>
                )}
              </div>
            </Field>
          </div>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={savingName}
              className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}>{savingName ? "Saving…" : "Save profile"}</button>
            {nameMsg && <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{nameMsg}</span>}
          </div>
        </form>
      </Panel>

      <Panel title="Change password" description="You'll stay signed in here; other sessions are signed out.">
        <form onSubmit={savePassword} className="space-y-4">
          <Field label="Current password">
            <input type="password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} required
              className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="New password">
              <input type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} required
                className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
            </Field>
            <Field label="Confirm new password">
              <input type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} required
                className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
            </Field>
          </div>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={pwBusy}
              className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}>{pwBusy ? "Updating…" : "Change password"}</button>
            {pwMsg && <span className="text-xs" style={{ color: pwMsg.ok ? "#10b981" : "#ef4444" }}>{pwMsg.text}</span>}
          </div>
        </form>
      </Panel>
    </div>
  );
}

/* ── Preferences ─────────────────────────────────────────────────────────── */

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function PreferencesTab() {
  const [theme, setThemeState] = useState<Theme>("system");
  useEffect(() => { setThemeState(getTheme()); }, []);

  function choose(t: Theme) { setTheme(t); setThemeState(t); }

  return (
    <div className="max-w-2xl">
      <Panel title="Appearance" description="Choose how ASTRA looks on this device.">
        <div className="grid grid-cols-3 gap-3">
          {THEMES.map(({ value, label, icon: Icon }) => {
            const active = theme === value;
            return (
              <button key={value} onClick={() => choose(value)}
                className="flex flex-col items-center gap-2 py-4 rounded-xl transition-colors"
                style={{
                  border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
                  background: active ? "rgba(37,99,235,0.06)" : "var(--bg)",
                  color: active ? "var(--accent)" : "var(--text-secondary)",
                }}>
                <Icon size={20} />
                <span className="text-sm font-medium">{label}</span>
              </button>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

/* ── Organization (admin) ────────────────────────────────────────────────── */

function OrganizationTab() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ["org-settings"], queryFn: getOrgSettings });
  const [form, setForm] = useState<OrganizationSettingsInput>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (data) setForm({
      org_name: data.org_name,
      auto_approve_automatic: data.auto_approve_automatic,
      require_admin_for_approval_tier: data.require_admin_for_approval_tier,
      min_password_length: data.min_password_length,
      enrollment_token_default_days: data.enrollment_token_default_days,
    });
  }, [data]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      await updateOrgSettings(form);
      await queryClient.invalidateQueries({ queryKey: ["org-settings"] });
      await queryClient.invalidateQueries({ queryKey: ["permission-matrix"] });
      setMsg({ ok: true, text: "Settings saved" });
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMsg({ ok: false, text: detail ?? "Couldn't save settings" });
    } finally { setSaving(false); }
  }

  if (isLoading) return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>;
  if (isError) return <p className="text-sm" style={{ color: "#ef4444" }}>Couldn't load organization settings.</p>;

  return (
    <form onSubmit={save} className="space-y-4 max-w-2xl">
      <Panel title="Organization" description="Your workspace identity.">
        <Field label="Organization name">
          <input value={form.org_name ?? ""} onChange={(e) => setForm({ ...form, org_name: e.target.value })} required
            className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
        </Field>
      </Panel>

      <Panel title="Automation & self-healing" description="Control how much the platform does on its own.">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Auto-approve automatic actions</p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              When off, even safe automatic fixes wait for a human — a global pause switch for self-healing.
            </p>
          </div>
          <Toggle on={!!form.auto_approve_automatic} onChange={(v) => setForm({ ...form, auto_approve_automatic: v })} />
        </div>
        <div className="flex items-start justify-between gap-4 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Require admin for approvals</p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              When on, approval-required remediations can only be cleared by an admin — not a technician.
            </p>
          </div>
          <Toggle on={!!form.require_admin_for_approval_tier} onChange={(v) => setForm({ ...form, require_admin_for_approval_tier: v })} />
        </div>
      </Panel>

      <Panel title="Security & enrollment" description="Baseline policy for accounts and agent enrollment.">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Minimum password length">
            <input type="number" min={12} max={128} value={form.min_password_length ?? 12}
              onChange={(e) => setForm({ ...form, min_password_length: Number(e.target.value) })}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
          </Field>
          <Field label="Enrollment token default (days)">
            <input type="number" min={1} max={90} value={form.enrollment_token_default_days ?? 7}
              onChange={(e) => setForm({ ...form, enrollment_token_default_days: Number(e.target.value) })}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle} />
          </Field>
        </div>
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Password length has an enforced floor of 12 characters; you can only raise it.
        </p>
      </Panel>

      <div className="flex items-center gap-3">
        <button type="submit" disabled={saving}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--accent)" }}>{saving ? "Saving…" : "Save changes"}</button>
        {msg && <span className="text-xs" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</span>}
      </div>
    </form>
  );
}

/* ── Permissions ─────────────────────────────────────────────────────────── */

function PermissionsTab() {
  const { data, isLoading } = useQuery({ queryKey: ["permission-matrix"], queryFn: getPermissionMatrix });

  if (isLoading) return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>;
  if (!data) return <p className="text-sm" style={{ color: "#ef4444" }}>Couldn't load the permission matrix.</p>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {data.roles.map((r) => (
          <div key={r.role} className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <span className="text-xs font-medium px-2 py-0.5 rounded-full capitalize"
              style={{ color: ROLE_STYLE[r.role as UserRole].color, background: ROLE_STYLE[r.role as UserRole].bg }}>{r.label}</span>
            <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>{r.description}</p>
          </div>
        ))}
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Capability</th>
                {data.roles.map((r) => (
                  <th key={r.role} className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wide capitalize" style={{ color: "var(--text-secondary)" }}>{r.role}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.capabilities.map((cap) => (
                <tr key={cap.key} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3" style={{ color: "var(--text-primary)" }}>{cap.label}</td>
                  {data.roles.map((r) => (
                    <td key={r.role} className="px-4 py-3 text-center">
                      {r.capabilities[cap.key] ? (
                        <Check size={16} className="inline" color="#10b981" />
                      ) : (
                        <Minus size={16} className="inline" style={{ color: "var(--text-secondary)", opacity: 0.4 }} />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
        Roles are built in and enforced by the API. The technician&apos;s approval rights reflect your current organization policy.
      </p>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────────────────── */

export default function SettingsPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";
  const [tab, setTab] = useState<Tab>("profile");

  const tabs: { key: Tab; label: string; icon: typeof UserIcon; show: boolean }[] = [
    { key: "profile", label: "Profile", icon: UserIcon, show: true },
    { key: "preferences", label: "Preferences", icon: Palette, show: true },
    { key: "organization", label: "Organization", icon: Building2, show: !!isAdmin },
    { key: "permissions", label: "Permissions", icon: ShieldCheck, show: true },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <SettingsIcon size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Settings</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Your account, preferences and organization configuration
          </p>
        </div>
      </div>

      <div className="flex gap-1 border-b" style={{ borderColor: "var(--border)" }}>
        {tabs.filter((t) => t.show).map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px"
            style={tab === key
              ? { borderColor: "var(--accent)", color: "var(--accent)" }
              : { borderColor: "transparent", color: "var(--text-secondary)" }}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {tab === "profile" && <ProfileTab />}
      {tab === "preferences" && <PreferencesTab />}
      {tab === "organization" && isAdmin && <OrganizationTab />}
      {tab === "permissions" && <PermissionsTab />}
    </div>
  );
}
