"use client";
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Save, CalendarDays } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  getAttendanceConfig, putAttendanceSettings, addHoliday, deleteHoliday,
} from "@/lib/api/tracker";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
    weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
}

/** Configuration > Attendance: the working-day calendar, full/half-day thresholds, and the
 *  holiday list the register scores days against. Admin edits; others read. */
export function AttendanceConfig() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";
  const { data } = useQuery({ queryKey: ["tracker-attendance-config"], queryFn: getAttendanceConfig });

  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4]);
  const [fullH, setFullH] = useState(8);
  const [halfH, setHalfH] = useState(4);
  const [newDay, setNewDay] = useState("");
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setDays(data.working_days);
      setFullH(Math.round((data.full_day_minutes / 60) * 100) / 100);
      setHalfH(Math.round((data.half_day_minutes / 60) * 100) / 100);
    }
  }, [data]);

  const refresh = () => qc.invalidateQueries({ queryKey: ["tracker-attendance-config"] });

  const saveSettings = useMutation({
    mutationFn: () => putAttendanceSettings({
      working_days: days,
      full_day_minutes: Math.round(fullH * 60),
      half_day_minutes: Math.round(halfH * 60),
    }),
    onSuccess: (cfg) => { setError(null); qc.setQueryData(["tracker-attendance-config"], cfg); },
    onError: () => setError("Could not save — check the thresholds (half ≤ full) and days."),
  });

  const add = useMutation({
    mutationFn: () => addHoliday(newDay, newName.trim()),
    onSuccess: () => { setNewDay(""); setNewName(""); setError(null); refresh(); },
    onError: (e: unknown) => {
      const s = (e as { response?: { status?: number } })?.response?.status;
      setError(s === 409 ? "A holiday is already set for that date." : "Could not add the holiday.");
    },
  });

  const remove = useMutation({ mutationFn: (id: string) => deleteHoliday(id), onSuccess: refresh });

  const holidays = data?.holidays ?? [];
  const dirty = !!data && (
    JSON.stringify(days) !== JSON.stringify(data.working_days) ||
    Math.round(fullH * 60) !== data.full_day_minutes ||
    Math.round(halfH * 60) !== data.half_day_minutes
  );

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Attendance</h2>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Working days, full/half-day hours and holidays — the register scores days against these.
            {!isAdmin && " Only an admin can change these."}
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => saveSettings.mutate()}
            disabled={!dirty || saveSettings.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--accent)", color: "#fff" }}
          >
            <Save size={14} /> {saveSettings.isPending ? "Saving…" : "Save rules"}
          </button>
        )}
      </div>

      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{error}</p>}

      {/* Rules */}
      <div className="rounded-2xl p-5 space-y-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="flex flex-col gap-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
          Working days
          <div className="flex flex-wrap gap-1.5">
            {DAYS.map((d, i) => {
              const on = days.includes(i);
              return (
                <button
                  key={d}
                  disabled={!isAdmin}
                  onClick={() => setDays(on ? days.filter((x) => x !== i) : [...days, i].sort((a, b) => a - b))}
                  className="px-2.5 py-1.5 rounded-lg text-xs font-medium disabled:opacity-60"
                  style={{
                    background: on ? "var(--accent)" : "var(--bg)",
                    color: on ? "#fff" : "var(--text-secondary)",
                    border: "1px solid var(--border)",
                  }}
                >
                  {d}
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex flex-wrap gap-4">
          <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
            Full day (hours)
            <input type="number" min={0.5} max={24} step={0.5} value={fullH} disabled={!isAdmin}
              onChange={(e) => setFullH(Number(e.target.value))}
              className="w-28 px-3 py-2 rounded-lg text-sm outline-none disabled:opacity-60"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          </label>
          <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
            Half day (hours)
            <input type="number" min={0.5} max={24} step={0.5} value={halfH} disabled={!isAdmin}
              onChange={(e) => setHalfH(Number(e.target.value))}
              className="w-28 px-3 py-2 rounded-lg text-sm outline-none disabled:opacity-60"
              style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
          </label>
        </div>
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          A working day with at least the full-day hours counts Present; at least the half-day hours
          counts a half day; below that is Absent. Non-working days and holidays are never Absent.
        </p>
      </div>

      {/* Holidays */}
      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: "var(--border)" }}>
          <CalendarDays size={15} style={{ color: "var(--accent)" }} />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Holidays</h3>
        </div>
        <div className="p-5 space-y-2">
          {holidays.length === 0 && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No holidays set.</p>
          )}
          {holidays.map((hol) => (
            <div key={hol.id} className="flex items-center gap-3">
              <span className="w-40 shrink-0 text-sm tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatDay(hol.day)}</span>
              <span className="flex-1 text-sm" style={{ color: "var(--text-primary)" }}>{hol.name}</span>
              {isAdmin && (
                <button onClick={() => remove.mutate(hol.id)} className="p-1.5 rounded-lg" title="Remove holiday"
                  style={{ color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          ))}
          {isAdmin && (
            <div className="flex flex-wrap items-center gap-2 pt-2">
              <input type="date" value={newDay} onChange={(e) => setNewDay(e.target.value)}
                className="px-3 py-1.5 rounded-lg text-sm outline-none"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
              <input value={newName} placeholder="holiday name" onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && newDay && newName.trim()) add.mutate(); }}
                className="flex-1 min-w-[160px] px-3 py-1.5 rounded-lg text-sm outline-none"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
              <button onClick={() => add.mutate()} disabled={!newDay || !newName.trim() || add.isPending}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                <Plus size={14} /> Add
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
