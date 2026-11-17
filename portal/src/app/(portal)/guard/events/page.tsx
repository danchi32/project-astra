"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import {
  FINDING_KINDS, getGuardEventSummary, getGuardEvents, type FindingKind, type GuardEventRow,
} from "@/lib/api/guard";
import { isUpgradeRequired } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3 · E3 · AI Guard → What was found. What the SAVIO browser extension saw on the org's
// PCs: counts and kinds only. The text itself never leaves the PC, so there is nothing to show
// here but "2 PAN numbers were pasted into chatgpt.com". Admin only: it names people.

const CHANNEL: Record<GuardEventRow["channel"], string> = {
  paste: "Pasted", drop: "Dropped", file: "File chosen", submit: "Form sent",
};

const RESULT: Record<GuardEventRow["action"], { label: string; color: string }> = {
  allow: { label: "Recorded", color: "var(--text-secondary)" },
  warn: { label: "Warned", color: "#f59e0b" },
  block: { label: "Blocked", color: "#ef4444" },
};

const status = (e: unknown) => (e as { response?: { status?: number } } | null)?.response?.status;

function found(e: Pick<GuardEventRow, "counts" | "contact_list" | "keyword_hits" | "unknown">) {
  if (e.unknown) return "Could not be checked";
  const parts = (Object.entries(e.counts) as [FindingKind, number][])
    .filter(([, n]) => n > 0).map(([k, n]) => `${FINDING_KINDS[k] ?? k} ×${n}`);
  if (e.contact_list) parts.push("a contact list");
  if (e.keyword_hits) parts.push(`${e.keyword_hits} restricted keyword${e.keyword_hits > 1 ? "s" : ""}`);
  return parts.join(", ");
}

export default function GuardEventsPage() {
  const [days, setDays] = useState(7);
  const [offset, setOffset] = useState(0);
  const summary = useQuery({ queryKey: ["guard-events-summary", days], queryFn: () => getGuardEventSummary(days),
    retry: false, refetchInterval: 60_000 });
  const events = useQuery({ queryKey: ["guard-events", days, offset], queryFn: () => getGuardEvents(days, offset),
    enabled: summary.isSuccess, refetchInterval: 60_000 });

  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };
  const s = summary.data;

  if (isUpgradeRequired(summary.error) || status(summary.error) === 403) {
    const upgrade = isUpgradeRequired(summary.error);
    return (
      <div className="rounded-xl p-8 text-center max-w-lg mx-auto" style={panel}>
        <ShieldAlert size={22} className="mx-auto mb-3" style={{ color: "var(--accent)" }} />
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          {upgrade ? "AI Guard is an add-on" : "Only an admin can see this"}
        </h2>
        <p className="text-sm mt-2" style={muted}>
          {upgrade
            ? "See when client data is pasted or uploaded into AI chats and websites. Ask your SAVIO contact to switch it on."
            : "This page names the people involved, so it is limited to admins."}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-6xl">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><ShieldAlert size={18} /></div>
          <div>
            <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>What was found</h1>
            <p className="text-xs max-w-2xl" style={muted}>
              Sensitive data the SAVIO browser extension saw being pasted, dropped, uploaded or sent on a website. Only what
              kind and how many is recorded. The content itself is checked on the PC and never leaves it.
            </p>
          </div>
        </div>
        <select value={days} onChange={(e) => { setDays(Number(e.target.value)); setOffset(0); }}
          className="px-3 py-1.5 rounded-lg text-sm outline-none"
          style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          {[7, 30, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}
        </select>
      </div>

      {summary.isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {summary.error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(summary.error, "Could not load.")}</p>}

      {s && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {([["Found", s.total, "var(--text-primary)"], ["Warned", s.warned, "#f59e0b"],
               ["Blocked", s.blocked, "#ef4444"], ["Could not check", s.unknown, "var(--text-secondary)"]] as const)
              .map(([label, n, color]) => (
                <div key={label} className="rounded-xl p-4" style={panel}>
                  <div className="text-xs" style={muted}>{label}</div>
                  <div className="text-2xl font-semibold mt-1" style={{ color }}>{n}</div>
                </div>
              ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="rounded-xl p-4 space-y-1.5" style={panel}>
              <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>What</h2>
              {(Object.entries(s.kinds) as [FindingKind, number][]).map(([k, n]) => (
                <Row key={k} label={FINDING_KINDS[k] ?? k} n={n} />
              ))}
              {s.contact_lists > 0 && <Row label="Contact lists" n={s.contact_lists} />}
              {s.keyword_events > 0 && <Row label="Restricted keywords" n={s.keyword_events} />}
              {!Object.keys(s.kinds).length && !s.contact_lists && !s.keyword_events && <Empty />}
            </div>
            <div className="rounded-xl p-4 space-y-1.5" style={panel}>
              <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Where</h2>
              {s.top_sites.map((x) => <Row key={x.site} label={x.site} n={x.events} mono />)}
              {!s.top_sites.length && <Empty />}
            </div>
            <div className="rounded-xl p-4 space-y-1.5" style={panel}>
              <h2 className="text-sm font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Who</h2>
              {s.top_people.map((x) => <Row key={x.windows_user} label={x.windows_user} n={x.events} />)}
              {!s.top_people.length && <Empty />}
            </div>
          </div>

          <div className="rounded-xl overflow-x-auto" style={panel}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["When", "PC · person", "Site", "How", "Found", "Result"].map((h) => (
                    <th key={h} className="text-left px-4 py-2 text-xs uppercase whitespace-nowrap" style={muted}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(events.data ?? []).map((e) => (
                  <tr key={e.id} style={{ borderBottom: "1px solid var(--border)", color: "var(--text-primary)" }}>
                    <td className="px-4 py-2 text-xs whitespace-nowrap" style={muted}>{new Date(e.occurred_at).toLocaleString()}</td>
                    <td className="px-4 py-2 text-xs"><span className="font-medium">{e.hostname}</span><span className="block" style={muted}>{e.windows_user}</span></td>
                    <td className="px-4 py-2 font-mono text-xs">{e.site}</td>
                    <td className="px-4 py-2 text-xs">{CHANNEL[e.channel]}</td>
                    <td className="px-4 py-2 text-xs">{found(e)}</td>
                    <td className="px-4 py-2 text-xs font-medium" style={{ color: RESULT[e.action].color }}>{RESULT[e.action].label}</td>
                  </tr>
                ))}
                {events.data && !events.data.length && (
                  <tr><td colSpan={6} className="px-4 py-6 text-center text-sm" style={muted}>
                    {offset ? "No older events." : "Nothing found in this period. PCs report within a minute of an event."}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
          {(offset > 0 || (events.data?.length ?? 0) === 100) && (
            <div className="flex justify-end gap-2">
              <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 100))}
                className="px-3 py-1.5 rounded-lg text-sm disabled:opacity-40" style={{ ...panel, color: "var(--text-primary)" }}>Newer</button>
              <button disabled={(events.data?.length ?? 0) < 100} onClick={() => setOffset(offset + 100)}
                className="px-3 py-1.5 rounded-lg text-sm disabled:opacity-40" style={{ ...panel, color: "var(--text-primary)" }}>Older</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Row({ label, n, mono }: { label: string; n: number; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm" style={{ color: "var(--text-primary)" }}>
      <span className={`truncate ${mono ? "font-mono text-xs" : ""}`}>{label}</span>
      <span className="text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>{n}</span>
    </div>
  );
}

function Empty() {
  return <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Nothing yet.</p>;
}
