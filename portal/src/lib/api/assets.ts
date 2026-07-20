import { apiClient } from "./client";
import type { Asset, AssetInput, AssetPassport, AssetSummary } from "./types";

// Device passport — full lifecycle history + analytics for one asset.
export const getAssetPassport = (id: string) =>
  apiClient.get<AssetPassport>(`/assets/${id}/passport`).then((r) => r.data);

export const listAssets = (archived = false) =>
  apiClient.get<Asset[]>("/assets", { params: { archived } }).then((r) => r.data);

export const archiveAsset = (id: string) =>
  apiClient.post<Asset>(`/assets/${id}/archive`).then((r) => r.data);

export const restoreAsset = (id: string) =>
  apiClient.post<Asset>(`/assets/${id}/restore`).then((r) => r.data);

export const getAssetSummary = () =>
  apiClient.get<AssetSummary>("/assets/summary").then((r) => r.data);

export const createAsset = (data: AssetInput) =>
  apiClient.post<Asset>("/assets", data).then((r) => r.data);

export const updateAsset = (id: string, data: Partial<AssetInput>) =>
  apiClient.patch<Asset>(`/assets/${id}`, data).then((r) => r.data);

export const deleteAsset = (id: string) =>
  apiClient.delete(`/assets/${id}`).then((r) => r.data);

// Re-send the receipt-confirmation email to the current assignee.
export const resendAcknowledgement = (id: string) =>
  apiClient.post<Asset>(`/assets/${id}/resend-acknowledgement`).then((r) => r.data);
