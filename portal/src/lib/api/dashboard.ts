import { apiClient } from "./client";
import type {
  DashboardOverview, DashboardSummary, Device, TelemetrySnapshot,
} from "./types";

export const getDashboardSummary = () =>
  apiClient.get<DashboardSummary>("/dashboard/summary").then((r) => r.data);

/** Everything the dashboard shows, in one call. One request rather than several because
 *  the server scores the fleet once and derives both the compliance summary and the ranked
 *  issue list from that pass. */
export const getDashboardOverview = () =>
  apiClient.get<DashboardOverview>("/dashboard/overview").then((r) => r.data);

export const getDevices = () =>
  apiClient.get<Device[]>("/devices").then((r) => r.data);

export const getDeviceTelemetry = (deviceId: string, limit = 60) =>
  apiClient.get<TelemetrySnapshot[]>(`/devices/${deviceId}/telemetry?limit=${limit}`).then((r) => r.data);
