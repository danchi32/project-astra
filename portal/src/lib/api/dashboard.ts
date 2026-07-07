import { apiClient } from "./client";
import type { DashboardSummary, Device, TelemetrySnapshot } from "./types";

export const getDashboardSummary = () =>
  apiClient.get<DashboardSummary>("/dashboard/summary").then((r) => r.data);

export const getDevices = () =>
  apiClient.get<Device[]>("/devices").then((r) => r.data);

export const getDeviceTelemetry = (deviceId: string, limit = 60) =>
  apiClient.get<TelemetrySnapshot[]>(`/devices/${deviceId}/telemetry?limit=${limit}`).then((r) => r.data);
