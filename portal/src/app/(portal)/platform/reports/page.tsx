"use client";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getPlatformBilling, getPlatformReports } from "@/lib/api/platform";

const card = { background: "var(--surface)", border: "1px solid var(--border)" } as const;

function csvCell(v: unknown): string {
  const s = String(v ?? "");
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadCsv(filename: string, headers: string[], rows: unknown[][]) {
  const csv = [headers, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl p-4" style={card}>
      <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{value}</p>
      {sub && <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{sub}</p>}
    </div>
  );
}

export default function PlatformReportsPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const enabled = !!me?.is_platform_admin;
  const { data: reports } = useQuery({ queryKey: ["platform-reports"], queryFn: getPlatformReports, enabled });
  const { data: billing } = useQuery({ queryKey: ["platform-billing"], queryFn: getPlatformBilling, enabled });

  if (me && !me.is_platform_admin) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Platform administrator access required.</p>;
  }

  const today = new Date().toISOString().slice(0, 10);
  const maxSignups = Math.max(1, ...(reports?.signups_by_month ?? []).map((m) => m.count));

  function exportOrgs() {
    if (!billing) return;
    downloadCsv(`astra-organizations-${today}.csv`,
      ["Organization", "Status", "Provider", "Licenses", "Discount %", "Seat price (cents)", "MRR (cents)", "Renews", "Trial ends", "Created"],
      billing.rows.map((r) => [
        r.name, r.subscription_status, r.billing_provider ?? "", r.license_count,
        r.discount_percent ?? "", r.seat_price_cents ?? "", r.mrr_cents ?? "",
        r.current_period_end ?? "", r.trial_ends_at ?? "", r.created_at,
      ]));
  }
  function exportFleet() {
    if (!reports) return;
    downloadCsv(`astra-fleet-${today}.csv`,
      ["Organization", "Devices", "Online"],
      reports.devices_by_org.map((s) => [s.org_name, s.devices, s.online]));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
            <BarChart3 size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Reports</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Growth, self-healing outcomes and fleet analytics across every organization
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={exportOrgs} disabled={!billing}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ ...card, color: "var(--text-primary)" }}>
            <Download size={14} /> Organizations CSV
          </button>
          <button onClick={exportFleet} disabled={!reports}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ ...card, color: "var(--text-primary)" }}>
            <Download size={14} /> Fleet CSV
          </button>
        </div>
      </div>

      {/* Self-healing outcomes */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <Stat label="Fixes (30d)" value={reports?.remediation_total_30d ?? "…"} />
        <Stat label="Succeeded" value={reports?.remediation_succeeded_30d ?? "…"} />
        <Stat label="Failed" value={reports?.remediation_failed_30d ?? "…"} />
        <Stat label="Success rate" value={reports?.remediation_success_rate != null ? `${reports.remediation_success_rate}%` : "—"} />
        <Stat label="AI chats (30d)" value={reports?.conversations_30d ?? "…"} sub={`${reports?.messages_30d ?? 0} messages`} />
        <Stat label="Devices online" value={reports ? `${reports.online_devices}/${reports.total_devices}` : "…"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Signups trend */}
        <div className="rounded-xl p-5" style={card}>
          <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Organization sign-ups — last 12 months</h2>
          <div className="flex items-end gap-1.5 h-32">
            {(reports?.signups_by_month ?? []).map((m) => (
              <div key={m.month} className="flex-1 flex flex-col items-center gap-1" title={`${m.month}: ${m.count}`}>
                <span className="text-[10px] tabular-nums" style={{ color: "var(--text-secondary)" }}>{m.count || ""}</span>
                <div className="w-full rounded-t"
                  style={{ height: `${Math.max(3, (m.count / maxSignups) * 100)}%`, background: "var(--accent)", opacity: m.count ? 1 : 0.15 }} />
                <span className="text-[9px]" style={{ color: "var(--text-secondary)" }}>{m.month.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Top fixes */}
        <div className="rounded-xl p-5" style={card}>
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Most-applied fixes (30d)</h2>
          {reports && reports.top_actions_30d.length === 0 && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No self-healing activity in the last 30 days.</p>
          )}
          <ul className="space-y-2">
            {reports?.top_actions_30d.map((a) => {
              const max = reports.top_actions_30d[0]?.count || 1;
              return (
                <li key={a.action_id} className="text-sm">
                  <div className="flex items-center justify-between mb-0.5">
                    <span style={{ color: "var(--text-primary)" }}>{a.label}</span>
                    <span className="tabular-nums" style={{ color: "var(--text-secondary)" }}>{a.count}</span>
                  </div>
                  <div className="h-1.5 rounded-full" style={{ background: "var(--bg)" }}>
                    <div className="h-full rounded-full" style={{ width: `${(a.count / max) * 100}%`, background: "var(--accent)" }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      {/* Fleet by organization */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="px-5 py-3" style={{ ...card, borderBottom: "1px solid var(--border)" }}>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Fleet by organization</h2>
        </div>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Organization", "Devices", "Online", "Online %"].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {reports?.devices_by_org.map((s) => (
                <tr key={s.org_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{s.org_name}</td>
                  <td className="px-4 py-2.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>{s.devices}</td>
                  <td className="px-4 py-2.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>{s.online}</td>
                  <td className="px-4 py-2.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {s.devices ? Math.round((s.online / s.devices) * 100) : 0}%
                  </td>
                </tr>
              ))}
              {reports && reports.devices_by_org.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>No devices enrolled anywhere yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
