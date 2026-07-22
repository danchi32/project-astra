import { apiClient } from "./client";
import type { Installer } from "./types";

// The org's ready-to-run installer — the permanent enrollment key is baked in.
export const getInstaller = () =>
  apiClient.get<Installer>("/devices/installer").then((r) => r.data);

// Rotate the org's enrollment key (break-glass if an installer leaks). Returns
// the fresh installer; old installers stop enrolling new devices.
export const rotateEnrollmentKey = () =>
  apiClient.post<Installer>("/devices/enrollment-key/rotate").then((r) => r.data);

// Downloads the portable installer bundle (.zip) for mass deployment — the agent
// binaries + a pre-keyed installer, for locked-down machines. Triggers a download.
export const downloadOfflineInstaller = async () => {
  const res = await apiClient.post("/devices/offline-installer", undefined, { responseType: "blob" });
  triggerDownload(res.data as Blob, "AstraAgent-Portable.zip");
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
