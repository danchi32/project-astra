"use client";
import { useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Info, ArrowRight } from "lucide-react";
import {
  getAttendance, getTeamRollup, getAccounts,
  type DailyUserSummary,
} from "@/lib/api/tracker";
import { TrackerHeader } from "./TrackerHeader";
import {
  UpgradeRequired,
  isUpgradeRequired,
  requiredFeature,
} from "@/components/upgrade-required";

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

/** Sum a nullable minute field across rows: null stays unknown, so we track whether ANY row had
 *  a measured value and show "—" when none did, never a misleading 0. */
function sumOptional(rows: DailyUserSummary[], key: keyof DailyUserSummary): number | null {
  let total = 0;
  let measured = false;
  for (const r of rows) {
    const v = r[key];
    if (typeof v === "number") { total += v; measured = true; }
  }
  return measured ? total : null;
}

const BUCKET = {
  productive: { label: "Productive", color: "#10b981" },
  neutral: { label: "Neutral", color: "#64748b" },
  unproductive: { label: "Unproductive", color: "#ef4444" },
} as const;

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{value}</p>
      <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{label}</p>
    </div>
  );
}

export default function TrackerDashboardPage() {
  const today = useMemo(() => new Date(), []);
  const range = useMemo(() => {
    const from = new Date(today);
    from.setDate(from.getDate() - 6);
    return { from: isoDay(from), to: isoDay(today) };
  }, [today]);

  const attendance = useQuery({
    queryKey: ["tracker-attendance", range.from, range.to],
    queryFn: () => getAttendance(range),
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });
  const teams = useQuery({
    queryKey: ["tracker-team-rollup", range.from, range.to],
    queryFn: () => getTeamRollup(range),
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });
  const accounts = useQuery({
    queryKey: ["tracker-accounts"],
    queryFn: getAccounts,
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });

  const err = attendance.error || teams.error || accounts.error;
  if (isUpgradeRequired(err)) return <UpgradeRequired feature={requiredFeature(err)} />;

  const rows = attendance.data ?? [];
  const accts = accounts.data ?? [];
  const teamRows = teams.data ?? [];

  const people = new Set(rows.map((r) => r.username)).size;
  const mapped = accts.filter((a) => a.user_id).length;
  const worked = rows.reduce((s, r) => s + r.worked_minutes, 0);
  const prod = sumOptional(rows, "productive_minutes");
  const neu = sumOptional(rows, "neutral_minutes");
  const unp = sumOptional(rows, "unproductive_minutes");
  const splitTotal = (prod ?? 0) + (neu ?? 0) + (unp ?? 0);

  const topTeams = [...teamRows].sort((a, b) => b.worked_minutes - a.worked_minutes).slice(0, 6);

  return (
    <div className="space-y-6">
      <TrackerHeader title="Tracker" subtitle="Workforce overview — last 7 days (UTC)" />

      <div
        className="rounded-xl px-4 py-3 flex items-start gap-2 text-xs"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
      >
        <Info size={14} className="mt-0.5 shrink-0" style={{ color: "var(--accent)" }} />
        <span>
          Activity tracking is on for this organisation and shown transparently to the people
          being tracked. Figures below cover the last 7 days; open a section for detail.
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="People tracked (7d)" value={String(people)} />
        <StatCard label="Accounts mapped to a person" value={`${mapped}/${accts.length}`} />
        <StatCard label="Worked (7d)" value={formatMinutes(worked)} />
        <StatCard label="Productive (7d)" value={prod == null ? "—" : formatMinutes(prod)} />
      </div>

      {/* Productivity split */}
      <div className="rounded-2xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Productivity split (7 days)</h2>
        {splitTotal === 0 ? (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No app/website activity measured yet.</p>
        ) : (
          <>
            <div className="flex h-3 rounded-full overflow-hidden" style={{ background: "var(--bg)" }}>
              <div style={{ width: `${((prod ?? 0) / splitTotal) * 100}%`, background: BUCKET.productive.color }} />
              <div style={{ width: `${((neu ?? 0) / splitTotal) * 100}%`, background: BUCKET.neutral.color }} />
              <div style={{ width: `${((unp ?? 0) / splitTotal) * 100}%`, background: BUCKET.unproductive.color }} />
            </div>
            <div className="flex flex-wrap gap-4 mt-3 text-xs">
              {([["productive", prod], ["neutral", neu], ["unproductive", unp]] as const).map(([k, v]) => (
                <span key={k} className="inline-flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
                  <span className="w-2.5 h-2.5 rounded-sm" style={{ background: BUCKET[k].color }} />
                  {BUCKET[k].label}:{" "}
                  <span className="tabular-nums" style={{ color: "var(--text-primary)" }}>{formatMinutes(v ?? 0)}</span>
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      {/* By team */}
      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 border-b flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>By department</h2>
          <Link href="/tracker/teams" className="text-xs inline-flex items-center gap-1 hover:underline" style={{ color: "var(--accent)" }}>
            All departments <ArrowRight size={12} />
          </Link>
        </div>
        <div className="p-5 space-y-2">
          {topTeams.length === 0 && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              No teams yet — set them up in Groups &amp; Teams and map people in Configuration.
            </p>
          )}
          {topTeams.map((t) => (
            <div key={t.team_id} className="flex items-center gap-3 text-sm">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: t.colour || "var(--accent)" }} />
              <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>{t.team_name}</span>
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{t.shift_name ?? "no shift"}</span>
              <span className="tabular-nums font-medium w-16 text-right" style={{ color: "var(--text-primary)" }}>{formatMinutes(t.worked_minutes)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
