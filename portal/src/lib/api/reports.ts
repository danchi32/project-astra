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
