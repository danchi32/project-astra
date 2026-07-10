"use client";
import type { ReactNode } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Monitor, AlertTriangle, RefreshCw, Package,
  Zap, Bell, History, ArrowRight, CheckCircle2, XCircle, Clock,
} from "lucide-react";
import { getDashboardSummary, getDevices } from "@/lib/api/dashboard";
import { getAssetSummary } from "@/lib/api/assets";
import { listRemediations } from "@/lib/api/remediation";
import { listNotifications } from "@/lib/api/notifications";
import { listAuditLogs } from "@/lib/api/audit";
import { StatCard } from "@/components/stat-card";
import { DeviceStatusBadge } from "@/components/device-status-badge";
import { DonutChart, type DonutDatum } from "@/components/donut-chart";
import { StatusBarChart, type BarDatum } from "@/components/status-bar-chart";
import {
  InsightCard, InsightMetric, InsightMiniStats, InsightProgressRow, InsightButton,
} from "@/components/insight-card";
import { SkeletonStatCard, SkeletonPanel, SkeletonTableRow, SkeletonInsightCard } from "@/components/skeleton";
import { formatRam, formatStorage, formatCurrency, formatRelativeTime, humanizeAuditAction } from "@/lib/utils";
import { CATEGORY_COLORS, REMEDIATION_STATUS_LABELS, REMEDIATION_STATUS_COLORS } from "@/lib/chart-colors";
import type { NotificationSeverity } from "@/lib/api/types";

const REFETCH = 30_000;

const SEVERITY_COLOR: Record<NotificationSeverity, string> = {
  info: "#3b82f6",
  warning: "#f59e0b",
  critical: "#ef4444",
};

function SectionHeader({ title, href, linkLabel }: { title: string; href?: string; linkLabel?: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h2>
      {href && (
        <Link
          href={href}
          className="flex items-center gap-1 text-xs font-medium hover:underline"
          style={{ color: "var(--accent)" }}
        >
          {linkLabel ?? "View all"} <ArrowRight size={12} />
        </Link>
      )}
    </div>
  );
}

function Panel({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl p-5" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      {children}
    </div>
  );
}

function MiniStat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="text-lg font-semibold tabular-nums" style={{ color: accent ?? "var(--text-primary)" }}>{value}</p>
    </div>
  );
}

