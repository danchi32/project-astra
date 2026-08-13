import { apiClient } from "./client";
import type { Page, PageParams } from "./types";

export type CheckStatus = "pass" | "fail" | "unknown";
export type DeviceComplianceStatus = "compliant" | "at_risk" | "non_compliant" | "unknown";

export interface CheckResult {
  key: string;
  label: string;
  status: CheckStatus;
  detail: string;
  fix_action_id: string | null;
}

export interface DeviceCompliance {
  device_id: string;
  hostname: string;
  status: DeviceComplianceStatus;
  score: number;
  passed: number;
  failed: number;
  checks: CheckResult[];
}

export interface CheckBreakdown {
  key: string;
  label: string;
  passed: number;
  failed: number;
  unknown: number;
}

export interface UsbPosture {
  blocked: number;
  allowed: number;
  unknown: number;
}

export interface ComplianceSummary {
  total_devices: number;
  compliant: number;
  at_risk: number;
  non_compliant: number;
  unknown: number;
  score: number;
  checks: CheckBreakdown[];
  usb: UsbPosture;
}

export interface BannedSoftware {
  id: string;
  name: string;
  pattern: string;
  created_at: string;
}

export const getComplianceSummary = () =>
  apiClient.get<ComplianceSummary>("/compliance/summary").then((r) => r.data);

export const getComplianceDevices = (
  params: PageParams & { needs_attention?: boolean } = {},
) =>
  apiClient.get<Page<DeviceCompliance>>("/compliance/devices", { params }).then((r) => r.data);

export const getDeviceCompliance = (deviceId: string) =>
  apiClient.get<DeviceCompliance>(`/compliance/devices/${deviceId}`).then((r) => r.data);

export const listBannedSoftware = () =>
  apiClient.get<BannedSoftware[]>("/compliance/banned-software").then((r) => r.data);

export const addBannedSoftware = (name: string) =>
  apiClient.post<BannedSoftware>("/compliance/banned-software", { name }).then((r) => r.data);

export const removeBannedSoftware = (id: string) =>
  apiClient.delete(`/compliance/banned-software/${id}`).then((r) => r.data);
