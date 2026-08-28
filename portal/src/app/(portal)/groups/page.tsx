"use client";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, Plus, Pencil, Trash2, X, Search, Users as UsersIcon, Monitor, Zap } from "lucide-react";
import {
  listDeviceGroups, createDeviceGroup, updateDeviceGroup, deleteDeviceGroup,
  getGroupDevices, setGroupDevices,
  listUserTeams, createUserTeam, updateUserTeam, deleteUserTeam,
  getTeamUsers, setTeamUsers, runGroupAction,
  type DeviceGroup, type UserTeam, type GroupActionResult,
} from "@/lib/api/grouping";
import { listDevicesPaged } from "@/lib/api/devices";
import { listAllUsers } from "@/lib/api/users";
import { getMe } from "@/lib/api/auth";
import { ScrollPanel, pageShell } from "@/components/scroll-panel";
import { apiErrorMessage } from "@/lib/utils";

// A small fixed palette rather than a colour picker. Groups are read as chips in a dense
// table, so what matters is that any two are TELLABLE APART at a glance — a free picker
// reliably produces three shades of blue that aren't.
const COLOURS = [
  "#9a2fbb", "#2563eb", "#0891b2", "#059669",
  "#ca8a04", "#ea580c", "#dc2626", "#64748b",
];

type Kind = "groups" | "teams";

/**
 * What can be pushed to a whole group.
 *
 * `tier` drives the grouping and the colour, and mirrors the backend registry — but it is
 * a LABEL, not the rule. The server checks the tier per device, so a technician who reaches
 * an admin-only action here gets refusals counted back, not a fleet of sign-outs.
 *
 * `scope` says what the push fans out over. A session action goes to each signed-in person,
 * so on a terminal server with thirty users it is thirty actions — worth showing plainly
 * before someone aims one at a group of servers.
 *
 * `destructive` is narrower than "admin-only" on purpose. Blocking USB is admin-only and
 * completely reversible; signing everyone out destroys unsaved work and cannot be undone.
 * Only the second kind demands the group name typed back.
 */
type BulkTier = "automatic" | "approval" | "admin";
type BulkAction = {
  id: string;
  label: string;
  tier: BulkTier;
  scope: "devices" | "sessions";
  destructive?: boolean;
  params?: Record<string, string>;
  /** Free-text parameter the operator must supply, if any. */
  field?: { key: "app_name" | "message"; label: string; placeholder: string };
  blurb: string;
};

const BULK_ACTIONS: BulkAction[] = [
  { id: "flush_dns", label: "Flush DNS cache", tier: "automatic", scope: "devices",
    blurb: "Clears the resolver cache on every device in the group." },
  { id: "restart_explorer", label: "Restart Windows Explorer", tier: "automatic", scope: "devices",
    blurb: "Restarts the shell. Open windows close; saved work is untouched." },
  { id: "clear_temp", label: "Clear temporary files", tier: "automatic", scope: "devices",
    blurb: "Removes each signed-in user's temp files to reclaim disk." },
  { id: "clear_system_temp", label: "Deep clean system temp", tier: "automatic", scope: "devices",
    blurb: "Machine-wide caches, Prefetch and the Windows Update download cache." },
  { id: "clear_browser_cache", label: "Clear browser cache", tier: "automatic", scope: "devices",
    blurb: "Chrome, Edge and Firefox HTTP caches. Leaves history and passwords alone." },
  { id: "restart_network_adapter", label: "Restart network adapter", tier: "automatic", scope: "devices",
    blurb: "Briefly drops connectivity on each device, including the agent's own." },
  { id: "restart_service", label: "Restart Print Spooler", tier: "automatic", scope: "devices",
    params: { service_name: "Spooler" }, blurb: "Restarts the spooler across the group." },

  { id: "windows_update_install", label: "Install pending Windows updates", tier: "approval", scope: "devices",
    blurb: "Installs everything pending. Never auto-reboots; reports when a restart is needed." },
  { id: "office_repair", label: "Repair Microsoft Office", tier: "approval", scope: "devices",
    blurb: "Opens Office's own repair. Someone at each PC must approve a prompt and click through it." },
  { id: "network_reset", label: "Reset network stack", tier: "approval", scope: "devices",
    blurb: "Winsock and TCP/IP. REQUIRES A REBOOT on every device to take effect." },
  { id: "lock_session", label: "Lock every screen", tier: "approval", scope: "sessions",
    blurb: "Locks each signed-in session. Work stays open; they type their password to return." },
  { id: "message_session", label: "Message everyone", tier: "approval", scope: "sessions",
    field: { key: "message", label: "Message", placeholder: "Saving your work now — these machines reboot in 10 minutes." },
    blurb: "Shows a message box from IT on every signed-in desktop. One-way." },

  { id: "block_usb_storage", label: "Block USB storage", tier: "admin", scope: "devices",
    blurb: "Stops pen drives and portable disks. Reversible; keyboards and mice unaffected." },
  { id: "unblock_usb_storage", label: "Allow USB storage", tier: "admin", scope: "devices",
    blurb: "Reverses the block from the next time a drive is connected." },
  { id: "reset_windows_update_components", label: "Reset Windows Update components", tier: "admin", scope: "devices",
    blurb: "Rebuilds the update caches. Discards in-flight downloads." },
  { id: "uninstall_application", label: "Uninstall an application", tier: "admin", scope: "devices",
    destructive: true,
    field: { key: "app_name", label: "Application name", placeholder: "uTorrent" },
    blurb: "Removes the named application from every device in the group. Cannot be undone from ASTRA." },
  { id: "logoff_session", label: "Sign everyone out", tier: "admin", scope: "sessions",
    destructive: true,
    blurb: "Signs out every session in the group. UNSAVED WORK IS LOST — Windows does not prompt." },
];

