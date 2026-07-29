import { apiClient } from "./client";
import type { Device, Installer } from "./types";

// A single device (for the detail page).
export const getDevice = (id: string) =>
  apiClient.get<Device>(`/devices/${id}`).then((r) => r.data);

export interface DevicePage {
  items: Device[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Searched + paginated device list — the database does the filtering + paging, so this
// stays fast on large fleets. Pass a big page_size to pull everything (e.g. for export).
export const listDevicesPaged = (params: {
  q?: string;
  status?: "online" | "offline";
  page?: number;
  page_size?: number;
}) => apiClient.get<DevicePage>("/devices/paged", { params }).then((r) => r.data);

// The org's ready-to-run installer — the permanent enrollment key is baked in.
export const getInstaller = () =>
  apiClient.get<Installer>("/devices/installer").then((r) => r.data);

// Rotate the org's enrollment key (break-glass if an installer leaks). Returns
// the fresh installer; old installers stop enrolling new devices.
export const rotateEnrollmentKey = () =>
  apiClient.post<Installer>("/devices/enrollment-key/rotate").then((r) => r.data);

// When a blob-typed request fails, the error body is itself a Blob — pull the real
// `detail` out of it so we can show the actual backend reason, not a generic message.
async function blobErrorMessage(err: unknown, fallback: string): Promise<string> {
  const data = (err as { response?: { data?: unknown } })?.response?.data;
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      if (typeof parsed?.detail === "string") return parsed.detail;
    } catch {
      /* not JSON — fall through */
    }
  }
  return fallback;
}

// Downloads the portable installer bundle (.zip) for mass deployment — the agent
// binaries + a pre-keyed installer, for locked-down machines. Triggers a download.
export const downloadOfflineInstaller = async () => {
  try {
    const res = await apiClient.post("/devices/offline-installer", undefined, { responseType: "blob" });
    triggerDownload(res.data as Blob, "AstraAgent-Portable.zip");
  } catch (err) {
    throw new Error(await blobErrorMessage(err, "Couldn't build the portable installer."));
  }
};

// Org-agnostic uninstaller (Uninstall-AstraAgent.bat + .ps1), offered as a separate download.
export const downloadUninstaller = async () => {
  const res = await apiClient.get("/downloads/uninstaller", { responseType: "blob" });
  triggerDownload(res.data as Blob, "AstraAgent-Uninstaller.zip");
};

// Permanently remove a device record (admin only). Uninstalling the agent only stops
// heartbeats — the device stays visible as OFFLINE until it's removed here. This also
// deletes its telemetry history and cannot be undone.
export const deleteDevice = (id: string) =>
  apiClient.delete(`/devices/${id}`).then((r) => r.data);

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
