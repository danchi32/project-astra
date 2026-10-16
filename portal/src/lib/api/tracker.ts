import { apiClient } from "./client";

/** One (device, Windows account, day) attendance row from the backend.
 *
 * Keyed on the Windows account the agent reports, not a portal user — `user_id` is the
 * reserved hook for resolving it to a directory user later and is null in Phase 1. The
 * active/idle/productive minute fields are null until their collectors (P2/P3) ship, so the
 * UI must show them as "—", never as a measured 0. */
export interface DailyUserSummary {
  device_id: string;
  device_hostname: string | null;
  username: string;
  user_id: string | null;
  day: string; // YYYY-MM-DD
  first_in: string | null;
  last_out: string | null;
  worked_minutes: number;
  active_minutes: number | null;
  idle_minutes: number | null;
  productive_minutes: number | null;
  neutral_minutes: number | null;
  unproductive_minutes: number | null;
}

/** One derived work/break span — the raw material behind a day's worked total. */
export interface WorkSessionSpan {
  device_id: string;
  username: string;
  day: string;
  kind: string; // "work" | "break"
  started_at: string;
  ended_at: string | null; // null while the span is still open (person is in now)
}

export const getAttendance = (params: {
  from?: string;
  to?: string;
  device_id?: string;
  username?: string;
} = {}) =>
  apiClient.get<DailyUserSummary[]>("/tracker/attendance", { params }).then((r) => r.data);

export const getDaySessions = (params: {
  device_id: string;
  username: string;
  day: string;
}) =>
  apiClient
    .get<WorkSessionSpan[]>("/tracker/attendance/sessions", { params })
    .then((r) => r.data);

/** Minutes in one app/website over the range, with its productivity bucket. */
export interface AppUsage {
  label: string;
  bucket: "productive" | "neutral" | "unproductive";
  minutes: number;
}

/** The per-user drill-down: per-day rows, productivity totals, and app breakdown. */
export interface UserDetail {
  username: string;
  day_from: string;
  day_to: string;
  worked_minutes: number;
  active_minutes: number | null;
  productive_minutes: number | null;
  neutral_minutes: number | null;
  unproductive_minutes: number | null;
  days: DailyUserSummary[];
  apps: AppUsage[];
}

export const getUserDetail = (params: { username: string; from?: string; to?: string }) =>
  apiClient.get<UserDetail>("/tracker/user", { params }).then((r) => r.data);