export default function DashboardPage() {
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: getDashboardSummary,
    refetchInterval: REFETCH,
  });

  const { data: devices, isLoading: devicesLoading, isError: devicesError } = useQuery({
    queryKey: ["devices"],
    queryFn: getDevices,
    refetchInterval: REFETCH,
  });

  const { data: assetSummary, isLoading: assetsLoading, isError: assetsError } = useQuery({
    queryKey: ["asset-summary"],
    queryFn: getAssetSummary,
    refetchInterval: REFETCH,
  });

  const { data: remediations, isLoading: remediationsLoading, isError: remediationsError } = useQuery({
    queryKey: ["remediations"],
    queryFn: listRemediations,
    refetchInterval: REFETCH,
  });

  const { data: unreadNotifications, isLoading: notificationsLoading, isError: notificationsError } = useQuery({
    queryKey: ["unread-notifications-list"],
    queryFn: () => listNotifications(true),
    refetchInterval: REFETCH,
  });

  const { data: auditLogs, isLoading: auditLoading, isError: auditError } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: listAuditLogs,
    refetchInterval: REFETCH,
  });

  // Remediation status breakdown for the bar chart.
  const remediationStatusCounts = (remediations ?? []).reduce<Record<string, number>>((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1;
    return acc;
  }, {});
  const remediationChartData: BarDatum[] = Object.entries(remediationStatusCounts).map(([status, count]) => ({
    name: REMEDIATION_STATUS_LABELS[status as keyof typeof REMEDIATION_STATUS_LABELS] ?? status.replace(/_/g, " "),
    value: count,
    color: REMEDIATION_STATUS_COLORS[status as keyof typeof REMEDIATION_STATUS_COLORS] ?? "#3b82f6",
  }));
  const pendingApprovalCount = remediationStatusCounts["pending_approval"] ?? 0;

  // Device status donut.
  const onlineCount = devices?.filter((d) => d.status === "online").length ?? 0;
  const offlineCount = (devices?.length ?? 0) - onlineCount;
  const deviceStatusData: DonutDatum[] = [
    { name: "Online", value: onlineCount, color: "#10b981" },
    { name: "Offline", value: offlineCount, color: "#64748b" },
  ];

  const recentUnread = (unreadNotifications ?? []).slice(0, 5);
  const recentActivity = [...(auditLogs ?? [])]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 8);

  // Top asset categories as "name — count/total" progress rows (mirrors the M365 license-breakdown pattern).
  const topCategories = assetSummary
    ? Object.entries(assetSummary.by_category)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 4)
    : [];

  return (
    <div
      className="space-y-6 -m-6 p-6"
      style={{
        background:
          "radial-gradient(900px circle at 10% -10%, color-mix(in srgb, var(--accent) 8%, transparent), transparent 55%), " +
          "radial-gradient(800px circle at 95% -5%, color-mix(in srgb, #ec4899 6%, transparent), transparent 50%), " +
          "var(--bg)",
      }}
    >
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Dashboard
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
          Real-time overview of your IT environment
        </p>
      </div>

      {/* Hero insight cards: Devices / Assets / Remediation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Devices */}
        {summaryLoading ? (
          <SkeletonInsightCard />
        ) : summaryError ? (
          <InsightCard title="Devices" subtitle="Across your fleet">
            <ErrorNote text="Couldn't load dashboard summary." />
          </InsightCard>
        ) : (
          <InsightCard
            title="Device fleet"
            subtitle="Across your fleet"
            actions={<InsightButton href="/devices">View devices</InsightButton>}
          >
            <InsightMetric value={summary?.total_devices ?? 0} label="Total devices" />
            <InsightProgressRow
              label="Online"
              value={summary?.online_devices ?? 0}
              max={summary?.total_devices ?? 0}
              color="#10b981"
            />
            <InsightProgressRow
              label="Offline"
              value={summary?.offline_devices ?? 0}
              max={summary?.total_devices ?? 0}
              color="#64748b"
            />
            <div className="mt-4 pt-4 grid grid-cols-2 gap-3" style={{ borderTop: "1px solid var(--border)" }}>
              <MiniStat label="Avg CPU" value={`${Math.round(summary?.avg_cpu_percent ?? 0)}%`} />
              <MiniStat label="Avg RAM" value={`${Math.round(summary?.avg_ram_percent ?? 0)}%`} />
            </div>
          </InsightCard>
        )}

        {/* Assets */}
        {assetsLoading ? (
          <SkeletonInsightCard />
        ) : assetsError ? (
          <InsightCard title="Assets" subtitle="Registered IT assets">
            <ErrorNote text="Couldn't load asset summary." />
          </InsightCard>
        ) : (
          <InsightCard
            title="IT assets"
            subtitle="Registered IT assets"
            actions={
              <>
                <InsightButton href="/assets">Add asset</InsightButton>
                <InsightButton href="/assets">View assets</InsightButton>
              </>
            }
          >
            <InsightMetric value={assetSummary?.total ?? 0} label="Total assets" />
            <InsightMiniStats
              items={[
                { label: "Total value", value: formatCurrency(assetSummary?.total_value ?? 0) },
                {
                  label: "Warranty <60d",
                  value: assetSummary?.warranty_expiring_soon ?? 0,
                  accent: assetSummary && assetSummary.warranty_expiring_soon > 0 ? "#ef4444" : undefined,
                },
              ]}
            />
            {topCategories.length === 0 ? (
              <EmptyNote icon={Package} text="No assets registered yet." />
            ) : (
              <div>
                <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>
                  Top categories
                </p>
                {topCategories.map(([category, count]) => (
                  <InsightProgressRow
                    key={category}
                    label={category.charAt(0).toUpperCase() + category.slice(1).replace(/_/g, " ")}
                    value={count}
                    max={assetSummary?.total ?? 0}
                    color={CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] ?? "#64748b"}
                  />
                ))}
              </div>
            )}
          </InsightCard>
        )}

        {/* Remediation */}
        {remediationsLoading ? (
          <SkeletonInsightCard />
        ) : remediationsError ? (
          <InsightCard title="Self-healing" subtitle="Needs your attention">
            <ErrorNote text="Couldn't load remediation activity." />
          </InsightCard>
        ) : (
          <InsightCard
            title="Self-healing"
            subtitle="Needs your attention"
            actions={<InsightButton href="/self-healing">Review approvals</InsightButton>}
          >
            <InsightMetric
              value={pendingApprovalCount}
              label="Pending approval"
            />
            {remediationChartData.length === 0 ? (
              <EmptyNote icon={Zap} text="No remediation activity yet." />
            ) : (
              <StatusBarChart data={remediationChartData} height={160} />
            )}
          </InsightCard>
        )}
      </div>

      {/* Slim strip: metrics not covered by the hero cards above */}
      <div className="grid grid-cols-2 gap-4">
        {summaryLoading ? (
          <>
            <SkeletonStatCard />
            <SkeletonStatCard />
          </>
        ) : summaryError ? (
          <div className="col-span-full">
            <ErrorNote text="Couldn't load dashboard summary." />
          </div>
        ) : (
          <>
            <StatCard
              title="Critical Events"
              value={summary?.critical_event_count ?? 0}
              icon={AlertTriangle}
              variant={summary && summary.critical_event_count > 0 ? "danger" : "default"}
            />
            <StatCard
              title="Pending Updates"
              value={summary?.pending_update_count ?? 0}
              icon={RefreshCw}
              variant={summary && summary.pending_update_count > 5 ? "warning" : "default"}
            />
          </>
        )}
      </div>

      {/* Notifications + Recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Notifications */}
        <div>
          <SectionHeader title="Notifications" href="/notifications" />
          {notificationsLoading ? (
            <SkeletonPanel lines={4} height={260} />
          ) : notificationsError ? (
            <Panel><ErrorNote text="Couldn't load notifications." /></Panel>
          ) : (
            <Panel>
              <div className="flex items-center gap-2 mb-3">
                <div className="p-2 rounded-lg shrink-0" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
                  <Bell size={16} />
                </div>
                <MiniStat label="Unread" value={String(unreadNotifications?.length ?? 0)} />
              </div>
              {recentUnread.length === 0 ? (
                <EmptyNote icon={Bell} text="You're all caught up — no unread notifications." />
              ) : (
                <ul className="space-y-2">
                  {recentUnread.map((n) => (
                    <li key={n.id} className="flex items-start gap-2 text-sm">
                      <span
                        className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                        style={{ background: SEVERITY_COLOR[n.severity] }}
                      />
                      <div className="min-w-0">
                        <p className="font-medium truncate" style={{ color: "var(--text-primary)" }}>{n.title}</p>
                        <p className="text-xs truncate" style={{ color: "var(--text-secondary)" }}>
                          {n.message}
                        </p>
                      </div>
                      <span className="text-xs shrink-0 ml-auto" style={{ color: "var(--text-secondary)" }}>
                        {formatRelativeTime(n.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
        </div>

        {/* Recent activity feed */}
        <div>
          <SectionHeader title="Recent activity" href="/audit" />
          {auditLoading ? (
            <SkeletonPanel lines={5} height={260} />
          ) : auditError ? (
            <Panel><ErrorNote text="Couldn't load recent activity." /></Panel>
          ) : (
            <Panel>
              {recentActivity.length === 0 ? (
                <EmptyNote icon={History} text="No activity recorded yet." />
              ) : (
                <ul className="space-y-2.5">
                  {recentActivity.map((log) => (
                    <li key={log.id} className="flex items-start gap-2 text-sm">
                      <Clock size={13} className="mt-0.5 shrink-0" style={{ color: "var(--text-secondary)" }} />
                      <div className="min-w-0 flex-1">
                        <span style={{ color: "var(--text-primary)" }}>{humanizeAuditAction(log.action)}</span>{" "}
                        <span style={{ color: "var(--text-secondary)" }}>
                          {log.actor_email ? `by ${log.actor_email}` : ""}
                        </span>
                      </div>
                      <span className="text-xs shrink-0" style={{ color: "var(--text-secondary)" }}>
                        {formatRelativeTime(log.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
        </div>
      </div>

      {/* Devices table + status donut */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
          <div className="px-5 py-4 flex items-center justify-between" style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Devices</h2>
            <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
              {devices?.length ?? 0} total
            </span>
          </div>
          <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
            <table className="w-full text-sm whitespace-nowrap">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Hostname", "Brand / Model", "RAM", "Storage", "Software", "User", "Status"].map((h) => (
                    <th key={h} className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wide"
                      style={{ color: "var(--text-secondary)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {devicesLoading && Array.from({ length: 4 }).map((_, i) => <SkeletonTableRow key={i} cols={7} />)}
                {!devicesLoading && devicesError && (
                  <tr><td colSpan={7} className="px-5 py-8 text-center"><ErrorNote text="Couldn't load devices." /></td></tr>
                )}
                {!devicesLoading && !devicesError && (!devices || devices.length === 0) && (
                  <tr><td colSpan={7} className="px-5 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
                    No devices enrolled yet. Create an enrollment token and run the Windows agent.
                  </td></tr>
                )}
                {devices?.map((d) => (
                  <tr key={d.id} className="transition-colors hover:bg-blue-500/5" style={{ borderBottom: "1px solid var(--border)" }}>
                    <td className="px-5 py-3 font-medium" style={{ color: "var(--text-primary)" }}>
                      {d.hostname}
                      <div className="text-xs font-normal max-w-[160px] truncate" style={{ color: "var(--text-secondary)" }} title={d.os_version}>{d.os_version}</div>
                    </td>
                    <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>
                      {d.manufacturer ?? "—"}{d.model ? ` ${d.model}` : ""}
                    </td>
                    <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatRam(d.total_ram_mb)}</td>
                    <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{formatStorage(d.total_storage_gb)}</td>
                    <td className="px-5 py-3 tabular-nums" style={{ color: "var(--text-secondary)" }}>{d.installed_app_count > 0 ? d.installed_app_count : "—"}</td>
                    <td className="px-5 py-3" style={{ color: "var(--text-secondary)" }}>{d.logged_in_user ?? "—"}</td>
                    <td className="px-5 py-3"><DeviceStatusBadge status={d.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Device status donut */}
        <div>
          <SectionHeader title="Device status" />
          {devicesLoading ? (
            <SkeletonPanel lines={2} height={220} />
          ) : devicesError ? (
            <Panel><ErrorNote text="Couldn't load device status." /></Panel>
          ) : (devices?.length ?? 0) === 0 ? (
            <Panel><EmptyNote icon={Monitor} text="No devices enrolled yet." /></Panel>
          ) : (
            <Panel>
              <DonutChart data={deviceStatusData} height={190} />
              <div className="flex items-center justify-center gap-4 mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                <span className="flex items-center gap-1"><CheckCircle2 size={12} color="#10b981" /> {onlineCount} online</span>
                <span className="flex items-center gap-1"><XCircle size={12} color="#64748b" /> {offlineCount} offline</span>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyNote({ icon: Icon, text }: { icon: typeof Package; text: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
      <Icon size={22} style={{ color: "var(--text-secondary)" }} />
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{text}</p>
    </div>
  );
}

function ErrorNote({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
      <AlertTriangle size={22} color="#ef4444" />
      <p className="text-xs" style={{ color: "#ef4444" }}>{text}</p>
    </div>
  );
}
