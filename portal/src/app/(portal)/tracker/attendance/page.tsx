"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Download, Info, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { getAttendance, getAttendanceConfig, type DailyUserSummary } from "@/lib/api/tracker";
import { TrackerHeader } from "../TrackerHeader";
import {
  UpgradeRequired,
  isUpgradeRequired,
  requiredFeature,
} from "@/components/upgrade-required";

/** YYYY-MM-DD for a Date, in the browser's own zone — the date inputs work in local days. */
function isoDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function formatWorked(min: number): string {
  if (min <= 0) return "0m";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function formatOptionalMinutes(min: number | null): string {
  return min == null ? "—" : formatWorked(min);
}

/** A UTC clock time, because the day a row is counted against is a UTC calendar day. */
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

function download(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const csvEsc = (v: string | number | null) => {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

// ── Register (monthly muster roll) ────────────────────────────────────────────

type Status = "present" | "half" | "absent" | "holiday" | "off" | "future";

// Convention mirrors the backend: a day's "weekday" is its UTC weekday, 0 = Monday … 6 = Sunday
// (JS getUTCDay is 0 = Sunday, so shift it).
function mondayIndex(year: number, month: number, day: number): number {
  return (new Date(Date.UTC(year, month, day)).getUTCDay() + 6) % 7;
}

function monthBounds(year: number, month: number) {
  // month is 0-based. Work in UTC since attendance days are UTC calendar days.
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const from = `${year}-${String(month + 1).padStart(2, "0")}-01`;
  const to = `${year}-${String(month + 1).padStart(2, "0")}-${String(days).padStart(2, "0")}`;
  return { days, from, to };
}

interface Rules {
  workingDays: Set<number>;
  holidays: Set<string>;
  fullMin: number;
  halfMin: number;
}

function dayStatus(year: number, month: number, day: number, worked: number | undefined, todayIso: string, rules: Rules): Status {
  const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  if (iso > todayIso) return "future";
  if (rules.holidays.has(iso)) return "holiday";
  if (!rules.workingDays.has(mondayIndex(year, month, day))) return "off";
  const w = worked ?? 0;
  if (w >= rules.fullMin) return "present";
  if (w >= rules.halfMin) return "half";
  return "absent"; // a working day below the half-day threshold
}

const STATUS_STYLE: Record<Status, { bg: string; fg: string }> = {
  present: { bg: "rgba(16,185,129,0.14)", fg: "#10b981" },
  half: { bg: "rgba(245,158,11,0.14)", fg: "#f59e0b" },
  absent: { bg: "rgba(239,68,68,0.12)", fg: "#ef4444" },
  holiday: { bg: "rgba(99,102,241,0.14)", fg: "#6366f1" },
  off: { bg: "var(--bg)", fg: "var(--text-secondary)" },
  future: { bg: "transparent", fg: "var(--text-secondary)" },
};

function RegisterView({ today }: { today: Date }) {
  const [cursor, setCursor] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const [q, setQ] = useState("");
  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const { days, from, to } = monthBounds(year, month);
  const todayIso = isoDay(today);
  const atCurrentMonth = year === today.getFullYear() && month === today.getMonth();

  const { data, error, isFetching } = useQuery({
    queryKey: ["tracker-attendance", from, to],
    queryFn: () => getAttendance({ from, to }),
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });
  const configQuery = useQuery({
    queryKey: ["tracker-attendance-config"],
    queryFn: getAttendanceConfig,
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });
  const rules: Rules = useMemo(() => ({
    workingDays: new Set(configQuery.data?.working_days ?? [0, 1, 2, 3, 4]),
    holidays: new Set((configQuery.data?.holidays ?? []).map((h) => h.day)),
    fullMin: configQuery.data?.full_day_minutes ?? 480,
    halfMin: configQuery.data?.half_day_minutes ?? 240,
  }), [configQuery.data]);
  const holidayName = (iso: string) =>
    (configQuery.data?.holidays ?? []).find((h) => h.day === iso)?.name ?? "Holiday";

  // Pivot to username → { dayNumber → worked minutes }, summing across a user's devices.
  const { users, workedByUser } = useMemo(() => {
    const map = new Map<string, Map<number, number>>();
    for (const r of data ?? []) {
      const day = Number(r.day.slice(8, 10));
      const u = map.get(r.username) ?? new Map<number, number>();
      u.set(day, (u.get(day) ?? 0) + r.worked_minutes);
      map.set(r.username, u);
    }
    const needle = q.trim().toLowerCase();
    const names = [...map.keys()].filter((n) => !needle || n.toLowerCase().includes(needle)).sort();
    return { users: names, workedByUser: map };
  }, [data, q]);

  const dayList = useMemo(() => Array.from({ length: days }, (_, i) => i + 1), [days]);

  // Per-person totals for the month.
  function personStats(username: string) {
    const worked = workedByUser.get(username);
    let present = 0, half = 0, absent = 0, totalWorked = 0;
    for (const d of dayList) {
      const w = worked?.get(d);
      const s = dayStatus(year, month, d, w, todayIso, rules);
      if (s === "present") { present += 1; totalWorked += w ?? 0; }
      else if (s === "half") { half += 1; totalWorked += w ?? 0; }
      else if (s === "absent") absent += 1;
    }
    return { present, half, absent, totalWorked };
  }

  const totals = useMemo(() => {
    let present = 0, half = 0, absent = 0, worked = 0;
    for (const u of users) {
      const s = personStats(u);
      present += s.present; half += s.half; absent += s.absent; worked += s.totalWorked;
    }
    return { present, half, absent, worked };
  }, [users, workedByUser, year, month, todayIso, rules]);

  if (isUpgradeRequired(error)) return <UpgradeRequired feature={requiredFeature(error)} />;

  const monthLabel = cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" });

  function exportCsv() {
    const header = ["User", ...dayList.map(String), "Present", "Half", "Absent", "Total worked"];
    const lines = users.map((u) => {
      const worked = workedByUser.get(u);
      const cells = dayList.map((d) => {
        const w = worked?.get(d);
        const s = dayStatus(year, month, d, w, todayIso, rules);
        if (s === "present" || s === "half") return (Math.round(((w ?? 0) / 60) * 10) / 10).toString();
        if (s === "absent") return "A";
        if (s === "holiday") return "H";
        if (s === "off") return "-";
        return "";
      });
      const st = personStats(u);
      return [u, ...cells, st.present, st.half, st.absent, formatWorked(st.totalWorked)].map(csvEsc).join(",");
    });
    download(`attendance_register_${from}.csv`, [header.join(","), ...lines].join("\r\n"));
  }

  return (
    <div className="space-y-4">
      {/* Month nav + search + export */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex items-center gap-1">
          <button onClick={() => setCursor(new Date(year, month - 1, 1))}
            className="p-2 rounded-lg" style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }} title="Previous month">
            <ChevronLeft size={16} />
          </button>
          <span className="px-3 text-sm font-medium tabular-nums" style={{ color: "var(--text-primary)" }}>{monthLabel}</span>
          <button onClick={() => setCursor(new Date(year, month + 1, 1))} disabled={atCurrentMonth}
            className="p-2 rounded-lg disabled:opacity-40" style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }} title="Next month">
            <ChevronRight size={16} />
          </button>
        </div>
        <div className="relative flex-1 min-w-[180px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="search user…"
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </div>
        <button onClick={exportCsv} disabled={users.length === 0}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          <Download size={14} /> Export register
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          ["People", String(users.length)],
          ["Present days", String(totals.present)],
          ["Half days", String(totals.half)],
          ["Absent days", String(totals.absent)],
          ["Worked this month", formatWorked(totals.worked)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
            <p className="text-2xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>{value}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>{label}</p>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs" style={{ color: "var(--text-secondary)" }}>
        {([["present", "Present (full day)"], ["half", "Half day"], ["absent", "Absent"], ["holiday", "Holiday"], ["off", "Non-working / weekend"]] as const).map(([k, label]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: STATUS_STYLE[k].bg, border: `1px solid ${STATUS_STYLE[k].fg}` }} />
            {label}
          </span>
        ))}
        <span className="opacity-70">Cell shows worked hours. Rules come from Configuration → Attendance.</span>
      </div>

      {/* Register matrix */}
      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th className="sticky left-0 z-10 px-3 py-2 text-left font-medium"
                  style={{ background: "var(--surface)", color: "var(--text-secondary)", minWidth: 160 }}>User</th>
                {dayList.map((d) => {
                  const weekday = new Date(Date.UTC(year, month, d)).getUTCDay();
                  const weekend = weekday === 0 || weekday === 6;
                  return (
                    <th key={d} className="px-0 py-2 text-center font-medium" style={{ minWidth: 30, color: weekend ? "var(--accent)" : "var(--text-secondary)" }}>
                      <div>{d}</div>
                      <div className="opacity-60">{["S", "M", "T", "W", "T", "F", "S"][weekday]}</div>
                    </th>
                  );
                })}
                <th className="px-3 py-2 text-center font-medium" style={{ color: "var(--text-secondary)", minWidth: 60 }}>P / A</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const worked = workedByUser.get(u);
                const st = personStats(u);
                return (
                  <tr key={u} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td className="sticky left-0 z-10 px-3 py-1.5 font-medium whitespace-nowrap" style={{ background: "var(--surface)" }}>
                      <Link href={`/tracker/users/${encodeURIComponent(u)}`} className="hover:underline" style={{ color: "var(--accent)" }}>{u}</Link>
                    </td>
                    {dayList.map((d) => {
                      const w = worked?.get(d);
                      const s = dayStatus(year, month, d, w, todayIso, rules);
                      const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
                      const style = STATUS_STYLE[s];
                      const label = s === "present" || s === "half" ? (Math.round((w ?? 0) / 60) || "<1")
                        : s === "absent" ? "A" : s === "holiday" ? "H" : s === "off" ? "·" : "";
                      const title = s === "present" || s === "half" ? `${formatWorked(w ?? 0)}${s === "half" ? " (half day)" : ""}`
                        : s === "absent" ? "Absent" : s === "holiday" ? holidayName(iso) : s === "off" ? "Non-working day" : "";
                      return (
                        <td key={d} className="text-center tabular-nums" style={{ background: style.bg, color: style.fg, padding: "6px 0" }} title={title}>
                          {label}
                        </td>
                      );
                    })}
                    <td className="px-3 py-1.5 text-center tabular-nums whitespace-nowrap" style={{ color: "var(--text-secondary)" }}>
                      <span style={{ color: "#10b981" }}>{st.present}</span>
                      {st.half > 0 && <> · <span style={{ color: "#f59e0b" }}>{st.half}</span></>}
                      {" / "}<span style={{ color: "#ef4444" }}>{st.absent}</span>
                    </td>
                  </tr>
                );
              })}
              {users.length === 0 && (
                <tr><td colSpan={days + 2} className="px-5 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                  {isFetching ? "Loading…" : "No attendance for this month yet."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── Daily log (the per-day table) ─────────────────────────────────────────────

function DailyLog({ today }: { today: Date }) {
  const [from, setFrom] = useState(() => {
    const d = new Date(today);
    d.setDate(d.getDate() - 6);
    return isoDay(d);
  });
  const [to, setTo] = useState(() => isoDay(today));
  const [q, setQ] = useState("");

  const { data, error, isFetching } = useQuery({
    queryKey: ["tracker-attendance", from, to],
    queryFn: () => getAttendance({ from, to }),
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });

  const rows = useMemo(() => {
    const all = data ?? [];
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all.filter((r) => r.username.toLowerCase().includes(needle) || (r.device_hostname ?? "").toLowerCase().includes(needle));
  }, [data, q]);

  function exportCsv(list: DailyUserSummary[]) {
    const header = ["Date (UTC)", "User", "Device", "First in (UTC)", "Last out (UTC)", "Worked minutes", "Worked"];
    const lines = list.map((r) => [
      r.day, r.username, r.device_hostname ?? r.device_id,
      formatTimeUtc(r.first_in), formatTimeUtc(r.last_out), r.worked_minutes, formatWorked(r.worked_minutes),
    ].map(csvEsc).join(","));
    download(`attendance_${from}_to_${to}.csv`, [header.join(","), ...lines].join("\r\n"));
  }

  if (isUpgradeRequired(error)) return <UpgradeRequired feature={requiredFeature(error)} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          From
          <input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm outline-none" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </label>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          To
          <input type="date" value={to} min={from} max={isoDay(today)} onChange={(e) => setTo(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm outline-none" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </label>
        <div className="flex flex-col gap-1 text-xs flex-1 min-w-[200px]" style={{ color: "var(--text-secondary)" }}>
          Search
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="user or device…"
              className="w-full pl-9 pr-3 py-2 rounded-lg text-sm outline-none" style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          </div>
        </div>
        <button onClick={() => exportCsv(rows)} disabled={rows.length === 0}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}>
          <Download size={14} /> Export CSV
        </button>
      </div>

      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Date", "User", "Device", "First in", "Last out", "Worked", "Active", "Productive"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.device_id}-${r.username}-${r.day}`} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-5 py-3 whitespace-nowrap" style={{ color: "var(--text-secondary)" }}>{formatDay(r.day)}</td>
                  <td className="px-5 py-3 font-medium">
                    <Link href={`/tracker/users/${encodeURIComponent(r.username)}`} className="hover:underline" style={{ color: "var(--accent)" }}>{r.username}</Link>
                  </td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>{r.device_hostname ?? "—"}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatTimeUtc(r.first_in)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{r.last_out ? formatTimeUtc(r.last_out) : <span title="Still signed in">in now</span>}</td>
                  <td className="px-5 py-3 tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>{formatWorked(r.worked_minutes)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptionalMinutes(r.active_minutes)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptionalMinutes(r.productive_minutes)}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={8} className="px-5 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                  {isFetching ? "Loading…" : q.trim() ? "No rows match your search." : "No attendance in this range yet. It appears once agents that report activity check in."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function AttendancePage() {
  const today = useMemo(() => new Date(), []);
  const [view, setView] = useState<"register" | "log">("register");

  return (
    <div className="space-y-6">
      <TrackerHeader title="Attendance" subtitle="Monthly register and the day-by-day log" />

      <div className="rounded-xl px-4 py-3 flex items-start gap-2 text-xs"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
        <Info size={14} className="mt-0.5 shrink-0" style={{ color: "var(--accent)" }} />
        <span>
          Activity tracking is on for this organisation and shown transparently to the people being
          tracked. &ldquo;Worked&rdquo; means signed in and unlocked. Times and day boundaries are in UTC.
        </span>
      </div>

      {/* View switch */}
      <div className="inline-flex rounded-lg p-0.5" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
        {([["register", "Register"], ["log", "Daily log"]] as const).map(([k, label]) => (
          <button key={k} onClick={() => setView(k)}
            className="px-4 py-1.5 rounded-md text-sm font-medium transition-colors"
            style={{ background: view === k ? "var(--accent)" : "transparent", color: view === k ? "#fff" : "var(--text-secondary)" }}>
            {label}
          </button>
        ))}
      </div>

      {view === "register" ? <RegisterView today={today} /> : <DailyLog today={today} />}
    </div>
  );
}
