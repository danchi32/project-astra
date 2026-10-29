"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, AlertTriangle, Moon } from "lucide-react";
import {
  getUserDetail, getUserTimeline,
  type AppUsage, type ActivitySegment,
} from "@/lib/api/tracker";
import {
  UpgradeRequired,
  isUpgradeRequired,
  requiredFeature,
} from "@/components/upgrade-required";

const BUCKET = {
  productive: { label: "Productive", color: "#10b981" },
  neutral: { label: "Neutral", color: "#64748b" },
  unproductive: { label: "Unproductive", color: "#ef4444" },
} as const;

function isoDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function formatMinutes(min: number): string {
  if (min <= 0) return "0m";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function formatOptional(min: number | null): string {
  return min == null ? "—" : formatMinutes(min);
}

function formatTimeUtc(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC",
  });
}

function formatDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
    weekday: "short", day: "numeric", month: "short", timeZone: "UTC",
  });
}

/** The productive/neutral/unproductive split as one stacked bar. */
function ProductivityBar({
  productive, neutral, unproductive,
}: { productive: number | null; neutral: number | null; unproductive: number | null }) {
  const p = productive ?? 0, n = neutral ?? 0, u = unproductive ?? 0;
  const total = p + n + u;
  if (total === 0) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No app/website activity measured for this range.</p>;
  }
  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden" style={{ background: "var(--bg)" }}>
        <div style={{ width: `${(p / total) * 100}%`, background: BUCKET.productive.color }} />
        <div style={{ width: `${(n / total) * 100}%`, background: BUCKET.neutral.color }} />
        <div style={{ width: `${(u / total) * 100}%`, background: BUCKET.unproductive.color }} />
      </div>
      <div className="flex flex-wrap gap-4 mt-3 text-xs">
        {([["productive", p], ["neutral", n], ["unproductive", u]] as const).map(([k, v]) => (
          <span key={k} className="inline-flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: BUCKET[k].color }} />
            {BUCKET[k].label}: <span className="tabular-nums" style={{ color: "var(--text-primary)" }}>{formatMinutes(v)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function AppRow({ app, max }: { app: AppUsage; max: number }) {
  const color = BUCKET[app.bucket]?.color ?? BUCKET.neutral.color;
  return (
    <div className="flex items-center gap-3">
      <span className="w-40 shrink-0 truncate text-sm" style={{ color: "var(--text-primary)" }} title={app.label}>
        {app.label}
      </span>
      <div className="flex-1 h-2.5 rounded-full overflow-hidden" style={{ background: "var(--bg)" }}>
        <div style={{ width: `${max > 0 ? (app.minutes / max) * 100 : 0}%`, background: color, height: "100%" }} />
      </div>
      <span className="w-16 text-right text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
        {formatMinutes(app.minutes)}
      </span>
    </div>
  );
}

/** The timestamped activity timeline for one day: when each app/website was in use, merged into
 *  segments. Its own day picker, independent of the range above. */
function ActivityTimeline({ username, initialDay }: { username: string; initialDay: string }) {
  const [day, setDay] = useState(initialDay);
  const { data, isFetching } = useQuery({
    queryKey: ["tracker-timeline", username, day],
    queryFn: () => getUserTimeline(username, day),
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });
  const segments: ActivitySegment[] = data ?? [];
  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="px-5 py-3 border-b flex items-center justify-between gap-3" style={{ borderColor: "var(--border)" }}>
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Activity timeline</h2>
        <input type="date" value={day} max={isoDay(new Date())} onChange={(e) => setDay(e.target.value)}
          className="px-3 py-1.5 rounded-lg text-sm outline-none"
          style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
      </div>
      <div className="p-5">
        {segments.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {isFetching ? "Loading…" : "No app/website activity captured for this day."}
          </p>
        ) : (
          <ol>
            {segments.map((s, i) => {
              const color = BUCKET[s.bucket]?.color ?? BUCKET.neutral.color;
              return (
                <li key={`${s.started_at}-${i}`} className="flex items-start gap-3 py-2"
                  style={{ borderTop: i ? "1px solid var(--border)" : "none" }}>
                  <span className="w-28 shrink-0 text-xs tabular-nums pt-0.5" style={{ color: "var(--text-secondary)" }}>
                    {formatTimeUtc(s.started_at)}–{formatTimeUtc(s.ended_at)}
                  </span>
                  <span className="w-1 self-stretch rounded-full shrink-0" style={{ background: s.idle ? "var(--border)" : color }} />
                  <span className="flex-1 text-sm break-all" style={{ color: "var(--text-primary)" }}>
                    {s.label}
                    {s.idle && (
                      <span className="ml-2 inline-flex items-center gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                        <Moon size={11} /> idle
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatMinutes(s.minutes)}</span>
                </li>
              );
            })}
          </ol>
        )}
        <p className="text-xs mt-3" style={{ color: "var(--text-secondary)" }}>
          Times in UTC. Sensitive sites appear as &ldquo;(private site)&rdquo;; websites show the path only when path capture is on.
        </p>
      </div>
    </div>
  );
}

export default function UserDetailPage() {
  const params = useParams<{ user: string }>();
  const username = decodeURIComponent(params.user);

  const today = useMemo(() => new Date(), []);
  const [from, setFrom] = useState(() => {
    const d = new Date(today);
    d.setDate(d.getDate() - 6);
    return isoDay(d);
  });
  const [to, setTo] = useState(() => isoDay(today));

  const { data, error, isFetching } = useQuery({
    queryKey: ["tracker-user", username, from, to],
    queryFn: () => getUserDetail({ username, from, to }),
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });

  if (isUpgradeRequired(error)) {
    return <UpgradeRequired feature={requiredFeature(error)} />;
  }

  const maxApp = data?.apps[0]?.minutes ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/tracker/users" className="p-2 rounded-lg" style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
          <ArrowLeft size={16} />
        </Link>
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <Clock size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>{username}</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Time tracker — attendance and productivity (times in UTC)
          </p>
        </div>
      </div>

      {/* Range */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          From
          <input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </label>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          To
          <input type="date" value={to} min={from} max={isoDay(today)} onChange={(e) => setTo(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </label>
      </div>

      {/* Totals */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {([
          ["Worked", formatMinutes(data?.worked_minutes ?? 0)],
          ["Active", formatOptional(data?.active_minutes ?? null)],
          ["Idle", formatOptional(data?.idle_minutes ?? null)],
          ["Productive", formatOptional(data?.productive_minutes ?? null)],
          ["Unproductive", formatOptional(data?.unproductive_minutes ?? null)],
        ] as const).map(([label, val]) => (
          <div key={label} className="rounded-2xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <p className="text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{val}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{label}</p>
          </div>
        ))}
      </div>

      {/* Shift summary — only when the person's team has an assigned shift. Off-shift work is
          shown as overtime, never as absence or lateness. */}
      {data?.shift_name && (
        <div className="rounded-2xl p-4 flex flex-wrap items-center gap-x-6 gap-y-2"
          style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <span className="inline-flex items-center gap-2 text-sm">
            <Clock size={15} style={{ color: "var(--accent)" }} />
            <span style={{ color: "var(--text-secondary)" }}>Shift</span>
            <span className="font-medium" style={{ color: "var(--text-primary)" }}>{data.shift_name}</span>
          </span>
          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
            In-shift <span className="font-medium tabular-nums" style={{ color: "var(--text-primary)" }}>{formatOptional(data.in_shift_minutes)}</span>
          </span>
          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Overtime / off-shift <span className="font-medium tabular-nums" style={{ color: "#f59e0b" }}>{formatOptional(data.overtime_minutes)}</span>
          </span>
          <span className="text-xs flex-1 min-w-[220px]" style={{ color: "var(--text-secondary)" }}>
            Work outside the shift counts as overtime, not absence — so extra hours at another time are credited, never penalised.
          </span>
        </div>
      )}

      {/* Idle-faking review flag — only when there is something to review, and framed as a
          signal to check, never an accusation. */}
      {(data?.suspected_idle_minutes ?? 0) > 0 && (
        <div
          className="rounded-xl px-4 py-3 flex items-start gap-2 text-sm"
          style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.4)" }}
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: "#f59e0b" }} />
          <span style={{ color: "var(--text-secondary)" }}>
            <strong style={{ color: "var(--text-primary)" }}>
              {formatMinutes(data!.suspected_idle_minutes!)}
            </strong>{" "}
            of input looked mechanically repetitive (possible mouse-jiggler) — worth a look, not
            a conclusion. Based on mouse movement only.
          </span>
        </div>
      )}

      {/* Productivity split */}
      <div className="rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Productivity split</h2>
        <ProductivityBar
          productive={data?.productive_minutes ?? null}
          neutral={data?.neutral_minutes ?? null}
          unproductive={data?.unproductive_minutes ?? null} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top apps / sites */}
        <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Top apps & sites</h2>
          </div>
          <div className="p-5 space-y-3">
            {(data?.apps ?? []).slice(0, 12).map((app) => (
              <AppRow key={app.label} app={app} max={maxApp} />
            ))}
            {!data?.apps?.length && (
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {isFetching ? "Loading…" : "No app/website activity for this range."}
              </p>
            )}
          </div>
        </div>

        {/* Per-day */}
        <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border)" }}>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Daily breakdown</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Date", "First in", "Last out", "Worked", "Productive",
                    ...(data?.shift_name ? ["Late", "In-shift", "Overtime"] : [])].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data?.days ?? []).map((d) => (
                  <tr key={`${d.device_id}-${d.day}`} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td className="px-4 py-2.5 whitespace-nowrap" style={{ color: "var(--text-secondary)" }}>{formatDay(d.day)}</td>
                    <td className="px-4 py-2.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatTimeUtc(d.first_in)}</td>
                    <td className="px-4 py-2.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>{d.last_out ? formatTimeUtc(d.last_out) : "in now"}</td>
                    <td className="px-4 py-2.5 tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>{formatMinutes(d.worked_minutes)}</td>
                    <td className="px-4 py-2.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptional(d.productive_minutes)}</td>
                    {data?.shift_name && (
                      <>
                        <td className="px-4 py-2.5 tabular-nums" style={{ color: d.late_minutes ? "#f59e0b" : "var(--text-secondary)" }}>
                          {d.late_minutes == null ? "—" : d.late_minutes === 0 ? "On time" : `${formatMinutes(d.late_minutes)} late`}
                        </td>
                        <td className="px-4 py-2.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptional(d.in_shift_minutes)}</td>
                        <td className="px-4 py-2.5 tabular-nums" style={{ color: (d.overtime_minutes ?? 0) > 0 ? "#f59e0b" : "var(--text-secondary)" }}>{formatOptional(d.overtime_minutes)}</td>
                      </>
                    )}
                  </tr>
                ))}
                {!data?.days?.length && (
                  <tr><td colSpan={data?.shift_name ? 8 : 5} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                    {isFetching ? "Loading…" : "No attendance in this range."}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <ActivityTimeline username={username} initialDay={to} />
    </div>
  );
}
