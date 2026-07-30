import { apiClient } from "./client";
import type { RemediationTask } from "./types";

export const listRemediations = () =>
  apiClient.get<RemediationTask[]>("/remediations").then((r) => r.data);

// Create a remediation task (staff only). Used e.g. to push a Windows Update install
// from the Telemetry → Windows Updates view.
export const createRemediation = (data: {
  device_id: string;
  action_id: string;
  params?: Record<string, string>;
  reason: string;   // required by the backend — an audit-visible justification
  /**
   * Approve in the same call. Use it wherever the person clicking IS the approver — they
   * picked this exact action and pressed Run. Creating then approving in two calls left the
   * task briefly pending, which fired an "Approval needed" notification for something
   * approved milliseconds later and kept the approval queue permanently empty. Role checks
   * are still enforced server-side.
   */
  approve?: boolean;
}) => apiClient.post<RemediationTask>("/remediations", data).then((r) => r.data);

export const approveRemediation = (id: string) =>
  apiClient.post<RemediationTask>(`/remediations/${id}/approve`).then((r) => r.data);

export const rejectRemediation = (id: string) =>
  apiClient.post<RemediationTask>(`/remediations/${id}/reject`).then((r) => r.data);
