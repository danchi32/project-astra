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

// Pulls the filename out of a Content-Disposition header. The backend mints a fresh
// enrollment ticket per download and puts it in the name, so the name only exists once
// the response comes back — and saving the file under any other name leaves the
// installer with no ticket to enrol with.
function filenameFromDisposition(header: unknown): string | null {
  if (typeof header !== "string") return null;
  // RFC 5987 form first (filename*=UTF-8''…), then the plain quoted form.
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      /* malformed encoding — fall through to the plain form */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}

// Downloads the one-click .exe installer, saved under the name the server chose.
export const downloadExeInstaller = async () => {
  try {
    const res = await apiClient.post("/devices/exe-installer", undefined, { responseType: "blob" });
    const name = filenameFromDisposition(res.headers?.["content-disposition"]);
    if (!name) {
      // Without the real name the download would be useless — it would carry no
      // ticket. Fail loudly rather than saving a file that cannot enrol. The usual
      // cause is Content-Disposition not being exposed to the browser by CORS.
      throw new Error(
        "The server did not say what to name the installer, so it would not be able " +
          "to enrol this device. Use the .zip installer, or try again.",
      );
    }
    triggerDownload(res.data as Blob, name);
  } catch (err) {
    if (err instanceof Error && err.message.startsWith("The server did not say")) throw err;
    throw new Error(await blobErrorMessage(err, "Couldn't download the .exe installer."));
  }
};

// Break-glass: kill every .exe installer handed out so far. Leaves the permanent
// enrollment key (and so any .zip installers) working — rotateEnrollmentKey does those.
export const revokeExeInstallers = async (): Promise<number> => {
  const res = await apiClient.post("/devices/exe-installer/revoke");
  return (res.data as { revoked: number }).revoked;
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
