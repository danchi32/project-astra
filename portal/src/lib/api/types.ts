/** One page of a list endpoint. Every paginated endpoint returns this shape, so the portal
 *  has one contract to code against rather than one per endpoint. */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Params every paginated endpoint accepts. */
export interface PageParams {
  page?: number;
  page_size?: number;
}

// ── Dashboard overview ─────────────────────────────────────────────────────

/** One thing worth doing, phrased as the decision rather than the measurement. */
export interface DashboardAction {
  key: string;
  title: string;
  detail: string;
  count: number;
  severity: "high" | "medium" | "low";
  href: string;
}

/** Updates split by why they are not in effect — they need different responses, so the
 *  dashboard never rolls them into one number. */
export interface PatchState {
  pending: number;
  awaiting_restart: number;
  failed: number;
  devices_with_pending: number;
  devices_awaiting_restart: number;
}

export interface TrendPoint {
  day: string;
  devices_reporting: number;
  cpu_avg: number;
  disk_free_min_pct: number | null;
}

export interface DashboardOverview {
  needs_you: DashboardAction[];
  compliance: import("./compliance").ComplianceSummary;
  patch: PatchState;
  trend: TrendPoint[];
  top_issues: import("./fleet").FleetIssue[];
}

// ── Billing identity + invoices ────────────────────────────────────────────

export type InvoiceStatus = "draft" | "open" | "paid" | "failed" | "refunded" | "void";

/** Money is in minor units, as integers, exactly as the API stores it. Formatting happens
 *  at the edge; a float here would reintroduce the rounding the backend avoids. */
export interface Invoice {
  id: string;
  org_id: string;
  number: string;
  issued_on: string;
  period_start: string | null;
  period_end: string | null;
  plan: string | null;
  seats: number | null;
  currency: string;
  subtotal_cents: number;
  discount_cents: number;
  tax_cents: number;
  total_cents: number;
  status: InvoiceStatus;
  paid_at: string | null;
  renews_on: string | null;
  provider: string | null;
  transaction_id: string | null;
  payment_method: string | null;
  /** Set when the payment rail is the seller of record (Paddle) and issues the document
   *  itself. Null means ASTRA is the seller and renders its own. */
  provider_invoice_url: string | null;
  org_name?: string | null;
}

export interface BillingProfile {
  legal_name: string | null;
  billing_contact_name: string | null;
  billing_email: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country_code: string | null;
  tax_id_label: string | null;
  tax_id: string | null;
  registration_number: string | null;
  /** False until the fields an invoice actually needs are present. */
  complete: boolean;
}

export type UserRole = "admin" | "technician" | "user";

export interface User {
  id: string;
  org_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_platform_admin?: boolean;
  // True while this session is a platform admin's read-only "view as organization".
  view_as?: boolean;
  created_at: string;
}

export type SubscriptionStatus =
  | "trialing" | "active" | "past_due" | "suspended" | "canceled";

export type BillingProvider = "razorpay" | "paddle" | "paypal";

export interface BillingStatus {
  billing_enabled: boolean;
  providers: BillingProvider[];          // rails configured & able to sell now
  billing_provider: BillingProvider | null; // the rail this org pays on, once chosen
  plan: string;
  subscription_status: SubscriptionStatus;
  writable: boolean;
  read_only_reason: string | null;
  trial_ends_at: string | null;
  current_period_end: string | null;
  has_subscription: boolean;
  seat_type: "device" | "user";
  licenses: number;
  seats_used: number;
  discount_percent: number | null;
  unit_price_configured: boolean;
}

/** What a plan grants. Derived by the server on every read, never stored — a console that
 *  disagrees with the gate is worse than no console. */
export type PlanTier = "essential" | "professional" | "expert";

export const PLAN_TIERS: { value: PlanTier; label: string; blurb: string }[] = [
  { value: "essential", label: "Essential", blurb: "Inventory, telemetry, patching and AI diagnosis." },
  { value: "professional", label: "Professional", blurb: "The AI fixes issues on its own, plus lock-down." },
  { value: "expert", label: "Expert", blurb: "Compliance, fleet-wide remediation and export." },
];

