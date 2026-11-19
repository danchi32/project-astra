"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, MinusCircle, Printer } from "lucide-react";
import { FINDING_KINDS, getIncident, updateIncident, type IncidentStep } from "@/lib/api/guard";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3b · I1 · one breach record, and J7: printed (the browser's own print-to-PDF, as L1 does)
// it is the incident report — the facts, the steps with when and by whom, and the full timeline.
// No legal deadlines here: what must be reported, to whom and by when is for counsel.

const ACTION: Record<string, string> = { "dpdp.incident_open": "Record started", "dpdp.incident_update": "Updated" };

function since(iso: string, until?: string | null) {
  const h = Math.max(0, Math.floor(((until ? new Date(until) : new Date()).getTime() - new Date(iso).getTime()) / 3_600_000));
  return h < 48 ? `${h} hour${h === 1 ? "" : "s"}` : `${Math.floor(h / 24)} days`;
}

/** An update's audit detail in words: the step settled, closed / reopened, and which facts changed. */
function describe(action: string, detail: Record<string, unknown> | null): string {
  if (action !== "dpdp.incident_update" || !detail) return "";
  // The audit holds which step and which fields, never the words (security review 3b M2).
  const { step, status, fields } = detail as { step?: { key: string; state: string | null }; status?: string; fields?: string[] };
  const parts: string[] = [];
  if (step) parts.push(`${step.key}: ${step.state === "not_needed" ? "not needed" : step.state ?? "undone"}`);
  if (status) parts.push(status === "closed" ? "closed" : "reopened");
  if (fields?.length) parts.push(`changed ${fields.join(", ").replaceAll("_", " ")}`);
  return parts.join("; ");
}

export default function IncidentPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { data, error, isLoading } = useQuery({ queryKey: ["incident", id], queryFn: () => getIncident(id), retry: false });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (data) setNotes(Object.fromEntries(data.steps.map((s) => [s.key, s.note ?? ""])));
  }, [data]);

  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const input = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

  async function change(body: Parameters<typeof updateIncident>[1]) {
    setMsg(null);
    setBusy(true);
    try {
      await updateIncident(id, body);
      await qc.invalidateQueries({ queryKey: ["incident", id] });
      await qc.invalidateQueries({ queryKey: ["incidents"] });
    } catch (e) { setMsg(apiErrorMessage(e, "Could not save.")); }
    setBusy(false);
  }
  const setStep = (s: IncidentStep, state: IncidentStep["state"]) =>
    change({ step: { key: s.key, state, note: notes[s.key]?.trim() || null } });

  if (isLoading) return <p className="text-sm" style={muted}>Loading…</p>;
  if (error || !data) return <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load.")}</p>;
  const open = data.status === "open";
  const settled = data.steps.every((s) => s.state);

  return (
    <div className="space-y-4 max-w-4xl print:max-w-none">
      <div className="flex items-center justify-between gap-3 print:hidden">
        <Link href="/guard/incidents" className="text-xs underline" style={{ color: "var(--accent)" }}>All breach records</Link>
        <button onClick={() => window.print()} className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm" style={input}>
          <Printer size={14} /> Print the incident report
        </button>
      </div>

      <div className="rounded-xl p-5 space-y-2" style={panel}>
        <div className="text-xs uppercase tracking-wide" style={muted}>Incident report · personal data</div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>{data.title}</h1>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm" style={{ color: "var(--text-primary)" }}>
          <div><span style={muted}>Status: </span>{open ? "Open" : `Closed ${new Date(data.closed_at!).toLocaleString()}`}</div>
          <div><span style={muted}>Found: </span>{new Date(data.found_at).toLocaleString()}
            <span style={muted}> ({since(data.found_at, data.closed_at)} {open ? "ago" : "to close"})</span></div>
          <div><span style={muted}>Data involved: </span>{data.kinds.length ? data.kinds.map((k) => FINDING_KINDS[k] ?? k).join(", ") : "Not recorded"}</div>
          <div><span style={muted}>People affected (about): </span>{data.people_affected ?? "Not known yet"}</div>
          {data.case && (
            <div className="sm:col-span-2"><span style={muted}>From a case: </span>{data.case.windows_user} · {data.case.level} risk ·
              opened {new Date(data.case.opened_at).toLocaleString()} <Link href="/guard/cases" className="underline print:hidden" style={{ color: "var(--accent)" }}>Cases</Link></div>
          )}
        </div>
        {data.what_happened && <p className="text-sm whitespace-pre-wrap pt-1" style={{ color: "var(--text-primary)" }}>{data.what_happened}</p>}
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Steps</h2>
        {data.steps.map((s) => {
          const Icon = s.state === "done" ? CheckCircle2 : s.state === "not_needed" ? MinusCircle : Circle;
          return (
            <div key={s.key} className="rounded-xl p-4 flex items-start gap-3 break-inside-avoid" style={panel}>
              <Icon size={16} className="mt-0.5 shrink-0" style={{ color: s.state === "done" ? "#10b981" : s.state ? "var(--text-secondary)" : "#f59e0b" }} />
              <div className="flex-1 space-y-1 text-sm" style={{ color: "var(--text-primary)" }}>
                <div className="font-medium">{s.title}</div>
                <div className="text-xs" style={muted}>{s.help}</div>
                {s.state && (
                  <div className="text-xs">
                    {s.state === "done" ? "Done" : "Not needed (on counsel's advice)"} · {new Date(s.at!).toLocaleString()} · {s.by}
                    {s.note && <div className="whitespace-pre-wrap mt-0.5">{s.note}</div>}
                  </div>
                )}
                {open && (
                  <div className="space-y-1.5 print:hidden">
                    {!s.state && (
                      <textarea aria-label={`Note for ${s.title}`} rows={2} maxLength={1000} placeholder="What was done (optional)"
                        value={notes[s.key] ?? ""} onChange={(e) => setNotes({ ...notes, [s.key]: e.target.value })}
                        className="w-full px-3 py-2 rounded-lg text-xs outline-none" style={input} />
                    )}
                    <div className="flex flex-wrap gap-2">
                      {!s.state && <button disabled={busy} onClick={() => setStep(s, "done")}
                        className="px-2.5 py-1 rounded-lg text-xs font-medium text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>Done</button>}
                      {!s.state && s.optional && <button disabled={busy} onClick={() => setStep(s, "not_needed")}
                        className="px-2.5 py-1 rounded-lg text-xs disabled:opacity-50" style={input}>Counsel says not needed</button>}
                      {s.state && <button disabled={busy} onClick={() => setStep(s, null)}
                        className="text-xs underline disabled:opacity-50" style={muted}>Undo</button>}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2 print:hidden">
        {open ? (
          <button disabled={busy || !settled} onClick={() => change({ closed: true })} title={settled ? "" : "Settle every step first"}
            className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
            Close the record
          </button>
        ) : (
          <button disabled={busy} onClick={() => change({ closed: false })} className="px-3 py-2 rounded-lg text-sm" style={input}>Reopen</button>
        )}
        {open && !settled && <span className="text-xs" style={muted}>Settle every step to close it.</span>}
        {msg && <span className="text-xs" style={{ color: "#ef4444" }}>{msg}</span>}
      </div>

      <div className="rounded-xl p-4 space-y-1 break-inside-avoid" style={panel}>
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Timeline</h2>
        {data.timeline.map((t, n) => (
          <div key={n} className="flex gap-3 text-xs" style={{ color: "var(--text-primary)" }}>
            <span className="shrink-0 w-40" style={muted}>{new Date(t.at).toLocaleString()}</span>
            <span className="shrink-0 w-32">{t.by ?? "—"}</span>
            <span>{ACTION[t.action] ?? t.action}{describe(t.action, t.detail) ? `: ${describe(t.action, t.detail)}` : ""}</span>
          </div>
        ))}
      </div>

      <p className="text-xs" style={muted}>
        This is a working record kept in SAVIO. It is not legal advice: what has to be reported, to whom and by when is
        for your counsel to confirm. Printed {new Date().toLocaleString()}.
      </p>
    </div>
  );
}
