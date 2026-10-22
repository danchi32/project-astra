"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { getAttendance, getAccounts } from "@/lib/api/tracker";
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
function formatOptional(min: number | null): string {
  return min == null ? "—" : formatMinutes(min);
}

interface Row {
  username: string;
  person: string | null;
  worked: number;
  active: number | null;
  productive: number | null;
}

export default function TrackerUsersPage() {
  const today = useMemo(() => new Date(), []);
  const [from, setFrom] = useState(() => {
    const d = new Date(today);
    d.setDate(d.getDate() - 6);
    return isoDay(d);
  });
  const [to, setTo] = useState(() => isoDay(today));
  const [q, setQ] = useState("");

  const attendance = useQuery({
    queryKey: ["tracker-attendance", from, to],
    queryFn: () => getAttendance({ from, to }),
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });
  const accounts = useQuery({
    queryKey: ["tracker-accounts"],
    queryFn: getAccounts,
    retry: (count, err) => !isUpgradeRequired(err) && count < 2,
  });

  const err = attendance.error || accounts.error;

  const rows: Row[] = useMemo(() => {
    const personByAccount = new Map(
      (accounts.data ?? []).map((a) => [a.username, a.user_name]),
    );
    const byUser = new Map<string, Row>();
    for (const r of attendance.data ?? []) {
      const cur = byUser.get(r.username) ?? {
        username: r.username, person: personByAccount.get(r.username) ?? null,
        worked: 0, active: null, productive: null,
      };
      cur.worked += r.worked_minutes;
      if (typeof r.active_minutes === "number") cur.active = (cur.active ?? 0) + r.active_minutes;
      if (typeof r.productive_minutes === "number")
        cur.productive = (cur.productive ?? 0) + r.productive_minutes;
      byUser.set(r.username, cur);
    }
    const all = [...byUser.values()].sort((a, b) => b.worked - a.worked);
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all.filter(
      (r) => r.username.toLowerCase().includes(needle) || (r.person ?? "").toLowerCase().includes(needle),
    );
  }, [attendance.data, accounts.data, q]);

  if (isUpgradeRequired(err)) return <UpgradeRequired feature={requiredFeature(err)} />;

  return (
    <div className="space-y-6">
      <TrackerHeader title="Employees" subtitle="Per-person worked time and productivity — click someone for detail" />

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
        <div className="flex flex-col gap-1 text-xs flex-1 min-w-[200px]" style={{ color: "var(--text-secondary)" }}>
          Search
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-secondary)" }} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="user or person…"
              className="w-full pl-9 pr-3 py-2 rounded-lg text-sm outline-none"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          </div>
        </div>
      </div>

      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["User", "Person", "Worked", "Active", "Productive"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.username} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-5 py-3 font-medium">
                    <Link href={`/tracker/users/${encodeURIComponent(r.username)}`} className="hover:underline" style={{ color: "var(--accent)" }}>
                      {r.username}
                    </Link>
                  </td>
                  <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>{r.person ?? "—"}</td>
                  <td className="px-5 py-3 tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>{formatMinutes(r.worked)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptional(r.active)}</td>
                  <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatOptional(r.productive)}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                    {attendance.isFetching ? "Loading…" : "No tracked users in this range yet."}
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
