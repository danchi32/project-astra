import { apiClient } from "./client";
import type { AssetReport, FleetHealthReport, RemediationReport } from "./types";

export const getFleetHealthReport = () =>
  apiClient.get<FleetHealthReport>("/reports/fleet-health").then((r) => r.data);

export const getRemediationReport = (days: number) =>
  apiClient
    .get<RemediationReport>("/reports/remediation", { params: { days } })
    .then((r) => r.data);

export const getAssetReport = () =>
  apiClient.get<AssetReport>("/reports/assets").then((r) => r.data);

async function downloadCsv(path: string, params: Record<string, unknown> | undefined, filename: string) {
  const res = await apiClient.get<Blob>(path, { params, responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const exportFleetHealthCsv = () =>
  downloadCsv("/reports/fleet-health/export", undefined, "fleet-health-report.csv");

export const exportRemediationCsv = (days: number) =>
  downloadCsv("/reports/remediation/export", { days }, "remediation-report.csv");

export const exportAssetsCsv = () =>
  downloadCsv("/reports/assets/export", undefined, "asset-report.csv");

export interface HealthCheckReport {
  organization: string;
  generated_at: string;
  days_of_data: number;
  complete: boolean;
  devices: number;
  score: number;
  compliant: number;
  at_risk: number;
  non_compliant: number;
  findings: { key: string; title: string; severity: "high" | "medium" | "low"; count: number; devices: string[]; advice: string }[];
  disks_filling_soon: string[];
  old_hardware: string[];
  warranty: { asset: string; ends: string; expired: boolean }[];
  software: { distinct_apps: number; per_user_installs: number; ai_tools: { name: string; devices: number }[] };
  per_device: { hostname: string; score: number; status: string; failed: string[] }[];
}

export const getHealthCheckReport = () =>
  apiClient.get<HealthCheckReport>("/reports/health-check").then((r) => r.data);
