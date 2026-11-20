import { apiClient } from "./client";

// Phase 3 · AI Guard: the org's browser policy (D10/D1/D2) and what each PC reported.
export interface BrowserPolicy {
  incognito_off: boolean;
  extension_developer_mode_off: boolean;
  dev_tools_off: boolean;
  new_profiles_off: boolean;
  blocked_sites: string[];
  // D1: whole kinds of site on top of blocked_sites; "Always allowed" still wins.
  blocked_categories: string[];
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
  // D3/D5: read PDFs too (uploads and the weekly check), on the PC. Word and Excel always.
  guard_read_pdfs: boolean;
  // D2: sign-in only to the org's own accounts; the extension sends each service its header.
  microsoft_tenant_id: string | null;
  microsoft_policy_id: string | null;
  // The same IDs in Windows' own tenant restrictions, for Office apps and Edge on the PC.
  microsoft_on_windows: boolean;
  claude_org_ids: string[];
  chatgpt_workspace_ids: string[];
  slack_requester_id: string | null;
  slack_allowed_ids: string[];
  extension_allowlist?: string[];   // 3b M2: allowed while company accounts lock the browser
  // D10: the agent closes browsers these settings don't reach, as they start.
  block_other_browsers: boolean;
  // C3: USB drives and phones, through Windows' own policies.
  usb_mode: "off" | "read_only" | "encrypted_only" | "on_request" | "block" | "company_drives";
  // C3b: in company_drives mode, the only USB drives that work.
  usb_approved_drives: { id: string; name: string }[];
  // C3b: record what is copied onto USB drives, in counts, checked on the PC.
  usb_observe: boolean;
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

export interface SiteCategory { key: string; label: string; hosts: string[] }

export const getSiteCategories = () =>
  apiClient.get<SiteCategory[]>("/guard/site-categories").then((r) => r.data);

export const endGuardPilot = () =>
  apiClient.post<BrowserPolicyRead>("/guard/browser-policy/end-pilot").then((r) => r.data);

export interface BrowserResult {
  // Scanner: E4's firewall block on the native host. Windows: its own tenant restrictions (Office apps).
  browser: "Chrome" | "Edge" | "Firefox" | "Scanner" | "Windows" | "Usb" | "UsbEncryption" | "UsbDevices";
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
  // D1: the policy this PC should be on: a group's name, or null for everyone's.
  policy_group: string | null;
  policy_version: number;
  // D10: browsers the policy doesn't reach that are installed on this PC (from its app inventory).
  other_browsers: string[];
  // C3: this PC's USB mode, and until when IT let it write to USB drives ("write on request").
  usb_mode: BrowserPolicy["usb_mode"];
  usb_write_until: string | null;
}

// I1: DPDP readiness from SAVIO's own records.
export interface DpdpItem {
  key: string;
  title: string;
  why: string;
  status: "done" | "todo";
  detail: string;
  link: string;
}

export interface DpdpReadiness {
  score: number;
  done: number;
  total: number;
  items: DpdpItem[];
  // Folders with the most files of personal data unchanged for two years: review these first.
  retention: { hostname: string; path: string; old: number; files_with_findings: number; contact_lists: number }[];
  map: {
    on_pcs: { pcs: number; files: number; contact_lists: number; kinds: Record<string, number> };
    leaving: { events: number; kinds: Record<string, number>; where: Record<string, number> };
  };
  contact: { name: string | null; email: string | null };
  disclaimer: string;
  generated_at: string;
}

export const getDpdp = () => apiClient.get<DpdpReadiness>("/guard/dpdp").then((r) => r.data);
export const setPrivacyContact = (name: string, email: string) =>
  apiClient.put("/guard/dpdp/contact", { name: name || null, email: email || null });

// I1: breach records (the breach workflow; the record page prints as the incident report, J7).
export type IncidentStepKey = "contain" | "assess" | "counsel" | "board" | "people" | "fix";
export interface IncidentStep {
  key: IncidentStepKey;
  title: string;
  help: string;
  optional: boolean;                       // reporting: can be "not needed" on counsel's advice
  state: "done" | "not_needed" | null;
  at: string | null;
  by: string | null;
  note: string | null;
}
export interface Incident {
  id: string;
  case_id: string | null;
  title: string;
  what_happened: string;
  found_at: string;
  kinds: FindingKind[];
  people_affected: number | null;
  status: "open" | "closed";
  opened_at: string;
  closed_at: string | null;
  steps: IncidentStep[];
}
export interface IncidentDetail extends Incident {
  case: { id: string; windows_user: string; opened_at: string; level: string } | null;
  timeline: { at: string; by: string | null; action: string; detail: Record<string, unknown> | null }[];
}
export interface IncidentFacts {
  title: string;
  what_happened: string;
  found_at: string;
  kinds: FindingKind[];
  people_affected: number | null;
}
export const getIncidents = () => apiClient.get<Incident[]>("/guard/incidents").then((r) => r.data);
export const getIncident = (id: string) => apiClient.get<IncidentDetail>(`/guard/incidents/${id}`).then((r) => r.data);
export const openIncident = (body: IncidentFacts & { case_id?: string | null }) =>
  apiClient.post<Incident>("/guard/incidents", body).then((r) => r.data);
export const updateIncident = (id: string, body: Partial<IncidentFacts> & {
  step?: { key: IncidentStepKey; state: "done" | "not_needed" | null; note?: string | null }; closed?: boolean;
}) => apiClient.patch<Incident>(`/guard/incidents/${id}`, body).then((r) => r.data);

// C3b: USB drives the org's PCs have used, and which policies already approve each.
export interface DriveSeen {
  id: string;
  name: string;
  unique_serial: boolean;   // false: Windows made the serial up, so it changes with the USB port
  pcs: string[];
  last_seen: string;
  approved_in: string[];
}

export const getDrivesSeen = () => apiClient.get<DriveSeen[]>("/guard/drives").then((r) => r.data);

export const openUsbWindow =(deviceId: string, minutes: number) =>
  apiClient.post<{ device_id: string; until: string }>(`/guard/devices/${deviceId}/usb-window`, { minutes }).then((r) => r.data);

export const closeUsbWindow = (deviceId: string) => apiClient.delete(`/guard/devices/${deviceId}/usb-window`);

// D1: a device group's own policy. A PC in several groups gets the lowest priority number's.
export interface GroupPolicy {
  group_id: string;
  group_name: string;
  priority: number;
  version: number;
  policy: BrowserPolicy;
  updated_at: string;
}

export const getGroupPolicies = () =>
  apiClient.get<GroupPolicy[]>("/guard/group-policies").then((r) => r.data);

export const putGroupPolicy = (groupId: string, priority: number, policy: BrowserPolicy) =>
  apiClient.put<GroupPolicy>(`/guard/group-policies/${groupId}`, { priority, policy }).then((r) => r.data);

export const deleteGroupPolicy = (groupId: string) =>
  apiClient.delete(`/guard/group-policies/${groupId}`).then(() => undefined);

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
  // "usb": files copied to a USB drive, or (on an approval) a request to write to one.
  channel: "paste" | "drop" | "file" | "submit" | "usb";
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
  reason: "client_or_ca" | "backup" | "presentation" | "other" | null;   // C3b: a USB request's why
  requested_at: string;
  decided_at: string | null;
  valid_until: string | null;
}

