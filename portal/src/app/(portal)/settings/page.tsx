"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Settings as SettingsIcon, User as UserIcon, Palette, Building2, ShieldCheck,
  Check, Minus, Monitor, Sun, Moon, Mail, Copy, RefreshCw, MapPin, Pencil, Trash2,
  LifeBuoy,
} from "lucide-react";
import { getMe, updateProfile, changePassword } from "@/lib/api/auth";
import {
  getOrgSettings, updateOrgSettings, getPermissionMatrix,
  getEmailSettings, configureEmailSettings, verifyEmailSettings, chooseEmailSender,
  updateAssetEmailTemplate,
  getHelpdeskSettings, updateHelpdeskSettings, verifyHelpdeskSettings,
} from "@/lib/api/settings";
import { listLocations, createLocation, renameLocation, deleteLocation } from "@/lib/api/locations";
import { RichTextEditor, type RichTextHandle } from "@/components/rich-text-editor";
import { getTheme, setTheme, type Theme } from "@/lib/theme";
import type {
  EmailSendMethod, EmailSettings, EmailVerificationStatus, HelpdeskSettingsInput,
  OrganizationSettingsInput, UserRole,
} from "@/lib/api/types";

type Tab =
  | "profile" | "preferences" | "organization" | "email" | "helpdesk"
  | "locations" | "permissions";

function errDetail(err: unknown): string | undefined {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
}

