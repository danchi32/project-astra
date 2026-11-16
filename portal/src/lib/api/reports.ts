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

// C3: what the assistant proposed, and where SAVIO held or refused it (staff only).
export interface AiSafetyReport {
  generated_at: string;
  period_days: number;
  proposals: number;
  ran_unattended: number;
  raised: number;
  flagged: number;
  refused: number;
  by_reason: Record<string, number>;
  events: { at: string; kind: "raised" | "flagged" | "refused"; action_id: string; device_hostname: string | null; reasons: string[] }[];
}

export const getAiSafetyReport = (days: number) =>
  apiClient.get<AiSafetyReport>("/reports/ai-safety", { params: { days } }).then((r) => r.data);

// J5: what SAVIO's unattended fixes were worth. Every figure has its basis.
export interface ValueReport {
  generated_at: string;
  period_days: number;
  fixed_unattended: number;
  minutes_per_fix: number;
  hours_saved: number;
  hourly_cost: number | null;
  inr_saved: number | null;
  proven_improved: number;
  held_7_days: number;
  came_back: number;
  basis: Record<string, string>;
  fixes: { task_id: string; action: string; device_hostname: string | null; completed_at: string | null; proof: string | null; held_7_days: boolean | null }[];
}

export const getValueReport = (days: number) =>
  apiClient.get<ValueReport>("/reports/value", { params: { days } }).then((r) => r.data);
