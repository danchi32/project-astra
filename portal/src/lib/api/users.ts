import { apiClient } from "./client";
import type { User, UserRole } from "./types";

export const listUsers = () => apiClient.get<User[]>("/users").then((r) => r.data);

export const createUser = (data: {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
}) => apiClient.post<User>("/users", data).then((r) => r.data);

export const updateUser = (
  id: string,
  data: Partial<{ full_name: string; role: UserRole; is_active: boolean; password: string }>
) => apiClient.patch<User>(`/users/${id}`, data).then((r) => r.data);

export const deleteUser = (id: string) => apiClient.delete(`/users/${id}`).then((r) => r.data);