// C1: cases, not alerts. One person's events as one ranked story. Admin only (names people).
export interface GuardCaseSite {
  site: string;
  kind: string | null;   // a site category key, if the site is in one
  new: boolean;          // first seen in the org this week
  events: number;
  items: number;
  contact_lists: number;
  went_ahead: number;
  blocked: number;
  channels: string[];
  origins: string[];     // C2: where its files were downloaded from (host names)
}

export interface GuardCase {
  id: string;
  windows_user: string;
  opened_at: string;
  last_event_at: string;
  status: "open" | "closed";
  resolution: "expected" | "handled" | null;
  score: number;
  level: "low" | "medium" | "high";
  reasons: string[];
  sites: GuardCaseSite[];
  kinds: Record<string, number>;
  events: number;
  devices: string[];
  closed_at: string | null;
}

export interface GuardCases {
  open: { high: number; medium: number; low: number };
  quiet_sites: string[];
  quiet_events_30d: number;
  cases: GuardCase[];
}

export const getGuardCases = (status: "open" | "closed") =>
  apiClient.get<GuardCases>("/guard/cases", { params: { status } }).then((r) => r.data);

// C4: the fixes SAVIO offers for a case, per PC: existing remediation actions.
export interface GuardCaseAction {
  device_id: string;
  hostname: string;
  action_id: string;
  label: string;
  params: Record<string, string>;
  available: boolean;
  why: string | null;
}

export const getGuardCaseActions = (id: string) =>
  apiClient.get<GuardCaseAction[]>(`/guard/cases/${id}/actions`).then((r) => r.data);

export const closeGuardCase =(id: string, resolution: "expected" | "handled", quiet_site: string | null) =>
  apiClient.post<GuardCase>(`/guard/cases/${id}/close`, { resolution, quiet_site }).then((r) => r.data);

export const removeQuietSite = (site: string) =>
  apiClient.delete(`/guard/quiet-sites/${encodeURIComponent(site)}`);

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