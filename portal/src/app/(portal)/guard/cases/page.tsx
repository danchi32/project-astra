"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { closeGuardCase, getGuardCases, removeQuietSite, type GuardCase } from "@/lib/api/guard";
import { isUpgradeRequired } from "@/components/upgrade-required";
import { apiErrorMessage } from "@/lib/utils";

// Phase 3c · C1 · AI Guard → Cases. Not one alert per event: each person's run of events is one
// case, scored as a whole and explained in plain words. Only a high case notifies, once. IT
// closes it as expected (optionally making a site quiet) or handled. Admin only: cases name people.

const LEVEL: Record<GuardCase["level"], { label: string; color: string }> = {
  high: { label: "High", color: "#ef4444" },
  medium: { label: "Medium", color: "#f59e0b" },
  low: { label: "Low", color: "var(--text-secondary)" },
};
const RESOLUTION = { expected: "Expected", handled: "Handled" } as const;

const status = (e: unknown) => (e as { response?: { status?: number } } | null)?.response?.status;
const when = (s: string) => new Date(s).toLocaleString();

export default function GuardCasesPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"open" | "closed">("open");
  const { data, error, isLoading } = useQuery({ queryKey: ["guard-cases", tab], queryFn: () => getGuardCases(tab),
    retry: false, refetchInterval: 60_000 });
  const [quiet, setQuiet] = useState<Record<string, string>>({});   // case id → site to make quiet
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const muted = { color: "var(--text-secondary)" };
  const panel = { background: "var(--surface)", border: "1px solid var(--border)" };

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

  async function close(c: GuardCase, resolution: "expected" | "handled") {
    setBusy(c.id); setMsg(null);
    const site = resolution === "expected" ? quiet[c.id] || null : null;
    try {
      await closeGuardCase(c.id, resolution, site);
      setMsg({ ok: true, text: `Closed as ${RESOLUTION[resolution].toLowerCase()}.`
        + (site ? ` ${site} no longer raises cases; its events are still recorded.` : "") });
      await qc.invalidateQueries({ queryKey: ["guard-cases"] });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not close the case.") });
    } finally { setBusy(null); }
  }

  async function unquiet(site: string) {
    setMsg(null);
    try {
      await removeQuietSite(site);
      await qc.invalidateQueries({ queryKey: ["guard-cases"] });
    } catch (e) {
      setMsg({ ok: false, text: apiErrorMessage(e, "Could not change it.") });
    }
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><ShieldAlert size={18} /></div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Cases</h1>
          <p className="text-xs max-w-2xl" style={muted}>
            Instead of an alert for every event, SAVIO joins what one person does into one case, ranks it by the whole
            story (how much, what kind, where it went, whether they went ahead after a warning) and says why. Only a high
            case notifies you, once. You see what kind of data it was, never the data itself.
          </p>
        </div>
      </div>

      {data && (
        <div className="flex flex-wrap gap-3 text-sm">
          {(["high", "medium", "low"] as const).map((l) => (
            <div key={l} className="rounded-xl px-4 py-2" style={panel}>
              <span className="text-lg font-semibold" style={{ color: LEVEL[l].color }}>{data.open[l]}</span>{" "}
              <span style={muted}>{LEVEL[l].label.toLowerCase()} open</span>
            </div>
          ))}
          {data.quiet_sites.length > 0 && (
            <div className="rounded-xl px-4 py-2 text-xs flex flex-wrap items-center gap-2" style={panel}>
              <span style={muted}>Quiet sites ({data.quiet_events_30d} events in 30 days, not raised):</span>
              {data.quiet_sites.map((s) => (
                <span key={s} className="font-mono inline-flex items-center gap-1" style={{ color: "var(--text-primary)" }}>
                  {s}
                  <button onClick={() => unquiet(s)} className="underline" style={muted} title="Raise cases for it again">undo</button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2">
        {(["open", "closed"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className="px-3 py-1.5 rounded-lg text-sm"
            style={tab === t ? { background: "var(--accent)", color: "white" } : { ...panel, color: "var(--text-primary)" }}>
            {t === "open" ? "Open" : "Closed"}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load.")}</p>}
      {msg && <p className="text-xs" style={{ color: msg.ok ? "#10b981" : "#ef4444" }}>{msg.text}</p>}

      {data && !data.cases.length && (
        <p className="text-sm" style={muted}>{tab === "open" ? "No open cases. Nothing needs a look." : "No closed cases yet."}</p>
      )}

      {data?.cases.map((c) => (
        <div key={c.id} className="rounded-xl p-4 space-y-3" style={{ ...panel, borderLeft: `4px solid ${LEVEL[c.level].color}` }}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="text-sm" style={{ color: "var(--text-primary)" }}>
              <span className="text-xs font-semibold uppercase mr-2" style={{ color: LEVEL[c.level].color }}>{LEVEL[c.level].label}</span>
              <span className="font-medium">{c.windows_user}</span>
              <span style={muted}> · {c.devices.join(", ")} · {c.events} event{c.events === 1 ? "" : "s"}</span>
            </div>
            <div className="text-xs" style={muted}>
              {when(c.opened_at)} – {when(c.last_event_at)}
              {c.status === "closed" && c.resolution && <> · {RESOLUTION[c.resolution]} {c.closed_at ? when(c.closed_at) : ""}</>}
            </div>
          </div>

          <ul className="text-sm list-disc pl-5 space-y-0.5" style={{ color: "var(--text-primary)" }}>
            {c.reasons.map((r) => <li key={r}>{r}</li>)}
          </ul>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  {["Site", "Came from", "Events", "Sensitive items", "Contact lists", "Went ahead after a warning", "Blocked", "How"].map((h) => (
                    <th key={h} className="text-left py-1 pr-3 uppercase whitespace-nowrap" style={muted}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {c.sites.map((s) => (
                  <tr key={s.site} style={{ color: "var(--text-primary)" }}>
                    <td className="py-1 pr-3 font-mono">{s.site}{s.new && <span className="ml-1" style={{ color: "#f59e0b" }}>new</span>}</td>
                    <td className="py-1 pr-3 font-mono" style={muted}>{s.origins?.length ? s.origins.join(", ") : "—"}</td>
                    <td className="py-1 pr-3">{s.events}</td>
                    <td className="py-1 pr-3">{s.items}</td>
                    <td className="py-1 pr-3">{s.contact_lists}</td>
                    <td className="py-1 pr-3">{s.went_ahead}</td>
                    <td className="py-1 pr-3">{s.blocked}</td>
                    <td className="py-1 pr-3" style={muted}>{s.channels.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {c.status === "open" && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <button disabled={busy === c.id} onClick={() => close(c, "handled")}
                className="px-3 py-1.5 rounded-lg text-sm font-medium text-white disabled:opacity-50" style={{ background: "var(--accent)" }}>
                Handled
              </button>
              <button disabled={busy === c.id} onClick={() => close(c, "expected")}
                className="px-3 py-1.5 rounded-lg text-sm disabled:opacity-50" style={{ ...panel, color: "var(--text-primary)" }}>
                Expected (normal work)
              </button>
              <label className="text-xs flex items-center gap-1" style={muted}>
                and stop raising cases for
                <select value={quiet[c.id] ?? ""} onChange={(e) => setQuiet({ ...quiet, [c.id]: e.target.value })}
                  className="px-2 py-1 rounded-lg text-xs outline-none"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                  <option value="">no site</option>
                  {c.sites.map((s) => <option key={s.site} value={s.site}>{s.site}</option>)}
                </select>
              </label>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
