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
