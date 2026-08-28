import { apiClient } from "./client";
import type { RemediationTask } from "./types";

export type SessionState = "active" | "disconnected";
export type SessionConnection = "console" | "rdp";

export interface DeviceSession {
  id: string;
  device_id: string;
  hostname: string;
  session_id: number;
  username: string | null;
  state: SessionState;
  connection: SessionConnection;
  station: string | null;
  client_name: string | null;
  logon_at: string | null;
  idle_seconds: number | null;
  /** The DEVICE's freshness, not the session's — a session on a machine that last checked
   *  in 13 hours ago is a record of who was there, not who is there. */
  device_online: boolean;
  device_last_seen_at: string | null;
  groups: string[];
}

export interface SessionCounts {
  all: number;
  active: number;
  disconnected: number;
  console: number;
  rdp: number;
}

export interface SessionPage {
  items: DeviceSession[];
  total: number;
  /** Counts over the whole filtered set, not the page — see the backend schema. */
  counts: SessionCounts;
}

export const listSessions = (params: {
  q?: string;
  state?: SessionState;
  connection?: SessionConnection;
  group_id?: string;
  online?: boolean;
  page?: number;
  page_size?: number;
} = {}) => apiClient.get<SessionPage>("/sessions", { params }).then((r) => r.data);

export const listDeviceSessions = (deviceId: string) =>
  apiClient.get<DeviceSession[]>(`/sessions/device/${deviceId}`).then((r) => r.data);

export type SessionActionId =
  | "lock_session"
  | "logoff_session"
  | "message_session"
  | "reset_local_password";

/**
 * Push one action at one session.
 *
 * Returns the remediation task, same as every other action in the product — these are not a
 * separate command channel, they are ordinary remediations with a session id attached, so
 * they appear in Self-Healing and the audit log like everything else.
 */
export const actOnSession = (body: {
  device_id: string;
  action_id: SessionActionId;
  session_id: number;
  message?: string;
  username?: string;
  reason?: string;
}) => apiClient.post<RemediationTask>("/sessions/actions", body).then((r) => r.data);
