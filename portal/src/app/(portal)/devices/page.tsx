"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Monitor, Download, Copy, Check, RefreshCw, Trash2,
} from "lucide-react";
import { getDevices } from "@/lib/api/dashboard";
import { getMe } from "@/lib/api/auth";
import { getInstaller, rotateEnrollmentKey, downloadOfflineInstaller, downloadUninstaller, deleteDevice } from "@/lib/api/devices";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { formatRam, formatStorage } from "@/lib/utils";
import type { Device } from "@/lib/api/types";

// Quote a CSV cell only when it contains a comma, quote or newline (RFC 4180).
function csvCell(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function exportDevicesCsv(devices: Device[]) {
  const headers = [
    "Hostname", "OS", "Manufacturer", "Model", "Serial", "CPU",
    "RAM (MB)", "Storage (GB)", "Installed apps", "Logged-in user", "Status", "Last seen",
  ];
  const rows = devices.map((d) => [
    d.hostname, d.os_version, d.manufacturer, d.model, d.serial_number, d.cpu_name,
    d.total_ram_mb, d.total_storage_gb, d.installed_app_count, d.logged_in_user,
    d.status, d.last_seen_at,
  ]);
  const csv = [headers, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `astra-devices-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      className="p-1.5 rounded-lg" title="Copy"
      style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
      {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
    </button>
  );
}

function InstallAgentPanel() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [offlineBusy, setOfflineBusy] = useState(false);
  const [uninstallBusy, setUninstallBusy] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const { data: installer, isLoading } = useQuery({
    queryKey: ["installer"],
    queryFn: getInstaller,
    enabled: open,
  });

  const runCmd = "powershell -ExecutionPolicy Bypass -File .\\Install-AstraAgent.ps1";

  async function downloadOffline() {
    setOfflineBusy(true); setError("");
    try {
      await downloadOfflineInstaller();
    } catch {
      setError("Couldn't build the portable installer. Try again.");
    } finally { setOfflineBusy(false); }
  }

  async function downloadUninstall() {
    setUninstallBusy(true); setError("");
    try {
      await downloadUninstaller();
    } catch {
      setError("Couldn't download the uninstaller. Try again.");
    } finally { setUninstallBusy(false); }
  }

  async function rotate() {
    if (!confirm(
      "Rotate this organization's enrollment key?\n\nInstallers you've already distributed will stop enrolling new machines — you'll need to re-download. Already-enrolled devices keep working."
    )) return;
    setRotating(true); setError(""); setNotice("");
    try {
      const next = await rotateEnrollmentKey();
      queryClient.setQueryData(["installer"], next);
      setNotice("Key rotated. Re-download the installer for any new machines.");
    } catch {
      setError("Couldn't rotate the key. Try again.");
    } finally { setRotating(false); }
  }

  return (
    <div className="rounded-xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg shrink-0" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
            <Download size={18} />
          </div>
          <div>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Install the ASTRA agent</h2>
            <p className="text-xs mt-0.5 max-w-xl" style={{ color: "var(--text-secondary)" }}>
              Download your organization&apos;s installer and run it on any Windows machine. Your enrollment
              key is already built in — no tokens, nothing to type. Devices appear here within a minute.
            </p>
          </div>
        </div>
        {!open && (
          <button onClick={() => setOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white shrink-0"
            style={{ background: "var(--accent)" }}>
            <Download size={16} /> Get installer
          </button>
        )}
      </div>

      {open && (
        <div className="mt-4 space-y-3 max-w-xl">
          {error && <p className="text-sm text-red-500">{error}</p>}
          {notice && <p className="text-sm" style={{ color: "#10b981" }}>{notice}</p>}
          {isLoading && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Preparing your installer…</p>}

          {installer && (
            <>
              {/* Step 1 — download */}
              <div className="rounded-lg p-3" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>
                  1. On the target Windows machine, download the installer
                </p>
                <div className="flex flex-wrap gap-2">
                  <button onClick={downloadOffline} disabled={offlineBusy}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                    style={{ background: "var(--accent)" }}>
                    <Download size={15} /> {offlineBusy ? "Preparing…" : "Download installer (.zip)"}
                  </button>
                </div>
                <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>
                  Your server URL and enrollment key are already baked in — nothing to type. Extract the
                  .zip and double-click <span className="font-mono">Install.bat</span> (or run the command below).
                </p>
              </div>

              {/* Step 2 — run */}
              <div className="rounded-lg p-3 space-y-2" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                  2. Right-click → <span className="font-semibold">Run with PowerShell</span> (approve the prompt), or run:
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs font-mono px-2 py-1.5 rounded truncate" style={{ background: "var(--surface)", color: "var(--text-primary)" }}>{runCmd}</code>
                  <CopyButton text={runCmd} />
                </div>
                <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  The device enrolls automatically and appears under Devices within a minute.
                </p>
              </div>

              {/* Enrollment key + rotate */}
              <div className="rounded-lg p-3 space-y-2" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Organization enrollment key (permanent)</p>
                  <button onClick={rotate} disabled={rotating}
                    className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg disabled:opacity-50"
                    style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "#f59e0b" }}>
                    <RefreshCw size={12} /> {rotating ? "Rotating…" : "Rotate key"}
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs font-mono px-2 py-1.5 rounded truncate" style={{ background: "var(--surface)", color: "var(--text-primary)" }}>{installer.enrollment_key}</code>
                  <CopyButton text={installer.enrollment_key} />
                </div>
                <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Never expires. Rotate only if an installer leaks — old installers stop working; already-enrolled devices are unaffected.
                </p>
              </div>

              {/* Uninstaller — separate download, not part of the installer bundle */}
              <div className="rounded-lg p-3" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Remove the agent from a machine</p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                      Extract and double-click <span className="font-mono">Uninstall-AstraAgent.bat</span> (self-elevates).
                    </p>
                  </div>
                  <button onClick={downloadUninstall} disabled={uninstallBusy}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium shrink-0 disabled:opacity-50"
                    style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    <Download size={15} /> {uninstallBusy ? "Preparing…" : "Uninstaller"}
                  </button>
                </div>
              </div>

              <button onClick={() => setOpen(false)}
                className="px-3 py-2 rounded-lg text-sm font-medium"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Done</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function DevicesPage() {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: devices, isLoading } = useQuery({
    queryKey: ["devices"],
    queryFn: getDevices,
    refetchInterval: 30_000,
  });
  const isAdmin = me?.role === "admin";
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function removeDevice(d: Device) {
    if (!confirm(
      `Remove "${d.hostname}" from the portal?\n\n` +
      `This permanently deletes the device and its telemetry history and cannot be undone. ` +
      `Uninstalling the agent alone only marks it OFFLINE. ` +
      `If the agent is still installed and running, the device will re-enroll and reappear.`
    )) return;
    setDeletingId(d.id);
    try {
      await deleteDevice(d.id);
      await queryClient.invalidateQueries({ queryKey: ["devices"] });
    } catch {
      alert("Couldn't remove the device. Please try again.");
    } finally {
      setDeletingId(null);
    }
  }

  const colCount = isAdmin ? 10 : 9;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(154,47,187,0.1)", color: "var(--accent)" }}>
          <Monitor size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Devices</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Asset inventory — all enrolled endpoints in your organization
          </p>
        </div>
      </div>

      {isAdmin && <InstallAgentPanel />}

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          {devices ? `${devices.length} device${devices.length === 1 ? "" : "s"}` : ""}
        </p>
        <button
          onClick={() => devices && exportDevicesCsv(devices)}
          disabled={!devices || devices.length === 0}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          <Download size={15} /> Export CSV
        </button>
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
                {isAdmin && (
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>Actions</th>
                )}
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={colCount} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>
              )}
              {!isLoading && (!devices || devices.length === 0) && (
                <tr><td colSpan={colCount} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                  No devices enrolled yet. {isAdmin ? "Use “Install agent” above to add your first endpoint." : ""}
                </td></tr>
              )}
              {devices?.map((d) => (
                <tr key={d.id} className="hover:bg-brand-500/5 transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
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
                  {isAdmin && (
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => removeDevice(d)}
                        disabled={deletingId === d.id}
                        title="Remove device from portal"
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
                        style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#ef4444" }}>
                        <Trash2 size={13} /> {deletingId === d.id ? "Removing…" : "Remove"}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
