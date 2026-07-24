"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getPlatformAudit } from "@/lib/api/platform";

// platform.view_as → "View as", platform.organization.create → "Organization create"
function prettyAction(action: string): string {
  const stripped = action.replace(/^platform\./, "").replace(/[._]/g, " ");
  return stripped.charAt(0).toUpperCase() + stripped.slice(1);
}

function prettyDetail(detail: Record<string, unknown> | null): string {
  if (!detail) return "—";
  return Object.entries(detail).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ") || "—";
}

export default function PlatformAuditPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: entries, isLoading } = useQuery({
    queryKey: ["platform-audit"],
    queryFn: () => getPlatformAudit(200),
    enabled: !!me?.is_platform_admin,
  });

  if (me && !me.is_platform_admin) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Platform administrator access required.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <ScrollText size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Audit trail</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Every platform-operator action, across all organizations
          </p>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["When", "Action", "Organization", "Operator", "Detail"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={5} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {entries?.map((e) => (
                <tr key={e.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{new Date(e.created_at).toLocaleString()}</td>
                  <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{prettyAction(e.action)}</td>
                  <td className="px-4 py-2.5">
                    {e.org_name
                      ? <Link href={`/platform/${e.org_id}`} className="hover:underline" style={{ color: "var(--accent)" }}>{e.org_name}</Link>
                      : <span style={{ color: "var(--text-secondary)" }}>(deleted)</span>}
                  </td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{e.actor_email ?? "system"}</td>
                  <td className="px-4 py-2.5 max-w-[360px] truncate" style={{ color: "var(--text-secondary)" }} title={prettyDetail(e.detail)}>
                    {prettyDetail(e.detail)}
                  </td>
                </tr>
              ))}
              {entries && entries.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No operator actions recorded yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
