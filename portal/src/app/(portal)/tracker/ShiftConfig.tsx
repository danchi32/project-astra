"use client";
import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Pencil, Clock, X } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  getShifts, createShift, updateShift, deleteShift,
  getTeamShifts, assignTeamShift,
  type WorkShift, type WorkShiftWrite,
} from "@/lib/api/tracker";

// Common IANA zones covering the usual department spread (APAC / Middle East / UK-EU / US /
// India). The field is a free input backed by this list, and the backend validates any value,
// so an unlisted zone is still accepted — these are just the quick picks.
const TIMEZONES = [
  "Asia/Kolkata", "Asia/Singapore", "Asia/Dubai", "Asia/Tokyo", "Australia/Sydney",
  "Europe/London", "Europe/Berlin", "America/New_York", "America/Chicago",
  "America/Los_Angeles", "UTC",
];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DEFAULT_DAYS = [0, 1, 2, 3, 4];

const pad = (n: number) => String(n).padStart(2, "0");
const minToTime = (m: number) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
const timeToMin = (t: string) => {
  const [h, m] = t.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
};
const daysLabel = (d: number[]) =>
  d.length === 7 ? "Every day" : d.length === 0 ? "No days" : d.map((i) => DAYS[i]).join(" ");

interface FormState {
  id: string | null; // null => creating
  name: string;
  timezone: string;
  start: string;
  end: string;
  days: number[];
  colour: string;
}

const EMPTY: FormState = {
  id: null, name: "", timezone: "Asia/Kolkata", start: "09:00", end: "18:00",
  days: DEFAULT_DAYS, colour: "#6366f1",
};

