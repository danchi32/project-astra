"use client";
import { useQuery } from "@tanstack/react-query";
import { getDevices } from "@/lib/api/dashboard";
import { DeviceStatusBadge } from "@/components/device-status-badge";

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
          All enrolled endpoints in your organization
        </p>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Hostname", "Machine ID", "OS Version", "Serial", "User", "Agent", "Status", "Enrolled"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={8} className="px-5 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>
              )}
              {devices?.map((d) => (
                <tr key={d.id} className="hover:bg-blue-500/5 transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-5 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{d.hostname}</td>
                  <td className="px-5 py-3 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{d.machine_id}</td>
                  <td className="px-5 py-3 max-w-[160px] truncate" style={{ color: "var(--text-secondary)" }}>{d.os_version}</td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>{d.serial_number ?? "—"}</td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>{d.logged_in_user ?? "—"}</td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>v{d.agent_version}</td>
                  <td className="px-5 py-3"><DeviceStatusBadge status={d.status} /></td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>
                    {new Date(d.created_at).toLocaleDateString()}
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
