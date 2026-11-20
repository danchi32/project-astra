"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  FINDING_KINDS, closeUsbWindow, deleteGroupPolicy, endGuardPilot, getBrowserPolicy, getBrowserPolicyDevices,
  getDrivesSeen, getGroupPolicies, getSiteCategories, openUsbWindow, putBrowserPolicy, putGroupPolicy, type BrowserPolicy,
  type DeviceBrowserState, type FindingKind,
} from "@/lib/api/guard";
import { listDeviceGroups } from "@/lib/api/grouping";
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
  { key: "block_other_browsers", label: "Close other browsers",
    help: "None of this reaches Brave, Opera, Vivaldi, Yandex, Tor, Chromium, Waterfox or LibreWolf. SAVIO closes them as they start and tells the person to use Chrome, Edge or Firefox. To remove one, use the PC's Software tab." },
];

// What a PC's report rows are, where they aren't a browser.
const WHERE: Record<string, string> = {
  Scanner: "Scanner's network block", Windows: "Microsoft 365 on the PC", Usb: "USB drives", UsbEncryption: "USB encryption",
  UsbDevices: "Company drives",
};

// C3: USB drives and phones.
const USB_MODES: { value: BrowserPolicy["usb_mode"]; label: string; help: string }[] = [
  { value: "off", label: "Leave as they are", help: "SAVIO does not change anything about USB drives." },
  { value: "read_only", label: "Read-only", help: "Files can be opened from a drive or phone, never copied onto one." },
  { value: "encrypted_only", label: "Encrypted drives only",
    help: "Copying only onto drives encrypted with BitLocker To Go; phones read-only." },
  { value: "on_request", label: "Read-only, IT can allow writing for a while",
    help: "Read-only, until IT allows writing on one PC for a set time (in the PC list below). It ends by itself." },
  { value: "company_drives", label: "Company drives only",
    help: "Only the drives you approve below work; any other USB drive does not work at all. Phones read-only." },
  { value: "block", label: "Block", help: "No access to USB drives or phones at all." },
];

/** C3b: the approved company drives, and the drives seen on the org's PCs to approve from. */
function CompanyDrives({ form, setForm, canEdit }: {
  form: BrowserPolicy; setForm: (f: BrowserPolicy) => void; canEdit: boolean;
}) {
  const { data: seen } = useQuery({ queryKey: ["drives-seen"], queryFn: getDrivesSeen, enabled: canEdit, retry: false });
  const [names, setNames] = useState<Record<string, string>>({});
  const muted = { color: "var(--text-secondary)" };
  const box = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };
  const approved = new Set(form.usb_approved_drives.map((d) => d.id.toUpperCase()));
  const pending = (seen ?? []).filter((d) => !approved.has(d.id.toUpperCase()));
  return (
    <div className="rounded-lg p-3 space-y-3 text-sm" style={box}>
      <div>
        <div className="font-medium">Company drives ({form.usb_approved_drives.length})</div>
        {!form.usb_approved_drives.length && (
          <p className="text-xs" style={{ color: "#f59e0b" }}>None approved yet: no USB drive will work on these PCs.</p>
        )}
        {form.usb_approved_drives.map((d) => (
          <div key={d.id} className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-medium">{d.name}</span>
            <span className="font-mono truncate max-w-md" style={muted} title={d.id}>{d.id}</span>
            {canEdit && (
              <button className="underline" style={muted}
                onClick={() => setForm({ ...form, usb_approved_drives: form.usb_approved_drives.filter((x) => x.id !== d.id) })}>
                remove
              </button>
            )}
          </div>
        ))}
      </div>
      {canEdit && (
        <div>
          <div className="font-medium">Drives seen on your PCs</div>
          <p className="text-xs" style={muted}>Plug a new company drive into any PC with SAVIO; it shows up here within the hour.</p>
          {pending.map((d) => (
            <div key={d.id} className="flex flex-wrap items-center gap-2 text-xs py-1">
              <span>{d.name}</span>
              <span style={muted}>on {d.pcs.join(", ")}</span>
              {/* Windows made its ID up, so any drive of that model in that port would share it:
                  it cannot be approved on its own (review 3b L2). */}
              {!d.unique_serial ? <span style={{ color: "#f59e0b" }}>no serial number of its own, so it cannot be approved</span> : (
                <>
                  <input placeholder="Name, e.g. Accounts drive 1" maxLength={60} value={names[d.id] ?? ""}
                    onChange={(e) => setNames({ ...names, [d.id]: e.target.value })}
                    className="px-2 py-1 rounded text-xs outline-none" style={box} />
                  <button className="underline" style={{ color: "var(--accent)" }} disabled={!(names[d.id] ?? "").trim()}
                    onClick={() => setForm({ ...form, usb_approved_drives: [...form.usb_approved_drives,
                      { id: d.id, name: (names[d.id] ?? "").trim() }] })}>
                    Approve
                  </button>
                </>
              )}
            </div>
          ))}
          {seen && !pending.length && <p className="text-xs" style={muted}>No other drives seen.</p>}
          <p className="text-xs" style={muted}>Approving or removing takes effect when you save the policy.</p>
        </div>
      )}
    </div>
  );
}
const USB_MINUTES = [[15, "15 minutes"], [30, "30 minutes"], [60, "1 hour"], [240, "4 hours"], [480, "8 hours"]] as const;

