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
  guard_mode: "log" | "warn" | "justify" | "redact" | "approve" | "block";
  guard_watched_sites: string[];
  guard_ignore_kinds: FindingKind[];
  guard_keywords: string[];
}

export const FINDING_KINDS = {
  Aadhaar: "Aadhaar numbers", Pan: "PAN", Gstin: "GSTIN", PaymentCard: "Card numbers",
  IndianMobile: "Mobile numbers", Email: "E-mail addresses", BankAccount: "Bank account numbers",
} as const;
export type FindingKind = keyof typeof FINDING_KINDS;

// D7: why someone went ahead after a "justify" prompt. Mirrors the extension's fixed list.
export const REASONS = {
  client_request: "The client asked for it", approved: "Manager approved", not_real: "Test or sample data",
  own_data: "Their own information", other: "Another work reason",
} as const;
export type Reason = keyof typeof REASONS;

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
  justified: number;
  redacted: number;
  blocked: number;
  unknown: number;
  went_ahead: number;
  stopped: number;
  reasons: Partial<Record<Reason, number>>;
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
  mode: "log" | "warn" | "justify" | "redact" | "approve" | "block";
  action: "allow" | "warn" | "justify" | "redact" | "approve" | "block";
  counts: Partial<Record<FindingKind, number>>;
  contact_list: boolean;
  keyword_hits: number;
  unknown: boolean;
  outcome: "proceeded" | "cancelled" | "requested" | null;
  reason: Reason | null;
}

export const getGuardEventSummary = (days: number) =>
  apiClient.get<GuardEventSummary>("/guard/events/summary", { params: { days } }).then((r) => r.data);

export const getGuardEvents = (days: number, offset = 0) =>
  apiClient.get<GuardEventRow[]>("/guard/events", { params: { days, limit: 100, offset } }).then((r) => r.data);

export const getBrowserPolicyDevices = () =>
  apiClient.get<DeviceBrowserState[]>("/guard/browser-policy/devices").then((r) => r.data);

// D7: requests to let one held paste / upload through. Admin only; decisions are audited.
export interface GuardApproval {
  id: string;
  device_id: string;
  hostname: string;
  windows_user: string;
  site: string;
  channel: GuardEventRow["channel"];
  counts: Partial<Record<FindingKind, number>>;
  contact_list: boolean;
  keyword_hits: number;
  status: "pending" | "approved" | "denied" | "expired" | "ended";
  requested_at: string;
  decided_at: string | null;
  valid_until: string | null;
}

export const getGuardApprovals = () =>
  apiClient.get<GuardApproval[]>("/guard/approvals").then((r) => r.data);

export const approveGuardApproval = (id: string, minutes: number) =>
  apiClient.post<GuardApproval>(`/guard/approvals/${id}/approve`, { minutes }).then((r) => r.data);

export const denyGuardApproval = (id: string) =>
  apiClient.post<GuardApproval>(`/guard/approvals/${id}/deny`).then((r) => r.data);