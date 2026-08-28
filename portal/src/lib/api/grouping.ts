import { apiClient } from "./client";

export interface DeviceGroup {
  id: string;
  name: string;
  description: string | null;
  colour: string | null;
  device_count: number;
}

export interface UserTeam {
  id: string;
  name: string;
  description: string | null;
  colour: string | null;
  member_count: number;
}

export interface GroupWrite {
  name: string;
  description?: string | null;
  colour?: string | null;
}

export const listDeviceGroups = () =>
  apiClient.get<DeviceGroup[]>("/grouping/groups").then((r) => r.data);

export const createDeviceGroup = (body: GroupWrite) =>
  apiClient.post<DeviceGroup>("/grouping/groups", body).then((r) => r.data);

export const updateDeviceGroup = (id: string, body: GroupWrite) =>
  apiClient.patch<DeviceGroup>(`/grouping/groups/${id}`, body).then((r) => r.data);

export const deleteDeviceGroup = (id: string) =>
  apiClient.delete(`/grouping/groups/${id}`).then(() => undefined);

export const getGroupDevices = (id: string) =>
  apiClient.get<string[]>(`/grouping/groups/${id}/devices`).then((r) => r.data);

/** Replaces the group's devices with exactly this set — see MembershipWrite on the backend
 *  for why membership is sent whole rather than as add/remove deltas. */
export const setGroupDevices = (id: string, deviceIds: string[]) =>
  apiClient
    .put<DeviceGroup>(`/grouping/groups/${id}/devices`, { device_ids: deviceIds })
    .then((r) => r.data);

export interface GroupActionResult {
  action_id: string;
  /** "devices" or "sessions" — a session action fans out per signed-in session, so a
   *  terminal server counts once per person on it, not once as a machine. */
  fanned_over: string;
  targets: number;
  queued: number;
  failed: number;
  already_running: number;
  error: string | null;
}

/**
 * Push one action to everything in a group.
 *
 * Expert-plan only, same as the fleet-wide push — a 402 back means the plan, not the role.
 * Tiers are still enforced per device, so a technician aiming an admin-only action at 200
 * machines gets 200 refusals in `failed` rather than 200 sign-outs.
 */
export const runGroupAction = (
  groupId: string,
  body: { action_id: string; params?: Record<string, string>; message?: string; reason?: string },
) =>
  apiClient
    .post<GroupActionResult>(`/grouping/groups/${groupId}/actions`, body)
    .then((r) => r.data);

export const listUserTeams = () =>
  apiClient.get<UserTeam[]>("/grouping/teams").then((r) => r.data);

export const createUserTeam = (body: GroupWrite) =>
  apiClient.post<UserTeam>("/grouping/teams", body).then((r) => r.data);

export const updateUserTeam = (id: string, body: GroupWrite) =>
  apiClient.patch<UserTeam>(`/grouping/teams/${id}`, body).then((r) => r.data);

export const deleteUserTeam = (id: string) =>
  apiClient.delete(`/grouping/teams/${id}`).then(() => undefined);

export const getTeamUsers = (id: string) =>
  apiClient.get<string[]>(`/grouping/teams/${id}/users`).then((r) => r.data);

export const setTeamUsers = (id: string, userIds: string[]) =>
  apiClient
    .put<UserTeam>(`/grouping/teams/${id}/users`, { user_ids: userIds })
    .then((r) => r.data);
