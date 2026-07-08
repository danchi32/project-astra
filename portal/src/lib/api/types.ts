export type UserRole = "admin" | "technician" | "user";

export interface User {
  id: string;
  org_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
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

export interface DashboardSummary {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  avg_cpu_percent: number;
  avg_ram_percent: number;
  critical_event_count: number;
  pending_update_count: number;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export interface ToolTrailEntry {
  tool: string;
  input: Record<string, unknown>;
  output: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  tool_trail: ToolTrailEntry[] | null;
  created_at: string;
}
