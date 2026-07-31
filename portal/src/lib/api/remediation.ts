import { apiClient } from "./client";
import type { Page, PageParams, RemediationStatus, RemediationTask } from "./types";

export const listRemediations = (
  params: PageParams & { device_id?: string; status?: RemediationStatus[] } = {},
) =>
  apiClient
    .get<Page<RemediationTask>>("/remediations", {
      params,
      // Repeat the key per value (?status=a&status=b) — axios' default bracket form is not
      // what FastAPI reads a list query param from.
      paramsSerializer: { indexes: null },
    })
    .then((r) => r.data);

/** Tasks for one device, filtered in the database.
 *
 *  The device page used to pull the org's whole task list and filter it client-side. Paged,
 *  that becomes "the most recent 50 tasks, filtered" — a busy fleet would show a device as
 *  idle while a fix was queued on it. */
export const listRemediationsForDevice = (deviceId: string) =>
  apiClient
    .get<Page<RemediationTask>>("/remediations", {
      params: { device_id: deviceId, page_size: 200 },
    })
    .then((r) => r.data.items);

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

/** Org-wide task counts per status, for the dashboard chart. Counting the rows on a page
 *  would chart "the last 50 tasks" while looking exactly like a chart of everything. */
export const getRemediationSummary = () =>
  apiClient.get<Record<string, number>>("/remediations/summary").then((r) => r.data);

export const approveRemediation = (id: string) =>
  apiClient.post<RemediationTask>(`/remediations/${id}/approve`).then((r) => r.data);

export const rejectRemediation = (id: string) =>
  apiClient.post<RemediationTask>(`/remediations/${id}/reject`).then((r) => r.data);