/** C3: one PC's USB write window: when it ends, or a way to open one. */
function UsbWindow({ device, canEdit }: { device: DeviceBrowserState; canEdit: boolean }) {
  const qc = useQueryClient();
  const [minutes, setMinutes] = useState(30);
  const [error, setError] = useState<string | null>(null);
  const muted = { color: "var(--text-secondary)" };
  async function run(f: () => Promise<unknown>) {
    setError(null);
    try { await f(); await qc.invalidateQueries({ queryKey: ["browser-policy-devices"] }); }
    catch (e) { setError(apiErrorMessage(e, "Could not change it.")); }
  }
  const open = device.usb_write_until && new Date(device.usb_write_until) > new Date();
  return (
    <div className="mt-1 flex flex-wrap items-center gap-2">
      {open ? (
        <>
          <span style={{ color: "#f59e0b" }}>USB writing allowed until {new Date(device.usb_write_until!).toLocaleTimeString()}</span>
          {canEdit && <button className="underline" style={muted} onClick={() => run(() => closeUsbWindow(device.device_id))}>end now</button>}
        </>
      ) : canEdit ? (
        <>
          <select aria-label="For how long" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}
            className="px-1 py-0.5 rounded text-xs" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            {USB_MINUTES.map(([m, label]) => <option key={m} value={m}>{label}</option>)}
          </select>
          <button className="underline" style={{ color: "var(--accent)" }}
            onClick={() => run(() => openUsbWindow(device.device_id, minutes))}>Allow USB writing</button>
        </>
      ) : <span style={muted}>USB read-only</span>}
      {error && <span style={{ color: "#ef4444" }}>{error}</span>}
    </div>
  );
}

const lines = (s: string) => s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);

