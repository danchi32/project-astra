import { apiClient } from "./client";
import type { RemediationTask } from "./types";

export const listRemediations = () =>
  apiClient.get<RemediationTask[]>("/remediations").then((r) => r.data);

export const approveRemediation = (id: string) =>
  apiClient.post<RemediationTask>(`/remediations/${id}/approve`).then((r) => r.data);

export const rejectRemediation = (id: string) =>
  apiClient.post<RemediationTask>(`/remediations/${id}/reject`).then((r) => r.data);
