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

type SignupInput = {
  organization_name: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
};

// Step 1 of signup. When email is configured the server emails a code and returns
// { otp_required: true } (call registerVerify next). Otherwise the org is created
// immediately and tokens are returned + stored.
export async function registerStart(input: SignupInput) {
  const { data } = await apiClient.post<{
    otp_required: boolean;
    access_token: string | null;
    refresh_token: string | null;
  }>("/auth/register/start", input);
  if (!data.otp_required && data.access_token && data.refresh_token) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
  }
  return data;
}

// Step 2 of signup: confirm the emailed code, creating the org and logging in.
export async function registerVerify(admin_email: string, code: string) {
  const { data } = await apiClient.post<{ access_token: string; refresh_token: string }>(
    "/auth/register/verify",
    { admin_email, code }
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

export async function updateProfile(full_name: string): Promise<User> {
  const { data } = await apiClient.patch<User>("/auth/me", { full_name });
  return data;
}

export async function changePassword(current_password: string, new_password: string): Promise<void> {
  await apiClient.post("/auth/change-password", { current_password, new_password });
}
