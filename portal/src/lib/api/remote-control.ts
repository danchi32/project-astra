import { apiClient } from "./client";

/**
 * Where a request for someone's screen has got to.
 *
 * `declined` and `no_response` are separate and must stay that way in the UI. A refusal
 * is an answer — the technician has been told no and should stop. Silence is not an
 * answer: the person was in a meeting, or the prompt opened behind a full-screen window,
 * and the right next move is to try again or phone them. Showing both as "denied" is the
 * bug this distinction exists to prevent.
 */
export type RemoteSessionStatus =
  | "pending"
  | "approved"
  | "active"
  | "ended"
  | "declined"
  | "no_response"
  | "expired"
  | "failed";

export interface RemoteSession {
  id: string;
  device_id: string;
  device_hostname: string | null;
  requested_by_user_id: string;
  requested_by_name: string | null;
  reason: string;
  status: RemoteSessionStatus;
  requested_at: string;
  responded_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  /**
   * Present only once the person at the device has agreed, and only for the technician
   * who asked. It is a credential — it signs its bearer into the relay — so it is minted
   * per request and never stored. Treat it as write-once: put it in the iframe, don't
   * copy it anywhere, don't log it.
   */
  viewer_url: string | null;
  /** Seconds left on the prompt, from the server that enforces the deadline. */
  expires_in_seconds: number | null;
}

export interface RemoteSessionPage {
  items: RemoteSession[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export const requestRemoteSession = (body: { device_id: string; reason: string }) =>
  apiClient.post<RemoteSession>("/remote-sessions", body).then((r) => r.data);

export const getRemoteSession = (id: string) =>
  apiClient.get<RemoteSession>(`/remote-sessions/${id}`).then((r) => r.data);

export const endRemoteSession = (id: string) =>
  apiClient.post<RemoteSession>(`/remote-sessions/${id}/end`).then((r) => r.data);

export const listRemoteSessions = (
  params: { device_id?: string; status?: RemoteSessionStatus[]; page?: number; page_size?: number } = {},
) => apiClient.get<RemoteSessionPage>("/remote-sessions", { params }).then((r) => r.data);

/** Minimum the backend accepts — mirrored so the button can disable before a round trip. */
export const MIN_REASON_LENGTH = 10;
