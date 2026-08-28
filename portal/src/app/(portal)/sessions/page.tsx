"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Users, Search, ChevronLeft, ChevronRight, Lock, LogOut, MessageSquare,
  KeyRound, Monitor, MonitorSmartphone, X,
} from "lucide-react";
import {
  listSessions, actOnSession,
  type DeviceSession, type SessionActionId, type SessionConnection, type SessionState,
} from "@/lib/api/sessions";
import { listDeviceGroups } from "@/lib/api/grouping";
import { getMe } from "@/lib/api/auth";
import { ScrollPanel, stickyHeadCell } from "@/components/scroll-panel";
import { apiErrorMessage } from "@/lib/utils";

const PAGE_SIZE = 50;

// The tab strip. `state` and `connection` are separate filters on the backend, so a tab is
// whichever of the two it sets — All clears both. Kept as data rather than five near-copies
// of the same button, because the counts and the active styling are identical for each.
type Tab = { key: string; label: string; state?: SessionState; connection?: SessionConnection };
const TABS: Tab[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active", state: "active" },
  { key: "disconnected", label: "Disconnected", state: "disconnected" },
  { key: "console", label: "Console", connection: "console" },
  { key: "rdp", label: "RDP", connection: "rdp" },
];

// What each action does to the person at the machine, in the words the confirmation uses.
// The severity drives the button colour and whether the dialog needs typed confirmation:
// a lock is an inconvenience, a sign-out destroys work.
const ACTIONS: Record<SessionActionId, {
  label: string;
  adminOnly: boolean;
  destructive: boolean;
  blurb: string;
}> = {
  lock_session: {
    label: "Lock",
    adminOnly: false,
    destructive: false,
    blurb: "Locks the screen, exactly as Win+L does. Their work stays open and running; they type their password to come back.",
  },
  message_session: {
    label: "Message",
    adminOnly: false,
    destructive: false,
    blurb: "Shows a message box from IT on their desktop. One-way — there is no reply for you to read.",
  },
  logoff_session: {
    label: "Sign out",
    adminOnly: true,
    destructive: true,
    blurb: "Signs the session out of Windows. ANYTHING UNSAVED IS LOST — Windows does not prompt, because nobody is at the keyboard to answer. Send a message first if someone might be there.",
  },
  reset_local_password: {
    label: "Password",
    adminOnly: true,
    destructive: false,
    blurb: "Resets a LOCAL Windows account's password to a new random one and requires a change at next sign-in. The agent generates it and returns it once — read it to them and don't keep it. Domain and Entra accounts are refused; reset those in AD or Entra.",
  },
};

function relative(iso: string | null): string {
  if (!iso) return "—";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 90) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/**
 * The name to show in the User column.
 *
 * A local account reports as `MACHINE\Person`, and the machine is already the next column
 * along — so the prefix is pure repetition that pushed "DESKTOP-3T83JH6\Raj Pandey" onto three
 * wrapped lines and made one row as tall as three. A DOMAIN prefix is kept, because there it
 * carries real information: which directory the account lives in.
 */
function displayUser(username: string | null, hostname: string): string | null {
  if (!username) return null;
  const cut = username.lastIndexOf("\\");
  if (cut < 0) return username;
  const scope = username.slice(0, cut);
  const account = username.slice(cut + 1);
  return scope.toLowerCase() === hostname.toLowerCase() ? account : username;
}

