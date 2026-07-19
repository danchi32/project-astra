import { apiClient } from "./client";
import type {
  EmailSettings,
  OrganizationSettings,
  OrganizationSettingsInput,
  PermissionMatrix,
} from "./types";

// Per-org outbound email (DNS-verified sending domain).
export const getEmailSettings = () =>
  apiClient.get<EmailSettings>("/settings/email").then((r) => r.data);

export const configureEmailSettings = (data: { from_name: string; from_address: string }) =>
  apiClient.post<EmailSettings>("/settings/email", data).then((r) => r.data);

export const verifyEmailSettings = () =>
  apiClient.post<EmailSettings>("/settings/email/verify").then((r) => r.data);

export const updateAssetEmailTemplate = (data: { subject: string; body: string }) =>
  apiClient.put<EmailSettings>("/settings/email/asset-template", data).then((r) => r.data);

export const getOrgSettings = () =>
  apiClient.get<OrganizationSettings>("/settings/organization").then((r) => r.data);

export const updateOrgSettings = (data: OrganizationSettingsInput) =>
  apiClient.patch<OrganizationSettings>("/settings/organization", data).then((r) => r.data);

export const getPermissionMatrix = () =>
  apiClient.get<PermissionMatrix>("/settings/permissions").then((r) => r.data);
