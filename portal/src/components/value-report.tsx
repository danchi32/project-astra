"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getValueReport } from "@/lib/api/reports";
import { apiErrorMessage } from "@/lib/utils";

// J5 · Value report. Every figure is the org's own setting times a count of real fixes, and
// says so underneath. Rupees only appear when the org has set an hourly cost.

const PROOF: Record<string, { label: string; color: string }> = {
  improved: { label: "Improved", color: "#10b981" },
  unchanged: { label: "No change", color: "var(--text-secondary)" },
  worse: { label: "Worse", color: "#ef4444" },
  unmeasured: { label: "Not measured", color: "var(--text-secondary)" },
};

export function ValueReport() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useQuery({ queryKey: ["report-value", days], queryFn: () => getValueReport(days) });
  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };

  const cards = data ? [
    { label: "Fixed with nobody involved", value: String(data.fixed_unattended), basis: data.basis.fixed_unattended },
    { label: "Hours saved", value: String(data.hours_saved), basis: data.basis.hours_saved },
    { label: "Saved (₹)", value: data.inr_saved === null ? "—" : `₹${data.inr_saved.toLocaleString("en-IN")}`,
      basis: data.basis.inr_saved ?? "Set your IT cost per hour in Settings to see this." },
    { label: "Proven to work", value: String(data.proven_improved), basis: data.basis.proven_improved },
  ] : [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm max-w-2xl" style={muted}>
          What SAVIO&apos;s self-healing was worth. Only fixes that ran with nobody approving them count as time saved.
          The minutes and hourly cost are yours, set in <Link href="/settings" className="underline">Settings</Link>.
        </p>
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          {[7, 30, 90].map((p) => (
            <button key={p} onClick={() => setDays(p)} className="px-3 py-1.5 rounded-md text-sm font-medium"
              style={days === p ? { background: "var(--accent)", color: "white" } : muted}>Last {p}d</button>
          ))}
        </div>
      </div>
      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load the Value report.")}</p>}
      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {cards.map((c) => (
              <div key={c.label} className="rounded-xl p-4" style={panel}>
                <p className="text-xs uppercase tracking-wide" style={muted}>{c.label}</p>
                <p className="text-2xl font-semibold mt-1" style={{ color: "var(--text-primary)" }}>{c.value}</p>
                <p className="text-xs mt-1" style={muted}>{c.basis}</p>
              </div>
            ))}
          </div>
          {(data.held_7_days > 0 || data.came_back > 0) && (
            <p className="text-sm" style={muted}>
              At the 7-day recheck, {data.held_7_days} still held and {data.came_back} had come back.
            </p>
          )}
          <div className="rounded-xl overflow-x-auto" style={panel}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Fix", "Device", "Done", "Proof"].map((h) => (
                    <th key={h} className="text-left px-4 py-2 text-xs uppercase" style={muted}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.fixes.map((f) => (
                  <tr key={f.task_id} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    <td className="px-4 py-2">{f.action}</td>
                    <td className="px-4 py-2">{f.device_hostname ?? "—"}</td>
                    <td className="px-4 py-2 whitespace-nowrap" style={muted}>{f.completed_at ? new Date(f.completed_at).toLocaleString() : "—"}</td>
                    <td className="px-4 py-2" style={{ color: PROOF[f.proof ?? ""]?.color ?? muted.color }}>
                      {f.proof ? PROOF[f.proof]?.label ?? f.proof : "Nothing to measure"}
                      {f.held_7_days === true && <span style={muted}> · held 7 days</span>}
                      {f.held_7_days === false && <span style={{ color: "#ef4444" }}> · came back</span>}
                    </td>
                  </tr>
                ))}
                {!data.fixes.length && (
                  <tr><td colSpan={4} className="px-4 py-6 text-center" style={muted}>No unattended fixes in the last {data.period_days} days.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
