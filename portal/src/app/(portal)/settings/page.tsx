"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Settings as SettingsIcon, User as UserIcon, Palette, Building2, ShieldCheck,
  Check, Minus, Monitor, Sun, Moon, Mail, Copy, RefreshCw,
} from "lucide-react";
import { getMe, updateProfile, changePassword } from "@/lib/api/auth";
import {
  getOrgSettings, updateOrgSettings, getPermissionMatrix,
  getEmailSettings, configureEmailSettings, verifyEmailSettings, updateAssetEmailTemplate,
} from "@/lib/api/settings";
import { getTheme, setTheme, type Theme } from "@/lib/theme";
import type { EmailSettings, EmailVerificationStatus, OrganizationSettingsInput, UserRole } from "@/lib/api/types";

type Tab = "profile" | "preferences" | "organization" | "email" | "permissions";

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

/* ── Email (per-org verified sending domain) ─────────────────────────────── */

const EMAIL_STATUS: Record<EmailVerificationStatus, { label: string; color: string }> = {
  unconfigured: { label: "Not set up", color: "#64748b" },
  pending: { label: "Pending DNS", color: "#f59e0b" },
  verified: { label: "Verified", color: "#10b981" },
  failed: { label: "Verification failed", color: "#ef4444" },
};

function DnsValue({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-start gap-2">
      <code className="flex-1 text-xs font-mono break-all px-2 py-1.5 rounded" style={{ background: "var(--bg)", color: "var(--text-primary)" }}>{value}</code>
      <button type="button" title="Copy"
        onClick={async () => { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
        className="p-1.5 rounded-lg shrink-0" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
        {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
      </button>
    </div>
  );
}

const TEMPLATE_SAMPLE: Record<string, string> = {
  employee_name: "Sam Rivera", asset_name: "Dell Latitude 7440", asset_tag: "AST-001",
  status: "in use", hostname: "LAPTOP-SAM", brand_model: "Dell Latitude 7440",
  serial: "5CD1234XYZ", cpu: "Intel Core i7-1365U", ram: "16 GB", storage: "512 GB",
  software: "142 apps", device_user: "ACME\\sam", org_name: "Your Company",
};

function AssetEmailTemplateEditor({ settings }: { settings: EmailSettings }) {
  const queryClient = useQueryClient();
  const [subject, setSubject] = useState(settings.asset_email_subject ?? "");
  const [body, setBody] = useState(settings.asset_email_body ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  async function save() {
    setSaving(true); setSaved(false);
    try {
      const next = await updateAssetEmailTemplate({ subject, body });
      queryClient.setQueryData(["email-settings"], next);
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  }

  function insert(token: string) {
    const t = `{{${token}}}`;
    const ta = bodyRef.current;
    if (!ta) { setBody(body + t); return; }
    const start = ta.selectionStart, end = ta.selectionEnd;
    setBody(body.slice(0, start) + t + body.slice(end));
    requestAnimationFrame(() => { ta.focus(); ta.selectionStart = ta.selectionEnd = start + t.length; });
  }

  const render = (s: string) =>
    s.replace(/\{\{(\w+)\}\}/g, (_, k) =>
      k === "acknowledge_button" ? "[ Acknowledge receipt ]" : (TEMPLATE_SAMPLE[k] ?? `{{${k}}}`));

  return (
    <Panel title="Asset assignment email"
      description="Customize the email sent automatically when you assign an asset to someone. The “Acknowledge receipt” button is added for you (or place it yourself with {{acknowledge_button}}).">
      <Field label="Subject">
        <input value={subject} onChange={(e) => setSubject(e.target.value)}
          className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" style={inputStyle} />
      </Field>
      <Field label="Message">
        <textarea ref={bodyRef} value={body} onChange={(e) => setBody(e.target.value)} rows={7}
          className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 font-mono" style={inputStyle} />
      </Field>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs" style={{ color: "var(--text-secondary)" }}>Insert:</span>
        {settings.asset_email_placeholders.map((p) => (
          <button key={p} type="button" onClick={() => insert(p)}
            className="text-xs font-mono px-2 py-1 rounded-lg" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            {`{{${p}}}`}
          </button>
        ))}
        <button type="button" onClick={() => insert("acknowledge_button")}
          className="text-xs font-mono px-2 py-1 rounded-lg" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--accent)" }}>
          {`{{acknowledge_button}}`}
        </button>
      </div>
      <div className="rounded-lg p-4" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
        <p className="text-xs uppercase tracking-wide mb-2" style={{ color: "var(--text-secondary)" }}>Preview</p>
        <p className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{render(subject) || "—"}</p>
        <p className="text-sm whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>{render(body)}</p>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={save} disabled={saving}
          className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
          {saving ? "Saving…" : "Save template"}
        </button>
        {saved && <span className="text-sm" style={{ color: "#10b981" }}>Saved</span>}
      </div>
    </Panel>
  );
}

function EmailTab() {
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({ queryKey: ["email-settings"], queryFn: getEmailSettings });
  const [fromName, setFromName] = useState("");
  const [fromAddress, setFromAddress] = useState("");
  const [busy, setBusy] = useState<"save" | "verify" | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (settings) {
      setFromName(settings.from_name ?? "");
      setFromAddress(settings.from_address ?? "");
    }
  }, [settings]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy("save"); setError("");
    try {
      const next = await configureEmailSettings({ from_name: fromName.trim(), from_address: fromAddress.trim() });
      queryClient.setQueryData(["email-settings"], next);
    } catch (err) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Couldn't save. Check the address and try again.");
    } finally { setBusy(null); }
  }
  async function verify() {
    setBusy("verify"); setError("");
    try {
      const next = await verifyEmailSettings();
      queryClient.setQueryData(["email-settings"], next);
      if (next.status !== "verified") setError("DNS records not found yet. They can take up to a few hours to propagate — try again shortly.");
    } catch (err) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Verification failed. Try again.");
    } finally { setBusy(null); }
  }

  if (isLoading) return <Panel title="Email"><p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p></Panel>;

  const status = settings?.status ?? "unconfigured";
  const badge = EMAIL_STATUS[status];

  return (
    <div className="space-y-6">
      <Panel title="Send email as your organization"
        description="Asset acknowledgements and other notifications will be sent from your own address once your domain is verified.">
        {!settings?.provider_ready && (
          <div className="rounded-lg px-3 py-2 text-xs" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid #f59e0b", color: "var(--text-primary)" }}>
            The email provider isn’t configured on this deployment yet, so verification won’t complete. Contact your ASTRA operator.
          </div>
        )}
        <form onSubmit={save} className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ color: badge.color, background: `${badge.color}1a` }}>{badge.label}</span>
            {settings?.verified_at && <span className="text-xs" style={{ color: "var(--text-secondary)" }}>since {new Date(settings.verified_at).toLocaleDateString()}</span>}
          </div>
          <Field label="Display name">
            <input value={fromName} onChange={(e) => setFromName(e.target.value)} placeholder="Acme IT"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" style={inputStyle} />
          </Field>
          <Field label="Send from address">
            <input type="email" value={fromAddress} onChange={(e) => setFromAddress(e.target.value)} placeholder="it-support@yourcompany.com"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" style={inputStyle} />
          </Field>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button type="submit" disabled={busy !== null || !fromAddress.trim() || !fromName.trim()}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
            {busy === "save" ? "Saving…" : settings?.configured ? "Update address" : "Save & get DNS records"}
          </button>
        </form>
      </Panel>

      {settings?.dns_records && settings.dns_records.length > 0 && status !== "verified" && (
        <Panel title="Add these DNS records"
          description="Add these at your DNS host (Cloudflare, GoDaddy, Google Workspace, etc.). They only add outbound authorization — your existing email is unaffected. Then click Verify.">
          <div className="space-y-4">
            {settings.dns_records.map((r, i) => (
              <div key={i} className="rounded-lg p-3 space-y-2" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                  <span className="font-semibold px-1.5 py-0.5 rounded" style={{ background: "var(--surface)", color: "var(--text-primary)" }}>{r.type}</span>
                  {r.purpose && <span>{r.purpose}</span>}
                  {r.priority != null && <span>priority {r.priority}</span>}
                  <span>TTL {r.ttl}</span>
                </div>
                <Field label="Name / Host"><DnsValue value={r.name} /></Field>
                <Field label="Value"><DnsValue value={r.value} /></Field>
              </div>
            ))}
          </div>
          <button type="button" onClick={verify} disabled={busy !== null}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
            <RefreshCw size={14} className={busy === "verify" ? "animate-spin" : ""} /> {busy === "verify" ? "Checking…" : "Verify DNS"}
          </button>
        </Panel>
      )}

      {status === "verified" && (
        <Panel title="You're all set">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Emails now send from <strong style={{ color: "var(--text-primary)" }}>{settings?.from_address}</strong>. Assign an asset to a user and they’ll get a receipt-confirmation email from you.
          </p>
        </Panel>
      )}

      {settings && <AssetEmailTemplateEditor settings={settings} />}
    </div>
  );
}

export default function SettingsPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";
  const [tab, setTab] = useState<Tab>("profile");

  const tabs: { key: Tab; label: string; icon: typeof UserIcon; show: boolean }[] = [
    { key: "profile", label: "Profile", icon: UserIcon, show: true },
    { key: "preferences", label: "Preferences", icon: Palette, show: true },
    { key: "organization", label: "Organization", icon: Building2, show: !!isAdmin },
    { key: "email", label: "Email", icon: Mail, show: !!isAdmin },
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
      {tab === "email" && isAdmin && <EmailTab />}
      {tab === "permissions" && <PermissionsTab />}
    </div>
  );
}
