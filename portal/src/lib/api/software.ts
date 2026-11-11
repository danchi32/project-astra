import { apiClient } from "./client";

export interface CatalogItem {
  package_id: string;
  name: string;
  publisher: string;
  category: string;
}

export interface DeploymentSummary {
  id: string;
  title: string;
  reason: string;
  created_at: string;
  status_counts: Record<string, number>;
}

export interface DeploymentCreated extends DeploymentSummary {
  queued: number;
  already_running: number;
  failed: number;
  not_attempted: number;
  error: string | null;
}

export interface DeploymentDetail extends DeploymentSummary {
  devices: { device_id: string; hostname: string; status: string; message: string | null; completed_at: string | null }[];
}

export const getSoftwareCatalog = () =>
  apiClient.get<CatalogItem[]>("/software/catalog").then((r) => r.data);

export const pushInstall = (body: {
  package_id: string; device_ids: string[]; group_ids: string[];
  exclude_device_ids: string[]; reason: string;
}) => apiClient.post<DeploymentCreated>("/deployments/install", body).then((r) => r.data);

export const listDeployments = () =>
  apiClient.get<DeploymentSummary[]>("/deployments").then((r) => r.data);

export const getDeployment = (id: string) =>
  apiClient.get<DeploymentDetail>(`/deployments/${id}`).then((r) => r.data);