/** Feature keys, labelled for the console. Mirrors backend app/services/entitlements.py. */
export const FEATURE_LABELS: Record<string, string> = {
  inventory: "Inventory & telemetry",
  patching: "Patch management",
  ai_diagnose: "AI diagnosis",
  reporting: "Reporting & dashboards",
  notifications: "Notifications",
  audit_view: "Audit trail",
  ai_act: "AI fixes unattended",
  approval_tiers: "Approval tiers",
  lockdown: "Secure offboarding",
  employee_chat: "Employee AI chat",
  compliance: "Compliance dashboard",
  banned_software: "Restricted software",
  fleet_correlation: "Fleet correlation",
  fleet_remediation: "Mass remediation",
  audit_export: "Audit export & retention",
  advanced_rbac: "Advanced RBAC & SSO",
};

export interface OrganizationAdmin {
  id: string;
  name: string;
  plan: string;
  subscription_status: SubscriptionStatus;
  trial_ends_at: string | null;
  current_period_end: string | null;
  created_at: string;
  license_count: number;
  discount_percent: number | null;
  billing_provider: string | null;
  ai_pro: boolean;
  /** Touched whenever the row changes, so the console can sort by recent activity. */
  updated_at: string | null;
  user_count: number;
  device_count: number;
  plan_tier: PlanTier;
  entitlements: string[];
  entitlement_overrides: Record<string, boolean> | null;
}

export interface PlatformOverview {
  total_organizations: number;
  orgs_by_status: Record<string, number>;
  trials_ending_7d: number;
  signups_30d: number;
  active_subscriptions: number;
  mrr_cents: number | null;
  total_users: number;
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  licenses_sold: number;
  remediation_pending: number;
}

// ── Per-org email sending (DNS-verified) ───────────────────────────────────

export type EmailVerificationStatus = "unconfigured" | "pending" | "verified" | "failed";

export interface EmailDnsRecord {
  type: string;      // TXT / MX / CNAME
  name: string;
  value: string;
  ttl: string;
  priority: number | null;
  purpose: string;   // DKIM / SPF
  status: string;
}

export interface EmailSettings {
  configured: boolean;
  provider_ready: boolean;
  status: EmailVerificationStatus;
  from_name: string | null;
  from_address: string | null;
  domain: string | null;
  dns_records: EmailDnsRecord[];
  last_error: string | null;
  verified_at: string | null;
  asset_email_subject: string | null;
  asset_email_body: string | null;
  asset_email_placeholders: string[];
}

// ── Operator console (platform admin) ──────────────────────────────────────

export interface PlatformBillingRow {
  id: string;
  name: string;
  plan: string;
  subscription_status: SubscriptionStatus;
  billing_provider: string | null;
  license_count: number;
  discount_percent: number | null;
  seat_price_cents: number | null;
  mrr_cents: number | null;
  current_period_end: string | null;
  trial_ends_at: string | null;
  created_at: string;
}

export interface PlatformBilling {
  price_per_seat_cents: number | null;
  mrr_cents: number | null;
  arr_cents: number | null;
  active_subscriptions: number;
  trialing: number;
  past_due: number;
  suspended: number;
  canceled: number;
  by_provider: Record<string, { subscriptions: number; mrr_cents: number | null }>;
  rows: PlatformBillingRow[];
}

export interface PlatformReports {
  signups_by_month: { month: string; count: number }[];
  remediation_total_30d: number;
  remediation_succeeded_30d: number;
  remediation_failed_30d: number;
  remediation_pending: number;
  remediation_success_rate: number | null;
  top_actions_30d: { action_id: string; label: string; count: number }[];
  total_devices: number;
  online_devices: number;
  devices_by_org: { org_id: string; org_name: string; devices: number; online: number }[];
  conversations_30d: number;
  messages_30d: number;
}

export interface PlatformAuditEntry {
  id: string;
  created_at: string;
  action: string;
  org_id: string;
  org_name: string | null;
  actor_email: string | null;
  target_type: string;
  target_id: string | null;
  detail: Record<string, unknown> | null;
}

export interface RemediationActionOption {
  id: string;
  label: string;
  tier: string;
  params: string[];
}

export interface GlobalFix {
  id: string;
  problem: string;
  action_id: string;
  action_label: string;
  params: Record<string, string> | null;
  created_at: string;
}

export type DeviceStatus = "online" | "offline";

