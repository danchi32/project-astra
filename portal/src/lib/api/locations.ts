import { apiClient } from "./client";
import type { Location } from "./types";

export const listLocations = () =>
  apiClient.get<Location[]>("/locations").then((r) => r.data);

export const createLocation = (name: string) =>
  apiClient.post<Location>("/locations", { name }).then((r) => r.data);

export const renameLocation = (id: string, name: string) =>
  apiClient.patch<Location>(`/locations/${id}`, { name }).then((r) => r.data);

export const deleteLocation = (id: string) =>
  apiClient.delete(`/locations/${id}`).then((r) => r.data);
