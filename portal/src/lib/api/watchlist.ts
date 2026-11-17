import { apiClient } from "./client";

// N2: what has gone quiet, is running out, or never finished. On demand until a scheduler exists.
export interface Watchlist {
  silent_hours: number;
  silent: { device_id: string; hostname: string; last_seen_at: string | null; hours: number }[];
  warranty: { asset_id: string; name: string; ends: string; days_left: number; bucket: "expired" | "30" | "60" | "90" }[];
  stuck: { task_id: string; action: string; hostname: string | null; rollout: string | null; state: string; hours: number }[];
  latest_agent: string | null;
  agents_behind: { hostname: string; version: string }[];
}

export const getWatchlist = (silentHours: number) =>
  apiClient.get<Watchlist>("/watchlist", { params: { silent_hours: silentHours } }).then((r) => r.data);
