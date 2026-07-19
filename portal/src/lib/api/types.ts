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
  user_count: number;
  device_count: number;
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

export interface DeviceWindowsUpdate {
  id: string;
  kb_article_id: string;
  title: string;
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
  created_at: string;
  updated_at: string;
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
