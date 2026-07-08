"use client";
import { useQuery } from "@tanstack/react-query";
import { getDevices } from "@/lib/api/dashboard";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { formatRam, formatStorage } from "@/lib/utils";

export default function DevicesPage() {
  const { data: devices, isLoading } = useQuery({
    queryKey: ["devices"],
    queryFn: getDevices,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Devices</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
          Asset inventory — all enrolled endpoints in your organization
        </p>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Hostname", "Brand / Model", "Serial", "CPU", "RAM", "Storage", "Software", "User", "Status"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={9} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>
              )}
              {!isLoading && (!devices || devices.length === 0) && (
                <tr><td colSpan={9} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                  No devices enrolled yet.
                </td></tr>
              )}
              {devices?.map((d) => (
                <tr key={d.id} className="hover:bg-blue-500/5 transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>
                    {d.hostname}
                    <div className="text-xs font-normal" style={{ color: "var(--text-secondary)" }}>{d.os_version}</div>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>
                    {d.manufacturer || d.model ? (
                      <>
                        <div style={{ color: "var(--text-primary)" }}>{d.manufacturer ?? "—"}</div>
                        <div className="text-xs">{d.model ?? ""}</div>
                      </>
                    ) : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{d.serial_number ?? "—"}</td>
                  <td className="px-4 py-3 max-w-[200px] truncate text-xs" style={{ color: "var(--text-secondary)" }} title={d.cpu_name ?? ""}>{d.cpu_name ?? "—"}</td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatRam(d.total_ram_mb)}</td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatStorage(d.total_storage_gb)}</td>
                  <td className="px-4 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {d.installed_app_count > 0 ? `${d.installed_app_count} apps` : "—"}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.logged_in_user ?? "—"}</td>
                  <td className="px-4 py-3"><DeviceStatusBadge status={d.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
