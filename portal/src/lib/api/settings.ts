import { apiClient } from "./client";
import type {
  OrganizationSettings,
  OrganizationSettingsInput,
  PermissionMatrix,
} from "./types";

export const getOrgSettings = () =>
  apiClient.get<OrganizationSettings>("/settings/organization").then((r) => r.data);

export const updateOrgSettings = (data: OrganizationSettingsInput) =>
  apiClient.patch<OrganizationSettings>("/settings/organization", data).then((r) => r.data);

export const getPermissionMatrix = () =>
  apiClient.get<PermissionMatrix>("/settings/permissions").then((r) => r.data);
