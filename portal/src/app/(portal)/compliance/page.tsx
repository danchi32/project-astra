"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert, Ban, Plus, X } from "lucide-react";
import {
  getComplianceSummary, getComplianceDevices,
  listBannedSoftware, addBannedSoftware, removeBannedSoftware,
} from "@/lib/api/compliance";
import type { DeviceComplianceStatus } from "@/lib/api/compliance";
import { getMe } from "@/lib/api/auth";
import { apiErrorMessage } from "@/lib/utils";
import { Pagination } from "@/components/pagination";
import { UpgradeRequired, isUpgradeRequired, requiredFeature } from "@/components/upgrade-required";

const STATUS_STYLE: Record<DeviceComplianceStatus, { label: string; color: string }> = {
  compliant: { label: "Compliant", color: "#10b981" },
  at_risk: { label: "At risk", color: "#f59e0b" },
  non_compliant: { label: "Non-compliant", color: "#ef4444" },
  unknown: { label: "Unknown", color: "#64748b" },
};

function ScoreRing({ score }: { score: number }) {
  const color = score >= 90 ? "#10b981" : score >= 70 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative w-28 h-28 shrink-0">
      <svg viewBox="0 0 36 36" className="w-28 h-28 -rotate-90">
        <circle cx="18" cy="18" r="16" fill="none" stroke="var(--border)" strokeWidth="3" />
        <circle cx="18" cy="18" r="16" fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${score} ${100 - score}`} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{score}%</span>
        <span className="text-[10px] uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>compliant</span>
      </div>
    </div>
  );
}

export default function CompliancePage() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";

  const { data: summary, error: summaryError } = useQuery({
    queryKey: ["compliance-summary"], queryFn: getComplianceSummary, refetchInterval: 60_000,
    // A plan refusal is a settled answer, not a blip — retrying it just delays the
    // explanation and hammers the API.
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });
  // Asked for as "needs attention" rather than fetched-and-filtered: the status is derived
  // from telemetry, so filtering a page in the browser would only ever surface the
  // at-risk devices that happened to land on it.
  const [page, setPage] = useState(1);
  const { data: devices, isFetching } = useQuery({
    queryKey: ["compliance-devices", page],
    queryFn: () => getComplianceDevices({ needs_attention: true, page }),
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
  const { data: banned } = useQuery({ queryKey: ["banned-software"], queryFn: listBannedSoftware });

  const [newBan, setNewBan] = useState("");
  const [banBusy, setBanBusy] = useState(false);
  const [banErr, setBanErr] = useState("");

  async function addBan(e: React.FormEvent) {
    e.preventDefault();
    const name = newBan.trim();
    if (!name) return;
    setBanBusy(true); setBanErr("");
    try {
      await addBannedSoftware(name);
      setNewBan("");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["banned-software"] }),
        qc.invalidateQueries({ queryKey: ["compliance-devices"] }),
        qc.invalidateQueries({ queryKey: ["compliance-summary"] }),
      ]);
    } catch (err) { setBanErr(apiErrorMessage(err, "Couldn't add it.")); }
    finally { setBanBusy(false); }
  }

  async function removeBan(id: string) {
    await removeBannedSoftware(id);
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["banned-software"] }),
      qc.invalidateQueries({ queryKey: ["compliance-devices"] }),
      qc.invalidateQueries({ queryKey: ["compliance-summary"] }),
    ]);
  }

  // Already filtered and ordered by the server.
  const attention = devices?.items ?? [];

  // The page stays in the nav and still opens — hiding it would make ASTRA look like it
  // lacks compliance entirely, which is the opposite of what an upgrade prompt is for.
  if (isUpgradeRequired(summaryError)) {
    return <UpgradeRequired feature={requiredFeature(summaryError)} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <ShieldCheck size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Compliance & Security</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Fleet posture across patching, disk, protection and restricted software
          </p>
        </div>
      </div>

      {/* Hero: score + status counts */}
      <div className="rounded-2xl p-5 flex items-center gap-6 flex-wrap" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <ScoreRing score={summary?.score ?? 100} />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 flex-1 min-w-[280px]">
          {([
            ["compliant", summary?.compliant], ["at_risk", summary?.at_risk],
            ["non_compliant", summary?.non_compliant], ["unknown", summary?.unknown],
          ] as const).map(([key, val]) => (
            <div key={key}>
              <p className="text-2xl font-semibold tabular-nums" style={{ color: STATUS_STYLE[key].color }}>{val ?? 0}</p>
              <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{STATUS_STYLE[key].label}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Per-check breakdown */}
        <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Checks</h2>
          </div>
          <div className="p-5 space-y-3">
            {(summary?.checks ?? []).map((c) => {
              const total = c.passed + c.failed + c.unknown || 1;
              return (
                <div key={c.key}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span style={{ color: "var(--text-primary)" }}>{c.label}</span>
                    <span className="text-xs" style={{ color: c.failed > 0 ? "#ef4444" : "var(--text-secondary)" }}>
                      {c.failed > 0 ? `${c.failed} failing` : "All good"}
                    </span>
                  </div>
                  <div className="flex h-2 rounded-full overflow-hidden" style={{ background: "var(--bg)" }}>
                    <div style={{ width: `${(c.passed / total) * 100}%`, background: "#10b981" }} />
                    <div style={{ width: `${(c.failed / total) * 100}%`, background: "#ef4444" }} />
                    <div style={{ width: `${(c.unknown / total) * 100}%`, background: "#64748b" }} />
                  </div>
                </div>
              );
            })}
            {!summary?.checks?.length && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No devices to evaluate yet.</p>}
          </div>
        </div>

        {/* Restricted software */}
        <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: "var(--border)" }}>
            <Ban size={15} style={{ color: "var(--accent)" }} />
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Restricted software</h2>
          </div>
          <div className="p-5 space-y-3">
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Add apps you don&apos;t allow. Any device with a match fails the “No restricted software” check.
            </p>
            {isAdmin && (
              <form onSubmit={addBan} className="flex gap-2">
                <input value={newBan} onChange={(e) => setNewBan(e.target.value)}
                  placeholder="e.g. uTorrent, TeamViewer…"
                  className="flex-1 px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
                <button type="submit" disabled={banBusy || !newBan.trim()}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
                  <Plus size={15} /> Add
                </button>
              </form>
            )}
            {banErr && <p className="text-xs text-red-500">{banErr}</p>}
            <div className="flex flex-wrap gap-2">
              {(banned ?? []).map((b) => (
                <span key={b.id} className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full"
                  style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }}>
                  {b.name}
                  {isAdmin && <button onClick={() => removeBan(b.id)} title="Remove"><X size={12} /></button>}
                </span>
              ))}
              {!banned?.length && <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Nothing restricted yet.</p>}
            </div>
          </div>
        </div>
      </div>

      {/* Needs attention */}
      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: "var(--border)" }}>
          <ShieldAlert size={15} style={{ color: "#f59e0b" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Needs attention</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Device", "Status", "Score", "Failing checks"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {attention.map((d) => (
                <tr key={d.device_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-5 py-3 font-medium">
                    <Link href={`/devices/${d.device_id}`} className="hover:underline" style={{ color: "var(--accent)" }}>{d.hostname}</Link>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: STATUS_STYLE[d.status].color, background: `${STATUS_STYLE[d.status].color}1a` }}>{STATUS_STYLE[d.status].label}</span>
                  </td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{d.score}%</td>
                  <td className="px-5 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      {d.checks.filter((c) => c.status === "fail").map((c) => (
                        <span key={c.key} className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444" }} title={c.detail}>{c.label}</span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
              {attention.length === 0 && (
                <tr><td colSpan={4} className="px-5 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                  {(summary?.total_devices ?? 0) > 0 ? "Everything looks compliant. 🎉" : "No devices to evaluate yet."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination page={page} onPage={setPage} data={devices} noun="device" busy={isFetching} />
      </div>
    </div>
  );
}