const TIER_LABEL: Record<BulkTier, string> = {
  automatic: "Safe and reversible",
  approval: "Needs technician or admin approval",
  admin: "Admin only",
};
const TIER_COLOR: Record<BulkTier, string> = {
  automatic: "#10b981",
  approval: "#f59e0b",
  admin: "#ef4444",
};

export default function GroupsPage() {
  const qc = useQueryClient();
  const [kind, setKind] = useState<Kind>("groups");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isStaff = me?.role === "admin" || me?.role === "technician";
  const isAdmin = me?.role === "admin";

  const { data: groups, isLoading: groupsLoading } = useQuery({
    queryKey: ["device-groups"], queryFn: listDeviceGroups,
  });
  const { data: teams, isLoading: teamsLoading } = useQuery({
    queryKey: ["user-teams"], queryFn: listUserTeams,
  });

  // Editing the group/team itself (name, description, colour). `null` = closed;
  // an object with no id = the create form.
  const [editing, setEditing] = useState<
    { id?: string; name: string; description: string; colour: string } | null
  >(null);
  // Editing MEMBERSHIP. Separate state because it is a different, much larger dialog and
  // conflating the two produced a form that was half about a name and half about 2,000
  // checkboxes.
  const [members, setMembers] = useState<{ id: string; name: string } | null>(null);
  // The group a bulk action is being aimed at. Holds the whole row rather than an id,
  // because the dialog puts the device count in front of the operator three times.
  const [acting, setActing] = useState<DeviceGroup | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!editing || !editing.name.trim()) return;
    setBusy(true); setMsg(null);
    const body = {
      name: editing.name.trim(),
      description: editing.description.trim() || null,
      colour: editing.colour || null,
    };
    try {
      if (kind === "groups") {
        if (editing.id) await updateDeviceGroup(editing.id, body);
        else await createDeviceGroup(body);
        await qc.invalidateQueries({ queryKey: ["device-groups"] });
      } else {
        if (editing.id) await updateUserTeam(editing.id, body);
        else await createUserTeam(body);
        await qc.invalidateQueries({ queryKey: ["user-teams"] });
      }
      setEditing(null);
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Couldn't save that.") });
    } finally { setBusy(false); }
  }

  async function remove(id: string, name: string) {
    const what = kind === "groups" ? "device group" : "team";
    const whom = kind === "groups" ? "The devices themselves are untouched." : "The users themselves are untouched.";
    if (!confirm(`Delete the ${what} "${name}"?\n\n${whom}`)) return;
    setBusy(true); setMsg(null);
    try {
      if (kind === "groups") {
        await deleteDeviceGroup(id);
        await qc.invalidateQueries({ queryKey: ["device-groups"] });
      } else {
        await deleteUserTeam(id);
        await qc.invalidateQueries({ queryKey: ["user-teams"] });
      }
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Couldn't delete that.") });
    } finally { setBusy(false); }
  }

  const rows: (DeviceGroup | UserTeam)[] = (kind === "groups" ? groups : teams) ?? [];
  const loading = kind === "groups" ? groupsLoading : teamsLoading;

  return (
    <div className={pageShell}>
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Boxes size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Groups &amp; Teams</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Device groups slice the fleet; teams group the people who look after it
          </p>
        </div>
      </div>

      {msg && (
        <div className="rounded-lg px-3 py-2 text-sm" style={{
          background: msg.ok ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)",
          border: `1px solid ${msg.ok ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}`,
          color: msg.ok ? "#10b981" : "#ef4444",
        }}>{msg.text}</div>
      )}

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-1">
          {([["groups", "Device groups", Monitor], ["teams", "Teams", UsersIcon]] as const).map(
            ([key, label, Icon]) => {
              const on = kind === key;
              return (
                <button key={key} onClick={() => setKind(key)}
                  className="px-3 py-2 rounded-lg text-sm font-medium inline-flex items-center gap-1.5"
                  style={{
                    background: on ? "rgba(154,47,187,0.12)" : "var(--surface)",
                    border: "1px solid var(--border)",
                    color: on ? "var(--accent)" : "var(--text-secondary)",
                  }}>
                  <Icon size={15} /> {label}
                </button>
              );
            },
          )}
        </div>
        {isStaff && (
          <button
            onClick={() => setEditing({ name: "", description: "", colour: COLOURS[0] })}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
            style={{ background: "var(--accent)" }}>
            <Plus size={15} /> New {kind === "groups" ? "group" : "team"}
          </button>
        )}
      </div>

      <ScrollPanel>
        <div className="p-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {loading && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading…</p>}
          {!loading && rows.length === 0 && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              {kind === "groups"
                ? "No device groups yet. A group is an overlapping label — “Finance laptops”, “HQ servers” — that you can filter Sessions and Devices by, and later push a fix to in one go."
                : "No teams yet. A team says who works together. It is not a permission: what each person may do still comes from their role."}
            </p>
          )}
          {rows.map((row) => {
            const count = "device_count" in row ? row.device_count : row.member_count;
            return (
              <div key={row.id} className="rounded-xl p-4 flex flex-col gap-2"
                style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ background: row.colour ?? "var(--text-secondary)" }} />
                    <span className="font-semibold truncate" style={{ color: "var(--text-primary)" }}>{row.name}</span>
                  </div>
                  {isStaff && (
                    <div className="flex items-center gap-1 shrink-0">
                      <button title="Edit" onClick={() => setEditing({
                        id: row.id, name: row.name,
                        description: row.description ?? "", colour: row.colour ?? COLOURS[0],
                      })} style={{ color: "var(--text-secondary)" }}><Pencil size={14} /></button>
                      <button title="Delete" onClick={() => remove(row.id, row.name)} disabled={busy}
                        style={{ color: "#ef4444" }}><Trash2 size={14} /></button>
                    </div>
                  )}
                </div>
                {row.description && (
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{row.description}</p>
                )}
                <div className="flex items-center justify-between gap-2 mt-auto pt-1">
                  <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    {count} {kind === "groups" ? (count === 1 ? "device" : "devices") : (count === 1 ? "member" : "members")}
                  </span>
                  {isStaff && (
                    <div className="flex items-center gap-1.5">
                      {/* Device groups only. A team is people, and a list of portal users is
                          not a list of machines — pretending otherwise is how a "bulk action"
                          reaches the wrong endpoints. */}
                      {kind === "groups" && (
                        <button
                          onClick={() => setActing(row as DeviceGroup)}
                          disabled={count === 0}
                          title={count === 0
                            ? "Add devices to this group first."
                            : `Push one action to all ${count} device${count === 1 ? "" : "s"}`}
                          className="text-xs px-2 py-1 rounded-lg inline-flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                          style={{ border: "1px solid var(--border)", color: "var(--accent)" }}>
                          <Zap size={11} /> Run action
                        </button>
                      )}
                      <button onClick={() => setMembers({ id: row.id, name: row.name })}
                        className="text-xs px-2 py-1 rounded-lg"
                        style={{ border: "1px solid var(--border)", color: "var(--accent)" }}>
                        Manage {kind === "groups" ? "devices" : "members"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </ScrollPanel>

      {/* Create / edit */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={() => !busy && setEditing(null)}>
          <div className="w-full max-w-md rounded-xl p-5" onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between gap-3 mb-3">
              <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                {editing.id ? "Edit" : "New"} {kind === "groups" ? "device group" : "team"}
              </h2>
              <button onClick={() => setEditing(null)} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
            </div>

            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>Name</label>
            <input value={editing.name} autoFocus maxLength={120}
              onChange={(e) => setEditing({ ...editing, name: e.target.value })}
              placeholder={kind === "groups" ? "Finance laptops" : "Service desk"}
              className="w-full mt-1 mb-3 px-3 py-2 rounded-lg text-sm outline-none"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />

            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>Description (optional)</label>
            <input value={editing.description} maxLength={500}
              onChange={(e) => setEditing({ ...editing, description: e.target.value })}
              className="w-full mt-1 mb-3 px-3 py-2 rounded-lg text-sm outline-none"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />

            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>Colour</label>
            <div className="flex gap-2 mt-1.5 flex-wrap">
              {COLOURS.map((c) => (
                <button key={c} onClick={() => setEditing({ ...editing, colour: c })}
                  className="w-7 h-7 rounded-full"
                  style={{ background: c, outline: editing.colour === c ? "2px solid var(--text-primary)" : "none", outlineOffset: 2 }} />
              ))}
            </div>

            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setEditing(null)} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
              <button onClick={save} disabled={busy || !editing.name.trim()}
                className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "var(--accent)" }}>{busy ? "Saving…" : "Save"}</button>
            </div>
          </div>
        </div>
      )}

      {acting && (
        <BulkActionDialog
          group={acting}
          isAdmin={isAdmin}
          onClose={() => setActing(null)}
        />
      )}

      {members && (
        <MembershipDialog
          kind={kind}
          id={members.id}
          name={members.name}
          onClose={() => setMembers(null)}
          onSaved={() => {
            void qc.invalidateQueries({ queryKey: [kind === "groups" ? "device-groups" : "user-teams"] });
            setMembers(null);
          }}
          onError={(text) => setMsg({ ok: false, text })}
        />
      )}
    </div>
  );
}

