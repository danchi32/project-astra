import { apiClient } from "./client";
import type {
  EmailSettings,
  HelpdeskSettings,
  HelpdeskSettingsInput,
  HelpdeskVerifyResult,
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

// The helpdesk ASTRA escalates into. The API key only ever travels one way — it goes out
// in the PATCH body and never comes back, so there is no "get the key" call here.
export const getHelpdeskSettings = () =>
  apiClient.get<HelpdeskSettings>("/settings/helpdesk").then((r) => r.data);

export const updateHelpdeskSettings = (data: HelpdeskSettingsInput) =>
  apiClient.patch<HelpdeskSettings>("/settings/helpdesk", data).then((r) => r.data);

/** Reads the instance's field schema. Creates nothing, so it is safe to press repeatedly. */
export const verifyHelpdeskSettings = () =>
  apiClient.post<HelpdeskVerifyResult>("/settings/helpdesk/verify").then((r) => r.data);
