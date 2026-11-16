"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAiSafetyReport } from "@/lib/api/reports";
import { apiErrorMessage } from "@/lib/utils";

// C3 · the AI Safety report. Every fix the assistant proposed, and the ones SAVIO stepped in
// on: held for a person because it leaned on text from the device or knowledge base, or
// refused outright because the assistant may never request that action.

const REASONS: Record<string, string> = {
  outside_text_names_action: "Device or KB text named the fix",
  outside_text_supplies_value: "A value came from device or KB text",
  outside_text_has_instructions: "Device or KB text contained instructions",
  value_not_from_user: "A value the user never gave",
  admin_only: "Admin-only action",
  operator_only: "Technician-only action",
  unknown_action: "Not a SAVIO action",
  rejected: "Rejected by validation",
};

const KIND: Record<string, { label: string; color: string }> = {
  raised: { label: "Held for approval", color: "#f59e0b" },
  flagged: { label: "Approver warned", color: "#3b82f6" },
  refused: { label: "Refused", color: "#ef4444" },
};

export function AiSafetyReport() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useQuery({
    queryKey: ["report-ai-safety", days],
    queryFn: () => getAiSafetyReport(days),
  });
  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };

  const cards: { label: string; value: number; color?: string }[] = data ? [
    { label: "Fixes proposed", value: data.proposals },
    { label: "Ran on their own", value: data.ran_unattended },
    { label: "Held for approval", value: data.raised, color: KIND.raised.color },
    { label: "Approver warned", value: data.flagged, color: KIND.flagged.color },
    { label: "Refused", value: data.refused, color: KIND.refused.color },
  ] : [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm max-w-2xl" style={muted}>
          Text from a PC&apos;s event log or the knowledge base can be written to look like an
          instruction. SAVIO never lets it run a fix on its own: such fixes wait for a person, and
          actions the assistant may not request are refused.
        </p>
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          {[7, 30, 90].map((p) => (
            <button key={p} onClick={() => setDays(p)} className="px-3 py-1.5 rounded-md text-sm font-medium"
              style={days === p ? { background: "var(--accent)", color: "white" } : muted}>
              Last {p}d
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load the AI Safety report.")}</p>}
      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {cards.map((c) => (
              <div key={c.label} className="rounded-xl p-4" style={panel}>
                <p className="text-xs uppercase tracking-wide" style={muted}>{c.label}</p>
                <p className="text-2xl font-semibold mt-1" style={{ color: c.color ?? "var(--text-primary)" }}>{c.value}</p>
              </div>
            ))}
          </div>

          {Object.keys(data.by_reason).length > 0 && (
            <div className="rounded-xl p-4 space-y-2" style={panel}>
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Why</p>
              {Object.entries(data.by_reason).sort((a, b) => b[1] - a[1]).map(([r, n]) => (
                <div key={r} className="flex justify-between text-sm" style={{ color: "var(--text-primary)" }}>
                  <span>{REASONS[r] ?? r}</span><span style={muted}>{n}</span>
                </div>
              ))}
            </div>
          )}

          <div className="rounded-xl overflow-x-auto" style={panel}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["When", "Outcome", "Action", "Device", "Why"].map((h) => (
                    <th key={h} className="text-left px-4 py-2 text-xs uppercase" style={muted}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.events.map((e, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    <td className="px-4 py-2 whitespace-nowrap" style={muted}>{new Date(e.at).toLocaleString()}</td>
                    <td className="px-4 py-2 whitespace-nowrap font-medium" style={{ color: KIND[e.kind]?.color }}>{KIND[e.kind]?.label ?? e.kind}</td>
                    <td className="px-4 py-2 font-mono text-xs">{e.action_id}</td>
                    <td className="px-4 py-2">{e.device_hostname ?? "—"}</td>
                    <td className="px-4 py-2" style={muted}>{e.reasons.map((r) => REASONS[r] ?? r).join(" · ")}</td>
                  </tr>
                ))}
                {!data.events.length && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center" style={muted}>
                    Nothing held or refused in the last {data.period_days} days.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
