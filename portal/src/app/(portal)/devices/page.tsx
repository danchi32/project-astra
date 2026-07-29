"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Monitor, Download, Search, X } from "lucide-react";
import { getDevices } from "@/lib/api/dashboard";
import { listAssets } from "@/lib/api/assets";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { formatRam, formatStorage } from "@/lib/utils";
import { ASSET_STATUS_LABELS, ASSET_STATUS_COLORS } from "@/lib/chart-colors";
import type { Device, Asset } from "@/lib/api/types";

// Quote a CSV cell only when it contains a comma, quote or newline (RFC 4180).
function csvCell(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// Every field the report can carry — device telemetry + its linked asset record.
type Field = { key: string; label: string; get: (d: Device, a?: Asset) => unknown };
const FIELDS: Field[] = [
  { key: "hostname", label: "Hostname", get: (d) => d.hostname },
  { key: "serial", label: "Serial number", get: (d) => d.serial_number },
  { key: "user", label: "Logged-in user", get: (d) => d.logged_in_user },
  { key: "online", label: "Online status", get: (d) => (d.status === "online" ? "Online" : "Offline") },
  { key: "os", label: "OS", get: (d) => d.os_version },
  { key: "agent", label: "Agent version", get: (d) => d.agent_version },
  { key: "manufacturer", label: "Manufacturer", get: (d) => d.manufacturer },
  { key: "model", label: "Model", get: (d) => d.model },
  { key: "cpu", label: "CPU", get: (d) => d.cpu_name },
  { key: "ram", label: "RAM", get: (d) => formatRam(d.total_ram_mb) },
  { key: "storage", label: "Storage", get: (d) => formatStorage(d.total_storage_gb) },
  { key: "software", label: "Installed apps", get: (d) => d.installed_app_count },
  { key: "last_seen", label: "Last seen", get: (d) => (d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "") },
  { key: "asset_tag", label: "Asset tag", get: (_d, a) => a?.asset_tag },
  { key: "asset_category", label: "Asset category", get: (_d, a) => a?.category },
  { key: "asset_status", label: "Asset state", get: (_d, a) => (a ? ASSET_STATUS_LABELS[a.status] ?? a.status : "") },
  { key: "assigned_to", label: "Assigned to", get: (_d, a) => a?.assigned_to_name },
  { key: "location", label: "Location", get: (_d, a) => a?.location },
  { key: "purchase_date", label: "Purchase date", get: (_d, a) => a?.purchase_date },
  { key: "warranty", label: "Warranty expiry", get: (_d, a) => a?.warranty_expiry },
  { key: "cost", label: "Cost", get: (_d, a) => a?.purchase_cost },
  { key: "acknowledgement", label: "Acknowledgement", get: (_d, a) => a?.acknowledgement_status },
  { key: "notes", label: "Notes", get: (_d, a) => a?.notes },
];
const DEFAULT_FIELDS = new Set(FIELDS.map((f) => f.key)); // full report by default

function assetState(a?: Asset) {
  if (!a) return null;
  return { label: ASSET_STATUS_LABELS[a.status] ?? a.status, color: ASSET_STATUS_COLORS[a.status] ?? "#64748b" };
}

export default function DevicesPage() {
  const { data: devices, isLoading } = useQuery({
    queryKey: ["devices"],
    queryFn: getDevices,
    refetchInterval: 30_000,
  });
  const { data: assets } = useQuery({ queryKey: ["assets"], queryFn: () => listAssets() });

  // Link each device to its asset record (for state + location + the report).
  const assetByDevice = useMemo(() => {
    const m = new Map<string, Asset>();
    for (const a of assets ?? []) if (a.device_id) m.set(a.device_id, a);
    return m;
  }, [assets]);

  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!devices) return devices;
    if (!q) return devices;
    return devices.filter((d) => {
      const a = assetByDevice.get(d.id);
      return [
        d.hostname, d.serial_number, d.logged_in_user, d.manufacturer, d.model, d.cpu_name, d.os_version,
        a?.location, a ? ASSET_STATUS_LABELS[a.status] : "", a?.assigned_to_name,
      ].some((f) => (f ?? "").toLowerCase().includes(q));
    });
  }, [devices, assetByDevice, q]);

  // Export dialog — pick which columns the CSV report should carry.
  const [exporting, setExporting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set(DEFAULT_FIELDS));
  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }
  function downloadReport() {
    const cols = FIELDS.filter((f) => selected.has(f.key));
    if (!cols.length || !filtered) return;
    const headers = cols.map((c) => c.label);
    const rows = filtered.map((d) => {
      const a = assetByDevice.get(d.id);
      return cols.map((c) => c.get(d, a));
    });
    const csv = [headers, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `astra-devices-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setExporting(false);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Monitor size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Devices</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Asset inventory — click a device for full details, telemetry and actions
          </p>
        </div>
      </div>

      {/* Toolbar: search + export */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search hostname, serial, user, location…"
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>
        <div className="flex items-center gap-3">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {filtered ? `${filtered.length} device${filtered.length === 1 ? "" : "s"}` : ""}
          </p>
          <button
            onClick={() => setExporting(true)}
            disabled={!devices || devices.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            <Download size={15} /> Export report
          </button>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Hostname", "Serial", "User", "Asset state", "Location", "Status"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={6} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>
              )}
              {!isLoading && (!filtered || filtered.length === 0) && (
                <tr><td colSpan={6} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                  {q ? "No devices match your search." : "No devices enrolled yet. Use “Get installer” on the dashboard to add your first endpoint."}
                </td></tr>
              )}
              {filtered?.map((d) => {
                const a = assetByDevice.get(d.id);
                const state = assetState(a);
                return (
                  <tr key={d.id} className="hover:bg-brand-500/5 transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
                    <td className="px-4 py-3 font-medium">
                      <Link href={`/devices/${d.id}`} className="hover:underline" style={{ color: "var(--accent)" }}>
                        {d.hostname}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>{d.serial_number ?? "—"}</td>
                    <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.logged_in_user ?? "—"}</td>
                    <td className="px-4 py-3">
                      {state ? (
                        <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                          style={{ color: state.color, background: `${state.color}1a` }}>{state.label}</span>
                      ) : <span style={{ color: "var(--text-secondary)" }}>—</span>}
                    </td>
                    <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a?.location ?? "—"}</td>
                    <td className="px-4 py-3"><DeviceStatusBadge status={d.status} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Export report — choose which details to include */}
      {exporting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={() => setExporting(false)}>
          <div className="w-full max-w-lg rounded-xl p-5 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between gap-3 mb-1">
              <div>
                <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Export report</h2>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                  Pick the columns to include. Every {filtered?.length ?? 0} device{(filtered?.length ?? 0) === 1 ? "" : "s"} in view is exported, each joined with its asset details (user, location, warranty, cost…).
                </p>
              </div>
              <button onClick={() => setExporting(false)} style={{ color: "var(--text-secondary)" }}><X size={18} /></button>
            </div>

            <div className="flex gap-2 my-3">
              <button onClick={() => setSelected(new Set(FIELDS.map((f) => f.key)))}
                className="text-xs px-2 py-1 rounded-lg" style={{ border: "1px solid var(--border)", color: "var(--accent)" }}>Select all</button>
              <button onClick={() => setSelected(new Set(["hostname"]))}
                className="text-xs px-2 py-1 rounded-lg" style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Clear</button>
            </div>

            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
              {FIELDS.map((f) => (
                <label key={f.key} className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: "var(--text-primary)" }}>
                  <input type="checkbox" checked={selected.has(f.key)} onChange={() => toggle(f.key)} className="accent-brand-500" />
                  {f.label}
                </label>
              ))}
            </div>

            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setExporting(false)}
                className="px-3 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
              <button onClick={downloadReport} disabled={selected.size === 0}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "var(--accent)" }}>
                <Download size={15} /> Download CSV
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
