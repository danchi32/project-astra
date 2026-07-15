import { apiClient } from "./client";
import type {
  Asset, Device, GlobalFix, KnowledgeArticle, OrganizationAdmin, PlatformOverview,
  RemediationActionOption, RemediationTask, SubscriptionStatus, User,
} from "./types";

export const getPlatformOverview = () =>
  apiClient.get<PlatformOverview>("/platform/overview").then((r) => r.data);

// Mint a read-only token to browse an org's full portal, then enter view-as mode.
export const createViewToken = (id: string) =>
  apiClient
    .post<{ access_token: string; org_id: string; org_name: string }>(`/platform/organizations/${id}/view-token`)
    .then((r) => r.data);

export const listOrganizations = () =>
  apiClient.get<OrganizationAdmin[]>("/platform/organizations").then((r) => r.data);

export const getOrganization = (id: string) =>
  apiClient.get<OrganizationAdmin>(`/platform/organizations/${id}`).then((r) => r.data);

export const getOrgUsers = (id: string) =>
  apiClient.get<User[]>(`/platform/organizations/${id}/users`).then((r) => r.data);

export const getOrgDevices = (id: string) =>
  apiClient.get<Device[]>(`/platform/organizations/${id}/devices`).then((r) => r.data);

export const getOrgRemediation = (id: string) =>
  apiClient.get<RemediationTask[]>(`/platform/organizations/${id}/remediation`).then((r) => r.data);

export const getOrgAssets = (id: string) =>
  apiClient.get<Asset[]>(`/platform/organizations/${id}/assets`).then((r) => r.data);

// Global problem→solution knowledge applied to every organization.
export const listGlobalKnowledge = () =>
  apiClient.get<KnowledgeArticle[]>("/platform/knowledge").then((r) => r.data);

export const createGlobalKnowledge = (data: { title: string; content: string }) =>
  apiClient.post<KnowledgeArticle>("/platform/knowledge", data).then((r) => r.data);

export const deleteGlobalKnowledge = (id: string) =>
  apiClient.delete(`/platform/knowledge/${id}`).then((r) => r.data);

// Global auto-apply fixes: problem → remediation action, applied for every org.
export const listRemediationActions = () =>
  apiClient.get<RemediationActionOption[]>("/platform/remediation-actions").then((r) => r.data);

export const listGlobalFixes = () =>
  apiClient.get<GlobalFix[]>("/platform/fixes").then((r) => r.data);

export const createGlobalFix = (data: {
  problem: string;
  action_id: string;
  process_name?: string;
  service_name?: string;
}) => apiClient.post<GlobalFix>("/platform/fixes", data).then((r) => r.data);

export const deleteGlobalFix = (id: string) =>
  apiClient.delete(`/platform/fixes/${id}`).then((r) => r.data);

export const updateOrganization = (
  id: string,
  data: Partial<{
    plan: string;
    subscription_status: SubscriptionStatus;
    trial_ends_at: string | null;
    current_period_end: string | null;
    extend_trial_days: number;
  }>
) => apiClient.patch<OrganizationAdmin>(`/platform/organizations/${id}`, data).then((r) => r.data);

export const deleteOrganization = (id: string) =>
  apiClient.delete(`/platform/organizations/${id}`).then((r) => r.data);

// Operator-set bulk discount (percentage) applied to an org's subscription.
export const setOrgDiscount = (id: string, percent: number) =>
  apiClient.post<OrganizationAdmin>(`/platform/organizations/${id}/discount`, { percent }).then((r) => r.data);

export const clearOrgDiscount = (id: string) =>
  apiClient.delete<OrganizationAdmin>(`/platform/organizations/${id}/discount`).then((r) => r.data);
