"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Plus, ShieldAlert } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  closeUsbWindow, deleteNamedPolicy, endGuardPilot, getBrowserPolicy, getBrowserPolicyDevices, getNamedPolicies,
  openUsbWindow, putBrowserPolicy, saveNamedPolicy, type BrowserPolicy, type DeviceBrowserState, type NamedPolicy,
} from "@/lib/api/guard";
import { listUserTeams } from "@/lib/api/grouping";
import { listAllUsers } from "@/lib/api/users";
import { isUpgradeRequired } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";
import { PolicyEditor, USB_MODES, changesOf, draftOf, exceptionOf, policyOf, type Draft } from "./policy-editor";
import { Chip, button, field, muted, tint } from "./policy-ui";

// AI Guard → Browser policies. A default policy for everyone, plus named policies for chosen
// teams and people: a PC gets the policy of the person it is assigned to in Assets, so it follows
// them to another PC. The agent sets only what is listed and never overwrites a browser policy
// the org already sets another way (a GPO); those show under PCs as conflicts.

// What a PC's report rows are, where they aren't a browser.
const WHERE: Record<string, string> = {
  Scanner: "Scanner's network block", Windows: "Microsoft 365 on the PC", Usb: "USB drives", UsbEncryption: "USB encryption",
  UsbDevices: "Company drives",
};

const MODE_LABEL: Record<BrowserPolicy["guard_mode"], string> = {
  log: "Record only", warn: "Warn", justify: "Ask for a reason", redact: "Hide sensitive parts", approve: "IT approval", block: "Block",
};

const USB_MINUTES = [[15, "15 minutes"], [30, "30 minutes"], [60, "1 hour"], [240, "4 hours"], [480, "8 hours"]] as const;

/** C3: one PC's USB write window: when it ends, or a way to open one. */
function UsbWindow({ device, canEdit }: { device: DeviceBrowserState; canEdit: boolean }) {
  const qc = useQueryClient();
  const [minutes, setMinutes] = useState(30);
  const [error, setError] = useState<string | null>(null);
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
          <span style={{ color: "var(--health-warn)" }}>USB writing allowed until {new Date(device.usb_write_until!).toLocaleTimeString()}</span>
          {canEdit && <button className="underline" style={muted} onClick={() => run(() => closeUsbWindow(device.device_id))}>end now</button>}
        </>
      ) : canEdit ? (
        <>
          <select aria-label="For how long" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}
            className="px-1 py-0.5 rounded text-xs" style={field}>
            {USB_MINUTES.map(([m, label]) => <option key={m} value={m}>{label}</option>)}
          </select>
          <button className="underline" style={{ color: "var(--accent)" }}
            onClick={() => run(() => openUsbWindow(device.device_id, minutes))}>Allow USB writing</button>
        </>
      ) : <span style={muted}>USB read-only</span>}
      {error && <span style={{ color: "var(--health-bad)" }}>{error}</span>}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="rounded-xl px-4 py-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="text-xs" style={muted}>{label}</div>
      <div className="text-xl font-semibold mt-0.5" style={{ color: tone ?? "var(--text-primary)" }}>{value}</div>
    </div>
  );
}

const th = "text-left px-4 py-2.5 text-xs font-medium uppercase tracking-wide";

