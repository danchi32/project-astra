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
  // "manual": installed by hand (pilot or test), so no force-install entry. Set by SAVIO.
  extension_install: "store" | "manual";
  edge_extension_id: string | null;
  firefox_extension_id: string | null;
  firefox_extension_url: string | null;
  // D3: the extension's own settings, handed to it as managed policy.
  guard_mode: "log" | "warn" | "justify" | "redact" | "approve" | "block";
  guard_watched_sites: string[];
  guard_ignore_kinds: FindingKind[];
  guard_keywords: string[];
  // D5: weekly scan of each person's Desktop / Documents / Downloads / OneDrive, on the PC.
  discovery_enabled: boolean;
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
  // E8: while set, record only. With no policy saved yet, when the pilot would end if it began now.
  pilot_until: string | null;
}

export const endGuardPilot = () =>
  apiClient.post<BrowserPolicyRead>("/guard/browser-policy/end-pilot").then((r) => r.data);

export interface BrowserResult {
  browser: "Chrome" | "Edge" | "Firefox" | "Scanner";   // Scanner: E4's firewall block on the native host
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

// `requested_at` is the request as the admin saw it: one that changed since is refused (409).
export const approveGuardApproval = (a: Pick<GuardApproval, "id" | "requested_at">, minutes: number) =>
  apiClient.post<GuardApproval>(`/guard/approvals/${a.id}/approve`, { minutes, requested_at: a.requested_at }).then((r) => r.data);

export const denyGuardApproval = (a: Pick<GuardApproval, "id" | "requested_at">) =>
  apiClient.post<GuardApproval>(`/guard/approvals/${a.id}/deny`, { requested_at: a.requested_at }).then((r) => r.data);
// D5: where sensitive files are on the org's PCs, by folder, counts only. Admin only.
export interface DiscoveryFolder {
  path: string;
  files: number;
  files_with_findings: number;
  counts: Partial<Record<FindingKind, number>>;
  contact_lists: number;
}

export interface DiscoveryDevice {
  device_id: string;
  hostname: string;
  scanned_at: string;
  files_scanned: number;
  files_skipped: number;
  truncated: boolean;
  folders: DiscoveryFolder[];
}

export interface Discovery {
  pcs: number;
  files_with_findings: number;
  contact_lists: number;
  kinds: Partial<Record<FindingKind, number>>;
  devices: DiscoveryDevice[];
}

export const getDiscovery = () => apiClient.get<Discovery>("/guard/discovery").then((r) => r.data);
// D5 slice 2: policy changes suggested by what AI Guard has seen, with the evidence. Admin only.
export interface GuardSuggestion {
  key: string;
  title: string;
  why: string;
  changes: string[];
}

export const getGuardSuggestions = () =>
  apiClient.get<GuardSuggestion[]>("/guard/suggestions").then((r) => r.data);

// `changes` as the admin saw them: if the evidence has since changed the suggestion, it is refused (409).
export const applyGuardSuggestion = (s: Pick<GuardSuggestion, "key" | "changes">) =>
  apiClient.post<BrowserPolicyRead>(`/guard/suggestions/${s.key}/apply`, { changes: s.changes }).then((r) => r.data);

export const dismissGuardSuggestion = (key: string) =>
  apiClient.post(`/guard/suggestions/${key}/dismiss`).then(() => undefined);