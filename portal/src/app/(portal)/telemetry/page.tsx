"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, DownloadCloud } from "lucide-react";
import { getDevices } from "@/lib/api/dashboard";
import { getMe } from "@/lib/api/auth";
import { createRemediation, approveRemediation } from "@/lib/api/remediation";
import {
  getDeviceTelemetry,
  getDeviceEvents,
  getDeviceApps,
  getDeviceServices,
  getDeviceUpdates,
} from "@/lib/api/device-detail";

type Tab = "events" | "apps" | "services" | "updates";
const TABS: { key: Tab; label: string }[] = [
  { key: "events", label: "Event Log" },
  { key: "apps", label: "Installed Apps" },
  { key: "services", label: "Services" },
  { key: "updates", label: "Windows Updates" },
];

function Gauge({ label, value, sub }: { label: string; value: number; sub: string }) {
  const color = value >= 90 ? "#ef4444" : value >= 70 ? "#f59e0b" : "#10b981";
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="text-xs uppercase tracking-wide mb-2" style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>{value.toFixed(0)}%</p>
      <div className="mt-2 h-1.5 rounded-full" style={{ background: "var(--bg)" }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(value, 100)}%`, background: color }} />
      </div>
      <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>{sub}</p>
    </div>
  );
}

const LEVEL_COLOR: Record<string, string> = {
  Error: "#ef4444",
  Warning: "#f59e0b",
  Information: "#64748b",
};

export default function TelemetryPage() {
  const [deviceId, setDeviceId] = useState<string>("");
  const [tab, setTab] = useState<Tab>("events");

  const { data: devices } = useQuery({ queryKey: ["devices"], queryFn: getDevices });
  const selected = deviceId || devices?.[0]?.id || "";

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";
  const [pushing, setPushing] = useState<string | null>(null);
  const [wuNotice, setWuNotice] = useState("");
  const [wuError, setWuError] = useState("");

  // Push a Windows Update install to the selected device. With a KB it installs just that
  // update; without one it installs all pending. The task is approval-tier — the admin's
  // click both creates and approves it. The elevated agent installs in the background and
  // never auto-reboots.
  async function pushUpdate(kb?: string) {
    const what = kb ? kb : "all pending Windows updates";
    if (!confirm(
      `Install ${what} on this device now?\n\n` +
      `The agent downloads and installs in the background and will NOT reboot — it reports ` +
      `if a restart is needed. Only devices that are online will pick this up.`
    )) return;
    setPushing(kb ?? "__all__"); setWuError(""); setWuNotice("");
    try {
      const task = await createRemediation({
        device_id: selected,
        action_id: "windows_update_install",
        params: kb ? { kb_article_id: kb } : undefined,
      });
      await approveRemediation(task.id);
      setWuNotice(`Queued: ${what} will install shortly (no auto-reboot). Track progress under Self-Healing.`);
    } catch {
      setWuError("Couldn't queue the update. The device may be offline, or you may lack permission.");
    } finally {
      setPushing(null);
    }
  }

  const { data: telemetry } = useQuery({
    queryKey: ["telemetry", selected],
    queryFn: () => getDeviceTelemetry(selected),
    enabled: !!selected,
    refetchInterval: 30_000,
  });
  const { data: events } = useQuery({
    queryKey: ["dev-events", selected], queryFn: () => getDeviceEvents(selected), enabled: !!selected && tab === "events",
  });
  const { data: apps } = useQuery({
    queryKey: ["dev-apps", selected], queryFn: () => getDeviceApps(selected), enabled: !!selected && tab === "apps",
  });
  const { data: services } = useQuery({
    queryKey: ["dev-services", selected], queryFn: () => getDeviceServices(selected), enabled: !!selected && tab === "services",
  });
  const { data: updates } = useQuery({
    queryKey: ["dev-updates", selected], queryFn: () => getDeviceUpdates(selected), enabled: !!selected && tab === "updates",
  });

  const latest = telemetry?.[0];
  const ramPct = latest && latest.ram_total_mb ? (latest.ram_used_mb / latest.ram_total_mb) * 100 : 0;
  const disk = latest?.disks?.[0];
  const diskPct = disk && disk.total_gb ? (disk.used_gb / disk.total_gb) * 100 : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            <Activity size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Telemetry</h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Live metrics and inventory per device
            </p>
          </div>
        </div>
        <select value={selected} onChange={(e) => setDeviceId(e.target.value)}
          className="px-3 py-2 rounded-lg text-sm outline-none"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          {devices?.map((d) => <option key={d.id} value={d.id}>{d.hostname}</option>)}
          {!devices?.length && <option>No devices</option>}
        </select>
      </div>

      {latest ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Gauge label="CPU" value={latest.cpu_percent} sub="Current load" />
          <Gauge label="Memory" value={ramPct} sub={`${(latest.ram_used_mb / 1024).toFixed(1)} / ${(latest.ram_total_mb / 1024).toFixed(1)} GB`} />
          <Gauge label="Disk" value={diskPct} sub={disk ? `${disk.drive} — ${disk.used_gb.toFixed(0)} / ${disk.total_gb.toFixed(0)} GB` : "No disk data"} />
        </div>
      ) : (
        <div className="rounded-xl p-8 text-center text-sm" style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
          No telemetry received for this device yet.
        </div>
      )}

      {latest && (
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Last snapshot: {new Date(latest.collected_at).toLocaleString()}
        </p>
      )}

      {/* Inventory tabs */}
      <div>
        <div className="flex gap-1 border-b" style={{ borderColor: "var(--border)" }}>
          {TABS.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className="px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors"
              style={{
                borderColor: tab === t.key ? "var(--accent)" : "transparent",
                color: tab === t.key ? "var(--accent)" : "var(--text-secondary)",
              }}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "updates" && isAdmin && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs space-y-1">
              {wuNotice && <p style={{ color: "#10b981" }}>{wuNotice}</p>}
              {wuError && <p className="text-red-500">{wuError}</p>}
            </div>
            {(updates?.some((u) => !u.is_installed)) && (
              <button
                onClick={() => pushUpdate()}
                disabled={pushing !== null || !selected}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 shrink-0"
                style={{ background: "var(--accent)" }}>
                <DownloadCloud size={15} /> {pushing === "__all__" ? "Queuing…" : "Install all pending"}
              </button>
            )}
          </div>
        )}

        <div className="rounded-b-xl overflow-hidden mt-3" style={{ border: "1px solid var(--border)" }}>
          <div className="overflow-x-auto max-h-[28rem] overflow-y-auto" style={{ background: "var(--surface)" }}>
            <table className="w-full text-sm whitespace-nowrap">
              {tab === "events" && (
                <>
                  <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Level", "Source", "Event", "Message", "When"].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {events?.map((e) => (
                      <tr key={e.id} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td className="px-4 py-2.5"><span className="text-xs font-medium" style={{ color: LEVEL_COLOR[e.level] ?? "var(--text-secondary)" }}>{e.level}</span></td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-primary)" }}>{e.source}</td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{e.event_id}</td>
                        <td className="px-4 py-2.5 max-w-md truncate" style={{ color: "var(--text-secondary)" }} title={e.message}>{e.message}</td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{new Date(e.occurred_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </>
              )}
              {tab === "apps" && (
                <>
                  <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Name", "Version", "Publisher", "Installed"].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {apps?.map((a) => (
                      <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{a.name}</td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{a.version ?? "—"}</td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{a.publisher ?? "—"}</td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{a.install_date ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </>
              )}
              {tab === "services" && (
                <>
                  <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Display Name", "Name", "Status", "Startup"].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {services?.map((s) => (
                      <tr key={s.id} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{s.display_name}</td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{s.name}</td>
                        <td className="px-4 py-2.5"><span className="text-xs font-medium" style={{ color: s.status === "Running" ? "#10b981" : "#64748b" }}>{s.status}</span></td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{s.start_type}</td>
                      </tr>
                    ))}
                  </tbody>
                </>
              )}
              {tab === "updates" && (
                <>
                  <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["KB", "Title", "Status", "Installed On"].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase" style={{ color: "var(--text-secondary)" }}>{h}</th>
                    ))}
                    {isAdmin && <th className="px-4 py-2.5 text-right text-xs font-medium uppercase" style={{ color: "var(--text-secondary)" }}>Action</th>}
                  </tr></thead>
                  <tbody>
                    {updates?.map((u) => (
                      <tr key={u.id} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{u.kb_article_id}</td>
                        <td className="px-4 py-2.5 max-w-lg truncate" style={{ color: "var(--text-secondary)" }} title={u.title}>{u.title}</td>
                        <td className="px-4 py-2.5"><span className="text-xs font-medium" style={{ color: u.is_installed ? "#10b981" : "#f59e0b" }}>{u.is_installed ? "Installed" : "Pending"}</span></td>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{u.installed_on ?? "—"}</td>
                        {isAdmin && (
                          <td className="px-4 py-2.5 text-right">
                            {!u.is_installed && u.kb_article_id && (
                              <button
                                onClick={() => pushUpdate(u.kb_article_id)}
                                disabled={pushing !== null}
                                title={`Install ${u.kb_article_id} on this device`}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
                                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--accent)" }}>
                                <DownloadCloud size={13} /> {pushing === u.kb_article_id ? "Queuing…" : "Install"}
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </>
              )}
            </table>
            {((tab === "events" && !events?.length) ||
              (tab === "apps" && !apps?.length) ||
              (tab === "services" && !services?.length) ||
              (tab === "updates" && !updates?.length)) && (
              <p className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-secondary)" }}>No data collected yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
