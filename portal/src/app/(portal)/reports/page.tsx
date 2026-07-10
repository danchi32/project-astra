"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download, HardDrive, Wrench, Package } from "lucide-react";
import {
  getFleetHealthReport, getRemediationReport, getAssetReport,
  exportFleetHealthCsv, exportRemediationCsv, exportAssetsCsv,
} from "@/lib/api/reports";

type Tab = "fleet" | "remediation" | "assets";

const TABS: { key: Tab; label: string; icon: typeof HardDrive }[] = [
  { key: "fleet", label: "Fleet health", icon: HardDrive },
  { key: "remediation", label: "Remediation", icon: Wrench },
  { key: "assets", label: "Assets", icon: Package },
];

function Card({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="text-2xl font-semibold mt-1" style={{ color: accent ?? "var(--text-primary)" }}>{value}</p>
    </div>
  );
}

function ExportButton({ onExport }: { onExport: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      onClick={async () => { setBusy(true); try { await onExport(); } finally { setBusy(false); } }}
      disabled={busy}
      className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
      style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
    >
      <Download size={14} /> {busy ? "Exporting…" : "Export CSV"}
    </button>
  );
}

function FleetHealthTab() {
  const { data, isLoading } = useQuery({ queryKey: ["report-fleet-health"], queryFn: getFleetHealthReport });
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ExportButton onExport={exportFleetHealthCsv} /></div>
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Devices" value={String(data.total_devices)} />
          <Card label="Online" value={String(data.online_devices)} accent="#10b981" />
          <Card label="Avg CPU" value={`${data.avg_cpu_percent}%`} />
          <Card label="Avg RAM" value={`${data.avg_ram_percent}%`} />
          <Card label="Critical events" value={String(data.total_critical_events)}
            accent={data.total_critical_events > 0 ? "#ef4444" : undefined} />
          <Card label="Pending updates" value={String(data.total_pending_updates)}
            accent={data.total_pending_updates > 0 ? "#f59e0b" : undefined} />
        </div>
      )}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Hostname", "Status", "CPU", "RAM", "Disk free (min)", "Critical events", "Pending updates", "Last seen"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={8} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !data?.devices.length && (
                <tr><td colSpan={8} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No devices enrolled yet.</td></tr>
              )}
              {data?.devices.map((d) => (
                <tr key={d.device_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{d.hostname}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: d.status === "online" ? "#10b981" : "#64748b", background: d.status === "online" ? "#10b9811a" : "#64748b1a" }}>
                      {d.status === "online" ? "Online" : "Offline"}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.cpu_percent != null ? `${d.cpu_percent}%` : "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.ram_percent != null ? `${d.ram_percent}%` : "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.disk_free_percent_min != null ? `${d.disk_free_percent_min}%` : "—"}</td>
                  <td className="px-4 py-3" style={{ color: d.critical_event_count > 0 ? "#ef4444" : "var(--text-secondary)" }}>{d.critical_event_count}</td>
                  <td className="px-4 py-3" style={{ color: d.pending_update_count > 0 ? "#f59e0b" : "var(--text-secondary)" }}>{d.pending_update_count}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const PERIODS = [7, 30, 90];

function RemediationTab() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery({
    queryKey: ["report-remediation", days],
    queryFn: () => getRemediationReport(days),
  });
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          {PERIODS.map((p) => (
            <button key={p} onClick={() => setDays(p)}
              className="px-3 py-1.5 rounded-md text-sm font-medium"
              style={days === p
                ? { background: "var(--accent)", color: "white" }
                : { color: "var(--text-secondary)" }}>
              Last {p}d
            </button>
          ))}
        </div>
        <ExportButton onExport={() => exportRemediationCsv(days)} />
      </div>
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Total tasks" value={String(data.total_tasks)} />
          <Card label="Succeeded" value={String(data.succeeded)} accent="#10b981" />
          <Card label="Failed" value={String(data.failed)} accent={data.failed > 0 ? "#ef4444" : undefined} />
          <Card label="Success rate" value={`${data.success_rate}%`} />
        </div>
      )}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Device", "Action", "Tier", "Status", "Source", "Created", "Completed"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={7} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !data?.tasks.length && (
                <tr><td colSpan={7} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No remediation activity in this period.</td></tr>
              )}
              {data?.tasks.map((t) => (
                <tr key={t.task_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{t.device_hostname ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{t.action_id}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{t.tier.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{t.status.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{t.source}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{new Date(t.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{t.completed_at ? new Date(t.completed_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function AssetsTab() {
  const { data, isLoading } = useQuery({ queryKey: ["report-assets"], queryFn: getAssetReport });
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ExportButton onExport={exportAssetsCsv} /></div>
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Total assets" value={String(data.summary.total)} />
          <Card label="Total value" value={data.summary.total_value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 })} />
          <Card label="In repair" value={String(data.summary.by_status["in_repair"] ?? 0)} accent="#f59e0b" />
          <Card label="Warranty <60d" value={String(data.summary.warranty_expiring_soon)}
            accent={data.summary.warranty_expiring_soon > 0 ? "#ef4444" : undefined} />
        </div>
      )}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Tag", "Name", "Category", "Status", "Assigned to", "Value", "Warranty"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={7} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !data?.assets.length && (
                <tr><td colSpan={7} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>No assets registered yet.</td></tr>
              )}
              {data?.assets.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.asset_tag ?? "—"}</td>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{a.name}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{a.category}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{a.status.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.assigned_to_name ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.purchase_cost != null ? a.purchase_cost.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }) : "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.warranty_expiry ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const [tab, setTab] = useState<Tab>("fleet");
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <BarChart3 size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Reports</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Fleet health, remediation activity and asset register — exportable to CSV
          </p>
        </div>
      </div>

      <div className="flex gap-1 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px"
            style={tab === key
              ? { borderColor: "var(--accent)", color: "var(--accent)" }
              : { borderColor: "transparent", color: "var(--text-secondary)" }}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {tab === "fleet" && <FleetHealthTab />}
      {tab === "remediation" && <RemediationTab />}
      {tab === "assets" && <AssetsTab />}
    </div>
  );
}
