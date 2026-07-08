"use client";
import { useQuery } from "@tanstack/react-query";
import { Monitor, Wifi, WifiOff, AlertTriangle, RefreshCw, Cpu, MemoryStick } from "lucide-react";
import { getDashboardSummary, getDevices } from "@/lib/api/dashboard";
import { StatCard } from "@/components/stat-card";
import { Gauge } from "@/components/gauge";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { formatRam, formatStorage } from "@/lib/utils";

export default function DashboardPage() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: getDashboardSummary,
    refetchInterval: 30_000,
  });

  const { data: devices, isLoading: devicesLoading } = useQuery({
    queryKey: ["devices"],
    queryFn: getDevices,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Dashboard
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
          Real-time overview of your IT environment
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Devices"
          value={summaryLoading ? "—" : (summary?.total_devices ?? 0)}
          icon={Monitor}
        />
        <StatCard
          title="Online"
          value={summaryLoading ? "—" : (summary?.online_devices ?? 0)}
          icon={Wifi}
          variant="success"
        />
        <StatCard
          title="Critical Events"
          value={summaryLoading ? "—" : (summary?.critical_event_count ?? 0)}
          icon={AlertTriangle}
          variant={summary && summary.critical_event_count > 0 ? "danger" : "default"}
        />
        <StatCard
          title="Pending Updates"
          value={summaryLoading ? "—" : (summary?.pending_update_count ?? 0)}
          icon={RefreshCw}
          variant={summary && summary.pending_update_count > 5 ? "warning" : "default"}
        />
      </div>

      {/* Gauges */}
      <div className="grid grid-cols-2 gap-4">
        <Gauge label="Avg CPU" value={summary?.avg_cpu_percent ?? 0} />
        <Gauge label="Avg RAM" value={summary?.avg_ram_percent ?? 0} />
      </div>

      {/* Devices table */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="px-5 py-4 flex items-center justify-between" style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Devices</h2>
          <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {devices?.length ?? 0} total
          </span>
        </div>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Hostname", "Brand / Model", "RAM", "Storage", "Software", "User", "Status"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {devicesLoading && (
                <tr><td colSpan={7} className="px-5 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>
              )}
              {!devicesLoading && (!devices || devices.length === 0) && (
                <tr><td colSpan={7} className="px-5 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                  No devices enrolled yet. Create an enrollment token and run the Windows agent.
                </td></tr>
              )}
              {devices?.map((d) => (
                <tr key={d.id} className="transition-colors hover:bg-blue-500/5" style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-5 py-3 font-medium" style={{ color: "var(--text-primary)" }}>
                    {d.hostname}
                    <div className="text-xs font-normal max-w-[160px] truncate" style={{ color: "var(--text-secondary)" }} title={d.os_version}>{d.os_version}</div>
                  </td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>
                    {d.manufacturer ?? "—"}{d.model ? ` ${d.model}` : ""}
                  </td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatRam(d.total_ram_mb)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatStorage(d.total_storage_gb)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{d.installed_app_count > 0 ? d.installed_app_count : "—"}</td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>{d.logged_in_user ?? "—"}</td>
                  <td className="px-5 py-3"><DeviceStatusBadge status={d.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
