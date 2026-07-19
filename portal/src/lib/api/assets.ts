import { apiClient } from "./client";
import type { Asset, AssetInput, AssetSummary } from "./types";

export const listAssets = () => apiClient.get<Asset[]>("/assets").then((r) => r.data);

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
