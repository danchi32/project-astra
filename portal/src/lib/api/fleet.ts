import { apiClient } from "./client";

export interface FleetAffected {
  device_id: string;
  hostname: string;
}

export interface FleetIssue {
  key: string;
  category: string; // "compliance" | "update"
  title: string;
  detail: string;
  severity: string; // "high" | "medium" | "low"
  fix_action_id: string | null;
  fix_params: Record<string, string> | null;
  /** Why there's no one-click fix, and what to do instead. Set only when fix_action_id is null. */
  fix_note: string | null;
  affected: FleetAffected[];
}

export interface BulkRemediateResult {
  queued: number;
  failed: number;
  error: string | null;
}

export const getFleetIssues = () =>
  apiClient.get<{ issues: FleetIssue[] }>("/fleet/issues").then((r) => r.data.issues);

export const bulkRemediate = (body: {
  device_ids: string[];
  action_id: string;
  params?: Record<string, string>;
  reason: string;
}) => apiClient.post<BulkRemediateResult>("/fleet/remediate", body).then((r) => r.data);
