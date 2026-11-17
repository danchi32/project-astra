"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Mail } from "lucide-react";
import { emailBrief, getBrief } from "@/lib/api/reports";
import { apiErrorMessage } from "@/lib/utils";

// J1 · Brief: the day or the week in plain language. On demand: there is no scheduled e-mail
// yet (2.0 decision), so "Email it to me" sends this one now, to you only.

export function BriefReport() {
  const [period, setPeriod] = useState<"day" | "week">("day");
  const { data, isLoading, error } = useQuery({ queryKey: ["report-brief", period], queryFn: () => getBrief(period) });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const toggle = { background: "var(--bg)", border: "1px solid var(--border)" };

  async function email() {
    setBusy(true); setMsg(null);
    try {
      const r = await emailBrief(period);
      setMsg(r.sent ? { ok: true, text: `Sent to ${r.to}.` } : { ok: false, text: "E-mail is not set up on this server, so nothing was sent." });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not send the brief.") });
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1 p-1 rounded-lg" style={toggle}>
          {(["day", "week"] as const).map((p) => (
            <button key={p} onClick={() => setPeriod(p)} className="px-3 py-1.5 rounded-md text-sm font-medium"
              style={period === p ? { background: "var(--accent)", color: "white" } : muted}>{p === "day" ? "Today" : "This week"}</button>
          ))}
        </div>
        <button onClick={email} disabled={busy || !data} className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ ...toggle, color: "var(--text-primary)" }}>
          <Mail size={14} /> {busy ? "Sending…" : "Email it to me"}
        </button>
      </div>
      {msg && <p className="text-xs" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}
      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load the brief.")}</p>}
      {data && (
        <div className="rounded-xl p-5 space-y-4" style={panel}>
          <div>
            <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>{data.title}</h2>
            <p className="text-sm mt-1 font-medium" style={{ color: "var(--text-primary)" }}>{data.headline}</p>
          </div>
          {data.sections.map((s) => (
            <div key={s.key}>
              <p className="text-xs uppercase tracking-wide font-semibold mb-1"
                style={{ color: s.key === "attention" ? "#f59e0b" : "var(--text-secondary)" }}>{s.title}</p>
              <ul className="space-y-1 text-sm list-disc pl-5" style={{ color: "var(--text-primary)" }}>
                {s.lines.map((l, i) => <li key={i}>{l}</li>)}
              </ul>
            </div>
          ))}
          <p className="text-xs pt-2" style={{ ...muted, borderTop: "1px solid var(--border)" }}>{data.footer}</p>
        </div>
      )}
    </div>
  );
}
