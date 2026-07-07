import type { DeviceStatus } from "@/lib/api/types";

export function DeviceStatusBadge({ status }: { status: DeviceStatus }) {
  const online = status === "online";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full"
      style={{
        background: online ? "rgba(16,185,129,0.1)" : "rgba(100,116,139,0.1)",
        color: online ? "#10b981" : "#64748b",
      }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: online ? "#10b981" : "#64748b" }} />
      {online ? "Online" : "Offline"}
    </span>
  );
}
