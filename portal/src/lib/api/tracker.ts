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
  suspected_idle_minutes: number | null;
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
  idle_minutes: number | null;
  productive_minutes: number | null;
  neutral_minutes: number | null;
  unproductive_minutes: number | null;
  suspected_idle_minutes: number | null;
  days: DailyUserSummary[];
  apps: AppUsage[];
}

export const getUserDetail = (params: { username: string; from?: string; to?: string }) =>
  apiClient.get<UserDetail>("/tracker/user", { params }).then((r) => r.data);

/** A productivity bucket. The three the whole Tracker scores against. */
export type Bucket = "productive" | "neutral" | "unproductive";

/** Per-org reclassification: which apps/domains this org counts as what. Keys are a website
 *  host (github.com) or an app keyword (substring of the process name); values are a bucket.
 *  An override only flips the bucket — the built-in human label is kept. */
export interface CategoryOverrides {
  domain: Record<string, Bucket>;
  app: Record<string, Bucket>;
}

/** What the category-config screen reads: the buckets, the built-in defaults (for reference),
 *  and this org's overrides. */
export interface CategoryConfig {
  buckets: Bucket[];
  builtin: CategoryOverrides;
  overrides: CategoryOverrides;
}

export const getCategories = () =>
  apiClient.get<CategoryConfig>("/tracker/categories").then((r) => r.data);

/** Full replace — the body is the whole override set, so removing a rule is leaving it out. */
export const putCategories = (overrides: CategoryOverrides) =>
  apiClient.put<CategoryConfig>("/tracker/categories", overrides).then((r) => r.data);

/** A named department shift. Times are minutes from LOCAL midnight in `timezone`; when
 *  end_minute <= start_minute the shift runs past midnight (a night shift). working_days are
 *  0 (Monday) … 6 (Sunday). */
export interface WorkShift {
  id: string;
  name: string;
  timezone: string;
  start_minute: number;
  end_minute: number;
  working_days: number[];
  colour: string | null;
  team_count: number;
}

export type WorkShiftWrite = Omit<WorkShift, "id" | "team_count">;

/** One team with its current shift assignment. */
export interface TeamShift {
  team_id: string;
  team_name: string;
  member_count: number;
  shift_id: string | null;
  shift_name: string | null;
}

export const getShifts = () =>
  apiClient.get<WorkShift[]>("/tracker/shifts").then((r) => r.data);

export const createShift = (body: WorkShiftWrite) =>
  apiClient.post<WorkShift>("/tracker/shifts", body).then((r) => r.data);

export const updateShift = (id: string, body: WorkShiftWrite) =>
  apiClient.put<WorkShift>(`/tracker/shifts/${id}`, body).then((r) => r.data);

export const deleteShift = (id: string) =>
  apiClient.delete(`/tracker/shifts/${id}`).then((r) => r.data);

export const getTeamShifts = () =>
  apiClient.get<TeamShift[]>("/tracker/team-shifts").then((r) => r.data);

export const assignTeamShift = (teamId: string, shiftId: string | null) =>
  apiClient
    .put<TeamShift>(`/tracker/teams/${teamId}/shift`, { shift_id: shiftId })
    .then((r) => r.data);

/** A tracked Windows account and who it maps to. `user_id` null = not yet mapped to a person. */
export interface TrackedAccount {
  username: string;
  user_id: string | null;
  user_name: string | null;
  user_email: string | null;
  last_seen: string | null;
  device_count: number;
}

export const getAccounts = () =>
  apiClient.get<TrackedAccount[]>("/tracker/accounts").then((r) => r.data);

export const assignAccount = (username: string, userId: string | null) =>
  apiClient
    .put<TrackedAccount>("/tracker/accounts", { username, user_id: userId })
    .then((r) => r.data);
