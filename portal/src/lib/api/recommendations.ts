import { apiClient } from "./client";

// J2: what SAVIO recommends, rebuilt from live data on every read.
export interface Recommendation {
  id: string;
  key: string;
  title: string;
  evidence: { count: number; devices: string[]; detail: string | null };
  risk: "high" | "medium" | "low";
  effort: "one_click" | "manual" | "purchase";
  action_id: string | null;
  advice: string;
  status: "open" | "dismissed" | "resolved";
  time_minutes: number | null;
  inr: number | null;
  basis: string | null;
  dismissed_reason: string | null;
  dismissed_at: string | null;
  created_at: string;
}

export const listRecommendations = (status: Recommendation["status"]) =>
  apiClient.get<Recommendation[]>("/recommendations", { params: { status } }).then((r) => r.data);

export const dismissRecommendation = (id: string, reason: string) =>
  apiClient.post<Recommendation>(`/recommendations/${id}/dismiss`, { reason }).then((r) => r.data);

export const restoreRecommendation = (id: string) =>
  apiClient.post<Recommendation>(`/recommendations/${id}/restore`).then((r) => r.data);
