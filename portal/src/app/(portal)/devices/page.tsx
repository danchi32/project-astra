"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Monitor, Download, Trash2, UserX, X, Search,
} from "lucide-react";
import { getDevices } from "@/lib/api/dashboard";
import { getMe } from "@/lib/api/auth";
import { deleteDevice } from "@/lib/api/devices";
import { createRemediation, approveRemediation } from "@/lib/api/remediation";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { formatRam, formatStorage, apiErrorMessage } from "@/lib/utils";
import type { Device } from "@/lib/api/types";

// Quote a CSV cell only when it contains a comma, quote or newline (RFC 4180).
function csvCell(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function exportDevicesCsv(devices: Device[]) {
  const headers = [
    "Hostname", "OS", "Agent version", "Manufacturer", "Model", "Serial", "CPU",
    "RAM (MB)", "Storage (GB)", "Installed apps", "Logged-in user", "Status", "Last seen",
  ];
  const rows = devices.map((d) => [
    d.hostname, d.os_version, d.agent_version, d.manufacturer, d.model, d.serial_number, d.cpu_name,
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
  const [query, setQuery] = useState("");

  const q = query.trim().toLowerCase();
  const filtered = !q ? devices : devices?.filter((d) =>
    [d.hostname, d.manufacturer, d.model, d.serial_number, d.cpu_name, d.logged_in_user, d.os_version]
      .some((f) => (f ?? "").toLowerCase().includes(q)));

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

  // Secure offboarding: disable / re-enable a device's LOCAL Windows account.
  const [lockTarget, setLockTarget] = useState<Device | null>(null);
  const [lockUser, setLockUser] = useState("");
  const [lockConfirm, setLockConfirm] = useState("");
  const [lockBusy, setLockBusy] = useState(false);
  const [lockMsg, setLockMsg] = useState<{ ok: boolean; text: string } | null>(null);

  function openLock(d: Device) {
    setLockTarget(d);
    // Devices report the user as "DOMAIN\\user"; prefill just the account name.
    setLockUser((d.logged_in_user ?? "").split("\\").pop() ?? "");
    setLockConfirm("");
    setLockMsg(null);
  }

  async function runLock(enable: boolean) {
    if (!lockTarget) return;
    const user = lockUser.trim();
    if (!user) { setLockMsg({ ok: false, text: "Enter the local Windows account name." }); return; }
    if (!enable && lockConfirm.trim() !== lockTarget.hostname) {
      setLockMsg({ ok: false, text: `Type the device name "${lockTarget.hostname}" to confirm.` });
      return;
    }
    setLockBusy(true); setLockMsg(null);
    try {
      const task = await createRemediation({
        device_id: lockTarget.id,
        action_id: enable ? "enable_local_account" : "disable_local_account",
        params: { username: user },
        reason: enable
          ? `Re-enable local account "${user}" (offboarding)`
          : `Disable local account "${user}" and sign out (offboarding)`,
      });
      await approveRemediation(task.id);
      setLockMsg({ ok: true, text: enable
        ? `Re-enabling "${user}" on ${lockTarget.hostname} — they can sign in again shortly.`
        : `Disabling "${user}" on ${lockTarget.hostname} and signing them out. Track it under Self-Healing.` });
    } catch (err) {
      setLockMsg({ ok: false, text: apiErrorMessage(err, "Couldn't queue it. The device may be offline, or you may lack permission.") });
    } finally {
      setLockBusy(false);
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

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search hostname, serial, model, user…"
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>
        <div className="flex items-center gap-3">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {filtered ? `${filtered.length} device${filtered.length === 1 ? "" : "s"}` : ""}
          </p>
          <button
            onClick={() => filtered && exportDevicesCsv(filtered)}
            disabled={!filtered || filtered.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            <Download size={15} /> Export CSV
          </button>
        </div>
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
              {!isLoading && (!filtered || filtered.length === 0) && (
                <tr><td colSpan={colCount} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                  {q
                    ? "No devices match your search."
                    : `No devices enrolled yet. ${isAdmin ? "Use “Install agent” above to add your first endpoint." : ""}`}
                </td></tr>
              )}
              {filtered?.map((d) => (
                <tr key={d.id} className="hover:bg-brand-500/5 transition-colors" style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/devices/${d.id}`} className="hover:underline" style={{ color: "var(--accent)" }}>
                      {d.hostname}
                    </Link>
                    <div className="text-xs font-normal" style={{ color: "var(--text-secondary)" }}>
                      {d.os_version}{d.agent_version ? ` · agent ${d.agent_version}` : ""}
                    </div>
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
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => openLock(d)}
                          title="Lock down: disable this device's local account (offboarding)"
                          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium"
                          style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#d97706" }}>
                          <UserX size={13} /> Lock down
                        </button>
                        <button
                          onClick={() => removeDevice(d)}
                          disabled={deletingId === d.id}
                          title="Remove device from portal"
                          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
                          style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "#ef4444" }}>
                          <Trash2 size={13} /> {deletingId === d.id ? "Removing…" : "Remove"}
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {lockTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.5)" }} onClick={() => !lockBusy && setLockTarget(null)}>
          <div className="w-full max-w-md rounded-xl p-5" onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg" style={{ background: "rgba(217,119,6,0.12)", color: "#d97706" }}>
                  <UserX size={18} />
                </div>
                <div>
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Lock down — {lockTarget.hostname}</h2>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Disable this device&apos;s local account for offboarding.</p>
                </div>
              </div>
              <button onClick={() => !lockBusy && setLockTarget(null)} style={{ color: "var(--text-secondary)" }}><X size={16} /></button>
            </div>

            <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>Local account name</label>
            <input value={lockUser} onChange={(e) => setLockUser(e.target.value)}
              placeholder="the employee's Windows username"
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 mb-3"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />

            <div className="rounded-lg p-3 text-xs mb-3 space-y-1" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
              <p><b>Disable</b> signs the user out now and blocks future sign-in. The password is <b>not</b> changed and <b>nothing is deleted</b> — fully reversible with Re-enable.</p>
              <p>Works on <b>local</b> Windows accounts only; domain/Entra accounts are managed in AD/Intune.</p>
            </div>

            <label className="block text-xs font-medium mb-1" style={{ color: "var(--text-secondary)" }}>
              Type <span className="font-mono" style={{ color: "var(--text-primary)" }}>{lockTarget.hostname}</span> to confirm disabling
            </label>
            <input value={lockConfirm} onChange={(e) => setLockConfirm(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-brand-500 mb-3"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />

            {lockMsg && <p className="text-xs mb-3" style={{ color: lockMsg.ok ? "#10b981" : "#ef4444" }}>{lockMsg.text}</p>}

            <div className="flex items-center justify-between gap-2">
              <button onClick={() => runLock(true)} disabled={lockBusy}
                className="px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                Re-enable account
              </button>
              <button onClick={() => runLock(false)} disabled={lockBusy}
                className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "#dc2626" }}>
                {lockBusy ? "Working…" : "Disable & sign out"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
