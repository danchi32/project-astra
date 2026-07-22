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
}) => apiClient.post<RemediationTask>("/remediations", data).then((r) => r.data);

export const approveRemediation = (id: string) =>
  apiClient.post<RemediationTask>(`/remediations/${id}/approve`).then((r) => r.data);

export const rejectRemediation = (id: string) =>
  apiClient.post<RemediationTask>(`/remediations/${id}/reject`).then((r) => r.data);
