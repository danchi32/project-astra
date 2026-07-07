import { apiClient } from "./client";
import type { User } from "./types";

export async function login(email: string, password: string) {
  const { data } = await apiClient.post<{ access_token: string; refresh_token: string }>(
    "/auth/login",
    { email, password }
  );
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  return data;
}

export async function logout() {
  const refresh = localStorage.getItem("refresh_token");
  if (refresh) {
    try { await apiClient.post("/auth/logout", { refresh_token: refresh }); } catch {}
  }
  localStorage.clear();
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me");
  return data;
}
