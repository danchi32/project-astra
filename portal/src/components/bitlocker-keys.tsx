"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, Eye, KeyRound, X } from "lucide-react";
import { getBitLockerKeys, revealBitLockerKey, type BitLockerKeyMeta, type BitLockerKeyRevealed } from "@/lib/api/device-detail";
import { apiErrorMessage } from "@/lib/utils";

// BitLocker recovery keys escrowed from this PC (2a+), for an admin standing at a recovery
// screen. The list shows the Key ID the recovery screen asks about; the 48-digit password only
// appears after an explicit reveal, which the server records in the audit log. It lives in this
// component's state and is gone when the dialog closes.

// The recovery screen identifies the key by the first 8 characters of its ID.
const shortId = (protectorId: string) => protectorId.slice(0, 8).toUpperCase();

export function BitLockerKeys({ deviceId }: { deviceId: string }) {
  const { data: keys, isLoading, error } = useQuery({
    queryKey: ["dev-bitlocker-keys", deviceId],
    queryFn: () => getBitLockerKeys(deviceId),
  });
  const [confirming, setConfirming] = useState<BitLockerKeyMeta | null>(null);
  const [revealed, setRevealed] = useState<BitLockerKeyRevealed | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function reveal(k: BitLockerKeyMeta) {
    setBusy(true);
    setMsg(null);
    try {
      setRevealed(await revealBitLockerKey(deviceId, k.id));
      setConfirming(null);
    } catch (e) {
      setMsg(apiErrorMessage(e, "Could not reveal the key."));
    } finally {
      setBusy(false);
    }
  }

  function close() {
    setRevealed(null);        // the password leaves memory with the dialog
    setCopied(false);
  }

  // A copied key would otherwise sit on the clipboard (and in Windows clipboard history or
  // cloud sync) indefinitely. Clear it after a minute, but only if it still holds this key:
  // never wipe something else the admin copied since.
  async function copy(password: string) {
    await navigator.clipboard.writeText(password);
    setCopied(true);
    setTimeout(async () => {
      try {
        if ((await navigator.clipboard.readText()) === password) await navigator.clipboard.writeText("");
      } catch {
        // Reading the clipboard needs permission; without it, overwrite only while this tab has focus.
        if (document.hasFocus()) await navigator.clipboard.writeText("").catch(() => {});
      }
    }, 60_000);
  }

  const muted = { color: "var(--text-secondary)" };
  const box = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

  return (
    <div className="rounded-xl p-4 space-y-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="text-xs" style={muted}>
        BitLocker recovery keys this PC has escrowed to SAVIO. Match the Key ID shown on the PC&apos;s
        recovery screen. Revealing a key is admin-only and recorded in the audit log with your name.
      </p>
      {msg && <p className="text-xs" style={{ color: "#ef4444" }}>{msg}</p>}
      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load recovery keys.")}</p>}
      {keys && (
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Drive", "Key ID", "Escrowed", ""].map((h) => (
                <th key={h} className="text-left py-2 text-xs uppercase" style={muted}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                <td className="py-2 font-medium">{k.drive}</td>
                <td className="py-2 font-mono" title={k.protector_id}>{shortId(k.protector_id)}</td>
                <td className="py-2" style={muted}>{new Date(k.escrowed_at).toLocaleString()}</td>
                <td className="py-2 text-right">
                  <button onClick={() => { setMsg(null); setConfirming(k); }} disabled={busy}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium disabled:opacity-50" style={box}>
                    <Eye size={12} /> Reveal
                  </button>
                </td>
              </tr>
            ))}
            {!keys.length && (
              <tr><td colSpan={4} className="py-6 text-center" style={muted}>
                No recovery keys escrowed yet. They appear once BitLocker is on and the agent (0.15 or later) has reported.
              </td></tr>
            )}
          </tbody>
        </table>
      )}

      {confirming && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}>
          <div className="w-full max-w-md rounded-xl p-5 space-y-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <p className="flex items-center gap-2 font-semibold" style={{ color: "var(--text-primary)" }}>
              <KeyRound size={16} /> Reveal recovery key {shortId(confirming.protector_id)} ({confirming.drive})?
            </p>
            <p className="text-sm" style={muted}>
              This is recorded in the audit log with your name, the device and the key ID. Only do it when the
              person in front of the PC needs the key.
            </p>
            {msg && <p className="text-xs" style={{ color: "#ef4444" }}>{msg}</p>}
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirming(null)} className="px-3 py-1.5 rounded-lg text-sm" style={box}>Cancel</button>
              <button onClick={() => reveal(confirming)} disabled={busy}
                className="px-3 py-1.5 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
                Reveal
              </button>
            </div>
          </div>
        </div>
      )}

      {revealed && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}>
          <div className="w-full max-w-md rounded-xl p-5 space-y-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <div className="flex items-start justify-between">
              <p className="font-semibold" style={{ color: "var(--text-primary)" }}>
                Recovery key {shortId(revealed.protector_id)} ({revealed.drive})
              </p>
              <button onClick={close} aria-label="Close" style={muted}><X size={18} /></button>
            </div>
            <p className="font-mono text-base tracking-wide break-all rounded-lg p-3 select-all" style={box}>
              {revealed.recovery_password}
            </p>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={muted}>
                Read it out or type it in; don&apos;t save it anywhere. A copy is cleared from the clipboard after a minute.
              </span>
              <button onClick={() => copy(revealed.recovery_password)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs" style={box}>
                <Copy size={12} /> {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
