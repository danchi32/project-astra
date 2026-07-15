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
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "AstraAgent-Portable.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};
