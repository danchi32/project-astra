"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Check, X, Zap } from "lucide-react";
import { listRemediations, approveRemediation, rejectRemediation } from "@/lib/api/remediation";
import type { RemediationStatus, RemediationTier, RemediationTask } from "@/lib/api/types";

const TIER_STYLE: Record<RemediationTier, { label: string; color: string; bg: string }> = {
  automatic: { label: "Automatic", color: "#10b981", bg: "rgba(16,185,129,0.1)" },
  approval_required: { label: "Approval required", color: "#f59e0b", bg: "rgba(245,158,11,0.1)" },
  admin_only: { label: "Admin only", color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
};

const STATUS_STYLE: Record<RemediationStatus, { color: string; bg: string }> = {
  pending_approval: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)" },
  approved: { color: "#b246d4", bg: "rgba(59,130,246,0.1)" },
  dispatched: { color: "#8b5cf6", bg: "rgba(139,92,246,0.1)" },
  succeeded: { color: "#10b981", bg: "rgba(16,185,129,0.1)" },
  failed: { color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  rejected: { color: "#64748b", bg: "rgba(100,116,139,0.1)" },
};

export default function SelfHealingPage() {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);

  const { data: tasks, isLoading } = useQuery({
    queryKey: ["remediations"],
    queryFn: listRemediations,
    refetchInterval: 10_000,
  });

  async function act(id: string, action: "approve" | "reject") {
    setBusy(id);
    try {
      await (action === "approve" ? approveRemediation(id) : rejectRemediation(id));
      await queryClient.invalidateQueries({ queryKey: ["remediations"] });
    } catch {
      // A 403 means your role can't approve this tier; the list will refresh unchanged.
      await queryClient.invalidateQueries({ queryKey: ["remediations"] });
    } finally {
      setBusy(null);
    }
  }

  const pending = tasks?.filter((t) => t.status === "pending_approval") ?? [];
  const history = tasks?.filter((t) => t.status !== "pending_approval") ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Zap size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Self Healing</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Automatic fixes run on their own; higher-risk fixes wait for your approval
          </p>
        </div>
      </div>

      {/* Pending approvals */}
      <div>
        <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
          Awaiting approval {pending.length > 0 && <span style={{ color: "var(--accent)" }}>({pending.length})</span>}
        </h2>
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
            <table className="w-full text-sm whitespace-nowrap">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Fix", "Device", "Tier", "Reason", "Source", ""].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                      style={{ color: "var(--text-secondary)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pending.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                    Nothing waiting for approval.
                  </td></tr>
                )}
                {pending.map((t) => (
                  <tr key={t.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{t.action_label ?? t.action_id}</td>
                    <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{t.device_hostname ?? "—"}</td>
                    <td className="px-4 py-3"><TierBadge tier={t.tier} /></td>
                    <td className="px-4 py-3 max-w-[240px] truncate" style={{ color: "var(--text-secondary)" }} title={t.reason}>{t.reason}</td>
                    <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{t.source === "assistant" ? "AI" : "Staff"}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex gap-2 justify-end">
                        <button onClick={() => act(t.id, "approve")} disabled={busy === t.id}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-white disabled:opacity-50"
                          style={{ background: "#10b981" }}>
                          <Check size={13} /> Approve
                        </button>
                        <button onClick={() => act(t.id, "reject")} disabled={busy === t.id}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium disabled:opacity-50"
                          style={{ background: "var(--bg)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                          <X size={13} /> Reject
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* History */}
      <div>
        <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Remediation history</h2>
        <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
            <table className="w-full text-sm whitespace-nowrap">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Fix", "Device", "Tier", "Status", "Result", "When"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                      style={{ color: "var(--text-secondary)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>
                )}
                {!isLoading && history.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>No remediations yet.</td></tr>
                )}
                {history.map((t) => (
                  <tr key={t.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{t.action_label ?? t.action_id}</td>
                    <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{t.device_hostname ?? "—"}</td>
                    <td className="px-4 py-3"><TierBadge tier={t.tier} /></td>
                    <td className="px-4 py-3"><StatusBadge status={t.status} /></td>
                    <td className="px-4 py-3 max-w-[280px] truncate" style={{ color: "var(--text-secondary)" }} title={t.result?.output ?? ""}>{t.result?.output ?? "—"}</td>
                    <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{new Date(t.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function TierBadge({ tier }: { tier: RemediationTier }) {
  const s = TIER_STYLE[tier];
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{ color: s.color, background: s.bg }}>
      {s.label}
    </span>
  );
}

function StatusBadge({ status }: { status: RemediationStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full capitalize" style={{ color: s.color, background: s.bg }}>
      {status.replace("_", " ")}
    </span>
  );
}
