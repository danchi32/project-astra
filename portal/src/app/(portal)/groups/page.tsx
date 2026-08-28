"use client";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, Plus, Pencil, Trash2, X, Search, Users as UsersIcon, Monitor } from "lucide-react";
import {
  listDeviceGroups, createDeviceGroup, updateDeviceGroup, deleteDeviceGroup,
  getGroupDevices, setGroupDevices,
  listUserTeams, createUserTeam, updateUserTeam, deleteUserTeam,
  getTeamUsers, setTeamUsers,
  type DeviceGroup, type UserTeam,
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

export default function GroupsPage() {
  const qc = useQueryClient();
  const [kind, setKind] = useState<Kind>("groups");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isStaff = me?.role === "admin" || me?.role === "technician";

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
                    <button onClick={() => setMembers({ id: row.id, name: row.name })}
                      className="text-xs px-2 py-1 rounded-lg"
                      style={{ border: "1px solid var(--border)", color: "var(--accent)" }}>
                      Manage {kind === "groups" ? "devices" : "members"}
                    </button>
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
