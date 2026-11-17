"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Lightbulb } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  dismissRecommendation, listRecommendations, restoreRecommendation, type Recommendation,
} from "@/lib/api/recommendations";
import { apiErrorMessage } from "@/lib/utils";

// J2 · Recommendations. Each one names what was seen and on which PCs; the time and rupee
// figures are the org's own settings times the PCs affected, with the working shown.

const RISK: Record<string, { label: string; color: string }> = {
  high: { label: "High risk", color: "#ef4444" },
  medium: { label: "Medium risk", color: "#f59e0b" },
  low: { label: "Low risk", color: "#3b82f6" },
};
const EFFORT: Record<string, string> = {
  one_click: "One click in Fleet Issues", manual: "Needs hands-on work", purchase: "Needs a purchase",
};

export default function RecommendationsPage() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isStaff = me?.role === "admin" || me?.role === "technician";
  const [status, setStatus] = useState<Recommendation["status"]>("open");
  const { data, isLoading, error } = useQuery({
    queryKey: ["recommendations", status], queryFn: () => listRecommendations(status), enabled: isStaff,
  });
  const [err, setErr] = useState<string | null>(null);
  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const btn = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

  async function act(fn: () => Promise<unknown>) {
    setErr(null);
    try { await fn(); qc.invalidateQueries({ queryKey: ["recommendations"] }); }
    catch (e) { setErr(apiErrorMessage(e, "That didn't work.")); }
  }
  function dismiss(r: Recommendation) {
    const why = prompt(`Why dismiss "${r.title}"? (goes in the audit log)`);
    if (why && why.trim().length >= 3) act(() => dismissRecommendation(r.id, why.trim()));
  }

  if (me && !isStaff) return <p className="text-sm" style={muted}>Recommendations are for IT staff.</p>;

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><Lightbulb size={18} /></div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Recommendations</h1>
          <p className="text-xs" style={muted}>
            What to do next, riskiest first, from what SAVIO sees on your PCs right now. Each one clears by itself once fixed.
          </p>
        </div>
      </div>

      <div className="flex gap-1 p-1 rounded-lg w-fit" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
        {(["open", "dismissed", "resolved"] as const).map((s) => (
          <button key={s} onClick={() => setStatus(s)} className="px-3 py-1.5 rounded-md text-sm font-medium capitalize"
            style={status === s ? { background: "var(--accent)", color: "white" } : muted}>{s}</button>
        ))}
      </div>

      {err && <p className="text-xs" style={{ color: "#ef4444" }}>{err}</p>}
      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load recommendations.")}</p>}
      {data && !data.length && (
        <p className="text-sm rounded-xl p-6 text-center" style={{ ...panel, ...muted }}>
          {status === "open" ? "Nothing to recommend right now." : `No ${status} recommendations.`}
        </p>
      )}

      {data?.map((r) => (
        <div key={r.id} className="rounded-xl p-4 space-y-2" style={panel}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-medium" style={{ color: "var(--text-primary)" }}>{r.title}</p>
              <p className="text-xs mt-0.5">
                <span style={{ color: RISK[r.risk]?.color }}>{RISK[r.risk]?.label}</span>
                <span style={muted}> · {EFFORT[r.effort]} · {r.evidence.count} affected</span>
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              {status === "open" && r.action_id && (
                <Link href="/fleet" className="px-2.5 py-1 rounded-lg text-xs font-medium text-white" style={{ background: "var(--accent)" }}>Fix in Fleet Issues</Link>
              )}
              {status === "open" && <button onClick={() => dismiss(r)} className="px-2.5 py-1 rounded-lg text-xs" style={btn}>Dismiss</button>}
              {status === "dismissed" && <button onClick={() => act(() => restoreRecommendation(r.id))} className="px-2.5 py-1 rounded-lg text-xs" style={btn}>Restore</button>}
            </div>
          </div>
          <p className="text-sm" style={{ color: "var(--text-primary)" }}>{r.advice}</p>
          {r.time_minutes !== null && (
            <p className="text-xs" style={muted}>
              By hand: about {r.time_minutes} min{r.inr !== null && <> · ₹{r.inr.toLocaleString("en-IN")}</>} ({r.basis})
            </p>
          )}
          {r.dismissed_reason && <p className="text-xs" style={muted}>Dismissed: {r.dismissed_reason}</p>}
          <details className="text-xs" style={muted}>
            <summary className="cursor-pointer">Evidence</summary>
            <ul className="mt-1 space-y-0.5 pl-4 list-disc">
              {r.evidence.devices.map((d) => <li key={d}>{d}</li>)}
              {r.evidence.count > r.evidence.devices.length && <li>…and {r.evidence.count - r.evidence.devices.length} more</li>}
            </ul>
          </details>
        </div>
      ))}
    </div>
  );
}
