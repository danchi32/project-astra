import { apiClient } from "./client";
import type {
  Asset, AssetInput, AssetPassport, AssetStatus, AssetSummary, Page, PageParams,
} from "./types";

// Device passport — full lifecycle history + analytics for one asset.
export const getAssetPassport = (id: string) =>
  apiClient.get<AssetPassport>(`/assets/${id}/passport`).then((r) => r.data);

export const listAssets = (
  params: PageParams & {
    archived?: boolean; q?: string; status?: AssetStatus; location?: string;
  } = {},
) =>
  apiClient.get<Page<Asset>>("/assets", { params }).then((r) => r.data);

/** The asset record for one device, resolved server-side.
 *
 *  Callers used to fetch the whole register and find the row in the browser. Now that the
 *  register is paged that search would only ever look at the first page, so a device whose
 *  asset sat on page 2 would show as having no asset at all. */
/** Asset records for the devices on screen, keyed by device id.
 *
 *  The devices table labels each row with its asset's state and location. It used to fetch
 *  the whole register and join in the browser: 2,000 rows read to annotate 50, and once the
 *  register is paged it would annotate the wrong ones. */
export const assetsForDevices = async (deviceIds: string[]): Promise<Map<string, Asset>> => {
  const map = new Map<string, Asset>();
  if (deviceIds.length === 0) return map;
  const page = await apiClient
    .get<Page<Asset>>("/assets", {
      params: { device_ids: deviceIds, page_size: deviceIds.length },
      paramsSerializer: { indexes: null },
    })
    .then((r) => r.data);
  for (const a of page.items) if (a.device_id) map.set(a.device_id, a);
  return map;
};

export const getAssetForDevice = async (deviceId: string): Promise<Asset | null> => {
  const page = await apiClient
    .get<Page<Asset>>("/assets", { params: { device_id: deviceId, page_size: 1 } })
    .then((r) => r.data);
  return page.items[0] ?? null;
};

export const archiveAsset = (id: string) =>
  apiClient.post<Asset>(`/assets/${id}/archive`).then((r) => r.data);

export const restoreAsset = (id: string) =>
  apiClient.post<Asset>(`/assets/${id}/restore`).then((r) => r.data);

/** Every location in use across the org's assets — the filter dropdown must offer all of
 *  them, not the handful that happen to appear on the page you are looking at. */
export const getAssetLocations = () =>
  apiClient.get<string[]>("/assets/locations").then((r) => r.data);

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

// L5b: warranty dates from a CSV (serial_number or asset_tag + warranty_expiry).
export interface WarrantyImportResult {
  rows: number; updated: number; unchanged: number; conflicts: number;
  unmatched: string[]; invalid: string[];
}

export const importWarrantyCsv = (csv: string) =>
  apiClient.post<WarrantyImportResult>("/assets/warranty/import", { csv }).then((r) => r.data);

// Read an invoice (PDF/JPG/PNG) for an asset's warranty and purchase details. The file goes as
// base64 in the request body and is not stored on the server.
export interface InvoiceResult {
  result: "set" | "same" | "conflict" | "not_stated";
  warranty_found: string | null;
  filled: string[];
  vendor: string | null;
  invoice_date: string | null;
}

export async function readInvoice(id: string, file: File): Promise<InvoiceResult> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return apiClient.post<InvoiceResult>(`/assets/${id}/warranty/invoice`, {
    media_type: file.type, data_b64: btoa(binary),
  }).then((r) => r.data);
}

// Pick between the date a person entered and one an import or lookup found.
export const resolveWarranty = (id: string, keep: "current" | "found") =>
  apiClient.post<Asset>(`/assets/${id}/warranty/resolve`, { keep }).then((r) => r.data);
