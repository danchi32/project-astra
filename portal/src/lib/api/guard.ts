import { apiClient } from "./client";

// Phase 3 · AI Guard: the org's browser policy (D10/D1/D2) and what each PC reported.
export interface BrowserPolicy {
  incognito_off: boolean;
  extension_developer_mode_off: boolean;
  dev_tools_off: boolean;
  new_profiles_off: boolean;
  blocked_sites: string[];
  allowed_sites: string[];
  google_allowed_domains: string[];
  chrome_extension_id: string | null;
  edge_extension_id: string | null;
  firefox_extension_id: string | null;
  firefox_extension_url: string | null;
  // D3: the extension's own settings, handed to it as managed policy.
  guard_mode: "log" | "warn" | "block";
  guard_watched_sites: string[];
  guard_ignore_kinds: FindingKind[];
  guard_keywords: string[];
}

export const FINDING_KINDS = {
  Aadhaar: "Aadhaar numbers", Pan: "PAN", Gstin: "GSTIN", PaymentCard: "Card numbers",
  IndianMobile: "Mobile numbers", Email: "E-mail addresses", BankAccount: "Bank account numbers",
} as const;
export type FindingKind = keyof typeof FINDING_KINDS;

export interface BrowserPolicyRead {
  version: number;
  policy: BrowserPolicy;
  updated_at: string | null;
}

export interface BrowserResult {
  browser: "Chrome" | "Edge" | "Firefox";
  set: string[];
  repaired: string[];
  removed: string[];
  conflicts: string[];
  error: string | null;
}

export interface DeviceBrowserState {
  device_id: string;
  hostname: string;
  version: number;
  results: BrowserResult[];
  reported_at: string;
}

export const getBrowserPolicy = () =>
  apiClient.get<BrowserPolicyRead>("/guard/browser-policy").then((r) => r.data);

export const putBrowserPolicy = (policy: BrowserPolicy) =>
  apiClient.put<BrowserPolicyRead>("/guard/browser-policy", policy).then((r) => r.data);

// E3: what the extension found. Counts only; never the content. Admin only.
export interface GuardEventSummary {
  days: number;
  total: number;
  allowed: number;
  warned: number;
  blocked: number;
  unknown: number;
  kinds: Partial<Record<FindingKind, number>>;
  contact_lists: number;
  keyword_events: number;
  top_sites: { site: string; events: number }[];
  top_people: { windows_user: string; events: number }[];
}

export interface GuardEventRow {
  id: string;
  occurred_at: string;
  device_id: string;
  hostname: string;
  windows_user: string;
  site: string;
  channel: "paste" | "drop" | "file" | "submit";
  mode: "log" | "warn" | "block";
  action: "allow" | "warn" | "block";
  counts: Partial<Record<FindingKind, number>>;
  contact_list: boolean;
  keyword_hits: number;
  unknown: boolean;
}

export const getGuardEventSummary = (days: number) =>
  apiClient.get<GuardEventSummary>("/guard/events/summary", { params: { days } }).then((r) => r.data);

export const getGuardEvents = (days: number, offset = 0) =>
  apiClient.get<GuardEventRow[]>("/guard/events", { params: { days, limit: 100, offset } }).then((r) => r.data);

export const getBrowserPolicyDevices = () =>
  apiClient.get<DeviceBrowserState[]>("/guard/browser-policy/devices").then((r) => r.data);
