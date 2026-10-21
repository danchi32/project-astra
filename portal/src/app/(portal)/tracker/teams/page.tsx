"use client";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { getTeamRollup } from "@/lib/api/tracker";
import { TrackerHeader } from "../TrackerHeader";
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

/** Productivity totals are null until measured — show "—", never a measured 0. */
function formatOptional(min: number | null): string {
  return min == null ? "—" : formatMinutes(min);
}

export default function TrackerTeamsPage() {
  const today = useMemo(() => new Date(), []);
  const [from, setFrom] = useState(() => {
    const d = new Date(today);
    d.setDate(d.getDate() - 6);
    return isoDay(d);
  });
  const [to, setTo] = useState(() => isoDay(today));

  const { data, error, isFetching } = useQuery({
    queryKey: ["tracker-team-rollup", from, to],
    queryFn: () => getTeamRollup({ from, to }),
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });

  if (isUpgradeRequired(error)) {
    return <UpgradeRequired feature={requiredFeature(error)} />;
  }

  const rows = data ?? [];

  return (
    <div className="space-y-6">
      <TrackerHeader
        title="Departments"
        subtitle="Attendance and productivity by department, measured against each one's shift"
      />

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

      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Team", "Shift", "Members", "Worked", "Active", "Productive", "Unproductive"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.team_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-5 py-3 font-medium" style={{ color: "var(--text-primary)" }}>
                    <span className="inline-flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: t.colour || "var(--accent)" }} />
                      {t.team_name}
                    </span>
                  </td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>{t.shift_name ?? "—"}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}
                    title={`${t.tracked_members} of ${t.member_count} with tracked activity`}>
                    {t.tracked_members}/{t.member_count}
                  </td>
                  <td className="px-5 py-3 tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>{formatMinutes(t.worked_minutes)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptional(t.active_minutes)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptional(t.productive_minutes)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptional(t.unproductive_minutes)}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                    <Users size={18} className="inline mb-1 opacity-60" />
                    <div>
                      {isFetching
                        ? "Loading…"
                        : "No teams yet. Create teams under Groups & Teams, map accounts to people in Configuration → People, and add people to teams."}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
