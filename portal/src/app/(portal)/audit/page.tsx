"use client";
import { useQuery } from "@tanstack/react-query";
import { Shield } from "lucide-react";
import { listAuditLogs } from "@/lib/api/audit";

function actionColor(action: string): string {
  if (action.includes("delete") || action.includes("reject")) return "#ef4444";
  if (action.includes("create") || action.includes("approve")) return "#10b981";
  if (action.includes("update") || action.includes("login")) return "#b246d4";
  return "#64748b";
}

export default function AuditPage() {
  const { data: logs, isLoading } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: listAuditLogs,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Shield size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Audit Logs</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Every privileged action taken in your organization
          </p>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["When", "Actor", "Action", "Target", "Details"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={5} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !logs?.length && (
                <tr><td colSpan={5} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>No audit events recorded yet.</td></tr>
              )}
              {logs?.map((l) => (
                <tr key={l.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{new Date(l.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-primary)" }}>{l.actor_email ?? "system"}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: actionColor(l.action), background: `${actionColor(l.action)}1a` }}>
                      {l.action}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {l.target_type}{l.target_id ? ` · ${l.target_id.slice(0, 8)}` : ""}
                  </td>
                  <td className="px-4 py-3 max-w-md truncate font-mono text-xs" style={{ color: "var(--text-secondary)" }}
                    title={l.detail ? JSON.stringify(l.detail) : ""}>
                    {l.detail ? JSON.stringify(l.detail) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