function ShiftForm({
  form, onChange, onSubmit, onCancel, pending,
}: {
  form: FormState;
  onChange: (f: FormState) => void;
  onSubmit: () => void;
  onCancel: () => void;
  pending: boolean;
}) {
  const valid = form.name.trim() !== "" && form.days.length > 0 && form.start !== form.end;
  return (
    <div className="rounded-2xl p-5 space-y-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {form.id ? "Edit shift" : "New shift"}
        </h3>
        {form.id && (
          <button onClick={onCancel} className="p-1 rounded" style={{ color: "var(--text-secondary)" }} title="Cancel edit">
            <X size={16} />
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          Name
          <input
            value={form.name}
            placeholder="e.g. India General"
            onChange={(e) => onChange({ ...form, name: e.target.value })}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          Timezone
          <input
            list="tz-list"
            value={form.timezone}
            onChange={(e) => onChange({ ...form, timezone: e.target.value })}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
          <datalist id="tz-list">{TIMEZONES.map((z) => <option key={z} value={z} />)}</datalist>
        </label>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          Start (local)
          <input type="time" value={form.start} onChange={(e) => onChange({ ...form, start: e.target.value })}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </label>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          End (local)
          <input type="time" value={form.end} onChange={(e) => onChange({ ...form, end: e.target.value })}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }} />
        </label>
      </div>
      <div className="flex flex-col gap-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
        Working days
        <div className="flex flex-wrap gap-1.5">
          {DAYS.map((d, i) => {
            const on = form.days.includes(i);
            return (
              <button
                key={d}
                onClick={() =>
                  onChange({
                    ...form,
                    days: on ? form.days.filter((x) => x !== i) : [...form.days, i].sort((a, b) => a - b),
                  })}
                className="px-2.5 py-1.5 rounded-lg text-xs font-medium"
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
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
          Colour
          <input type="color" value={form.colour}
            onChange={(e) => onChange({ ...form, colour: e.target.value })}
            className="w-8 h-8 rounded cursor-pointer" style={{ border: "1px solid var(--border)", background: "none" }} />
        </label>
        <div className="flex-1" />
        <button
          onClick={onSubmit}
          disabled={!valid || pending}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--accent)", color: "#fff" }}
        >
          <Plus size={14} /> {pending ? "Saving…" : form.id ? "Save shift" : "Add shift"}
        </button>
      </div>
    </div>
  );
}

export function ShiftConfig() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const isAdmin = me?.role === "admin";

  const { data: shifts } = useQuery({ queryKey: ["tracker-shifts"], queryFn: getShifts });
  const { data: teamShifts } = useQuery({ queryKey: ["tracker-team-shifts"], queryFn: getTeamShifts });

  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["tracker-shifts"] });
    qc.invalidateQueries({ queryKey: ["tracker-team-shifts"] });
  };

  const body = (): WorkShiftWrite => ({
    name: form.name.trim(),
    timezone: form.timezone.trim(),
    start_minute: timeToMin(form.start),
    end_minute: timeToMin(form.end),
    working_days: form.days,
    colour: form.colour || null,
  });

  const save = useMutation({
    mutationFn: () => (form.id ? updateShift(form.id, body()) : createShift(body())),
    onSuccess: () => { setForm(EMPTY); setError(null); invalidate(); },
    onError: (e: unknown) => {
      const status = (e as { response?: { status?: number } })?.response?.status;
      setError(status === 409 ? "A shift with that name already exists." : "Could not save the shift.");
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteShift(id),
    onSuccess: () => { if (form.id) setForm(EMPTY); invalidate(); },
  });

  const assign = useMutation({
    mutationFn: ({ teamId, shiftId }: { teamId: string; shiftId: string | null }) =>
      assignTeamShift(teamId, shiftId),
    onSuccess: () => invalidate(),
  });

  const edit = (s: WorkShift) => {
    setError(null);
    setForm({
      id: s.id, name: s.name, timezone: s.timezone,
      start: minToTime(s.start_minute), end: minToTime(s.end_minute),
      days: s.working_days, colour: s.colour || "#6366f1",
    });
  };

  const shiftList = shifts ?? [];
  const teams = teamShifts ?? [];
  const hasAssignableTeams = teams.length > 0;

  const shiftOptions = useMemo(
    () => shiftList.map((s) => ({ id: s.id, name: s.name })),
    [shiftList],
  );

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          Department shifts
        </h2>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
          Define each department&apos;s working hours in its own timezone, then assign a shift to
          a team. {!isAdmin && "Only an admin can change these."}
        </p>
      </div>

      {isAdmin && (
        <ShiftForm
          form={form}
          onChange={setForm}
          onSubmit={() => save.mutate()}
          onCancel={() => { setForm(EMPTY); setError(null); }}
          pending={save.isPending}
        />
      )}
      {error && <p className="text-sm" style={{ color: "#ef4444" }}>{error}</p>}

      {/* Defined shifts */}
      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border)" }}>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Shifts</h3>
        </div>
        <div className="p-5 space-y-2">
          {shiftList.length === 0 && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No shifts defined yet.</p>
          )}
          {shiftList.map((s) => (
            <div key={s.id} className="flex items-center gap-3 py-1.5">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: s.colour || "var(--accent)" }} />
              <span className="font-medium text-sm w-32 truncate" style={{ color: "var(--text-primary)" }} title={s.name}>
                {s.name}
              </span>
              <span className="text-xs tabular-nums shrink-0" style={{ color: "var(--text-secondary)" }}>
                {minToTime(s.start_minute)}–{minToTime(s.end_minute)}
                {s.end_minute <= s.start_minute && " +1d"}
              </span>
              <span className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>{s.timezone}</span>
              <span className="text-xs flex-1 truncate" style={{ color: "var(--text-secondary)" }}>{daysLabel(s.working_days)}</span>
              <span className="text-xs shrink-0" style={{ color: "var(--text-secondary)" }}>
                {s.team_count} team{s.team_count === 1 ? "" : "s"}
              </span>
              {isAdmin && (
                <>
                  <button onClick={() => edit(s)} className="p-1.5 rounded-lg" title="Edit"
                    style={{ color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                    <Pencil size={13} />
                  </button>
                  <button onClick={() => remove.mutate(s.id)} className="p-1.5 rounded-lg" title="Delete"
                    style={{ color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
                    <Trash2 size={13} />
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Team → shift assignment */}
      <div className="rounded-2xl overflow-hidden" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border)" }}>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Team shift assignments</h3>
        </div>
        <div className="p-5 space-y-2">
          {!hasAssignableTeams && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              No teams yet — create teams under Groups &amp; Teams, then assign each a shift here.
            </p>
          )}
          {teams.map((t) => (
            <div key={t.team_id} className="flex items-center gap-3">
              <Clock size={14} className="shrink-0" style={{ color: "var(--text-secondary)" }} />
              <span className="flex-1 text-sm truncate" style={{ color: "var(--text-primary)" }} title={t.team_name}>
                {t.team_name}
                <span className="ml-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                  {t.member_count} member{t.member_count === 1 ? "" : "s"}
                </span>
              </span>
              <select
                value={t.shift_id ?? ""}
                disabled={!isAdmin || assign.isPending}
                onChange={(e) => assign.mutate({ teamId: t.team_id, shiftId: e.target.value || null })}
                className="px-2 py-1.5 rounded-lg text-sm outline-none disabled:opacity-60"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              >
                <option value="">No shift</option>
                {shiftOptions.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
