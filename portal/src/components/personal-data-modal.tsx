"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ShieldAlert, X } from "lucide-react";
import { downloadPersonalData, erasePersonalData, getPersonalData } from "@/lib/api/users";
import { apiErrorMessage } from "@/lib/utils";

// Z2 — answer an employee's data request: see what SAVIO holds about them, hand it over as a
// file, or erase it. Windows usernames are the admin's call: SAVIO doesn't link a portal user
// to the accounts they sign in to computers with, so it suggests and the admin ticks.

const LABELS: Record<string, string> = {
  conversations: "AI chats",
  team_memberships: "Team memberships",
  assets_assigned: "Assets they hold",
  asset_history: "Asset history entries",
  support_escalations: "Support escalations",
  support_requests: "Support tickets they raised",
  remediations: "Fixes they requested or approved",
  remote_sessions: "Remote sessions they requested",
  deployments: "Software pushes they started",
  audit_entries: "Audit log entries",
  activity_samples: "Tracker activity events",
  work_sessions: "Tracker work sessions",
  daily_user_summary: "Tracker daily summaries",
  daily_app_usage: "Tracker app-usage days",
  device_sessions: "Signed-in sessions",
  apps_in_their_profile: "Apps installed in their profile",
  windows_accounts: "Windows accounts on computers",
};

const WHAT_HAPPENS: Record<string, string> = {
  deleted: "Deleted",
  unlinked: "Kept, no longer linked to them",
  pseudonymised: "Kept as a security record, name replaced",
  kept: "Not touched — remove the account on the computer itself",
};

export function PersonalDataModal({ userId, onClose }: { userId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [names, setNames] = useState<string[]>([]);
  const [typed, setTyped] = useState("");
  const [extra, setExtra] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [erased, setErased] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["personal-data", userId, names],
    queryFn: () => getPersonalData(userId, names),
    placeholderData: (prev) => prev,
  });
  const candidates = Array.from(new Set([...(data?.windows_username_candidates ?? []), ...names])).sort();

  const toggle = (n: string) => setNames((cur) => (cur.includes(n) ? cur.filter((x) => x !== n) : [...cur, n]));

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try { await fn(); } catch (e) { setError(apiErrorMessage(e, "Something went wrong")); } finally { setBusy(false); }
  }

  const erase = () => run(async () => {
    const r = await erasePersonalData(userId, names, typed);
    setErased(r.person);
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  });

  const muted = { color: "var(--text-secondary)" };
  const box = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}>
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl p-5 space-y-4"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Personal data</h2>
            <p className="text-sm" style={muted}>{data ? `${data.user.full_name} · ${data.user.email}` : "Loading…"}</p>
          </div>
          <button onClick={onClose} aria-label="Close" style={muted}><X size={18} /></button>
        </div>

        {erased ? (
          <div className="space-y-3">
            <p className="text-sm" style={{ color: "var(--text-primary)" }}>
              Erased. The audit log now refers to this person as <strong>{erased}</strong>.
            </p>
            <button onClick={onClose} className="px-3 py-2 rounded-lg text-sm" style={box}>Close</button>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                Which Windows usernames are this person?
              </p>
              <p className="text-xs" style={muted}>
                SAVIO records Tracker and sign-in data per Windows username, not per portal user. Tick the ones
                that belong to this person — and only those.
              </p>
              <div className="flex flex-wrap gap-2">
                {candidates.length === 0 && <span className="text-xs" style={muted}>No likely usernames seen.</span>}
                {candidates.map((n) => (
                  <label key={n} className="flex items-center gap-1.5 text-sm px-2 py-1 rounded-lg" style={box}>
                    <input type="checkbox" checked={names.includes(n)} onChange={() => toggle(n)} /> {n}
                  </label>
                ))}
              </div>
              <div className="flex gap-2">
                <input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="Add another, e.g. ACME\asha"
                  className="flex-1 px-3 py-1.5 rounded-lg text-sm outline-none" style={box} />
                <button disabled={!extra.trim()} onClick={() => { toggle(extra.trim()); setExtra(""); }}
                  className="px-3 py-1.5 rounded-lg text-sm disabled:opacity-50" style={box}>Add</button>
              </div>
            </div>

            {data && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide" style={muted}>
                    <th className="py-1.5">What</th><th className="py-1.5 text-right pr-4">Count</th><th className="py-1.5">On erase</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.erase).flatMap(([what, keys]) => keys.map((k) => (
                    <tr key={k} style={{ borderTop: "1px solid var(--border)", color: "var(--text-primary)" }}>
                      <td className="py-1.5">{k === "account" ? "Portal account" : LABELS[k] ?? k}</td>
                      <td className="py-1.5 text-right pr-4">{k === "account" ? 1 : data.counts[k] ?? 0}</td>
                      <td className="py-1.5" style={muted}>{WHAT_HAPPENS[what]}</td>
                    </tr>
                  )))}
                </tbody>
              </table>
            )}

            <button disabled={busy || !data} onClick={() => run(() => downloadPersonalData(userId, names))}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}>
              <Download size={15} /> Download everything (JSON)
            </button>

            <div className="rounded-lg p-3 space-y-2" style={{ border: "1px solid rgba(220,38,38,0.4)" }}>
              <p className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "#dc2626" }}>
                <ShieldAlert size={15} /> Erase this person
              </p>
              <p className="text-xs" style={muted}>
                Can&apos;t be undone. Download first if they asked for a copy. If they still sign in to these computers,
                new Tracker and sign-in data will be collected again.
              </p>
              <div className="flex gap-2">
                <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Type their email to confirm"
                  className="flex-1 px-3 py-1.5 rounded-lg text-sm outline-none" style={box} />
                <button onClick={erase}
                  disabled={busy || !data || typed.trim().toLowerCase() !== data.user.email.toLowerCase()}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium text-white disabled:opacity-40"
                  style={{ background: "#dc2626" }}>
                  Erase
                </button>
              </div>
            </div>

            {error && <p className="text-sm" style={{ color: "#dc2626" }}>{error}</p>}
          </>
        )}
      </div>
    </div>
  );
}