export interface Device {
  id: string;
  org_id: string;
  hostname: string;
  machine_id: string;
  os_version: string;
  serial_number: string | null;
  agent_version: string;
  logged_in_user: string | null;
  status: DeviceStatus;
  last_seen_at: string | null;
  is_active: boolean;
  created_at: string;
  // Hardware asset attributes
  manufacturer: string | null;
  model: string | null;
  cpu_name: string | null;
  total_ram_mb: number | null;
  total_storage_gb: number | null;
  installed_app_count: number;
}

export interface TelemetrySnapshot {
  id: string;
  device_id: string;
  cpu_percent: number;
  ram_total_mb: number;
  ram_used_mb: number;
  disks: { drive: string; total_gb: number; used_gb: number; free_gb: number }[];
  collected_at: string;
}

export interface DeviceEventLog {
  id: string;
  level: string;
  source: string;
  event_id: number;
  message: string;
  occurred_at: string;
}

export interface DeviceInstalledApp {
  id: string;
  name: string;
  version: string | null;
  publisher: string | null;
  install_date: string | null;
}

export interface DeviceServiceRow {
  id: string;
  name: string;
  display_name: string;
  status: string;
  start_type: string;
}

/** The states Windows itself distinguishes. is_installed could not tell "installed, waiting
 *  for a restart" from "never installed", so both rendered as "Pending" and contradicted the
 *  device's own Windows Update page. */
export type WindowsUpdateState = "pending" | "pending_restart" | "failed" | "installed";

export interface DeviceWindowsUpdate {
  id: string;
  kb_article_id: string;
  title: string;
  state: WindowsUpdateState;
  /** Windows' failure code, e.g. "0x80244018". Present only when state is "failed". */
  error_code: string | null;
  is_installed: boolean;
  installed_on: string | null;
}

