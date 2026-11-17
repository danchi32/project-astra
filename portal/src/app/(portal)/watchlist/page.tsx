"use client";
import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Eye } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import { getWatchlist } from "@/lib/api/watchlist";
import { apiErrorMessage } from "@/lib/utils";

// N2 · Watchlist. These are problems you only notice because something did NOT happen: a PC
// stopped reporting, a warranty date passed, a fix never finished. There is no scheduler yet,
// so nothing is e-mailed; this page is where they show.

const BUCKET: Record<string, { label: string; color: string }> = {
  expired: { label: "Ended", color: "#ef4444" },
  "30": { label: "≤ 30 days", color: "#f59e0b" },
  "60": { label: "≤ 60 days", color: "#3b82f6" },
  "90": { label: "≤ 90 days", color: "var(--text-secondary)" },
};

function Section({ title, count, empty, children }: { title: string; count: number; empty: string; children: ReactNode }) {
  return (
    <div className="rounded-xl" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="px-4 py-3 text-sm font-semibold" style={{ color: "var(--text-primary)", borderBottom: "1px solid var(--border)" }}>
        {title} <span style={{ color: count ? "#f59e0b" : "var(--text-secondary)" }}>({count})</span>
      </p>
      {count ? <div className="divide-y" style={{ borderColor: "var(--border)" }}>{children}</div>
        : <p className="px-4 py-4 text-sm" style={{ color: "var(--text-secondary)" }}>{empty}</p>}
    </div>
  );
}

function Row({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2 text-sm" style={{ borderTop: "1px solid var(--border)" }}>
      <span style={{ color: "var(--text-primary)" }}>{left}</span>
      <span className="text-xs text-right" style={{ color: "var(--text-secondary)" }}>{right}</span>
    </div>
  );
}

export default function WatchlistPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isStaff = me?.role === "admin" || me?.role === "technician";
  const [hours, setHours] = useState(6);
  const { data, isLoading, error } = useQuery({
    queryKey: ["watchlist", hours], queryFn: () => getWatchlist(hours), enabled: isStaff, refetchInterval: 60_000,
  });
  const muted = { color: "var(--text-secondary)" };

  if (me && !isStaff) return <p className="text-sm" style={muted}>The watchlist is for IT staff.</p>;

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.12)", color: "var(--accent)" }}><Eye size={18} /></div>
          <div>
            <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Watchlist</h1>
            <p className="text-xs max-w-xl" style={muted}>
              Problems you only notice because something did not happen: a PC stopped reporting, a warranty is running out,
              a fix never finished. Shown here when you look; nothing is e-mailed on a schedule yet.
            </p>
          </div>
        </div>
        <label className="text-xs flex items-center gap-2" style={muted}>
          Quiet for more than
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))} className="px-2 py-1 rounded-lg text-sm"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
            {[6, 24, 72, 168].map((h) => <option key={h} value={h}>{h < 24 ? `${h} hours` : `${h / 24} day${h > 24 ? "s" : ""}`}</option>)}
          </select>
        </label>
      </div>

      {isLoading && <p className="text-sm" style={muted}>Loading…</p>}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{apiErrorMessage(error, "Could not load the watchlist.")}</p>}
      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Section title="PCs gone quiet" count={data.silent.length} empty={`Every PC has reported in the last ${data.silent_hours} hours.`}>
            {data.silent.map((p) => (
              <Row key={p.device_id} left={<Link href={`/devices/${p.device_id}`} className="hover:underline">{p.hostname}</Link>}
                right={p.last_seen_at ? `last seen ${p.hours} h ago` : `never reported (enrolled ${p.hours} h ago)`} />
            ))}
          </Section>

          <Section title="Warranties ending" count={data.warranty.length} empty="No warranty ends in the next 90 days.">
            {data.warranty.map((w) => (
              <Row key={w.asset_id} left={w.name}
                right={<span style={{ color: BUCKET[w.bucket].color }}>
                  {BUCKET[w.bucket].label} · {w.ends}{w.days_left < 0 ? ` (${-w.days_left} days ago)` : ` (${w.days_left} days)`}
                </span>} />
            ))}
          </Section>

          <Section title="Work that never finished" count={data.stuck.length} empty="Nothing has been queued or running for over a day.">
            {data.stuck.map((t) => (
              <Row key={t.task_id} left={<>{t.action} on {t.hostname ?? "—"}{t.rollout && <span style={muted}> · {t.rollout}</span>}</>}
                right={`${t.state} · ${t.hours} h`} />
            ))}
          </Section>

          <Section title="Agents behind the current release" count={data.agents_behind.length}
            empty={data.latest_agent ? `Every PC runs ${data.latest_agent} or later.` : "No update channel is configured, so there is nothing to compare against."}>
            {data.agents_behind.map((a) => (
              <Row key={a.hostname} left={a.hostname} right={`${a.version} → ${data.latest_agent}`} />
            ))}
          </Section>
        </div>
      )}
    </div>
  );
}
