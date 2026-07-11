"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Monitor, Download, Plus, Copy, Check, KeyRound, X,
} from "lucide-react";
import { getDevices } from "@/lib/api/dashboard";
import { getMe } from "@/lib/api/auth";
import { listEnrollmentTokens, revokeEnrollmentToken, generateAgentInstaller, downloadOfflineInstaller } from "@/lib/api/devices";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { formatRam, formatStorage } from "@/lib/utils";
import type { AgentInstaller } from "@/lib/api/types";

function downloadScript(installer: AgentInstaller) {
  const blob = new Blob([installer.script], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = installer.filename;
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
  const [name, setName] = useState("");
  const [serverUrl, setServerUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [offlineBusy, setOfflineBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AgentInstaller | null>(null);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const installer = await generateAgentInstaller(name.trim(), serverUrl.trim());
      setResult(installer);
      await queryClient.invalidateQueries({ queryKey: ["enrollment-tokens"] });
    } catch {
      setError("Couldn't generate the token. Check the details and try again.");
    } finally { setBusy(false); }
  }

  async function downloadOffline() {
    if (!name.trim()) { setError("Enter a label first."); return; }
    setOfflineBusy(true); setError("");
    try {
      await downloadOfflineInstaller(name.trim(), serverUrl.trim());
      await queryClient.invalidateQueries({ queryKey: ["enrollment-tokens"] });
    } catch {
      setError("Couldn't build the offline installer. Try again.");
    } finally { setOfflineBusy(false); }
  }

  function reset() {
    setResult(null); setName(""); setServerUrl(""); setError("");
  }

  return (
    <div className="rounded-xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg shrink-0" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            <Download size={18} />
          </div>
          <div>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Install the ASTRA agent</h2>
            <p className="text-xs mt-0.5 max-w-xl" style={{ color: "var(--text-secondary)" }}>
              Download the Windows installer and enroll a machine with a one-time token.
              Once installed, the device appears here automatically within a minute.
            </p>
          </div>
        </div>
        {!open && (
          <button onClick={() => setOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white shrink-0"
            style={{ background: "var(--accent)" }}>
            <Plus size={16} /> Install agent
          </button>
        )}
      </div>

      {open && !result && (
        <form onSubmit={generate} className="mt-4 space-y-3 max-w-xl">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Label</label>
              <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sales laptops"
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
            </div>
            <div>
              <label className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Server URL (optional)</label>
              <input value={serverUrl} onChange={(e) => setServerUrl(e.target.value)} placeholder="https://astra.yourco.com"
                className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
            </div>
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={busy || offlineBusy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--accent)" }}>
              <KeyRound size={15} /> {busy ? "Generating…" : "Generate enrollment token"}
            </button>
            <button type="button" onClick={downloadOffline} disabled={busy || offlineBusy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
              <Download size={15} /> {offlineBusy ? "Preparing…" : "Offline installer (many PCs)"}
            </button>
            <button type="button" onClick={() => setOpen(false)}
              className="px-3 py-2 rounded-lg text-sm font-medium"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Cancel</button>
          </div>
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            <span className="font-medium">Offline installer</span>: one <span className="font-mono">.zip</span> with the
            agent bundled in — copy it to any number of PCs and run <span className="font-mono">Install.bat</span> as
            administrator. The token inside works for every machine.
          </p>
        </form>
      )}

      {result && (
        <div className="mt-4 space-y-3 max-w-xl">
          <div className="flex items-center gap-2 text-sm font-medium" style={{ color: "#10b981" }}>
            <Check size={16} /> Installer ready — one file, runs on the target machine
          </div>

          {/* Step 1 — download the one self-contained installer script */}
          <div className="rounded-lg p-3" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
            <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>
              1. On the target Windows machine, download the installer
            </p>
            <button onClick={() => downloadScript(result)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white"
              style={{ background: "var(--accent)" }}>
              <Download size={15} /> Download Install-AstraAgent.ps1
            </button>
            <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>
              The server URL and a one-time enrollment token are already baked in. The script
              downloads the agent from your server and installs it — nothing else to configure.
            </p>
          </div>

          {/* Step 2 — run it elevated */}
          <div className="rounded-lg p-3 space-y-2" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
            <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
              2. Right-click the file → <span className="font-semibold">Run with PowerShell</span> (approve the
              admin prompt). Or run in an elevated PowerShell:
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs font-mono px-2 py-1.5 rounded truncate" style={{ background: "var(--surface)", color: "var(--text-primary)" }}>
                powershell -ExecutionPolicy Bypass -File .\Install-AstraAgent.ps1
              </code>
              <CopyButton text={"powershell -ExecutionPolicy Bypass -File .\\Install-AstraAgent.ps1"} />
            </div>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              The device enrolls automatically and appears under Devices within a minute.
            </p>
          </div>

          <details className="text-xs" style={{ color: "var(--text-secondary)" }}>
            <summary className="cursor-pointer">Need the raw enrollment token?</summary>
            <div className="flex items-center gap-2 mt-2">
              <code className="flex-1 text-xs font-mono px-2 py-1.5 rounded truncate" style={{ background: "var(--surface)", color: "var(--text-primary)" }}>{result.token}</code>
              <CopyButton text={result.token} />
            </div>
            <p className="mt-1">Shown once — copy it now if you need it.</p>
          </details>

          <button onClick={reset}
            className="px-3 py-2 rounded-lg text-sm font-medium"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Generate another</button>
        </div>
      )}
    </div>
  );
}

function EnrollmentTokens() {
  const queryClient = useQueryClient();
  const { data: tokens, isLoading } = useQuery({ queryKey: ["enrollment-tokens"], queryFn: listEnrollmentTokens });

  async function revoke(id: string) {
    await revokeEnrollmentToken(id);
    await queryClient.invalidateQueries({ queryKey: ["enrollment-tokens"] });
  }

  const active = (tokens ?? []).filter((t) => !t.revoked_at);
  if (isLoading || active.length === 0) return null;

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
      <div className="px-5 py-3 flex items-center gap-2" style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
        <KeyRound size={14} style={{ color: "var(--text-secondary)" }} />
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Active enrollment tokens</h2>
      </div>
      <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
        <table className="w-full text-sm whitespace-nowrap">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Label", "Created", "Expires", ""].map((h) => (
                <th key={h} className="px-5 py-2.5 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {active.map((t) => (
              <tr key={t.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="px-5 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{t.name}</td>
                <td className="px-5 py-2.5" style={{ color: "var(--text-secondary)" }}>{new Date(t.created_at).toLocaleDateString()}</td>
                <td className="px-5 py-2.5" style={{ color: "var(--text-secondary)" }}>{new Date(t.expires_at).toLocaleDateString()}</td>
                <td className="px-5 py-2.5 text-right">
                  <button onClick={() => revoke(t.id)} title="Revoke"
                    className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg hover:bg-red-500/10 hover:text-red-500"
                    style={{ color: "var(--text-secondary)" }}>
                    <X size={13} /> Revoke
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function DevicesPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const { data: devices, isLoading } = useQuery({
    queryKey: ["devices"],
    queryFn: getDevices,
    refetchInterval: 30_000,
  });
  const isAdmin = me?.role === "admin";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
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
      {isAdmin && <EnrollmentTokens />}

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
                  No devices enrolled yet. {isAdmin ? "Use “Install agent” above to add your first endpoint." : ""}
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