/**
 * Push one action to every device — or every signed-in session — in a group.
 *
 * The whole design problem here is blast radius. A single click can reach hundreds of
 * machines, so the dialog never lets the operator forget how many: the count is in the
 * heading, in the button, and in the confirmation. Destructive actions additionally require
 * the group's name typed back, which is the only friction in the product that scales with
 * consequence rather than with tier.
 */
function BulkActionDialog({
  group, isAdmin, onClose,
}: {
  group: DeviceGroup;
  isAdmin: boolean;
  onClose: () => void;
}) {
  const [picked, setPicked] = useState<BulkAction | null>(null);
  const [value, setValue] = useState("");
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GroupActionResult | null>(null);
  const [error, setError] = useState("");

  // Admin-only actions are hidden from technicians rather than shown disabled. The server
  // refuses them either way; a list of greyed rows reads as "broken" rather than "not yours".
  const available = BULK_ACTIONS.filter((a) => a.tier !== "admin" || isAdmin);
  const needsField = picked?.field;
  const needsTyped = picked?.destructive;
  const ready = picked
    && (!needsField || value.trim().length > 0)
    && (!needsTyped || typed.trim().toLowerCase() === group.name.trim().toLowerCase());

  async function run() {
    if (!picked || !ready) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const body: { action_id: string; params?: Record<string, string>; message?: string } = {
        action_id: picked.id,
      };
      if (picked.params) body.params = { ...picked.params };
      if (picked.field?.key === "message") body.message = value.trim();
      if (picked.field?.key === "app_name") body.params = { ...body.params, app_name: value.trim() };
      setResult(await runGroupAction(group.id, body));
    } catch (e) {
      setError(apiErrorMessage(e, "Couldn't push that to the group."));
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}
      onClick={() => !busy && onClose()}>
      <div className="w-full max-w-lg rounded-xl p-5 flex flex-col max-h-[85vh]" onClick={(e) => e.stopPropagation()}
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              Run an action on {group.name}
            </h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              {group.device_count} device{group.device_count === 1 ? "" : "s"} in this group ·
              tiers are still checked per device
            </p>
          </div>
          <button onClick={onClose} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
        </div>

        {result ? (
          <div className="mt-4 flex flex-col gap-3">
            <div className="rounded-lg p-3" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
              <p className="text-sm font-medium mb-2" style={{ color: "var(--text-primary)" }}>
                Pushed to {result.targets} {result.fanned_over === "sessions" ? "session" : "device"}
                {result.targets === 1 ? "" : "s"}
              </p>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  { n: result.queued, label: "queued", color: "#10b981" },
                  { n: result.already_running, label: "already running", color: "#f59e0b" },
                  { n: result.failed, label: "refused", color: result.failed ? "#ef4444" : "var(--text-secondary)" },
                ].map((c) => (
                  <div key={c.label}>
                    <div className="text-lg font-semibold" style={{ color: c.color }}>{c.n}</div>
                    <div className="text-[11px]" style={{ color: "var(--text-secondary)" }}>{c.label}</div>
                  </div>
                ))}
              </div>
            </div>
            {result.error && (
              <p className="text-xs rounded-lg px-3 py-2" style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }}>
                {result.error}
              </p>
            )}
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Track individual tasks under Self-Healing. Offline devices pick theirs up when
              they next check in.
            </p>
            <div className="flex justify-end">
              <button onClick={onClose} className="px-3 py-2 rounded-lg text-sm font-medium text-white"
                style={{ background: "var(--accent)" }}>Done</button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 min-h-0 overflow-y-auto mt-3 rounded-lg" style={{ border: "1px solid var(--border)" }}>
              {(["automatic", "approval", "admin"] as BulkTier[]).map((tier) => {
                const inTier = available.filter((a) => a.tier === tier);
                if (!inTier.length) return null;
                return (
                  <div key={tier}>
                    <div className="px-3 py-1.5 text-[11px] uppercase tracking-wide font-medium sticky top-0"
                      style={{ background: "var(--bg)", color: TIER_COLOR[tier], borderBottom: "1px solid var(--border)" }}>
                      {TIER_LABEL[tier]}
                    </div>
                    {inTier.map((a) => {
                      const on = picked?.id === a.id && picked?.label === a.label;
                      return (
                        <button key={a.id + a.label}
                          onClick={() => { setPicked(a); setValue(""); setTyped(""); }}
                          className="w-full text-left px-3 py-2 flex flex-col gap-0.5"
                          style={{
                            background: on ? "rgba(154,47,187,0.1)" : "transparent",
                            borderBottom: "1px solid var(--border)",
                          }}>
                          <span className="text-sm font-medium flex items-center gap-1.5"
                            style={{ color: on ? "var(--accent)" : "var(--text-primary)" }}>
                            {a.label}
                            {a.scope === "sessions" && (
                              <span className="text-[10px] px-1.5 rounded-full"
                                style={{ background: "var(--bg)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                                per session
                              </span>
                            )}
                          </span>
                          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{a.blurb}</span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>

            {needsField && (
              <div className="mt-3">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>{needsField.label}</label>
                {needsField.key === "message" ? (
                  <textarea value={value} rows={3} maxLength={1000} autoFocus
                    onChange={(e) => setValue(e.target.value)} placeholder={needsField.placeholder}
                    className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                    style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                ) : (
                  <input value={value} autoFocus maxLength={300}
                    onChange={(e) => setValue(e.target.value)} placeholder={needsField.placeholder}
                    className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                    style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                )}
              </div>
            )}

            {needsTyped && (
              <div className="mt-3">
                <p className="text-xs rounded-lg px-2 py-1.5 mb-2"
                  style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }}>
                  This reaches {group.device_count} device{group.device_count === 1 ? "" : "s"} and
                  cannot be undone from ASTRA.
                </p>
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Type <span className="font-mono font-semibold">{group.name}</span> to confirm
                </label>
                <input value={typed} onChange={(e) => setTyped(e.target.value)}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
              </div>
            )}

            {error && (
              <p className="text-xs mt-3 rounded-lg px-3 py-2"
                style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }}>{error}</p>
            )}

            <div className="flex justify-end gap-2 mt-4">
              <button onClick={onClose} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
              <button onClick={run} disabled={busy || !ready}
                className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: picked?.destructive ? "#ef4444" : "var(--accent)" }}>
                {busy ? "Pushing…"
                  : picked ? `Run on ${group.device_count} device${group.device_count === 1 ? "" : "s"}`
                  : "Pick an action"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Pick the members of one group or team.
 *
 * Sends the WHOLE set on save, matching the backend's set-replacement endpoint. The
 * checkboxes are already a picture of the complete set, so anything else would mean
 * computing a delta from a list the operator can see in front of them — and getting it
 * wrong in the case where two people edit at once, which is the case deltas are supposed
 * to help with.
 */
function MembershipDialog({
  kind, id, name, onClose, onSaved, onError,
}: {
  kind: Kind;
  id: string;
  name: string;
  onClose: () => void;
  onSaved: () => void;
  onError: (text: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string> | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: devices } = useQuery({
    queryKey: ["devices-for-groups"],
    queryFn: () => listDevicesPaged({ page: 1, page_size: 10_000 }),
    enabled: kind === "groups",
  });
  const { data: users } = useQuery({
    queryKey: ["users", "all"], queryFn: listAllUsers, enabled: kind === "teams",
  });
  const { data: current } = useQuery({
    queryKey: ["membership", kind, id],
    queryFn: () => (kind === "groups" ? getGroupDevices(id) : getTeamUsers(id)),
  });

  // Seed the checkboxes once the server says what is currently in the group. `null` until
  // then, so an operator cannot save an empty set that only looks empty because the
  // membership had not loaded yet — which would silently clear the group.
  useEffect(() => {
    if (current && selected === null) setSelected(new Set(current));
  }, [current, selected]);

  const options = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (kind === "groups") {
      return (devices?.items ?? [])
        .map((d) => ({ id: d.id, label: d.hostname, sub: d.logged_in_user ?? d.serial_number ?? "" }))
        .filter((o) => !needle || o.label.toLowerCase().includes(needle) || o.sub.toLowerCase().includes(needle));
    }
    return (users ?? [])
      .map((u) => ({ id: u.id, label: u.full_name, sub: u.email }))
      .filter((o) => !needle || o.label.toLowerCase().includes(needle) || o.sub.toLowerCase().includes(needle));
  }, [kind, devices, users, search]);

  function toggle(optionId: string) {
    setSelected((prev) => {
      const next = new Set(prev ?? []);
      if (next.has(optionId)) next.delete(optionId); else next.add(optionId);
      return next;
    });
  }

  async function save() {
    if (selected === null) return;
    setBusy(true);
    try {
      const ids = [...selected];
      if (kind === "groups") await setGroupDevices(id, ids);
      else await setTeamUsers(id, ids);
      onSaved();
    } catch (e) {
      onError(apiErrorMessage(e, "Couldn't save the membership."));
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}
      onClick={() => !busy && onClose()}>
      <div className="w-full max-w-lg rounded-xl p-5 flex flex-col max-h-[85vh]" onClick={(e) => e.stopPropagation()}
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              {name} — {kind === "groups" ? "devices" : "members"}
            </h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
              {selected === null ? "Loading current membership…" : `${selected.size} selected`}
            </p>
          </div>
          <button onClick={onClose} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
        </div>

        <div className="relative my-3">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={kind === "groups" ? "Search hostname or user…" : "Search name or email…"}
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto rounded-lg" style={{ border: "1px solid var(--border)" }}>
          {options.map((o) => (
            <label key={o.id} className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer"
              style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
              <input type="checkbox" className="accent-brand-500"
                checked={selected?.has(o.id) ?? false}
                disabled={selected === null}
                onChange={() => toggle(o.id)} />
              <span className="flex-1 min-w-0 truncate">{o.label}</span>
              {o.sub && <span className="text-xs truncate max-w-[45%]" style={{ color: "var(--text-secondary)" }}>{o.sub}</span>}
            </label>
          ))}
          {options.length === 0 && (
            <p className="px-3 py-6 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
              Nothing matches that search.
            </p>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} disabled={busy}
            className="px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
          <button onClick={save} disabled={busy || selected === null}
            className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--accent)" }}>{busy ? "Saving…" : "Save membership"}</button>
        </div>
      </div>
    </div>
  );
}
