import { apiClient } from "./client";
import type {
  DeviceEventLog,
  DeviceInstalledApp,
  DeviceLocalAccount,
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

export const getDeviceLocalAccounts = (deviceId: string) =>
  apiClient.get<DeviceLocalAccount[]>(`/devices/${deviceId}/local-accounts`).then((r) => r.data);

// BitLocker recovery keys (2a+). The list never carries a password; reveal returns one, and
// the server records every reveal in the audit log.
export interface BitLockerKeyMeta {
  id: string;
  drive: string;
  protector_id: string;
  escrowed_at: string;
}

export interface BitLockerKeyRevealed {
  drive: string;
  protector_id: string;
  recovery_password: string;
  escrowed_at: string;
}

export const getBitLockerKeys = (deviceId: string) =>
  apiClient.get<BitLockerKeyMeta[]>(`/devices/${deviceId}/bitlocker-keys`).then((r) => r.data);

export const revealBitLockerKey = (deviceId: string, keyId: string) =>
  apiClient
    .post<BitLockerKeyRevealed>(`/devices/${deviceId}/bitlocker-keys/${keyId}/reveal`)
    .then((r) => r.data);