function idleLabel(seconds: number | null): string {
  // Null is not zero. Windows reports no last-input time on plenty of local sessions, and
  // showing "0s" there would read as "actively typing" for a machine nobody has touched.
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 120) return "active";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m idle`;
  return `${Math.round(minutes / 60)}h idle`;
}

export default function SessionsPage() {
  const qc = useQueryClient();
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");
  const [tab, setTab] = useState("all");
  const [groupId, setGroupId] = useState("");
  const [onlineOnly, setOnlineOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  // The action being confirmed. Held as one object rather than a flag per action, so only
  // one dialog can ever be open and the row it belongs to travels with it.
  const [pending, setPending] = useState<
    { session: DeviceSession; action: SessionActionId; text: string; typed: string } | null
  >(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => { setQ(searchInput.trim()); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [searchInput]);
  useEffect(() => { setPage(1); }, [tab, groupId, onlineOnly]);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";
  const { data: groups } = useQuery({ queryKey: ["device-groups"], queryFn: listDeviceGroups });

  const active = TABS.find((t) => t.key === tab) ?? TABS[0];
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["sessions", q, tab, groupId, onlineOnly, page],
    queryFn: () => listSessions({
      q: q || undefined,
      state: active.state,
      connection: active.connection,
      group_id: groupId || undefined,
      online: onlineOnly ? true : undefined,
      page, page_size: PAGE_SIZE,
    }),
    // Sessions are the one table in the product that is genuinely live — who is signed in
    // changes on a scale of minutes. It is still a toggle: an operator working through a
    // list does not want it reordering underneath them mid-click.
    refetchInterval: autoRefresh ? 30_000 : false,
  });

  const rows = data?.items ?? [];
  const counts = data?.counts;
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, total);

  const countFor = useMemo(
    () => (key: string) => (counts ? (counts as unknown as Record<string, number>)[key] ?? 0 : null),
    [counts],
  );

  function open(session: DeviceSession, action: SessionActionId) {
    setMsg(null);
    setPending({ session, action, text: "", typed: "" });
  }

  async function run() {
    if (!pending) return;
    const { session, action, text } = pending;
    const spec = ACTIONS[action];
    if (action === "message_session" && !text.trim()) return;
    if (spec.destructive && pending.typed.trim().toUpperCase() !== "SIGN OUT") return;

    setBusy(true);
    try {
      await actOnSession({
        device_id: session.device_id,
        action_id: action,
        session_id: session.session_id,
        message: action === "message_session" ? text.trim() : undefined,
        username: action === "reset_local_password" ? session.username ?? undefined : undefined,
      });
      setPending(null);
      setMsg({
        ok: true,
        text: action === "reset_local_password"
          // The password is generated on the device, so it exists only once the task has
          // run. Pointing at Self-Healing is the honest instruction — the portal cannot
          // show a value the device has not produced yet.
          ? `Queued on ${session.hostname}. The temporary password appears in the task result under Self-Healing once the device has run it.`
          : `${spec.label} queued on ${session.hostname} (session ${session.session_id}). Offline devices pick it up when they next check in.`,
      });
      void qc.invalidateQueries({ queryKey: ["sessions"] });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, `Couldn't queue the ${spec.label.toLowerCase()}.`) });
    } finally {
      setBusy(false);
    }
  }

  const spec = pending ? ACTIONS[pending.action] : null;

  return (
    // gap-3 rather than the shared pageShell's gap-6: on this page every 24px of chrome is a
    // row of the table that isn't on screen, and the table is the entire point of the page.
    <div className="flex flex-col gap-3 h-full min-h-0">
      {/* Title sits inline with the count instead of owning a block of its own. The subtitle
          that used to explain the page is gone — the column headers say the same thing, and it
          was costing two rows of fleet to repeat it on every visit. */}
      <div className="flex items-baseline gap-2.5 flex-wrap">
        <Users size={17} style={{ color: "var(--accent)" }} className="self-center shrink-0" />
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Sessions</h1>
        <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {total} signed in across the fleet
        </span>
      </div>

      {msg && (
        <div className="rounded-lg px-3 py-2 text-sm" style={{
          background: msg.ok ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)",
          border: `1px solid ${msg.ok ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}`,
          color: msg.ok ? "#10b981" : "#ef4444",
        }}>{msg.text}</div>
      )}

      {/* Toolbar: search, tabs, group filter */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap flex-1 min-w-[240px]">
          <div className="relative w-[190px] shrink-0">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
            <input
              value={searchInput} onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search user or device…"
              className="w-full pl-8 pr-2.5 py-1.5 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
              style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          </div>

          <div className="flex items-center gap-1 flex-wrap">
            {TABS.map((t) => {
              const on = t.key === tab;
              const n = countFor(t.key);
              return (
                <button key={t.key} onClick={() => setTab(t.key)}
                  className="px-2 py-1.5 rounded-lg text-sm font-medium inline-flex items-center gap-1.5 shrink-0"
                  style={{
                    background: on ? "rgba(154,47,187,0.12)" : "var(--surface)",
                    border: "1px solid var(--border)",
                    color: on ? "var(--accent)" : "var(--text-secondary)",
                  }}>
                  {t.label}
                  {n !== null && (
                    <span className="text-xs px-1.5 rounded-full"
                      style={{ background: on ? "rgba(154,47,187,0.15)" : "var(--bg)" }}>{n}</span>
                  )}
                </button>
              );
            })}
          </div>

          <select value={groupId} onChange={(e) => setGroupId(e.target.value)}
            className="px-2 py-1.5 rounded-lg text-sm font-medium outline-none max-w-[170px] shrink-0"
            style={{
              background: groupId ? "rgba(154,47,187,0.1)" : "var(--surface)",
              border: "1px solid var(--border)",
              color: groupId ? "var(--accent)" : "var(--text-primary)",
            }}>
            <option value="">All groups &amp; teams</option>
            {groups?.map((g) => (
              <option key={g.id} value={g.id}>{g.name} ({g.device_count})</option>
            ))}
          </select>

          <label className="inline-flex items-center gap-1.5 text-sm cursor-pointer" style={{ color: "var(--text-secondary)" }}>
            <input type="checkbox" checked={onlineOnly} onChange={(e) => setOnlineOnly(e.target.checked)} className="accent-brand-500" />
            Online only
          </label>
        </div>

        <label className="inline-flex items-center gap-1.5 text-sm cursor-pointer" style={{ color: "var(--text-secondary)" }}>
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} className="accent-brand-500" />
          Auto-refresh
        </label>
      </div>

      <ScrollPanel
        footer={total > 0 && (
          <div className="flex items-center justify-between gap-3 px-4 py-3 flex-wrap"
            style={{ borderTop: "1px solid var(--border)", background: "var(--surface)" }}>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Showing {from}–{to} of {total}{isFetching ? " · updating…" : ""}
            </p>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm font-medium disabled:opacity-40"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                <ChevronLeft size={15} /> Prev
              </button>
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>Page {page} of {pages}</span>
              <button onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page >= pages}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm font-medium disabled:opacity-40"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                Next <ChevronRight size={15} />
              </button>
            </div>
          </div>
        )}
      >
        {/* table-fixed + a colgroup, so the columns are sized by the layout rather than by the
            longest value in them. Before this the table set its own width from the content and
            the panel scrolled sideways — which put the actions off-screen on the very rows an
            operator opened the page to act on. Now User and Device absorb the slack and
            everything else is pinned. */}
        <table className="w-full text-sm table-fixed">
          {/* Widths add up to ~816px of the ~1010px content area at a 1280px window, leaving
              the User column the remainder. The actions column is sized for an admin's four
              buttons (4 × 28px + gaps + padding); a technician sees two and the column simply
              runs light rather than reflowing the table between roles. */}
          <colgroup>
            <col />                                  {/* User — takes the slack */}
            <col style={{ width: "11rem" }} />       {/* Device */}
            <col style={{ width: "7rem" }} />        {/* Session */}
            <col style={{ width: "6.5rem" }} />      {/* State */}
            <col style={{ width: "6rem" }} />        {/* Type */}
            <col style={{ width: "5rem" }} />        {/* Idle */}
            <col style={{ width: "6rem" }} />        {/* Last seen */}
            <col style={{ width: "9.5rem" }} />      {/* Actions */}
          </colgroup>
          <thead>
            <tr>
              {["User", "Device", "Session", "State", "Type", "Idle", "Last seen", ""].map((h, i) => (
                <th key={i} className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide"
                  style={stickyHeadCell}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={8} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>
            )}
            {!isLoading && rows.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                {q || tab !== "all" || groupId || onlineOnly
                  ? "No sessions match your filters."
                  : "No sessions reported yet. Devices report who is signed in with each telemetry push — agents older than the sessions feature report nothing here."}
              </td></tr>
            )}
            {rows.map((s) => {
              const who = displayUser(s.username, s.hostname);
              return (
              <tr key={s.id} className="hover:bg-brand-500/5 transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="px-3 py-2">
                  {/* title carries the full DOMAIN\user — the column shows the short form, so
                      the unabbreviated value has to stay reachable on hover. */}
                  <div className="font-medium truncate" title={s.username ?? undefined}
                    style={{ color: s.username ? "var(--text-primary)" : "var(--text-secondary)" }}>
                    {who ?? "(no user)"}
                  </div>
                  {s.groups.length > 0 && (
                    <div className="flex gap-1 flex-wrap">
                      {s.groups.map((g) => (
                        <span key={g} className="text-[10px] px-1.5 rounded-full truncate max-w-full"
                          style={{ background: "var(--bg)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>{g}</span>
                      ))}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2">
                  <Link href={`/devices/${s.device_id}`} title={s.hostname}
                    className="hover:underline font-medium truncate block" style={{ color: "var(--accent)" }}>
                    {s.hostname}
                  </Link>
                  {s.client_name && (
                    <div className="text-xs truncate" title={s.client_name} style={{ color: "var(--text-secondary)" }}>
                      from {s.client_name}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-xs truncate"
                  title={s.station ? `${s.session_id} · ${s.station}` : String(s.session_id)}
                  style={{ color: "var(--text-secondary)" }}>
                  {s.session_id}{s.station ? ` · ${s.station}` : ""}
                </td>
                <td className="px-3 py-2">
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap" style={{
                    color: s.state === "active" ? "#10b981" : "#f59e0b",
                    background: s.state === "active" ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)",
                  }}>{s.state === "active" ? "Active" : "Idle/Disc."}</span>
                </td>
                <td className="px-3 py-2">
                  <span className="inline-flex items-center gap-1 text-xs whitespace-nowrap" style={{ color: "var(--text-secondary)" }}>
                    {s.connection === "rdp" ? <MonitorSmartphone size={13} /> : <Monitor size={13} />}
                    {s.connection === "rdp" ? "RDP" : "Console"}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs truncate" style={{ color: "var(--text-secondary)" }}>{idleLabel(s.idle_seconds)}</td>
                <td className="px-3 py-2 text-xs truncate">
                  <span style={{ color: s.device_online ? "#10b981" : "var(--text-secondary)" }}>
                    {s.device_online ? "online" : relative(s.device_last_seen_at)}
                  </span>
                </td>
                <td className="px-3 py-2">
                  {/* Icon-only. Four labelled buttons were what actually forced the sideways
                      scroll, and they repeat identically down every row — the label earns its
                      width once, in a tooltip, not once per session. */}
                  <div className="flex items-center gap-1 justify-end">
                    {(Object.keys(ACTIONS) as SessionActionId[]).map((id) => {
                      const a = ACTIONS[id];
                      // Admin-only actions are hidden from technicians rather than shown
                      // disabled — the backend refuses them either way, and a row of greyed
                      // buttons reads as "broken" rather than "not yours".
                      if (a.adminOnly && !isAdmin) return null;
                      // A password reset needs an account to reset. A session with nobody
                      // signed into it has none.
                      if (id === "reset_local_password" && !s.username) return null;
                      const Icon = id === "lock_session" ? Lock
                        : id === "logoff_session" ? LogOut
                        : id === "message_session" ? MessageSquare : KeyRound;
                      return (
                        <button key={id} onClick={() => open(s, id)}
                          title={`${a.label} — ${a.blurb}`} aria-label={a.label}
                          className="inline-flex items-center justify-center w-7 h-7 rounded-lg shrink-0"
                          style={{
                            background: "var(--bg)", border: "1px solid var(--border)",
                            color: a.destructive ? "#ef4444" : "var(--text-primary)",
                          }}>
                          <Icon size={13} />
                        </button>
                      );
                    })}
                  </div>
                </td>
              </tr>);
            })}
          </tbody>
        </table>
      </ScrollPanel>

      {/* Confirm — every one of these interrupts a person, so none of them is a bare click */}
      {pending && spec && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={() => !busy && setPending(null)}>
          <div className="w-full max-w-md rounded-xl p-5" onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                {spec.label} — {pending.session.username ?? "(no user)"} on {pending.session.hostname}
              </h2>
              <button onClick={() => !busy && setPending(null)} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
            </div>
            <p className="text-sm mt-2" style={{ color: "var(--text-secondary)" }}>{spec.blurb}</p>

            {!pending.session.device_online && (
              <p className="text-xs mt-2 rounded-lg px-2 py-1.5"
                style={{ background: "rgba(245,158,11,0.1)", color: "#f59e0b" }}>
                This device last checked in {relative(pending.session.device_last_seen_at)}. The action
                is queued and will run whenever it comes back — by which time this session may be
                someone else&apos;s, or gone. The agent re-checks the session id before acting.
              </p>
            )}

            {pending.action === "message_session" && (
              <textarea
                value={pending.text} rows={4} maxLength={1000} autoFocus
                onChange={(e) => setPending({ ...pending, text: e.target.value })}
                placeholder="Saving your work now — this machine reboots in 10 minutes."
                className="w-full mt-3 px-3 py-2 rounded-lg text-sm outline-none"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
            )}

            {pending.action === "reset_local_password" && (
              <p className="text-sm mt-3 rounded-lg px-3 py-2" style={{ background: "var(--bg)", color: "var(--text-primary)" }}>
                Account: <span className="font-mono">{pending.session.username}</span>
              </p>
            )}

            {spec.destructive && (
              <div className="mt-3">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Type <span className="font-mono font-semibold">SIGN OUT</span> to confirm
                </label>
                <input value={pending.typed} autoFocus
                  onChange={(e) => setPending({ ...pending, typed: e.target.value })}
                  className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
              </div>
            )}

            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setPending(null)} disabled={busy}
                className="px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
              <button onClick={run}
                disabled={busy
                  || (pending.action === "message_session" && !pending.text.trim())
                  || (spec.destructive && pending.typed.trim().toUpperCase() !== "SIGN OUT")}
                className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: spec.destructive ? "#ef4444" : "var(--accent)" }}>
                {busy ? "Queueing…" : spec.label}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
