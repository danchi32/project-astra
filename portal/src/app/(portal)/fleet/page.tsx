"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Radar, Wrench, ChevronDown, ChevronRight, ShieldCheck } from "lucide-react";
import { getFleetIssues, bulkRemediate } from "@/lib/api/fleet";
import type { FleetIssue } from "@/lib/api/fleet";
import { getMe } from "@/lib/api/auth";
import { apiErrorMessage } from "@/lib/utils";

const SEV_COLOR: Record<string, string> = { high: "#ef4444", medium: "#f59e0b", low: "#64748b" };

export default function FleetPage() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isStaff = me?.role === "admin" || me?.role === "technician";

  const { data: issues, isLoading } = useQuery({ queryKey: ["fleet-issues"], queryFn: getFleetIssues, refetchInterval: 60_000 });

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  async function fixAll(issue: FleetIssue) {
    if (!issue.fix_action_id) return;
    const n = issue.affected.length;
    if (!confirm(`Push "${issue.title}" fix to ${n} device${n === 1 ? "" : "s"}?\n\nASTRA runs it on each endpoint in the background. Tracked under Self-Healing.`)) return;
    setBusyKey(issue.key); setMsg(null);
    try {
      const res = await bulkRemediate({
        device_ids: issue.affected.map((a) => a.device_id),
        action_id: issue.fix_action_id,
        params: issue.fix_params ?? undefined,
        reason: `Fleet fix: ${issue.title} (${n} devices)`,
      });
      setMsg({
        ok: res.failed === 0,
        text: res.failed === 0
          ? `Queued on ${res.queued} device${res.queued === 1 ? "" : "s"}. Track progress under Self-Healing.`
          : `Queued on ${res.queued}, ${res.failed} failed${res.error ? ` — ${res.error}` : ""}.`,
      });
      await qc.invalidateQueries({ queryKey: ["fleet-issues"] });
    } catch (e) { setMsg({ ok: false, text: apiErrorMessage(e, "Couldn't push the fleet fix.") }); }
    finally { setBusyKey(null); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Radar size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Fleet Issues</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Problems affecting many devices — fix them everywhere in one click
          </p>
        </div>
      </div>

      {msg && <p className="text-sm" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}

      {isLoading && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Scanning the fleet…</p>}

      {!isLoading && !issues?.length && (
        <div className="rounded-2xl p-10 text-center" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <ShieldCheck size={28} className="mx-auto mb-2" style={{ color: "#10b981" }} />
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>No fleet-wide issues found</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>Everything is patched, healthy and within policy.</p>
        </div>
      )}

      <div className="space-y-3">
        {issues?.map((issue) => {
          const open = expanded.has(issue.key);
          const n = issue.affected.length;
          const color = SEV_COLOR[issue.severity] ?? "#64748b";
          return (
            <div key={issue.key} className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-3 p-4">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: color }} title={issue.severity} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{issue.title}</span>
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ background: `${color}1a`, color }}>
                      {n} device{n === 1 ? "" : "s"}
                    </span>
                  </div>
                  {issue.detail && <p className="text-xs mt-0.5 truncate" style={{ color: "var(--text-secondary)" }}>{issue.detail}</p>}
                </div>
                {isStaff && issue.fix_action_id && (
                  <button onClick={() => fixAll(issue)} disabled={busyKey !== null}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 shrink-0" style={{ background: "var(--accent)" }}>
                    <Wrench size={14} /> {busyKey === issue.key ? "Queuing…" : `Fix all ${n}`}
                  </button>
                )}
                <button onClick={() => toggle(issue.key)} className="p-1.5 rounded-lg shrink-0" style={{ color: "var(--text-secondary)" }} title="Show devices">
                  {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
              </div>
              {open && (
                <div className="px-4 pb-4 pt-1 border-t" style={{ borderColor: "var(--border)" }}>
                  <div className="flex flex-wrap gap-2 mt-3">
                    {issue.affected.map((a) => (
                      <Link key={a.device_id} href={`/devices/${a.device_id}`}
                        className="text-xs px-2.5 py-1 rounded-full hover:underline" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--accent)" }}>
                        {a.hostname}
                      </Link>
                    ))}
                  </div>
                  {!issue.fix_action_id && (
                    <p className="text-xs mt-3" style={{ color: "var(--text-secondary)" }}>
                      No automatic fix for this one — open a device to investigate or remediate manually.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