const ROLE_STYLE: Record<UserRole, { color: string; bg: string }> = {
  admin: { color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  technician: { color: "#b246d4", bg: "rgba(59,130,246,0.1)" },
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
                  background: active ? "rgba(154,47,187,0.06)" : "var(--bg)",
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
            <input type="number" min={8} max={128} value={form.min_password_length ?? 8}
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
          Password length has an enforced floor of 8 characters; you can only raise it.
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

/** Turn a template written before the rich-text editor existed into equivalent markup.
 *
 *  Necessary rather than tidy: HTML collapses newlines, so loading a plain-text body into a
 *  contentEditable as-is would run every paragraph together and the author would find their
 *  template mangled by having opened it. Escaping first keeps a body that literally says
 *  "<b>" saying "<b>", which is how it sends today. */
function textToHtml(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped
    .split(/\n{2,}/)
    .map((para) => `<p>${para.replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function AssetEmailTemplateEditor({ settings }: { settings: EmailSettings }) {
  const queryClient = useQueryClient();
  const [subject, setSubject] = useState(settings.asset_email_subject ?? "");
  const [body, setBody] = useState(
    settings.asset_email_body_format === "html"
      ? (settings.asset_email_body ?? "")
      : textToHtml(settings.asset_email_body ?? ""),
  );
  // One comma-separated field rather than a row-adding widget: an admin pastes a couple of
  // addresses here once and never touches it again.
  const [cc, setCc] = useState((settings.asset_email_cc ?? []).join(", "));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const editorRef = useRef<RichTextHandle>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerGroup, setPickerGroup] = useState(0);

  async function save() {
    setSaving(true); setSaved(false);
    try {
      const next = await updateAssetEmailTemplate({
        // Always html: the body has been through the rich-text editor by the time it can be
        // saved, and an old plain-text template was converted when it loaded.
        subject, body, body_format: "html",
        // Always sent, so clearing the field actually clears the list. Omitting it would
        // leave the last address saved with no way to remove it.
        cc: cc.split(",").map((a) => a.trim()).filter(Boolean),
      });
      queryClient.setQueryData(["email-settings"], next);
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  }

  function insert(token: string) {
    editorRef.current?.insertText(`{{${token}}}`);
  }

  // Every placeholder the server offers, flattened for lookup. Sample values and the
  // needs-a-device flag both come from the API, so the editor can't disagree with the send
  // path about what a field is or what it looks like.
  // `?? []` because during a rolling deploy this page can briefly talk to an API that
  // predates the field. An empty picker is a bad half-hour; a crashed Settings page is a
  // support ticket.
  const groups = settings.asset_email_placeholder_groups ?? [];
  const all = groups.flatMap((g) => g.placeholders);
  const byKey = new Map(all.map((p) => [p.key, p]));

  // Two previews of the same template, because assets come in two kinds and only one of
  // them has hardware to talk about. Showing sample device values unconditionally is how a
  // template gets written that looks finished and arrives with holes in it.
  //
  // Sample values are escaped on the way in, the same as the send path escapes real ones —
  // otherwise a sample containing a bracket would render as markup here and as text in the
  // actual email, and the preview would be lying again in a new way.
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const render = (s: string, withDevice: boolean) =>
    s.replace(/\{\{(\w+)\}\}/g, (_, k) => {
      if (k === "acknowledge_button") return "[ Acknowledge receipt ]";
      const spec = byKey.get(k);
      if (!spec) return `{{${k}}}`;        // unknown token — left visible, as it will send
      if (!withDevice && spec.needs_device) return "";
      return esc(spec.sample);
    });

  const used = (key: string) => body.includes(`{{${key}}}`) || subject.includes(`{{${key}}}`);
  const usesDeviceFields = all.some((p) => p.needs_device && used(p.key));

  return (
    <Panel title="Asset assignment email"
      description="Customize the email sent automatically when you assign an asset to someone. The “Acknowledge receipt” button is added for you (or place it yourself with {{acknowledge_button}}).">
      <Field label="Subject">
        <input value={subject} onChange={(e) => setSubject(e.target.value)}
          className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
      </Field>
      <Field label="Copy to (CC)">
        <input value={cc} onChange={(e) => setCc(e.target.value)}
          placeholder="it@yourcompany.com, assets@yourcompany.com"
          className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
        <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
          Kept in your own inbox, and — because it is a CC rather than a hidden copy — the
          employee&apos;s Reply All comes back to you too. Applies to this email only, not to
          password resets or sign-in alerts. Up to 5 addresses.
        </p>
      </Field>
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-sm" style={{ color: "var(--text-secondary)" }}>Message</label>
          <button type="button" onClick={() => setPickerOpen((v) => !v)}
            className="text-xs font-medium" style={{ color: "var(--accent)" }}>
            {pickerOpen ? "Hide placeholders" : "Insert placeholder"}
          </button>
        </div>
        {/* The picker sits beside the editor rather than above it, so the text you are
            writing stays on screen while you hunt for the field to drop into it. */}
        <div className="flex gap-3 items-start">
          <div className="flex-1 min-w-0">
            <RichTextEditor ref={editorRef} value={body} onChange={setBody} />
          </div>
          {pickerOpen && (
            <div className="w-72 shrink-0 rounded-lg overflow-hidden"
              style={{ border: "1px solid var(--border)", background: "var(--bg)" }}>
              <div className="flex" style={{ maxHeight: 320 }}>
                <div className="w-28 shrink-0 overflow-y-auto py-1"
                  style={{ borderRight: "1px solid var(--border)" }}>
                  {groups.map((g, i) => (
                    <button key={g.key} type="button" onClick={() => setPickerGroup(i)}
                      className="w-full text-left px-2 py-1.5 text-xs leading-tight"
                      style={{
                        color: i === pickerGroup ? "var(--accent)" : "var(--text-secondary)",
                        background: i === pickerGroup ? "var(--surface)" : "transparent",
                        fontWeight: i === pickerGroup ? 600 : 400,
                      }}>
                      {g.title}
                    </button>
                  ))}
                  <button type="button" onClick={() => setPickerGroup(groups.length)}
                    className="w-full text-left px-2 py-1.5 text-xs leading-tight"
                    style={{
                      color: pickerGroup === groups.length ? "var(--accent)" : "var(--text-secondary)",
                      background: pickerGroup === groups.length ? "var(--surface)" : "transparent",
                      fontWeight: pickerGroup === groups.length ? 600 : 400,
                    }}>
                    The button
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-1.5 space-y-1">
                  {pickerGroup === groups.length ? (
                    <PlaceholderChip label="Acknowledge receipt" token="acknowledge_button"
                      hint="Positions the button instead of leaving it at the end"
                      onClick={() => insert("acknowledge_button")} accent />
                  ) : (
                    groups[pickerGroup]?.placeholders.map((p) => (
                      <PlaceholderChip key={p.key} label={p.label} token={p.key}
                        hint={`e.g. ${p.sample}`} warn={p.needs_device}
                        onClick={() => insert(p.key)} />
                    ))
                  )}
                  {groups[pickerGroup]?.key === "device" && (
                    <p className="text-[11px] px-1 pt-1" style={{ color: "#f59e0b" }}>
                      Empty unless the asset is linked to a device.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="rounded-lg p-4" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
        <p className="text-xs uppercase tracking-wide mb-2" style={{ color: "var(--text-secondary)" }}>
          Preview — asset linked to a device
        </p>
        <p className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{render(subject, true) || "—"}</p>
        {/* The body is markup now, so the preview has to render it as markup or it stops
            resembling the email. What it renders is what the server sanitized on save. */}
        <div className="astra-rte text-sm" style={{ color: "var(--text-secondary)" }}
          dangerouslySetInnerHTML={{ __html: render(body, true) }} />
      </div>

      {/* The second preview only earns its space when the template actually uses device
          fields. Otherwise both are identical and it is just noise. */}
      {usesDeviceFields && (
        <div className="rounded-lg p-4" style={{ background: "var(--bg)", border: "1px solid #f59e0b" }}>
          <p className="text-xs uppercase tracking-wide mb-2" style={{ color: "#f59e0b" }}>
            Preview — asset with no device linked
          </p>
          <p className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{render(subject, false) || "—"}</p>
          <div className="astra-rte text-sm" style={{ color: "var(--text-secondary)" }}
            dangerouslySetInnerHTML={{ __html: render(body, false) }} />
          {/* Names the fields this template actually uses, rather than reciting the whole
              device group — the recited list went stale the moment the group grew. */}
          <p className="text-xs mt-3" style={{ color: "var(--text-secondary)" }}>
            {all.filter((p) => p.needs_device && used(p.key)).map((p) => p.label).join(", ")}
            {" "}come from the device&apos;s own telemetry. An asset that isn&apos;t linked to a
            device has none of that, so they come out empty — as above. Link the asset to a
            device when you create it, or write the wording so the gaps read cleanly.
          </p>
        </div>
      )}
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

/** One row in the placeholder picker: what it means on top, what it inserts underneath.
 *  The token alone made you guess — {{brand_model}} and {{device_user}} in particular. */
function PlaceholderChip({ label, token, hint, onClick, warn, accent }: {
  label: string; token: string; hint: string; onClick: () => void;
  warn?: boolean; accent?: boolean;
}) {
  return (
    <button type="button" onClick={onClick} title={hint}
      className="w-full text-left px-2 py-1.5 rounded-md"
      style={{
        background: "var(--surface)",
        border: `1px solid ${warn ? "#f59e0b" : "var(--border)"}`,
      }}>
      <span className="block text-xs truncate"
        style={{ color: accent ? "var(--accent)" : "var(--text-primary)" }}>{label}</span>
      <span className="block text-[11px] font-mono truncate" style={{ color: "var(--text-secondary)" }}>
        {`{{${token}}}`}
      </span>
    </button>
  );
}

/** One of the two ways to send. A card rather than a radio row: the two options differ in
 *  what they cost the admin to set up, and that trade needs room to be stated. */
function SenderOption({
  selected, onSelect, disabled, title, body, note,
}: {
  selected: boolean; onSelect: () => void; disabled: boolean;
  title: string; body: string; note: string;
}) {
  return (
    <button type="button" onClick={onSelect} disabled={disabled}
      className="text-left p-3.5 rounded-xl transition-colors disabled:opacity-60"
      style={{
        background: selected ? "color-mix(in srgb, var(--accent) 8%, transparent)" : "var(--bg)",
        border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}`,
      }}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0 w-4 h-4 rounded-full flex items-center justify-center"
          style={{ border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}` }}>
          {selected && <span className="w-2 h-2 rounded-full" style={{ background: "var(--accent)" }} />}
        </span>
        <div>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</p>
          <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--text-secondary)" }}>{body}</p>
          <p className="text-xs mt-1.5 font-medium" style={{ color: "var(--accent)" }}>{note}</p>
        </div>
      </div>
    </button>
  );
}

function EmailTab() {
  const queryClient = useQueryClient();
  const { data: settings, isLoading } = useQuery({ queryKey: ["email-settings"], queryFn: getEmailSettings });
  const [fromName, setFromName] = useState("");
  const [fromAddress, setFromAddress] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [busy, setBusy] = useState<"save" | "verify" | "sender" | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (settings) {
      setFromName(settings.from_name ?? "");
      setFromAddress(settings.from_address ?? "");
      setReplyTo(settings.reply_to ?? "");
    }
  }, [settings]);

  async function chooseSender(next: EmailSendMethod) {
    setBusy("sender"); setError("");
    try {
      const saved = await chooseEmailSender({
        method: next,
        from_name: fromName.trim() || null,
        reply_to: replyTo.trim() || null,
      });
      queryClient.setQueryData(["email-settings"], saved);
    } catch (err) {
      setError(errDetail(err) ?? "Couldn't save. Check the reply-to address and try again.");
    } finally { setBusy(null); }
  }

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

  const method = settings?.method ?? "shared";
  const sharedAvailable = settings?.shared_sender_available ?? true;
  // Already sending through us, but no longer entitled to. Mail is deliberately still
  // going out — cutting a customer's employee-facing email the moment a plan changes turns
  // a billing event into a support incident — so this has to be visible instead.
  const sharedRevoked = method === "shared" && !sharedAvailable;

  return (
    <div className="space-y-6">
      <Panel
        title="How your email is sent"
        description="Asset acknowledgements and notifications go to your employees. Pick which address they arrive from."
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <SenderOption
            selected={method === "shared"}
            onSelect={() => chooseSender("shared")}
            disabled={busy !== null || !sharedAvailable}
            title="Send through ASTRA"
            body="Works immediately — nothing to set up. Mail arrives from our address, shown as coming from you."
            note={sharedAvailable ? "No DNS changes" : "Not included in your plan"}
          />
          <SenderOption
            selected={method === "dns"}
            onSelect={() => chooseSender("dns")}
            disabled={busy !== null}
            title="Send from your own domain"
            body="Mail arrives from your address, so it looks like every other email your IT team sends."
            note="Needs DNS records added"
          />
        </div>

        {/* What the employee will see. Shown rather than described — the difference
            between the two options is exactly this line. */}
        <div className="rounded-lg px-3 py-2.5 text-xs space-y-1"
          style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          <p style={{ color: "var(--text-secondary)" }}>Recipients will see</p>
          <p className="font-mono" style={{ color: "var(--text-primary)" }}>
            {settings?.effective_from || "—"}
          </p>
        </div>

        <Field label="Display name">
          <input value={fromName} onChange={(e) => setFromName(e.target.value)} placeholder="Acme IT"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
        </Field>

        <Field label="Reply-to address">
          <input type="email" value={replyTo} onChange={(e) => setReplyTo(e.target.value)}
            placeholder="helpdesk@yourcompany.com"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
          <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
            Where replies go when an employee answers the email.
          </p>
        </Field>

        {/* Not a nag. Without a reply-to on the shared sender, an employee's reply reaches
            ASTRA, where nobody reads a customer's staff mail — so their question is lost
            with no bounce and no trace. */}
        {sharedRevoked && (
          <p className="text-xs rounded-lg p-3"
            style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b" }}>
            Your plan no longer includes sending through ASTRA. Your email is still going
            out for now — set up your own sending domain below, or ask your ASTRA operator
            to re-enable it.
          </p>
        )}

        {method === "shared" && sharedAvailable && !settings?.reply_to && (
          <p className="text-xs rounded-lg p-3"
            style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b" }}>
            Set a reply-to address. Mail goes out from ASTRA&apos;s address, so without one a
            reply comes to us — and nobody here can answer your employee&apos;s question.
          </p>
        )}

        <div className="flex justify-end">
          <button type="button" onClick={() => chooseSender(method)} disabled={busy !== null}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
            style={{ background: "var(--accent)" }}>
            {busy === "sender" ? "Saving…" : "Save"}
          </button>
        </div>
      </Panel>

      {/* The domain panel also shows when the shared option isn't theirs — otherwise an
          Essential customer sees two cards, cannot pick either, and has nowhere to go. */}
      {method !== "dns" && sharedAvailable ? null : (
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
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
          </Field>
          <Field label="Send from address">
            <input type="email" value={fromAddress} onChange={(e) => setFromAddress(e.target.value)} placeholder="it-support@yourcompany.com"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
          </Field>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button type="submit" disabled={busy !== null || !fromAddress.trim() || !fromName.trim()}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
            {busy === "save" ? "Saving…" : settings?.configured ? "Update address" : "Save & get DNS records"}
          </button>
        </form>
      </Panel>
      )}

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

/* ── Locations ───────────────────────────────────────────────────────────── */

function LocationsTab() {
  const queryClient = useQueryClient();
  const { data: locations, isLoading } = useQuery({ queryKey: ["locations"], queryFn: listLocations });
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["locations"] });

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setBusy(true); setError("");
    try { await createLocation(newName.trim()); setNewName(""); await refresh(); }
    catch (err) { setError(errDetail(err) || "Couldn't add that location."); }
    finally { setBusy(false); }
  }
  async function saveRename(id: string) {
    if (!editName.trim()) { setEditingId(null); return; }
    setError("");
    try { await renameLocation(id, editName.trim()); setEditingId(null); await refresh(); }
    catch (err) { setError(errDetail(err) || "Couldn't rename that location."); }
  }
  async function remove(id: string, name: string) {
    if (!confirm(`Delete location "${name}"?`)) return;
    setError("");
    try { await deleteLocation(id); await refresh(); }
    catch (err) { setError(errDetail(err) || "Couldn't delete that location."); }
  }

  return (
    <Panel title="Locations"
      description="Your sites and offices. Assets pick a location from this list; renaming one updates every asset there, and a location can't be deleted while assets still use it.">
      <form onSubmit={add} className="flex gap-2">
        <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Add a location — e.g. HQ, SF Office, Warehouse-2"
          className="flex-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
        <button type="submit" disabled={busy || !newName.trim()}
          className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
          Add
        </button>
      </form>
      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="rounded-lg overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        {isLoading && <p className="px-4 py-3 text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>}
        {locations && locations.length === 0 && (
          <p className="px-4 py-6 text-sm text-center" style={{ color: "var(--text-secondary)" }}>No locations yet — add your first above.</p>
        )}
        {locations?.map((l) => (
          <div key={l.id} className="flex items-center gap-2 px-4 py-2.5" style={{ borderBottom: "1px solid var(--border)" }}>
            {editingId === l.id ? (
              <>
                <input value={editName} autoFocus onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") saveRename(l.id); if (e.key === "Escape") setEditingId(null); }}
                  className="flex-1 px-2 py-1 rounded text-sm outline-none focus:ring-2 focus:ring-brand-500" style={inputStyle} />
                <button onClick={() => saveRename(l.id)} className="text-xs px-2 py-1 rounded-lg text-white" style={{ background: "var(--accent)" }}>Save</button>
                <button onClick={() => setEditingId(null)} className="text-xs px-2 py-1 rounded-lg" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
              </>
            ) : (
              <>
                <span className="flex-1 text-sm font-medium" style={{ color: "var(--text-primary)" }}>{l.name}</span>
                <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{l.asset_count} asset{l.asset_count === 1 ? "" : "s"}</span>
                <button onClick={() => { setEditingId(l.id); setEditName(l.name); }} title="Rename"
                  className="p-1 rounded-lg hover:bg-brand-500/10 hover:text-brand-500" style={{ color: "var(--text-secondary)" }}><Pencil size={14} /></button>
                <button onClick={() => remove(l.id, l.name)} title="Delete"
                  className="p-1 rounded-lg hover:bg-red-500/10 hover:text-red-500" style={{ color: "var(--text-secondary)" }}><Trash2 size={14} /></button>
              </>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* ── Helpdesk ────────────────────────────────────────────────────────────── */

const PRIORITIES = [
  { value: 1, label: "Low" },
  { value: 2, label: "Medium" },
  { value: 3, label: "High" },
  { value: 4, label: "Urgent" },
];

function HelpdeskTab() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["helpdesk-settings"], queryFn: getHelpdeskSettings });

  const [domain, setDomain] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [priority, setPriority] = useState(1);
  const [workspace, setWorkspace] = useState("");
  const [busy, setBusy] = useState<"save" | "verify" | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (!data) return;
    setDomain(data.domain ?? "");
    setPriority(data.default_priority);
    setWorkspace(data.workspace_id ? String(data.workspace_id) : "");
  }, [data]);

  async function save(patch: HelpdeskSettingsInput) {
    setBusy("save");
    setMsg(null);
    try {
      await updateHelpdeskSettings(patch);
      // The key is write-only: clear the box so it is never sitting in the DOM, and so a
      // second save does not resend it.
      setApiKey("");
      await queryClient.invalidateQueries({ queryKey: ["helpdesk-settings"] });
      setMsg({ ok: true, text: "Saved." });
    } catch (err) {
      setMsg({ ok: false, text: errDetail(err) ?? "Could not save." });
    } finally {
      setBusy(null);
    }
  }

  async function verify() {
    setBusy("verify");
    setMsg(null);
    try {
      const result = await verifyHelpdeskSettings();
      await queryClient.invalidateQueries({ queryKey: ["helpdesk-settings"] });
      setMsg(result.ok
        ? { ok: true, text: "Connected. ASTRA can raise tickets in this helpdesk." }
        : { ok: false, text: result.detail ?? "Could not connect." });
    } catch (err) {
      setMsg({ ok: false, text: errDetail(err) ?? "Could not connect." });
    } finally {
      setBusy(null);
    }
  }

  if (isLoading || !data) {
    return <Panel title="Helpdesk"><p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p></Panel>;
  }

  const unreadable = data.api_key_masked === "unreadable";

  return (
    <div className="space-y-4">
      <Panel
        title="Freshservice"
        description="When ASTRA can't fix something itself, it asks the user and — with their agreement — raises a ticket in your own helpdesk, with everything it already tried attached."
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              {data.ready ? "Connected" : "Not connected"}
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              {data.ready
                ? data.last_verified_at
                  ? `Last checked ${new Date(data.last_verified_at).toLocaleString()}`
                  : "Not checked yet — run a connection test."
                : "Until this is connected, ASTRA won't offer to raise tickets."}
            </p>
          </div>
          <Toggle on={data.enabled} disabled={busy !== null}
            onChange={(on) => save({ enabled: on })} />
        </div>

        {/* Shown rather than hidden: a saved-but-unusable key looks identical to no key at
            all, and the admin who saved it would never know to re-enter it. */}
        {unreadable && (
          <p className="text-xs rounded-lg p-3" style={{ background: "rgba(245,158,11,0.12)", color: "#f59e0b" }}>
            The saved API key can no longer be read — the encryption key on this deployment
            has changed. Enter the key again to reconnect.
          </p>
        )}

        {data.last_error && !msg && (
          <p className="text-xs rounded-lg p-3" style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }}>
            {data.last_error}
          </p>
        )}

        <Field label="Freshservice domain">
          <input value={domain} onChange={(e) => setDomain(e.target.value)}
            placeholder="acme  —  or paste the full URL"
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={inputStyle} />
        </Field>

        <Field label={data.api_key_masked && !unreadable ? `API key (saved: ${data.api_key_masked})` : "API key"}>
          <input value={apiKey} onChange={(e) => setApiKey(e.target.value)}
            type="password" autoComplete="off"
            placeholder={data.api_key_masked && !unreadable ? "Leave blank to keep the saved key" : "From Freshservice → Profile Settings"}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={inputStyle} />
          <div className="flex items-baseline justify-between gap-3 mt-1">
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Stored encrypted. It is never shown again after saving.
            </p>
            {/* Turning the connector off leaves the key sitting in our database. An admin
                whose key leaked needs to be able to take it out. */}
            {data.api_key_masked && (
              <button onClick={() => save({ api_key: "" })} disabled={busy !== null}
                className="text-xs underline shrink-0 disabled:opacity-50"
                style={{ color: "var(--text-secondary)" }}>
                Remove saved key
              </button>
            )}
          </div>
        </Field>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Priority for ASTRA's tickets">
            <select value={priority} onChange={(e) => setPriority(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={inputStyle}>
              {PRIORITIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
              ASTRA files at this level rather than judging urgency itself.
            </p>
          </Field>

          <Field label="Workspace ID (optional)">
            <input value={workspace} onChange={(e) => setWorkspace(e.target.value.replace(/\D/g, ""))}
              inputMode="numeric" placeholder="Leave blank unless you have more than one"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
              style={inputStyle} />
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
              Multi-workspace accounts need this, or tickets land where nobody is watching.
            </p>
          </Field>
        </div>

        {msg && (
          <p className="text-sm" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>
        )}

        <div className="flex flex-wrap gap-2 justify-end">
          <button onClick={verify} disabled={busy !== null || !data.ready}
            className="px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            {busy === "verify" ? "Checking…" : "Test connection"}
          </button>
          <button
            onClick={() => save({
              domain: domain.trim() || undefined,
              api_key: apiKey.trim() || undefined,
              default_priority: priority,
              workspace_id: workspace ? Number(workspace) : null,
            })}
            disabled={busy !== null}
            className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--accent)" }}>
            {busy === "save" ? "Saving…" : "Save"}
          </button>
        </div>

        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Testing the connection only reads your ticket field settings — it never creates a
          ticket, so you can run it as often as you like.
        </p>
      </Panel>
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
    { key: "helpdesk", label: "Helpdesk", icon: LifeBuoy, show: !!isAdmin },
    { key: "locations", label: "Locations", icon: MapPin, show: !!isAdmin },
    { key: "permissions", label: "Permissions", icon: ShieldCheck, show: true },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
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
      {tab === "helpdesk" && isAdmin && <HelpdeskTab />}
      {tab === "locations" && isAdmin && <LocationsTab />}
      {tab === "permissions" && <PermissionsTab />}
    </div>
  );
}
