"use client";
import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Monitor, Users as UsersIcon, Package, Zap, Eye } from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  getOrganization, getOrgUsers, getOrgDevices, getOrgRemediation, getOrgAssets, createViewToken,
} from "@/lib/api/platform";
import { enterViewAs } from "@/lib/viewAs";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { formatRam, formatStorage } from "@/lib/utils";
import type { SubscriptionStatus } from "@/lib/api/types";

const STATUS_LABEL: Record<SubscriptionStatus, string> = {
  trialing: "Trial", active: "Active", past_due: "Past due", suspended: "Suspended", canceled: "Canceled",
};

export default function OrgDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const enabled = !!me?.is_platform_admin;
  const { data: org } = useQuery({ queryKey: ["platform-org", id], queryFn: () => getOrganization(id), enabled });
  const { data: users } = useQuery({ queryKey: ["platform-org-users", id], queryFn: () => getOrgUsers(id), enabled });
  const { data: devices } = useQuery({ queryKey: ["platform-org-devices", id], queryFn: () => getOrgDevices(id), enabled });
  const { data: assets } = useQuery({ queryKey: ["platform-org-assets", id], queryFn: () => getOrgAssets(id), enabled });
  const { data: remediation } = useQuery({ queryKey: ["platform-org-remediation", id], queryFn: () => getOrgRemediation(id), enabled });

  async function viewAs() {
    if (!org) return;
    const { access_token } = await createViewToken(id);
    queryClient.clear();
    enterViewAs(access_token, { id, name: org.name });
    router.push("/dashboard");
  }

  if (me && !me.is_platform_admin) {
    return <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Platform administrator access required.</p>;
  }

  const card = { background: "var(--surface)", border: "1px solid var(--border)" } as const;

  return (
    <div className="space-y-6">
      <Link href="/platform" className="inline-flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
        <ArrowLeft size={15} /> All organizations
      </Link>

      <div className="flex items-start justify-between gap-3">
        <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>{org?.name ?? "…"}</h1>
        {org && (
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Plan <span className="capitalize" style={{ color: "var(--text-primary)" }}>{org.plan}</span> ·
            Status <span style={{ color: "var(--text-primary)" }}>{STATUS_LABEL[org.subscription_status]}</span>
            {org.trial_ends_at && org.subscription_status === "trialing" && (
              <> · Trial ends {new Date(org.trial_ends_at).toLocaleDateString()}</>
            )}
            {org.current_period_end && <> · Renews {new Date(org.current_period_end).toLocaleDateString()}</>}
          </p>
        )}
        </div>
        <button onClick={viewAs} disabled={!org}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium shrink-0 disabled:opacity-50"
          style={{ background: "rgba(124,58,237,0.1)", border: "1px solid #7c3aed", color: "#7c3aed" }}>
          <Eye size={15} /> View full portal
        </button>
      </div>

      {/* Users */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 flex items-center gap-2" style={{ ...card, borderBottom: "1px solid var(--border)" }}>
          <UsersIcon size={14} style={{ color: "var(--text-secondary)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Users ({users?.length ?? 0})</h2>
        </div>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Name", "Email", "Role", "Status"].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{u.full_name}</td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{u.email}</td>
                  <td className="px-4 py-2.5 capitalize" style={{ color: "var(--text-secondary)" }}>{u.role}</td>
                  <td className="px-4 py-2.5" style={{ color: u.is_active ? "#10b981" : "#64748b" }}>{u.is_active ? "Active" : "Disabled"}</td>
                </tr>
              ))}
              {users && users.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center" style={{ color: "var(--text-secondary)" }}>No users.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {/* Devices */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 flex items-center gap-2" style={{ ...card, borderBottom: "1px solid var(--border)" }}>
          <Monitor size={14} style={{ color: "var(--text-secondary)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Devices ({devices?.length ?? 0})</h2>
        </div>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Hostname", "Brand / Model", "CPU", "RAM", "Storage", "User", "Status"].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {devices?.map((d) => (
                <tr key={d.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>
                    {d.hostname}
                    <div className="text-xs font-normal" style={{ color: "var(--text-secondary)" }}>{d.os_version}</div>
                  </td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{d.manufacturer ?? "—"} {d.model ?? ""}</td>
                  <td className="px-4 py-2.5 max-w-[180px] truncate text-xs" style={{ color: "var(--text-secondary)" }} title={d.cpu_name ?? ""}>{d.cpu_name ?? "—"}</td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{formatRam(d.total_ram_mb)}</td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{formatStorage(d.total_storage_gb)}</td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{d.logged_in_user ?? "—"}</td>
                  <td className="px-4 py-2.5"><DeviceStatusBadge status={d.status} /></td>
                </tr>
              ))}
              {devices && devices.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center" style={{ color: "var(--text-secondary)" }}>No devices enrolled.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {/* Self-healing history — what went wrong and what was applied */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 flex items-center gap-2" style={{ ...card, borderBottom: "1px solid var(--border)" }}>
          <Zap size={14} style={{ color: "var(--text-secondary)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Self-healing history ({remediation?.length ?? 0})</h2>
        </div>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Fix", "Device", "Status", "Reason", "When"].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {remediation?.slice(0, 50).map((t) => (
                <tr key={t.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{t.action_label ?? t.action_id}</td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{t.device_hostname ?? "—"}</td>
                  <td className="px-4 py-2.5 capitalize" style={{ color: "var(--text-secondary)" }}>{t.status.replace(/_/g, " ")}</td>
                  <td className="px-4 py-2.5 max-w-[280px] truncate" style={{ color: "var(--text-secondary)" }} title={t.reason}>{t.reason}</td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{new Date(t.created_at).toLocaleString()}</td>
                </tr>
              ))}
              {remediation && remediation.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center" style={{ color: "var(--text-secondary)" }}>No self-healing activity yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      {/* Assets */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="px-5 py-3 flex items-center gap-2" style={{ ...card, borderBottom: "1px solid var(--border)" }}>
          <Package size={14} style={{ color: "var(--text-secondary)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Assets ({assets?.length ?? 0})</h2>
        </div>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead><tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Name", "Category", "Status", "Assigned to", "Serial"].map((h) => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {assets?.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{a.name}</td>
                  <td className="px-4 py-2.5 capitalize" style={{ color: "var(--text-secondary)" }}>{a.category}</td>
                  <td className="px-4 py-2.5 capitalize" style={{ color: "var(--text-secondary)" }}>{a.status.replace(/_/g, " ")}</td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{a.assigned_to_name ?? "—"}</td>
                  <td className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>{a.serial_number ?? "—"}</td>
                </tr>
              ))}
              {assets && assets.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center" style={{ color: "var(--text-secondary)" }}>No assets.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
