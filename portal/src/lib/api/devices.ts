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
