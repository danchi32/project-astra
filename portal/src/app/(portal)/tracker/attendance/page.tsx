"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Download, Info, Search } from "lucide-react";
import { getAttendance, type DailyUserSummary } from "@/lib/api/tracker";
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

/** Minutes → "7h 30m". Attendance worked time is always a measured number, so 0 is a real 0,
 *  shown as "0m" rather than a dash. */
function formatWorked(min: number): string {
  if (min <= 0) return "0m";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

/** The P2/P3 minute fields are null until their collectors ship — show "—", never a 0 that
 *  would read as "measured and nothing". */
function formatOptionalMinutes(min: number | null): string {
  return min == null ? "—" : formatWorked(min);
}

/** A UTC clock time, because the day a row is counted against is a UTC calendar day — showing
 *  the time in a different zone than the day boundary is how a late-evening login lands on
 *  the "wrong" day on screen. */
function formatTimeUtc(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });
}

function formatDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

function toCsv(rows: DailyUserSummary[]): string {
  const header = [
    "Date (UTC)",
    "User",
    "Device",
    "First in (UTC)",
    "Last out (UTC)",
    "Worked minutes",
    "Worked",
  ];
  const esc = (v: string | number | null) => {
    const s = v == null ? "" : String(v);
    // Quote anything with a comma, quote or newline; double embedded quotes. A Windows
    // account like DOMAIN\user is fine unquoted, but first/last-out can be empty and a
    // future display name could carry a comma.
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = rows.map((r) =>
    [
      r.day,
      r.username,
      r.device_hostname ?? r.device_id,
      formatTimeUtc(r.first_in),
      formatTimeUtc(r.last_out),
      r.worked_minutes,
      formatWorked(r.worked_minutes),
    ]
      .map(esc)
      .join(","),
  );
  return [header.join(","), ...lines].join("\r\n");
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

export default function TrackerPage() {
  const today = useMemo(() => new Date(), []);
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
    // A plan refusal is a settled answer, not a blip — don't retry it.
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });

  const rows = useMemo(() => {
    const all = data ?? [];
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all.filter(
      (r) =>
        r.username.toLowerCase().includes(needle) ||
        (r.device_hostname ?? "").toLowerCase().includes(needle),
    );
  }, [data, q]);

  // The page stays reachable and explains itself rather than vanishing — hiding it would
  // make ASTRA look like it has no time tracking at all.
  if (isUpgradeRequired(error)) {
    return <UpgradeRequired feature={requiredFeature(error)} />;
  }

  return (
    <div className="space-y-6">
      <TrackerHeader
        title="Attendance"
        subtitle="First-in, last-out and worked hours per user, per day"
      />

      {/* Transparency note — this is monitoring, and saying so is part of the product. */}
      <div
        className="rounded-xl px-4 py-3 flex items-start gap-2 text-xs"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
      >
        <Info size={14} className="mt-0.5 shrink-0" style={{ color: "var(--accent)" }} />
        <span>
          Activity tracking is on for this organisation and shown transparently to the people
          being tracked. &ldquo;Worked&rdquo; means signed in and unlocked; active vs idle time
          arrives in a later phase. Times and day boundaries are in UTC.
        </span>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          From
          <input
            type="date"
            value={from}
            max={to}
            onChange={(e) => setFrom(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          To
          <input
            type="date"
            value={to}
            min={from}
            max={isoDay(today)}
            onChange={(e) => setTo(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
        </label>
        <div className="flex flex-col gap-1 text-xs flex-1 min-w-[200px]" style={{ color: "var(--text-secondary)" }}>
          Search
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: "var(--text-secondary)" }}
            />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="user or device…"
              className="w-full pl-9 pr-3 py-2 rounded-lg text-sm outline-none"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>
        </div>
        <button
          onClick={() => download(`attendance_${from}_to_${to}.csv`, toCsv(rows))}
          disabled={rows.length === 0}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}
          title={rows.length === 0 ? "Nothing to export" : "Export the rows below as CSV"}
        >
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Table */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Date", "User", "Device", "First in", "Last out", "Worked", "Active", "Productive"].map((h) => (
                  <th
                    key={h}
                    className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.device_id}-${r.username}-${r.day}`} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-5 py-3 whitespace-nowrap" style={{ color: "var(--text-secondary)" }}>
                    {formatDay(r.day)}
                  </td>
                  <td className="px-5 py-3 font-medium">
                    <Link
                      href={`/tracker/users/${encodeURIComponent(r.username)}`}
                      className="hover:underline"
                      style={{ color: "var(--accent)" }}
                    >
                      {r.username}
                    </Link>
                  </td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>
                    {r.device_hostname ?? "—"}
                  </td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {formatTimeUtc(r.first_in)}
                  </td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {r.last_out ? formatTimeUtc(r.last_out) : <span title="Still signed in">in now</span>}
                  </td>
                  <td className="px-5 py-3 tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>
                    {formatWorked(r.worked_minutes)}
                  </td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {formatOptionalMinutes(r.active_minutes)}
                  </td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {formatOptionalMinutes(r.productive_minutes)}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-5 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                    {isFetching
                      ? "Loading…"
                      : q.trim()
                        ? "No rows match your search."
                        : "No attendance in this range yet. It appears once agents that report activity check in."}
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
