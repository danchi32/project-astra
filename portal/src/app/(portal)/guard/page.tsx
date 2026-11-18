"use client";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  FINDING_KINDS, endGuardPilot, getBrowserPolicy, getBrowserPolicyDevices, getSiteCategories, putBrowserPolicy,
  type BrowserPolicy, type FindingKind,
} from "@/lib/api/guard";
import { isUpgradeRequired } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3 · AI Guard → Browser policy. What the org's PCs enforce in Chrome, Edge and Firefox.
// The agent sets only what is listed here and never overwrites a browser policy the org already
// sets another way (a GPO); those show up below as conflicts, per PC.

const SWITCHES: { key: keyof BrowserPolicy; label: string; help: string }[] = [
  { key: "incognito_off", label: "No incognito / InPrivate / private windows", help: "Private windows run without the extension." },
  { key: "extension_developer_mode_off", label: "No extension developer mode", help: "Stops people loading unpacked extensions (Chrome, Edge)." },
  { key: "new_profiles_off", label: "No new browser profiles or guest windows", help: "A fresh profile would start without the company's settings." },
  { key: "dev_tools_off", label: "No developer tools", help: "Broader: also stops IT staff using them. Firefox's only way to block temporary add-ons." },
];

const lines = (s: string) => s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);

const MODES: { value: BrowserPolicy["guard_mode"]; label: string; help: string }[] = [
  { value: "log", label: "Record only", help: "Nothing is stopped. Every organization starts here for 14 days to see what turns up." },
  { value: "warn", label: "Warn", help: "The person is told what was found and can go ahead." },
  { value: "justify", label: "Ask for a reason", help: "To go ahead, the person picks a work reason from a short list. You see which." },
  { value: "redact", label: "Hide the sensitive parts", help: "A paste goes in with numbers replaced, e.g. [PAN]. Files and forms get a warning." },
  { value: "approve", label: "Needs IT approval", help: "Held until an admin approves it under Approvals; then allowed on that site for a while." },
  { value: "block", label: "Block", help: "Paste, upload or send is refused. If the check itself fails, it warns instead." },
];