const MODES: { value: BrowserPolicy["guard_mode"]; label: string; help: string }[] = [
  { value: "log", label: "Record only", help: "Nothing is stopped. Every organization starts here for 14 days to see what turns up." },
  { value: "warn", label: "Warn", help: "The person is told what was found and can go ahead." },
  { value: "justify", label: "Ask for a reason", help: "To go ahead, the person picks a work reason from a short list. You see which." },
  { value: "redact", label: "Hide the sensitive parts", help: "A paste, a form's text boxes and text files go ahead with numbers replaced, e.g. [PAN]. Word, Excel and PDF files can't be changed, so they get a warning." },
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
  // D1: which policy the form edits: everyone's ("org") or one device group's (its id).
  const { data: groupPolicies } = useQuery({ queryKey: ["group-policies"], queryFn: getGroupPolicies, enabled: !!data });
  const { data: groups } = useQuery({ queryKey: ["device-groups"], queryFn: listDeviceGroups, enabled: !!data && isAdmin });
  const [scope, setScope] = useState("org");
  const [priority, setPriority] = useState(1);
  const groupPolicy = groupPolicies?.find((g) => g.group_id === scope);
  // A group without its own policy yet starts as a copy of everyone's.
  const shown = scope === "org" ? data?.policy : (groupPolicy?.policy ?? data?.policy);
  const [form, setForm] = useState<BrowserPolicy | null>(null);
  const [text, setText] = useState({ blocked: "", allowed: "", google: "", watched: "", keywords: "",
                                     claude: "", chatgpt: "", slack: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!shown) return;
    setForm(shown);
    setText({ blocked: shown.blocked_sites.join("\n"), allowed: shown.allowed_sites.join("\n"),
              google: shown.google_allowed_domains.join("\n"), watched: shown.guard_watched_sites.join("\n"),
              keywords: shown.guard_keywords.join("\n"), claude: shown.claude_org_ids.join("\n"),
              chatgpt: shown.chatgpt_workspace_ids.join("\n"), slack: shown.slack_allowed_ids.join("\n") });
  }, [shown]);

  function pick(next: string) {
    setScope(next); setMsg(null);
    const existing = groupPolicies?.find((g) => g.group_id === next);
    setPriority(existing?.priority ?? Math.max(0, ...(groupPolicies ?? []).map((g) => g.priority)) + 1);
  }

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
      const body = { ...form, blocked_sites: lines(text.blocked), allowed_sites: lines(text.allowed),
                     google_allowed_domains: lines(text.google), guard_watched_sites: lines(text.watched),
                     // Keywords may contain commas ("Q3, final"): one per line only.
                     guard_keywords: text.keywords.split("\n").map((x) => x.trim()).filter(Boolean),
                     claude_org_ids: lines(text.claude), chatgpt_workspace_ids: lines(text.chatgpt),
                     slack_allowed_ids: lines(text.slack) };
      if (scope === "org") {
        const r = await putBrowserPolicy(body);
        qc.setQueryData(["browser-policy"], r);
        setMsg({ ok: true, text: `Saved as version ${r.version}. PCs pick it up within the hour.` });
      } else {
        const r = await putGroupPolicy(scope, priority, body);
        await qc.invalidateQueries({ queryKey: ["group-policies"] });
        qc.invalidateQueries({ queryKey: ["browser-policy-devices"] });
        setMsg({ ok: true, text: `Saved for ${r.group_name} as version ${r.version}. Its PCs pick it up within the hour.` });
      }
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not save the policy.") });
    } finally { setSaving(false); }
  }

  async function removeGroupPolicy() {
    if (scope === "org") return;
    setSaving(true); setMsg(null);
    try {
      await deleteGroupPolicy(scope);
      await qc.invalidateQueries({ queryKey: ["group-policies"] });
      qc.invalidateQueries({ queryKey: ["browser-policy-devices"] });
      pick("org");
      setMsg({ ok: true, text: "Removed. That group's PCs go back to the policy for everyone within the hour." });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not remove the group's policy.") });
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

      {data && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-xs" style={muted}>Policy for</span>
          {[{ id: "org", label: "Everyone" }, ...(groupPolicies ?? []).map((g) => ({ id: g.group_id, label: g.group_name })),
            // The group being given a policy, before its first save.
            ...(scope !== "org" && !groupPolicy ? [{ id: scope, label: `${groups?.find((g) => g.id === scope)?.name ?? "Group"} (new)` }] : []),
          ].map((o) => (
            <button key={o.id} type="button" onClick={() => pick(o.id)} className="px-3 py-1 rounded-full text-xs font-medium"
              style={{ border: "1px solid var(--border)", background: scope === o.id ? "var(--accent)" : "var(--surface)",
                       color: scope === o.id ? "#fff" : "var(--text-primary)" }}>
              {o.label}
            </button>
          ))}
          {isAdmin && !!data.version && (groups ?? []).some((g) => !groupPolicies?.some((p) => p.group_id === g.id)) && (
            <select value="" onChange={(e) => e.target.value && pick(e.target.value)} aria-label="Add a policy for a group"
              className="px-2 py-1 rounded-lg text-xs outline-none" style={input}>
              <option value="">+ A policy for a group…</option>
              {(groups ?? []).filter((g) => !groupPolicies?.some((p) => p.group_id === g.id)).map((g) => (
                <option key={g.id} value={g.id}>{g.name} ({g.device_count} PCs)</option>
              ))}
            </select>
          )}
          {scope !== "org" && (
            <span className="text-xs basis-full" style={muted}>
              {groupPolicy ? "" : "New: starts as a copy of the policy for everyone. "}
              PCs in this group get this policy instead of the one for everyone. A PC in more than one such group gets
              the one with the lowest priority number.
            </span>
          )}
        </div>
      )}

      {form && (
        <div className="rounded-xl p-5 space-y-4" style={panel}>
          {SWITCHES.map((s) => (
            <label key={s.key} className="flex items-start gap-3 text-sm" style={{ color: "var(--text-primary)" }}>
              <input type="checkbox" className="mt-1" disabled={!isAdmin} checked={!!form[s.key]}
                onChange={(e) => setForm({ ...form, [s.key]: e.target.checked })} />
              <span>{s.label}<span className="block text-xs" style={muted}>{s.help}</span></span>
            </label>
          ))}
          <label className="block text-sm space-y-1" style={{ color: "var(--text-primary)" }}>
            <span>USB drives and phones</span>
            <select disabled={!isAdmin} value={form.usb_mode}
              onChange={(e) => setForm({ ...form, usb_mode: e.target.value as BrowserPolicy["usb_mode"] })}
              className="block w-full md:w-96 px-3 py-2 rounded-lg text-sm outline-none" style={input}>
              {USB_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <span className="block text-xs" style={muted}>
              {USB_MODES.find((m) => m.value === form.usb_mode)?.help} Uses Windows&apos; own settings. A change reaches each PC
              within the hour, and drives already plugged in are reconnected then; one with files open keeps the old rule until
              it is unplugged. If Group Policy already sets these on a PC, SAVIO leaves them alone and shows a conflict.
            </span>
          </label>
          {form.usb_mode === "company_drives" && <CompanyDrives form={form} setForm={setForm} canEdit={isAdmin} />}
          <label className="flex items-start gap-3 text-sm" style={{ color: "var(--text-primary)" }}>
            <input type="checkbox" className="mt-1" disabled={!isAdmin} checked={form.usb_observe}
              onChange={(e) => setForm({ ...form, usb_observe: e.target.checked })} />
            <span>Record what is copied onto USB drives
              <span className="block text-xs" style={muted}>
                Each copy is checked on the PC once it finishes. You see what kind of data went onto a drive and who was signed
                in, never the files&apos; names or contents; it joins that person&apos;s case. It does not stop the copy: the setting
                above does that.
              </span>
            </span>
          </label>
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
          <label className="flex items-start gap-3 text-sm" style={{ color: "var(--text-primary)" }}>
            <input type="checkbox" className="mt-1" disabled={!isAdmin} checked={form.guard_read_pdfs}
              onChange={(e) => setForm({ ...form, guard_read_pdfs: e.target.checked })} />
            <span>Read the text inside PDFs
              <span className="block text-xs" style={muted}>
                PDFs being uploaded, and PDFs in the weekly check above, are read on the PC like Word and Excel files.
                Off: an uploaded PDF counts as &ldquo;could not check&rdquo; and the weekly check skips PDFs.
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
          <div className="pt-4 space-y-3" style={{ borderTop: "1px solid var(--border)" }}>
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Company accounts only</h2>
              <p className="text-xs" style={muted}>
                People can sign in to these services only with your organization&apos;s own accounts, not a personal one.
                Each service enforces it itself, on plans that support it; the SAVIO extension sends it your IDs, so it
                needs the extension (Microsoft 365 on the PC excepted, below). Leave a service empty to leave it alone.
              </p>
            </div>
            <label className="flex items-start gap-3 text-sm" style={{ color: "var(--text-primary)" }}>
              <input type="checkbox" className="mt-1" disabled={!isAdmin} checked={form.microsoft_on_windows}
                onChange={(e) => setForm({ ...form, microsoft_on_windows: e.target.checked })} />
              <span>Microsoft 365 on the PC too: Outlook, Teams, Word and the other Office apps, and Edge
                <span className="block text-xs" style={muted}>
                  Uses Windows&apos; own tenant restrictions with the two Microsoft IDs below; no extension needed. Windows 11, or
                  Windows 10 2004 or later with updates. If Intune or Group Policy already sets this on a PC, SAVIO leaves it
                  alone and shows a conflict. A wrong ID stops Office signing in on every PC that gets it, so try it on one
                  group first.
                </span>
              </span>
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {([["microsoft_tenant_id", "Microsoft 365: tenant ID",
                  "Both IDs: Entra → External Identities → Cross-tenant access settings → Default settings → Tenant restrictions"],
                 ["microsoft_policy_id", "Microsoft 365: tenant restrictions policy ID",
                  "That page's Policy ID. Who may sign in to what is set there, in Microsoft Entra."],
                 ["slack_requester_id", "Slack: your own workspace or org ID", "Like T0123ABCD or E0123ABCD, from Slack support"]] as const).map(([k, label, help]) => (
                <label key={k} className="text-xs space-y-1" style={muted}>
                  <span className="font-medium">{label}</span>
                  <input disabled={!isAdmin} value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value.trim() || null })}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none font-mono" style={input} />
                  <span className="block">{help}</span>
                </label>
              ))}
              {([["slack", "Slack: allowed workspace and org IDs", "One per line, your own included."],
                 ["claude", "Claude: allowed organization IDs", "One per line, from Claude's admin settings."],
                 ["chatgpt", "ChatGPT: allowed workspace IDs", "One per line, from the ChatGPT Enterprise admin settings."]] as const).map(([k, label, help]) => (
                <label key={k} className="text-xs space-y-1" style={muted}>
                  <span className="font-medium">{label}</span>
                  <textarea rows={3} disabled={!isAdmin} value={text[k]} onChange={(e) => setText({ ...text, [k]: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none font-mono" style={input} />
                  <span className="block">{help}</span>
                </label>
              ))}
            </div>
          </div>
          {msg && <p className="text-xs" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs" style={muted}>
              {scope === "org"
                ? <>Version {data?.version ?? 0}{data?.updated_at ? ` · saved ${new Date(data.updated_at).toLocaleString()}` : ""}</>
                : groupPolicy ? <>Version {groupPolicy.version} · saved {new Date(groupPolicy.updated_at).toLocaleString()}</> : "Not saved yet"}
              {!isAdmin && " · only an admin can change it"}
            </span>
            {isAdmin && (
              <div className="flex flex-wrap items-center gap-2">
                {scope !== "org" && (
                  <>
                    <label className="text-xs flex items-center gap-1" style={muted}>
                      Priority
                      <input type="number" min={1} max={1000} value={priority}
                        onChange={(e) => setPriority(Math.min(1000, Math.max(1, Number(e.target.value) || 1)))}
                        className="w-16 px-2 py-1 rounded-lg text-sm outline-none" style={input} />
                    </label>
                    {groupPolicy && (
                      <button type="button" onClick={removeGroupPolicy} disabled={saving}
                        className="px-3 py-2 rounded-lg text-xs font-medium disabled:opacity-50"
                        style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                        Remove this group&apos;s policy
                      </button>
                    )}
                  </>
                )}
                <button onClick={save} disabled={saving} className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                  style={{ background: "var(--accent)" }}>{saving ? "Saving…" : "Save policy"}</button>
              </div>
            )}
          </div>
        </div>
      )}

      {data && (
        <div className="rounded-xl overflow-x-auto" style={panel}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["PC", "Policy", "Version", "Status", "Reported"].map((h) => (
                  <th key={h} className="text-left px-4 py-2 text-xs uppercase" style={muted}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(devices ?? []).map((d) => {
                const errors = d.results.filter((r) => r.error);
                const conflicts = d.results.flatMap((r) => r.conflicts.map((c) => `${WHERE[r.browser] ?? r.browser}: ${c}`));
                const behind = d.version !== d.policy_version;   // its own policy's, which may be a group's
                return (
                  <tr key={d.device_id} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    <td className="px-4 py-2 font-medium">{d.hostname}</td>
                    <td className="px-4 py-2 text-xs" style={muted}>{d.policy_group ?? "Everyone"}</td>
                    <td className="px-4 py-2" style={{ color: behind ? "#f59e0b" : muted.color }}>{d.version}{behind ? " (older)" : ""}</td>
                    <td className="px-4 py-2 text-xs">
                      {errors.map((r) => (
                        <div key={r.browser} style={{ color: "#ef4444" }}>
                          {WHERE[r.browser] ?? r.browser}: {r.error}
                        </div>
                      ))}
                      {conflicts.length > 0 && <div style={{ color: "#f59e0b" }}>Set elsewhere, left alone: {conflicts.join(", ")}</div>}
                      {!errors.length && !conflicts.length && <span style={{ color: "#10b981" }}>Applied</span>}
                      {d.other_browsers.length > 0 && (
                        <div>
                          <Link href={`/devices/${d.device_id}`} style={{ color: "#f59e0b" }}>
                            Other browsers installed: {d.other_browsers.join(", ")}
                          </Link>
                        </div>
                      )}
                      {d.usb_mode === "on_request" && <UsbWindow device={d} canEdit={isAdmin} />}
                    </td>
                    <td className="px-4 py-2 text-xs" style={muted}>{new Date(d.reported_at).toLocaleString()}</td>
                  </tr>
                );
              })}
              {devices && !devices.length && (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-sm" style={muted}>
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
