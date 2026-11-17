"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import {
  FINDING_KINDS, approveGuardApproval, denyGuardApproval, getGuardApprovals,
  type FindingKind, type GuardApproval,
} from "@/lib/api/guard";
import { isUpgradeRequired } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3 · D7 · AI Guard → Approvals. People whose paste or upload SAVIO held ("Needs IT
// approval" mode) ask here. An approval covers that person, PC, site and channel only, for the
// time chosen; the PC picks it up within a minute. Every decision is audited. Admin only.

const VERB: Record<GuardApproval["channel"], string> = {
  paste: "paste", drop: "drop content", file: "upload a file", submit: "send a form",
};
const DURATIONS = [[15, "15 minutes"], [30, "30 minutes"], [60, "1 hour"], [240, "4 hours"], [480, "8 hours"]] as const;
const STATUS: Record<GuardApproval["status"], { label: string; color: string }> = {
  pending: { label: "Waiting", color: "#f59e0b" },
  approved: { label: "Approved", color: "#10b981" },
  denied: { label: "Denied", color: "#ef4444" },
  expired: { label: "Expired unanswered", color: "var(--text-secondary)" },
  ended: { label: "Approval ended", color: "var(--text-secondary)" },
};

const status = (e: unknown) => (e as { response?: { status?: number } } | null)?.response?.status;

function found(a: GuardApproval) {
  const parts = (Object.entries(a.counts) as [FindingKind, number][])
    .filter(([, n]) => n > 0).map(([k, n]) => `${FINDING_KINDS[k] ?? k} ×${n}`);
  if (a.contact_list) parts.push("a contact list");
  if (a.keyword_hits) parts.push(`${a.keyword_hits} restricted keyword${a.keyword_hits > 1 ? "s" : ""}`);
  return parts.join(", ") || "Content SAVIO could not check";
}

export default function GuardApprovalsPage() {
  const qc = useQueryClient();
  const { data, error, isLoading } = useQuery({ queryKey: ["guard-approvals"], queryFn: getGuardApprovals,
    retry: false, refetchInterval: 30_000 });
  const [minutes, setMinutes] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };

  if (isUpgradeRequired(error) || status(error) === 403) {
    return (
      <div className="rounded-xl p-8 text-center max-w-lg mx-auto" style={panel}>
        <ShieldAlert size={22} className="mx-auto mb-3" style={{ color: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          {isUpgradeRequired(error) ? "AI Guard is an add-on" : "Only an admin can see this"}
        </h2>
      </div>
    );
  }

  async function decide(a: GuardApproval, approve: boolean) {
    setBusy(a.id); setMsg(null);
    try {
      const mins = minutes[a.id] ?? 30;
      if (approve) await approveGuardApproval(a.id, mins); else await denyGuardApproval(a.id);
      setMsg({ ok: true, text: approve
        ? `Approved for ${DURATIONS.find(([m]) => m === mins)?.[1] ?? `${mins} minutes`}. ${a.hostname} picks it up within a minute.`
        : "Denied." });
      await qc.invalidateQueries({ queryKey: ["guard-approvals"] });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not save the decision.") });
    } finally { setBusy(null); }
  }

  const pending = (data ?? []).filter((a) => a.status === "pending");
  const decided = (data ?? []).filter((a) => a.status !== "pending");

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><ShieldAlert size={18} /></div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Approvals</h1>
          <p className="text-xs max-w-2xl" style={muted}>
            Requests to let something SAVIO held go through. An approval covers that person, that PC, that site and that
            kind of action only, for the time you choose. You see what kind of data it was, never the data itself.
          </p>
        </div>
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load.")}</p>}
      {msg && <p className="text-xs" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}

      {data && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Waiting ({pending.length})</h2>
          {pending.map((a) => (
            <div key={a.id} className="rounded-xl p-4 flex flex-wrap items-center justify-between gap-3" style={panel}>
              <div className="text-sm min-w-0" style={{ color: "var(--text-primary)" }}>
                <div><span className="font-medium">{a.windows_user}</span> on {a.hostname} wants to {VERB[a.channel]} on{" "}
                  <span className="font-mono text-xs">{a.site}</span></div>
                <div className="text-xs" style={muted}>{found(a)} · asked {new Date(a.requested_at).toLocaleString()}</div>
              </div>
              <div className="flex items-center gap-2">
                <select aria-label="For how long" value={minutes[a.id] ?? 30}
                  onChange={(e) => setMinutes({ ...minutes, [a.id]: Number(e.target.value) })}
                  className="px-2 py-1.5 rounded-lg text-sm outline-none"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                  {DURATIONS.map(([m, label]) => <option key={m} value={m}>{label}</option>)}
                </select>
                <button disabled={busy === a.id} onClick={() => decide(a, true)}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "#10b981" }}>Approve</button>
                <button disabled={busy === a.id} onClick={() => decide(a, false)}
                  className="px-3 py-1.5 rounded-lg text-sm disabled:opacity-50" style={{ ...panel, color: "var(--text-primary)" }}>Deny</button>
              </div>
            </div>
          ))}
          {!pending.length && <p className="text-sm" style={muted}>Nothing waiting.</p>}

          {decided.length > 0 && (
            <div className="rounded-xl overflow-x-auto" style={panel}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Asked", "Person · PC", "Site", "Wanted to", "Result"].map((h) => (
                      <th key={h} className="text-left px-4 py-2 text-xs uppercase whitespace-nowrap" style={muted}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {decided.map((a) => (
                    <tr key={a.id} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                      <td className="px-4 py-2 text-xs whitespace-nowrap" style={muted}>{new Date(a.requested_at).toLocaleString()}</td>
                      <td className="px-4 py-2 text-xs"><span className="font-medium">{a.windows_user}</span><span className="block" style={muted}>{a.hostname}</span></td>
                      <td className="px-4 py-2 font-mono text-xs">{a.site}</td>
                      <td className="px-4 py-2 text-xs">{VERB[a.channel]}</td>
                      <td className="px-4 py-2 text-xs">
                        <span className="font-medium" style={{ color: STATUS[a.status].color }}>{STATUS[a.status].label}</span>
                        {a.status === "approved" && a.valid_until && (
                          <span className="block" style={muted}>until {new Date(a.valid_until).toLocaleTimeString()}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