export interface AuditLog {
  id: string;
  action: string;
  target_type: string;
  target_id: string | null;
  actor_id: string | null;
  actor_email: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export type AssetCategory =
  | "laptop" | "desktop" | "server" | "monitor" | "phone" | "tablet"
  | "peripheral" | "network" | "license" | "software" | "other";

export type AssetStatus = "in_use" | "in_storage" | "in_repair" | "retired" | "lost";

export type AcknowledgementStatus = "not_required" | "pending" | "acknowledged";

export interface Asset {
  id: string;
  org_id: string;
  asset_tag: string | null;
  name: string;
  category: AssetCategory;
  status: AssetStatus;
  assigned_to_user_id: string | null;
  device_id: string | null;
  assigned_to_name: string | null;
  device_hostname: string | null;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  location: string | null;
  purchase_date: string | null;
  warranty_expiry: string | null;
  purchase_cost: number | null;
  notes: string | null;
  acknowledgement_status: AcknowledgementStatus;
  acknowledged_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Location {
  id: string;
  name: string;
  asset_count: number;
}

export type AssetEventType =
  | "created" | "assigned" | "unassigned" | "status_changed"
  | "location_changed" | "acknowledged" | "archived" | "restored" | "note";

export interface AssetEvent {
  id: string;
  event_type: AssetEventType;
  actor_name: string | null;
  user_name: string | null;
  from_value: string | null;
  to_value: string | null;
  note: string | null;
  occurred_at: string;
}

export interface AssetPassport {
  asset_id: string;
  name: string;
  category: string;
  asset_tag: string | null;
  serial_number: string | null;
  current_status: AssetStatus;
  current_location: string | null;
  current_holder: string | null;
  holder_since: string | null;
  acquired_at: string;
  age_days: number;
  repair_count: number;
  assignment_count: number;
  time_in_status: { status: string; seconds: number }[];
  events: AssetEvent[];
}

export interface AssetSummary {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  total_value: number;
  warranty_expiring_soon: number;
}

export type AssetInput = Partial<Omit<Asset,
  "id" | "org_id" | "assigned_to_name" | "device_hostname" | "created_at" | "updated_at"
  | "acknowledgement_status" | "acknowledged_at">> & {
  name: string;
};

export interface DashboardSummary {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  avg_cpu_percent: number;
  avg_ram_percent: number;
  critical_event_count: number;
  pending_update_count: number;
}

export interface KnowledgeArticle {
  id: string;
  title: string;
  content: string;
  source: "manual" | "resolved_issue";
  created_at: string;
  /** Learned articles: how the platform's own evidence for this fix is running. */
  successes: number;
  failures: number;
  /** null on a learned article that hasn't been confirmed enough times to be used yet. */
  published_at: string | null;
  /** Decided by the server, so this matches what search actually does. */
  learning_status: "authored" | "learning" | "in_use" | "paused";
}

/** The organization's connection to the helpdesk it already runs. */
export interface HelpdeskSettings {
  provider: "freshservice";
  enabled: boolean;
  domain: string | null;
  /** Masked. The API key is write-only — enough to recognise which key is saved, never
   *  enough to use it. "unreadable" means the encryption key changed and it must be
   *  re-entered. */
  api_key_masked: string;
  default_priority: number;
  default_source: number | null;
  workspace_id: number | null;
  group_id: number | null;
  /** { action_id: { category, sub_category } } — ASTRA's fixes mapped onto their tree. */
  category_map: Record<string, { category?: string; sub_category?: string }> | null;
  last_error: string | null;
  last_verified_at: string | null;
  /** Everything needed to actually file a ticket is present. Not the same as `enabled`:
   *  a half-filled form is not a connection. */
  ready: boolean;
}

export interface HelpdeskSettingsInput {
  enabled?: boolean;
  domain?: string;
  /** Send only when it changes. Omitting it leaves the stored credential alone. */
  api_key?: string;
  default_priority?: number;
  default_source?: number | null;
  workspace_id?: number | null;
  group_id?: number | null;
  category_map?: Record<string, { category?: string; sub_category?: string }> | null;
}

export interface HelpdeskVerifyResult {
  ok: boolean;
  detail: string | null;
}

export type RemediationTier = "automatic" | "approval_required" | "admin_only";
export type RemediationStatus =
  | "pending_approval"
  | "approved"
  | "dispatched"
  | "succeeded"
  | "failed"
  | "rejected";

export interface RemediationTask {
  id: string;
  device_id: string;
  device_hostname: string | null;
  action_id: string;
  action_label: string | null;
  // Needed to tell one job from another: "install KB5094126" and "install KB5100998" are
  // the same action_id. Without params the UI would treat the second as already running.
  params: Record<string, string> | null;
  tier: RemediationTier;
  status: RemediationStatus;
  reason: string;
  source: "assistant" | "user";
  result: { output?: string } | null;
  created_at: string;
  completed_at: string | null;
}

export interface FleetHealthDeviceRow {
  device_id: string;
  hostname: string;
  status: DeviceStatus;
  cpu_percent: number | null;
  ram_percent: number | null;
  disk_free_percent_min: number | null;
  critical_event_count: number;
  pending_update_count: number;
  last_seen_at: string | null;
}

export interface FleetHealthReport {
  generated_at: string;
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  avg_cpu_percent: number;
  avg_ram_percent: number;
  total_critical_events: number;
  total_pending_updates: number;
  devices: FleetHealthDeviceRow[];
}

export interface RemediationReportRow {
  task_id: string;
  device_hostname: string | null;
  action_id: string;
  tier: string;
  status: string;
  source: string;
  created_at: string;
  completed_at: string | null;
}

export interface RemediationReport {
  generated_at: string;
  period_days: number;
  total_tasks: number;
  succeeded: number;
  failed: number;
  pending_approval: number;
  success_rate: number;
  by_tier: Record<string, number>;
  by_action: Record<string, number>;
  tasks: RemediationReportRow[];
}

export interface AssetReport {
  generated_at: string;
  summary: AssetSummary;
  assets: Asset[];
}

export interface EnrollmentToken {
  id: string;
  name: string;
  expires_at: string;
  revoked_at: string | null;
  created_at: string;
}

export interface Installer {
  enrollment_key: string;
  server_url: string;
  filename: string;
  script: string;
}

export interface OrganizationSettings {
  org_name: string;
  auto_approve_automatic: boolean;
  require_admin_for_approval_tier: boolean;
  min_password_length: number;
  enrollment_token_default_days: number;
  updated_at: string;
}

export type OrganizationSettingsInput = Partial<
  Omit<OrganizationSettings, "updated_at">
>;

export interface RolePermissions {
  role: string;
  label: string;
  description: string;
  capabilities: Record<string, boolean>;
}

export interface PermissionMatrix {
  capabilities: { key: string; label: string }[];
  roles: RolePermissions[];
}

export type NotificationCategory = "remediation" | "telemetry" | "asset" | "system";
export type NotificationSeverity = "info" | "warning" | "critical";

export interface Notification {
  id: string;
  category: NotificationCategory;
  severity: NotificationSeverity;
  title: string;
  message: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
}
