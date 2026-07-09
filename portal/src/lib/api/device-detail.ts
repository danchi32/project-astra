import { apiClient } from "./client";
import type {
  DeviceEventLog,
  DeviceInstalledApp,
  DeviceServiceRow,
  DeviceWindowsUpdate,
  TelemetrySnapshot,
} from "./types";

export const getDeviceTelemetry = (deviceId: string, limit = 60) =>
  apiClient
    .get<TelemetrySnapshot[]>(`/devices/${deviceId}/telemetry?limit=${limit}`)
    .then((r) => r.data);

export const getDeviceEvents = (deviceId: string) =>
  apiClient.get<DeviceEventLog[]>(`/devices/${deviceId}/events`).then((r) => r.data);

export const getDeviceApps = (deviceId: string) =>
  apiClient.get<DeviceInstalledApp[]>(`/devices/${deviceId}/apps`).then((r) => r.data);

export const getDeviceServices = (deviceId: string) =>
  apiClient.get<DeviceServiceRow[]>(`/devices/${deviceId}/services`).then((r) => r.data);

export const getDeviceUpdates = (deviceId: string) =>
  apiClient.get<DeviceWindowsUpdate[]>(`/devices/${deviceId}/updates`).then((r) => r.data);