export default function GuardPage() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";
  const { data, error, isLoading } = useQuery({ queryKey: ["browser-policy"], queryFn: getBrowserPolicy, retry: false });
  const { data: named } = useQuery({ queryKey: ["named-policies"], queryFn: getNamedPolicies, enabled: !!data });
  const { data: devices } = useQuery({ queryKey: ["browser-policy-devices"], queryFn: getBrowserPolicyDevices,
    enabled: !!data, refetchInterval: 60_000 });
  const { data: teams } = useQuery({ queryKey: ["user-teams"], queryFn: listUserTeams, enabled: !!data });
  const { data: users } = useQuery({ queryKey: ["all-users"], queryFn: listAllUsers, enabled: !!data });
  const [tab, setTab] = useState<"policies" | "pcs">("policies");
  // Which policy is open: "default", "new", or a named policy's id. null: the list.
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [menu, setMenu] = useState(false);   // the "New" button's choice of kind

  if (isUpgradeRequired(error)) {
    return (
      <div className="rounded-xl p-8 text-center max-w-lg mx-auto" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <ShieldAlert size={22} className="mx-auto mb-3" style={{ color: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>AI Guard is an add-on</h2>
        <p className="text-sm mt-2" style={muted}>
          Lock down your employees&apos; browsers: no private windows, no unpacked extensions, blocked sites, and
          Google sign-in for your company account only. Ask your SAVIO contact to switch it on for your organization.
        </p>
      </div>
    );
  }

  const policies = named ?? [];
  const current = policies.find((p) => p.id === editing);
  const teamName = new Map((teams ?? []).map((t) => [t.id, t.name]));
  const userName = new Map((users ?? []).map((u) => [u.id, u.full_name]));
  const pcsOn = (name: string | null, exception = false) =>
    (devices ?? []).filter((d) => (exception ? d.exceptions.includes(name ?? "") : d.policy_name === name)).length;
  const withIssues = (devices ?? []).filter((d) => d.results.some((r) => r.error || r.conflicts.length)).length;

  // E8: the first 14 days only record. The backend refuses any other mode until then.
  const pilotUntil = data?.pilot_until ? new Date(data.pilot_until) : null;
  const pilotDays = pilotUntil ? Math.max(1, Math.ceil((pilotUntil.getTime() - Date.now()) / 86_400_000)) : 0;

  function open(target: "default" | "new" | "new-exception" | NamedPolicy) {
    if (!data) return;
    setMsg(null); setMenu(false);
    if (target === "default") { setEditing("default"); setDraft(draftOf(data.policy)); return; }
    if (target === "new" || target === "new-exception") {
      // A new full policy starts as a copy of the default one; a new exception changes nothing
      // yet. Either is ranked after the others.
      const next = Math.min(1000, Math.max(0, ...policies.map((p) => p.priority)) + 10);
      setEditing("new");
      setDraft(draftOf(data.policy, { name: "", priority: next, team_ids: [], user_ids: [] },
                       target === "new-exception" ? {} : null));
      return;
    }
    setEditing(target.id); setDraft(draftOf(target.policy ?? data.policy, target, target.exception));
  }

  async function save() {
    if (!draft || !editing) return;
    setSaving(true); setMsg(null);
    try {
      if (editing === "default") {
        const r = await putBrowserPolicy(policyOf(draft));
        qc.setQueryData(["browser-policy"], r);
        setMsg({ ok: true, text: `Saved as version ${r.version}. PCs pick it up within the hour.` });
      } else {
        const exception = draft.kind === "exception";
        const r = await saveNamedPolicy(editing === "new" ? null : editing, {
          name: draft.name.trim(), priority: draft.priority, team_ids: draft.team_ids, user_ids: draft.user_ids,
          kind: draft.kind, policy: exception ? null : policyOf(draft), exception: exception ? exceptionOf(draft) : null });
        await qc.invalidateQueries({ queryKey: ["named-policies"] });
        qc.invalidateQueries({ queryKey: ["browser-policy-devices"] });
        setEditing(r.id);
        setMsg({ ok: true, text: `Saved as version ${r.version}. Its people's PCs pick it up within the hour.` });
      }
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not save the policy.") });
    } finally { setSaving(false); }
  }

  async function remove() {
    if (!current || !window.confirm(`Delete “${current.name}”? Its people's PCs go back to the default policy.`)) return;
    setSaving(true); setMsg(null);
    try {
      await deleteNamedPolicy(current.id);
      await qc.invalidateQueries({ queryKey: ["named-policies"] });
      qc.invalidateQueries({ queryKey: ["browser-policy-devices"] });
      setEditing(null);
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not delete the policy.") });
    } finally { setSaving(false); }
  }

  async function endPilot() {
    setSaving(true); setMsg(null);
    try {
      qc.setQueryData(["browser-policy"], await endGuardPilot());
      qc.invalidateQueries({ queryKey: ["guard-suggestions"] });
      setMsg({ ok: true, text: "Pilot ended. Pick a mode in each policy and save; until then PCs keep recording only." });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not end the pilot.") });
    } finally { setSaving(false); }
  }

  if (editing && draft && data) {
    return (
      <div className="max-w-6xl">
        <PolicyEditor draft={draft} setDraft={setDraft} isDefault={editing === "default"} isNew={editing === "new"}
          canEdit={isAdmin} pilotUntil={pilotUntil} saving={saving} msg={msg}
          version={editing === "default" ? data.version || null : current?.version ?? null}
          savedAt={editing === "default" ? data.updated_at : current?.updated_at ?? null}
          onBack={() => { setEditing(null); setMsg(null); }} onSave={save} onDelete={remove} />
      </div>
    );
  }

  const assigned = (p: NamedPolicy) => [
    ...p.team_ids.map((id) => ({ id, label: teamName.get(id) ?? "Removed team", team: true })),
    ...p.user_ids.map((id) => ({ id, label: userName.get(id) ?? "Removed user", team: false })),
  ];

  return (
    <div className="space-y-5 max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg" style={{ background: tint("var(--accent)"), color: "var(--accent)" }}><ShieldAlert size={18} /></div>
          <div>
            <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Browser policies</h1>
            <p className="text-xs max-w-2xl" style={muted}>
              What SAVIO enforces in Chrome, Edge and Firefox, and on USB drives. Each PC gets the policy of the person it is
              assigned to in Assets, so a policy follows people to a new PC; anyone else gets the default.
            </p>
          </div>
        </div>
        {isAdmin && data && tab === "policies" && (
          <div className="relative">
            <button type="button" onClick={() => setMenu(!menu)} disabled={!data.version} aria-expanded={menu}
              title={data.version ? undefined : "Save the default policy first"}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50" style={button.primary}>
              <Plus size={15} /> New policy <ChevronDown size={14} />
            </button>
            {menu && (
              <div className="absolute right-0 mt-2 w-80 rounded-xl p-1 z-20 shadow-lg"
                style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                {([["new", "Full policy", "A whole package of settings for chosen teams or people, instead of the default."],
                   ["new-exception", "Exception", "Changes only a few things (USB, some sites, personal Gmail) for chosen people; everything else stays as their full policy has it."]] as const).map(([k, title, help]) => (
                  <button key={k} type="button" onClick={() => open(k)} className="w-full text-left rounded-lg px-3 py-2 hover:opacity-80"
                    style={{ color: "var(--text-primary)" }}>
                    <div className="text-sm font-medium">{title}</div>
                    <div className="text-xs" style={muted}>{help}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && !isUpgradeRequired(error) && <p className="text-sm" style={{ color: "var(--health-bad)" }}>{apiErrorMessage(error, "Could not load the policy.")}</p>}
      {msg && <p className="text-sm" style={{ color: msg.ok ? "var(--health-good)" : "var(--health-bad)" }}>{msg.text}</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Stat label="Policies" value={policies.length + 1} />
            <Stat label="PCs reporting" value={devices?.length ?? "—"} />
            <Stat label="PCs with conflicts or errors" value={withIssues} tone={withIssues ? "var(--health-warn)" : undefined} />
            <Stat label="Data protection" value={pilotUntil ? `Pilot · ${pilotDays}d left` : "Active"}
              tone={pilotUntil ? "var(--accent)" : "var(--health-good)"} />
          </div>

          {pilotUntil && (
            <div className="flex flex-wrap items-center gap-3 rounded-xl px-4 py-3 text-sm"
              style={{ background: tint("var(--accent)", 8), border: "1px solid var(--border)", color: "var(--text-primary)" }}>
              <span className="flex-1 min-w-[16rem]">
                <span className="font-medium">Pilot: record only until {pilotUntil.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}.</span>
                <span className="block text-xs" style={muted}>
                  {data.version ? `${pilotDays} ${pilotDays === 1 ? "day" : "days"} left. ` : "The 14 days start when you first save. "}
                  Nobody is interrupted while you see what turns up. Afterwards nothing changes on its own: you pick the mode.
                </span>
              </span>
              {isAdmin && !!data.version && (
                <button type="button" onClick={endPilot} disabled={saving} className="px-3 py-1.5 rounded-lg text-xs font-medium" style={button.plain}>
                  End the pilot now
                </button>
              )}
            </div>
          )}

          <div className="flex gap-1 border-b" style={{ borderColor: "var(--border)" }}>
            {([["policies", "Policies"], ["pcs", `PCs${devices ? ` (${devices.length})` : ""}`]] as const).map(([k, label]) => (
              <button key={k} type="button" onClick={() => setTab(k)} className="px-4 py-2 text-sm -mb-px"
                style={{ borderBottom: `2px solid ${tab === k ? "var(--accent)" : "transparent"}`,
                         color: tab === k ? "var(--accent)" : "var(--text-secondary)", fontWeight: tab === k ? 600 : 400 }}>
                {label}
              </button>
            ))}
          </div>

          {tab === "policies" && (
            <div className="rounded-xl overflow-x-auto" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)", ...muted }}>
                    {["Priority", "Policy", "Type", "Assigned to", "Sensitive data", "USB", "PCs", ""].map((h) => <th key={h} className={th}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {[...policies.map((p) => ({ p, isDefault: false })), { p: null, isDefault: true }].map(({ p, isDefault }) => {
                    const policy = isDefault ? data.policy : p!.policy;
                    const who = p ? assigned(p) : [];
                    const exception = p?.kind === "exception";
                    return (
                      <tr key={p?.id ?? "default"} onClick={() => open(p ?? "default")} className="cursor-pointer hover:opacity-90"
                        style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)",
                                 background: isDefault ? tint("var(--text-secondary)", 4) : undefined }}>
                        <td className="px-4 py-3 text-xs" style={muted}>{isDefault ? "Last" : p!.priority}</td>
                        <td className="px-4 py-3">
                          <div className="font-medium">{isDefault ? "Default policy" : p!.name}</div>
                          <div className="text-xs" style={muted}>
                            {isDefault ? (data.version ? `Version ${data.version}` : "Not saved yet") : `Version ${p!.version}`}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          {isDefault ? <Chip>Default</Chip> : exception ? <Chip tone="warn">Exception</Chip> : <Chip>Full policy</Chip>}
                        </td>
                        <td className="px-4 py-3">
                          {isDefault ? <span className="text-xs" style={muted}>Everyone not covered above</span> : (
                            <div className="flex flex-wrap gap-1 max-w-sm">
                              {who.slice(0, 4).map((w) => <Chip key={w.id} tone={w.team ? "accent" : "neutral"}>{w.label}</Chip>)}
                              {who.length > 4 && <Chip>+{who.length - 4}</Chip>}
                              {!who.length && <Chip tone="warn">Nobody yet</Chip>}
                            </div>
                          )}
                        </td>
                        {exception || !policy ? (
                          <td colSpan={2} className="px-4 py-3">
                            <div className="flex flex-wrap gap-1">
                              <span className="text-xs mr-1" style={muted}>Changes</span>
                              {changesOf(p!.exception ?? {}).map((c) => <Chip key={c} tone="accent">{c}</Chip>)}
                            </div>
                          </td>
                        ) : (
                          <>
                            <td className="px-4 py-3 text-xs">{MODE_LABEL[policy.guard_mode]}</td>
                            <td className="px-4 py-3 text-xs">{USB_MODES.find((m) => m.value === policy.usb_mode)?.label}</td>
                          </>
                        )}
                        <td className="px-4 py-3 text-xs">{pcsOn(isDefault ? null : p!.name, exception)}</td>
                        <td className="px-4 py-3 text-right" style={muted}><ChevronRight size={16} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {!data.version && (
                <p className="px-4 py-3 text-xs" style={muted}>Start with the default policy: open it, choose the settings and save.</p>
              )}
            </div>
          )}

          {tab === "pcs" && (
            <div className="rounded-xl overflow-x-auto" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)", ...muted }}>
                    {["PC", "Assigned to", "Policy", "Version", "Status", "Reported"].map((h) => <th key={h} className={th}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {(devices ?? []).map((d) => {
                    const errors = d.results.filter((r) => r.error);
                    const conflicts = d.results.flatMap((r) => r.conflicts.map((c) => `${WHERE[r.browser] ?? r.browser}: ${c}`));
                    const behind = d.version !== d.policy_version;   // its own policy's, which may be a named one's
                    return (
                      <tr key={d.device_id} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                        <td className="px-4 py-3 font-medium"><Link href={`/devices/${d.device_id}`}>{d.hostname}</Link></td>
                        <td className="px-4 py-3 text-xs">{d.assigned_to ?? <span style={muted}>Nobody</span>}</td>
                        <td className="px-4 py-3 text-xs">
                          <div className="flex flex-wrap gap-1">
                            {d.policy_name ? <Chip tone="accent">{d.policy_name}</Chip> : <Chip>Default</Chip>}
                            {d.exceptions.map((e) => <Chip key={e} tone="warn">+ {e}</Chip>)}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs">
                          {behind ? <Chip tone="warn">{d.version} · updating</Chip> : <span style={muted}>{d.version}</span>}
                        </td>
                        <td className="px-4 py-3 text-xs space-y-1">
                          {errors.map((r) => <div key={r.browser} style={{ color: "var(--health-bad)" }}>{WHERE[r.browser] ?? r.browser}: {r.error}</div>)}
                          {conflicts.length > 0 && <div style={{ color: "var(--health-warn)" }}>Set elsewhere, left alone: {conflicts.join(", ")}</div>}
                          {!errors.length && !conflicts.length && <Chip tone="good">Applied</Chip>}
                          {d.other_browsers.length > 0 && (
                            <div><Link href={`/devices/${d.device_id}`} style={{ color: "var(--health-warn)" }}>
                              Other browsers installed: {d.other_browsers.join(", ")}
                            </Link></div>
                          )}
                          {d.usb_mode === "on_request" && <UsbWindow device={d} canEdit={isAdmin} />}
                        </td>
                        <td className="px-4 py-3 text-xs" style={muted}>{new Date(d.reported_at).toLocaleString()}</td>
                      </tr>
                    );
                  })}
                  {devices && !devices.length && (
                    <tr><td colSpan={6} className="px-4 py-8 text-center text-sm" style={muted}>
                      No PC has reported yet. Agents with AI Guard support report within the hour.
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
