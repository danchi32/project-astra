"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Copy, Check, RefreshCw } from "lucide-react";
import {
  getInstaller,
  rotateEnrollmentKey,
  downloadOfflineInstaller,
  downloadExeInstaller,
  revokeExeInstallers,
  downloadUninstaller,
} from "@/lib/api/devices";

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
  const [exeBusy, setExeBusy] = useState(false);
  const [revokeBusy, setRevokeBusy] = useState(false);
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

  async function downloadExe() {
    setExeBusy(true); setError(""); setNotice("");
    try {
      await downloadExeInstaller();
    } catch (err) {
      setError((err as Error)?.message || "Couldn't download the .exe installer. Try again.");
    } finally { setExeBusy(false); }
  }

  async function revokeExe() {
    if (!confirm(
      "Invalidate every .exe installer downloaded so far?\n\nAny copy you have already distributed stops enrolling new machines. Already-enrolled devices, the .zip installer and your enrollment key are unaffected."
    )) return;
    setRevokeBusy(true); setError(""); setNotice("");
    try {
      const n = await revokeExeInstallers();
      setNotice(n === 0
        ? "No .exe installers were live — nothing to invalidate."
        : `Invalidated ${n} .exe installer${n === 1 ? "" : "s"}. Download a fresh one for any new machine.`);
    } catch {
      setError("Couldn't invalidate the .exe installers. Try again.");
    } finally { setRevokeBusy(false); }
  }

  async function downloadOffline() {
    setOfflineBusy(true); setError("");
    try {
      await downloadOfflineInstaller();
    } catch (err) {
      setError((err as Error)?.message || "Couldn't build the portable installer. Try again.");
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
                  {installer.exe_available && (
                    <button onClick={downloadExe} disabled={exeBusy}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                      style={{ background: "var(--accent)" }}>
                      <Download size={15} /> {exeBusy ? "Preparing…" : "Download installer (.exe)"}
                    </button>
                  )}
                  <button onClick={downloadOffline} disabled={offlineBusy}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                    style={installer.exe_available
                      ? { background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }
                      : { background: "var(--accent)", color: "white" }}>
                    <Download size={15} /> {offlineBusy ? "Preparing…" : ".zip (mass deployment)"}
                  </button>
                </div>
                {installer.exe_available && (
                  // A one-time ticket rides in the filename, so a rename breaks enrolment
                  // and the installer falls back to asking for a key. Say so up front —
                  // and say when it stops working, before copies are handed around.
                  <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>
                    Save the .exe under the name it downloads as, then double-click — nothing to
                    extract, nothing to type. Each download carries its own one-time enrollment
                    ticket{installer.exe_ticket_days ? ` that stops working after ${installer.exe_ticket_days} days` : ""};
                    your permanent key is never put in the filename.
                  </p>
                )}
                <p className="text-xs mt-2" style={{ color: "var(--text-secondary)" }}>
                  The .zip is for Intune/SCCM/GPO rollouts, or any machine where you would rather
                  run the script yourself.
                </p>
              </div>

              {/* Honest about the one rough edge, rather than letting an admin hit it cold
                  on a user's machine and assume the installer is broken. */}
              <div className="rounded-lg p-3" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.35)" }}>
                <p className="text-xs font-medium" style={{ color: "#f59e0b" }}>Windows will warn the first time</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
                  The agent is not code-signed yet, so SmartScreen shows{" "}
                  <span className="font-medium">“Windows protected your PC”</span> — click{" "}
                  <span className="font-medium">More info → Run anyway</span>.
                </p>
                <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
                  On a managed PC it may not run at all. Setup aborting with{" "}
                  <span className="font-medium">“Unable to execute file in the temporary directory”</span>{" "}
                  means an Intune policy is blocking unsigned, low-prevalence executables;{" "}
                  <span className="font-medium">Smart App Control</span> blocks it the same way.
                  Neither can be excluded locally —{" "}
                  <span className="font-medium">use the .zip on those machines</span>, which runs only
                  Windows&apos; own signed tools and is unaffected. A signed build removes all of this.
                </p>
              </div>

              {/* Step 2 — run */}
              <div className="rounded-lg p-3 space-y-2" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                  2. Approve the admin prompt. Using the .zip instead? Extract it and double-click{" "}
                  <span className="font-mono">Install.bat</span>, or run:
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
                  Never expires, and is only ever used by the .zip. Rotating it stops every .zip
                  installer you have distributed; already-enrolled devices are unaffected.
                </p>
              </div>

              {/* .exe installers are revocable on their own, precisely so a leaked one does
                  not force a key rotation that would break every .zip as well. */}
              {installer.exe_available && (
                <div className="rounded-lg p-3" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                        Downloaded .exe installers
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                        Each carries its own ticket
                        {installer.exe_ticket_days ? `, valid ${installer.exe_ticket_days} days` : ""}. Invalidate them if
                        one ends up somewhere it should not — your key and the .zip keep working.
                      </p>
                    </div>
                    <button onClick={revokeExe} disabled={revokeBusy}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg shrink-0 disabled:opacity-50"
                      style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "#f59e0b" }}>
                      <RefreshCw size={12} /> {revokeBusy ? "Invalidating…" : "Invalidate"}
                    </button>
                  </div>
                </div>
              )}

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
