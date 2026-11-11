import { apiClient } from "./client";
import type { Page, PageParams, User, UserRole } from "./types";

export const listUsers = (params: PageParams = {}) =>
  apiClient.get<Page<User>>("/users", { params }).then((r) => r.data);

/** Every user in the org, for the assignment pickers.
 *
 *  Named "all" so the call site says what it is doing. A picker silently backed by page 1
 *  would simply not offer the 51st employee, with nothing on screen to suggest why. */
export const listAllUsers = () =>
  apiClient
    .get<Page<User>>("/users", { params: { page_size: 1000 } })
    .then((r) => r.data.items);

export const createUser = (data: {
  email: string;
  full_name: string;
  role: UserRole;
  password?: string;   // omit for a login-less directory user
}) => apiClient.post<User>("/users", data).then((r) => r.data);

export const updateUser = (
  id: string,
  data: Partial<{ full_name: string; role: UserRole; is_active: boolean; password: string }>
) => apiClient.patch<User>(`/users/${id}`, data).then((r) => r.data);

export const deleteUser = (id: string) => apiClient.delete(`/users/${id}`).then((r) => r.data);

// Z2 — one person's data. Repeated `windows_username=` params (FastAPI's list form), not
// axios's default `windows_username[]=`.
export interface PersonalDataSummary {
  user: { id: string; email: string; full_name: string };
  windows_usernames: string[];
  windows_username_candidates: string[];
  counts: Record<string, number>;
  erase: { deleted: string[]; unlinked: string[]; pseudonymised: string[]; kept: string[] };
  pseudonym: string;
}

const winParams = (names: string[]) => ({
  params: { windows_username: names },
  paramsSerializer: { indexes: null },
});

export const getPersonalData = (id: string, names: string[]) =>
  apiClient.get<PersonalDataSummary>(`/users/${id}/personal-data`, winParams(names)).then((r) => r.data);

export async function downloadPersonalData(id: string, names: string[]) {
  const res = await apiClient.get<Blob>(`/users/${id}/personal-data/export`,
    { ...winParams(names), responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `personal-data-${id}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const erasePersonalData = (id: string, windows_usernames: string[], confirm_email: string) =>
  apiClient.post<{ person: string; counts: Record<string, number> }>(
    `/users/${id}/personal-data/erase`, { windows_usernames, confirm_email }).then((r) => r.data);