export default function GuardPage() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";
  const { data, error, isLoading } = useQuery({ queryKey: ["browser-policy"], queryFn: getBrowserPolicy, retry: false });
  const { data: devices } = useQuery({ queryKey: ["browser-policy-devices"], queryFn: getBrowserPolicyDevices,
    enabled: !!data, refetchInterval: 60_000 });
  const { data: categories } = useQuery({ queryKey: ["site-categories"], queryFn: getSiteCategories,
    enabled: !!data, staleTime: Infinity });
  const [form, setForm] = useState<BrowserPolicy | null>(null);
  const [text, setText] = useState({ blocked: "", allowed: "", google: "", watched: "", keywords: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!data) return;
    setForm(data.policy);
    setText({ blocked: data.policy.blocked_sites.join("\n"), allowed: data.policy.allowed_sites.join("\n"),
              google: data.policy.google_allowed_domains.join("\n"), watched: data.policy.guard_watched_sites.join("\n"),
              keywords: data.policy.guard_keywords.join("\n") });
  }, [data]);

  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const input = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

  if (isUpgradeRequired(error)) {
    return (
      <div className="rounded-xl p-8 text-center max-w-lg mx-auto" style={panel}>
        <ShieldAlert size={22} className="mx-auto mb-3" style={{ color: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>AI Guard is an add-on</h2>
        <p className="text-sm mt-2" style={muted}>
          Lock down your employees&apos; browsers: no private windows, no unpacked extensions, blocked sites, and
          Google sign-in for your company account only. Ask your SAVIO contact to switch it on for your organization.
        </p>
      </div>
    );
  }

  async function save() {
    if (!form) return;
    setSaving(true); setMsg(null);
    try {
      const r = await putBrowserPolicy({ ...form, blocked_sites: lines(text.blocked), allowed_sites: lines(text.allowed),
                                         google_allowed_domains: lines(text.google), guard_watched_sites: lines(text.watched),
                                         // Keywords may contain commas ("Q3, final"): one per line only.
                                         guard_keywords: text.keywords.split("\n").map((x) => x.trim()).filter(Boolean) });
      qc.setQueryData(["browser-policy"], r);
      setMsg({ ok: true, text: `Saved as version ${r.version}. PCs pick it up within the hour.` });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not save the policy.") });
    } finally { setSaving(false); }
  }

  // E8: the first 14 days only record. The backend refuses any other mode until then.
  const pilotUntil = data?.pilot_until ? new Date(data.pilot_until) : null;
  const pilotDays = pilotUntil ? Math.max(1, Math.ceil((pilotUntil.getTime() - Date.now()) / 86_400_000)) : 0;

  async function endPilot() {
    setSaving(true); setMsg(null);
    try {
      qc.setQueryData(["browser-policy"], await endGuardPilot());
      qc.invalidateQueries({ queryKey: ["guard-suggestions"] });
      setMsg({ ok: true, text: "Pilot ended. Pick a mode and save; until then PCs keep recording only." });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not end the pilot.") });
    } finally { setSaving(false); }
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><ShieldAlert size={18} /></div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Browser policy</h1>
          <p className="text-xs max-w-2xl" style={muted}>
            Applied by the SAVIO agent to Chrome, Edge and Firefox on every PC, and put back within a minute if someone
            removes it. SAVIO never overwrites a browser setting your organization already manages another way (such as
            Group Policy); those show as conflicts below.
          </p>
        </div>
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && !isUpgradeRequired(error) && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load the policy.")}</p>}

      {form && (
        <div className="rounded-xl p-5 space-y-4" style={panel}>
          {SWITCHES.map((s) => (
            <label key={s.key} className="flex items-start gap-3 text-sm" style={{ color: "var(--text-primary)" }}>
              <input type="checkbox" className="mt-1" disabled={!isAdmin} checked={!!form[s.key]}
                onChange={(e) => setForm({ ...form, [s.key]: e.target.checked })} />
              <span>{s.label}<span className="block text-xs" style={muted}>{s.help}</span></span>
            </label>
          ))}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {([["blocked", "Blocked sites", "One per line, e.g. wetransfer.com. Covers subdomains."],
               ["allowed", "Always allowed", "Exceptions to the block list."],
               ["google", "Google sign-in only for", "Your Workspace domains, e.g. acme.in. Personal Gmail is then refused."]] as const).map(([k, label, help]) => (
              <label key={k} className="text-xs space-y-1" style={muted}>
                <span className="font-medium">{label}</span>
                <textarea rows={5} disabled={!isAdmin} value={text[k]} onChange={(e) => setText({ ...text, [k]: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none font-mono" style={input} />
                <span className="block">{help}</span>
              </label>
            ))}
          </div>
          {categories && (
            <fieldset className="space-y-2">
              <legend className="text-xs font-medium" style={muted}>Also block whole kinds of site</legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {categories.map((c) => (
                  <label key={c.key} className="flex items-start gap-2 text-sm rounded-lg p-3" style={{ ...panel, color: "var(--text-primary)" }}>
                    <input type="checkbox" className="mt-1" disabled={!isAdmin} checked={form.blocked_categories.includes(c.key)}
                      onChange={(e) => setForm({ ...form, blocked_categories: e.target.checked
                        ? [...form.blocked_categories, c.key] : form.blocked_categories.filter((x) => x !== c.key) })} />
                    <span className="min-w-0">{c.label}
                      <span className="block text-xs break-words" style={muted}>{c.hosts.join(", ")}</span>
                    </span>
                  </label>
                ))}
              </div>
              <p className="text-xs" style={muted}>
                A site in &ldquo;Always allowed&rdquo; stays open even if its category is blocked, e.g. linkedin.com for a sales team.
              </p>
            </fieldset>
          )}
          <label className="flex items-start gap-3 text-sm pt-4" style={{ color: "var(--text-primary)", borderTop: "1px solid var(--border)" }}>
            <input type="checkbox" className="mt-1" disabled={!isAdmin} checked={form.discovery_enabled}
              onChange={(e) => setForm({ ...form, discovery_enabled: e.target.checked })} />
            <span>Find where sensitive files are kept
              <span className="block text-xs" style={muted}>
                Once a week, on each PC, SAVIO checks the text, Word and Excel files in people&apos;s Desktop, Documents,
                Downloads and OneDrive folders. You see which folders hold Aadhaar, PAN, card or bank numbers and how many,
                never the files&apos; names or contents. Results under AI Guard → Where data lives.
              </span>
            </span>
          </label>
          <div className="pt-4 space-y-3" style={{ borderTop: "1px solid var(--border)" }}>
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Sensitive data in the browser</h2>
              <p className="text-xs" style={muted}>
                The SAVIO extension checks what is pasted, dropped, uploaded or sent on a page, on the PC itself. Only counts
                (&ldquo;2 PAN numbers&rdquo;) are ever recorded, never the text. It is force-installed once it is published to
                the browser stores; until then these settings wait.
              </p>
            </div>
            {pilotUntil && (
              <div className="flex flex-wrap items-center gap-3 rounded-lg p-3 text-sm"
                style={{ background: "rgba(37,99,235,0.08)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                <span className="flex-1 min-w-[16rem]">
                  <span className="font-medium">Pilot: record only until {pilotUntil.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}.</span>
                  <span className="block text-xs" style={muted}>
                    {data?.version ? `${pilotDays} ${pilotDays === 1 ? "day" : "days"} left. ` : "The 14 days start when you first save. "}
                    Nobody is interrupted while you see what turns up. Afterwards nothing changes on its own: you pick the mode.
                  </span>
                </span>
                {isAdmin && !!data?.version && (
                  <button type="button" onClick={endPilot} disabled={saving}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium" style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    End the pilot now
                  </button>
                )}
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {MODES.map((m) => (
                <label key={m.value} className="flex items-start gap-2 text-sm rounded-lg p-3"
                  style={{ ...panel, color: "var(--text-primary)", opacity: pilotUntil && m.value !== "log" ? 0.5 : 1 }}>
                  <input type="radio" name="guard_mode" className="mt-1" disabled={!isAdmin || (!!pilotUntil && m.value !== "log")}
                    checked={form.guard_mode === m.value}
                    onChange={() => setForm({ ...form, guard_mode: m.value })} />
                  <span>{m.label}<span className="block text-xs" style={muted}>{m.help}</span></span>
                </label>
              ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {([["watched", "Sites to check", "One per line, e.g. chatgpt.com. Empty means every site."],
                 ["keywords", "Restricted keywords", "One per line, e.g. a project code name. Matched as whole words."]] as const).map(([k, label, help]) => (
                <label key={k} className="text-xs space-y-1" style={muted}>
                  <span className="font-medium">{label}</span>
                  <textarea rows={5} disabled={!isAdmin} value={text[k]} onChange={(e) => setText({ ...text, [k]: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none font-mono" style={input} />
                  <span className="block">{help}</span>
                </label>
              ))}
              <fieldset className="text-xs space-y-1" style={muted}>
                <legend className="font-medium">Count but never act on</legend>
                {(Object.entries(FINDING_KINDS) as [FindingKind, string][]).map(([kind, label]) => (
                  <label key={kind} className="flex items-center gap-2 text-sm" style={{ color: "var(--text-primary)" }}>
                    <input type="checkbox" disabled={!isAdmin} checked={form.guard_ignore_kinds.includes(kind)}
                      onChange={(e) => setForm({ ...form, guard_ignore_kinds: e.target.checked
                        ? [...form.guard_ignore_kinds, kind] : form.guard_ignore_kinds.filter((x) => x !== kind) })} />
                    {label}
                  </label>
                ))}
              </fieldset>
            </div>
          </div>
          {msg && <p className="text-xs" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}
          <div className="flex items-center justify-between">
            <span className="text-xs" style={muted}>
              Version {data?.version ?? 0}{data?.updated_at ? ` · saved ${new Date(data.updated_at).toLocaleString()}` : ""}
              {!isAdmin && " · only an admin can change it"}
            </span>
            {isAdmin && (
              <button onClick={save} disabled={saving} className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "var(--accent)" }}>{saving ? "Saving…" : "Save policy"}</button>
            )}
          </div>
        </div>
      )}

      {data && (
        <div className="rounded-xl overflow-x-auto" style={panel}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["PC", "Version", "Status", "Reported"].map((h) => (
                  <th key={h} className="text-left px-4 py-2 text-xs uppercase" style={muted}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(devices ?? []).map((d) => {
                const errors = d.results.filter((r) => r.error);
                const conflicts = d.results.flatMap((r) => r.conflicts.map((c) => `${r.browser}: ${c}`));
                const behind = d.version !== data.version;
                return (
                  <tr key={d.device_id} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    <td className="px-4 py-2 font-medium">{d.hostname}</td>
                    <td className="px-4 py-2" style={{ color: behind ? "#f59e0b" : muted.color }}>{d.version}{behind ? " (older)" : ""}</td>
                    <td className="px-4 py-2 text-xs">
                      {errors.map((r) => (
                        <div key={r.browser} style={{ color: "#ef4444" }}>
                          {r.browser === "Scanner" ? "Scanner's network block" : r.browser}: {r.error}
                        </div>
                      ))}
                      {conflicts.length > 0 && <div style={{ color: "#f59e0b" }}>Set elsewhere, left alone: {conflicts.join(", ")}</div>}
                      {!errors.length && !conflicts.length && <span style={{ color: "#10b981" }}>Applied</span>}
                    </td>
                    <td className="px-4 py-2 text-xs" style={muted}>{new Date(d.reported_at).toLocaleString()}</td>
                  </tr>
                );
              })}
              {devices && !devices.length && (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-sm" style={muted}>
                  No PC has reported yet. Agents with AI Guard support report within the hour.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
