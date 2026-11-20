"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { FINDING_KINDS, getIncidents, openIncident, type FindingKind } from "@/lib/api/guard";
import { isUpgradeRequired } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3b · I1 · AI Guard → Breach records. A possible personal-data breach, written down the
// moment it is found, with the steps taken. Often started from a case ("?case=<id>"). Admin only.

const status = (e: unknown) => (e as { response?: { status?: number } } | null)?.response?.status;
// "YYYY-MM-DDTHH:mm" in local time, for a datetime-local input.
const localNow = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };

export default function IncidentsPage() {
  const router = useRouter();
  const { data, error, isLoading } = useQuery({ queryKey: ["incidents"], queryFn: getIncidents, retry: false });
  const [caseId, setCaseId] = useState<string | null>(null);
  const [form, setForm] = useState(false);
  const [title, setTitle] = useState("");
  const [what, setWhat] = useState("");
  const [found, setFound] = useState(localNow);
  const [kinds, setKinds] = useState<FindingKind[]>([]);
  const [people, setPeople] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // From a case: open the form with it attached.
  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get("case");
    if (c) { setCaseId(c); setForm(true); }
  }, []);

  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const input = { background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" };

  if (isUpgradeRequired(error) || status(error) === 403) {
    return (
      <div className="rounded-xl p-8 text-center max-w-lg mx-auto" style={panel}>
        <ShieldAlert size={22} className="mx-auto mb-3" style={{ color: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          {isUpgradeRequired(error) ? "AI Guard is an add-on" : "Only an admin can see this"}
        </h2>
      </div>
    );
  }

  async function start() {
    setMsg(null);
    setBusy(true);
    try {
      const inc = await openIncident({
        title: title.trim(), what_happened: what.trim(), found_at: new Date(found).toISOString(), kinds,
        people_affected: people.trim() ? Number(people) : null, case_id: caseId,
      });
      router.push(`/guard/incidents/${inc.id}`);
    } catch (e) { setMsg(apiErrorMessage(e, "Could not start the record.")); setBusy(false); }
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><ShieldAlert size={18} /></div>
        <div className="flex-1">
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Breach records</h1>
          <p className="text-xs max-w-2xl" style={muted}>
            When personal data may have got out, write it down the moment it is found, then work through the steps.
            Each step records when and by whom, and the record prints as an incident report.
          </p>
        </div>
        {!form && (
          <button onClick={() => setForm(true)} className="px-3 py-2 rounded-lg text-sm font-medium text-white" style={{ background: "var(--accent)" }}>
            New breach record
          </button>
        )}
      </div>

      {form && (
        <div className="rounded-xl p-4 space-y-3" style={panel}>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            New breach record{caseId && <span className="font-normal" style={muted}> · from a case</span>}
          </h2>
          <input aria-label="Title" placeholder="What happened, in a line (e.g. Client list sent to a personal Gmail)" maxLength={200}
            value={title} onChange={(e) => setTitle(e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={input} />
          <textarea aria-label="What happened" placeholder="What is known so far: what, how it was found, which PCs or people" maxLength={4000}
            rows={4} value={what} onChange={(e) => setWhat(e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm outline-none" style={input} />
          <div className="flex flex-wrap gap-4 items-center text-sm" style={{ color: "var(--text-primary)" }}>
            <label className="flex items-center gap-2">Found
              <input aria-label="Found at" type="datetime-local" value={found} max={localNow()} onChange={(e) => setFound(e.target.value)}
                className="px-2 py-1.5 rounded-lg text-sm outline-none" style={input} />
            </label>
            <label className="flex items-center gap-2">People affected (about)
              <input aria-label="People affected" type="number" min={0} value={people} onChange={(e) => setPeople(e.target.value)}
                className="w-28 px-2 py-1.5 rounded-lg text-sm outline-none" style={input} />
            </label>
          </div>
          <div className="flex flex-wrap gap-3 text-xs" style={{ color: "var(--text-primary)" }}>
            <span style={muted}>Data involved:</span>
            {(Object.keys(FINDING_KINDS) as FindingKind[]).map((k) => (
              <label key={k} className="flex items-center gap-1">
                <input type="checkbox" checked={kinds.includes(k)}
                  onChange={(e) => setKinds(e.target.checked ? [...kinds, k] : kinds.filter((x) => x !== k))} />
                {FINDING_KINDS[k]}
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <button disabled={busy || !title.trim()} onClick={start}
              className="px-3 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
              Start the record
            </button>
            <button onClick={() => { setForm(false); setCaseId(null); }} className="px-3 py-2 rounded-lg text-sm" style={input}>Cancel</button>
            {msg && <span className="text-xs" style={{ color: "#ef4444" }}>{msg}</span>}
          </div>
        </div>
      )}

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load.")}</p>}
      {data && data.length === 0 && !form && <p className="text-sm" style={muted}>No breach records. That is the hope.</p>}
      {data?.map((i) => {
        const settled = i.steps.filter((s) => s.state).length;
        return (
          <Link key={i.id} href={`/guard/incidents/${i.id}`} className="block rounded-xl p-4" style={panel}>
            <div className="flex flex-wrap items-center gap-2 text-sm" style={{ color: "var(--text-primary)" }}>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{
                background: i.status === "open" ? "rgba(239,68,68,0.12)" : "rgba(16,185,129,0.12)",
                color: i.status === "open" ? "#ef4444" : "#10b981" }}>{i.status === "open" ? "Open" : "Closed"}</span>
              <span className="font-medium flex-1">{i.title}</span>
              <span className="text-xs" style={muted}>Found {new Date(i.found_at).toLocaleString()} · {settled} of {i.steps.length} steps</span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
