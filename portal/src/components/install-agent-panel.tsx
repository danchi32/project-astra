"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Copy, Check, RefreshCw } from "lucide-react";
import { getInstaller, rotateEnrollmentKey, downloadOfflineInstaller, downloadUninstaller } from "@/lib/api/devices";

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

// The org's self-service agent installer: download the pre-keyed bundle, run it, rotate the
// enrollment key, or grab the uninstaller. Shown on the Devices page (collapsed) and on the
// dedicated /install page (expanded via defaultOpen).
export function InstallAgentPanel({ defaultOpen = false }: { defaultOpen?: boolean }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(defaultOpen);
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

              {!defaultOpen && (
                <button onClick={() => setOpen(false)}
                  className="px-3 py-2 rounded-lg text-sm font-medium"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Done</button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
