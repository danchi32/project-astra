import { apiClient } from "./client";
import type { AgentInstaller, EnrollmentToken } from "./types";

export const listEnrollmentTokens = () =>
  apiClient.get<EnrollmentToken[]>("/devices/enrollment-tokens").then((r) => r.data);

export const revokeEnrollmentToken = (id: string) =>
  apiClient.delete(`/devices/enrollment-tokens/${id}`).then((r) => r.data);

export const generateAgentInstaller = (name: string, server_url?: string) =>
  apiClient
    .post<AgentInstaller>("/devices/agent-installer", { name, server_url: server_url || undefined })
    .then((r) => r.data);

// Downloads the single-file offline installer bundle (.zip) for mass deployment.
// The bundle embeds the agent binary + a pre-keyed script, so target machines
// need no download at install time. Triggers a browser download.
export const downloadOfflineInstaller = async (name: string, server_url?: string) => {
  const res = await apiClient.post(
    "/devices/offline-installer",
    { name, server_url: server_url || undefined },
    { responseType: "blob" },
  );
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "AstraAgent-Offline.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};
