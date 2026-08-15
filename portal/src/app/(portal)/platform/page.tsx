"use client";
/**
 * The operator console.
 *
 * Ordered the way an operator actually reads it: money first, then who is about to cost
 * them money, then every customer scored, then the machinery underneath. Counters that
 * answer "how much" come last, because they are the second question — the first is
 * "is anything wrong".
 */
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowRight, Banknote, Building2, Clock, Cpu, MessageSquare,
  Monitor, Percent, ShieldCheck, TrendingUp, Users, Wallet, Zap,
} from "lucide-react";
import { getMe } from "@/lib/api/auth";
import {
  getPlatformAnalytics, getPlatformBilling, getPlatformOverview, getPlatformReports,
} from "@/lib/api/platform";
import { formatMinor, formatRelativeTime } from "@/lib/utils";
import {
  EmptyNote, ErrorNote, HealthPill, Kpi, LoadingBlock, Panel, SectionHeading,
} from "@/components/platform/console-ui";
import { RevenueChart } from "@/components/platform/revenue-chart";
import { GrowthChart } from "@/components/platform/growth-chart";
import { HealthTable } from "@/components/platform/health-table";

const REFETCH = 60_000;

/** A compact metric for the operations strip — smaller than a KPI, same alignment. */
function Metric({ icon: Icon, label, value, sub }: {
  icon: typeof Monitor; label: string; value: string | number; sub?: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5">
        <Icon size={13} style={{ color: "var(--text-secondary)" }} />
        <p className="text-[11px] uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
          {label}
        </p>
      </div>
      <p className="mt-1 text-xl font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
        {value}
      </p>
      {sub && <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{sub}</p>}
    </div>
  );
}

export default function PlatformOverviewPage() {
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: getMe });
  const enabled = !!me?.is_platform_admin;

  const overviewQ = useQuery({
    queryKey: ["platform-overview"], queryFn: getPlatformOverview,
    enabled, refetchInterval: REFETCH,
  });
  const billingQ = useQuery({
    queryKey: ["platform-billing"], queryFn: getPlatformBilling,
    enabled, refetchInterval: REFETCH,
  });
  const reportsQ = useQuery({
    queryKey: ["platform-reports"], queryFn: getPlatformReports,
    enabled, refetchInterval: REFETCH,
  });
  const analyticsQ = useQuery({
    queryKey: ["platform-analytics"], queryFn: getPlatformAnalytics,
    enabled, refetchInterval: REFETCH,
  });

  if (me && !me.is_platform_admin) {
    return (
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Platform administrator access required.
      </p>
    );
  }

  const overview = overviewQ.data;
  const billing = billingQ.data;
  const reports = reportsQ.data;
  const analytics = analyticsQ.data;

  // Revenue reaching this console is denominated by the invoices behind it. With no
  // invoices yet there is nothing to denominate, and the seat-price setting carries no
  // currency of its own — so USD is the fallback, exactly as before.
  const currency = analytics?.revenue_currency ?? "USD";
  const priceUnset = billing?.price_per_seat_cents == null;

  // Both lists come from the scored rows rather than the billing rows, so the countdown
  // here and the one in the health table are the same number. Computing "days left" in the
  // browser reads a naive UTC timestamp as local time and lands a day out.
  const rows = analytics?.org_health ?? [];
  const trialsEndingSoon = rows
    .filter((r) => r.subscription_status === "trialing" && r.trial_days_left != null && r.trial_days_left <= 7)
    .sort((a, b) => (a.trial_days_left ?? 0) - (b.trial_days_left ?? 0));
  const pastDue = rows.filter(
    (r) => r.subscription_status === "past_due" || r.subscription_status === "suspended",
  );

  const health = analytics?.health_counts;
  const atRisk = health?.at_risk ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg shrink-0"
            style={{ background: "color-mix(in srgb, var(--accent) 12%, transparent)", color: "var(--accent)" }}>
            <ShieldCheck size={18} />
          </div>
          <div>
            <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
              Operator console
            </h1>
            <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
              Revenue, retention risk and fleet health across every customer
            </p>
          </div>
        </div>
        <Link href="/platform/organizations"
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white shrink-0"
          style={{ background: "var(--accent)" }}>
          Manage organizations <ArrowRight size={15} />
        </Link>
      </div>

      {/* ── Commercial headline ───────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <Kpi
          tone="accent" icon={Banknote} label="MRR"
          value={formatMinor(billing?.mrr_cents, currency)}
          hint={priceUnset
            ? "Set ASTRA_PRICE_PER_SEAT_CENTS"
            : `${billing?.active_subscriptions ?? 0} active subscription${billing?.active_subscriptions === 1 ? "" : "s"}`}
        />
        <Kpi
          icon={TrendingUp} label="ARR"
          value={formatMinor(billing?.arr_cents, currency)}
          hint="MRR × 12"
        />
        <Kpi
          icon={Wallet} label="Collected 90d"
          value={analytics ? formatMinor(analytics.collected_90d_cents, currency) : "…"}
          hint="Paid invoices, last 3 months"
        />
        <Kpi
          icon={Clock} label="Outstanding"
          tone={(analytics?.outstanding_cents ?? 0) > 0 ? "warn" : "default"}
          value={analytics ? formatMinor(analytics.outstanding_cents, currency) : "…"}
          hint="Issued and unpaid"
        />
        <Kpi
          icon={Users} label="ARPA"
          value={analytics ? formatMinor(analytics.arpa_cents, currency) : "…"}
          hint="Average revenue per account"
        />
        <Kpi
          icon={Percent} label="Trial conversion"
          value={analytics?.trial_conversion_rate != null ? `${analytics.trial_conversion_rate}%` : "—"}
          hint={analytics?.trial_conversion_rate != null
            ? "Of trials that have ended"
            : "No trials have ended yet"}
        />
      </div>

      {/* ── Revenue + portfolio health ────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel className="lg:col-span-2">
          <SectionHeading
            title="Billed vs collected"
            description={
              analytics?.other_currencies?.length
                ? `Last 12 months, ${currency}. Excludes invoices in ${analytics.other_currencies.join(", ")}.`
                : `Last 12 months${analytics?.revenue_currency ? `, ${currency}` : ""}`
            }
          />
          {analyticsQ.isLoading ? <LoadingBlock height={260} />
            : analyticsQ.isError ? <ErrorNote text="Couldn't load revenue history." />
              : <RevenueChart data={analytics?.revenue_by_month ?? []} currency={currency} />}
        </Panel>

        <Panel>
          <SectionHeading title="Portfolio health" description="Every customer, scored" />
          {analyticsQ.isLoading ? <LoadingBlock height={260} />
            : analyticsQ.isError ? <ErrorNote text="Couldn't load customer health." />
              : (
                <div className="space-y-3">
                  {(["at_risk", "watch", "healthy"] as const).map((band) => {
                    const count = health?.[band] ?? 0;
                    const total = analytics?.org_health.length ?? 0;
                    const pct = total ? Math.round((count / total) * 100) : 0;
                    const color = band === "healthy" ? "var(--health-good)"
                      : band === "watch" ? "var(--health-warn)" : "var(--health-bad)";
                    return (
                      <div key={band}>
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <HealthPill band={band} />
                          <span className="text-sm font-semibold tabular-nums"
                            style={{ color: "var(--text-primary)" }}>
                            {count}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full overflow-hidden"
                          style={{ background: "var(--border)" }}>
                          <div className="h-full rounded-full"
                            style={{ width: `${pct}%`, background: color }} />
                        </div>
                      </div>
                    );
                  })}

                  <div className="pt-3 mt-1 grid grid-cols-2 gap-3"
                    style={{ borderTop: "1px solid var(--border)" }}>
                    <div>
                      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Churn rate</p>
                      <p className="text-lg font-semibold tabular-nums"
                        style={{ color: "var(--text-primary)" }}>
                        {analytics?.churn_rate != null ? `${analytics.churn_rate}%` : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Canceled</p>
                      <p className="text-lg font-semibold tabular-nums"
                        style={{ color: "var(--text-primary)" }}>
                        {analytics?.canceled_orgs ?? "—"}
                      </p>
                    </div>
                  </div>
                </div>
              )}
        </Panel>
      </div>

      {/* ── Time-sensitive commercial actions ─────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel>
          <SectionHeading
            title="Trials ending within 7 days"
            description="Conversions still winnable"
            action={
              <Link href="/platform/billing" className="text-xs" style={{ color: "var(--accent)" }}>
                Billing →
              </Link>
            }
          />
          {analyticsQ.isLoading ? <LoadingBlock height={120} />
            : trialsEndingSoon.length === 0
              ? <EmptyNote icon={Clock} text="No trials ending this week." />
              : (
                <ul className="space-y-2">
                  {trialsEndingSoon.slice(0, 5).map((r) => (
                    <li key={r.org_id} className="flex items-center justify-between gap-2 text-sm">
                      <Link href={`/platform/${r.org_id}`} className="hover:underline font-medium truncate"
                        style={{ color: "var(--text-primary)" }}>
                        {r.org_name}
                      </Link>
                      <span className="text-xs tabular-nums shrink-0"
                        style={{ color: "var(--health-warn)" }}>
                        {r.trial_days_left}d left
                      </span>
                    </li>
                  ))}
                </ul>
              )}
        </Panel>

        <Panel>
          <SectionHeading title="Past due & suspended" description="Revenue already at risk" />
          {analyticsQ.isLoading ? <LoadingBlock height={120} />
            : pastDue.length === 0
              ? <EmptyNote icon={ShieldCheck} text="All customers in good standing." />
              : (
                <ul className="space-y-2">
                  {pastDue.slice(0, 5).map((r) => (
                    <li key={r.org_id} className="flex items-center justify-between gap-2 text-sm">
                      <Link href={`/platform/${r.org_id}`} className="hover:underline font-medium truncate"
                        style={{ color: "var(--text-primary)" }}>
                        {r.org_name}
                      </Link>
                      <span className="text-xs capitalize shrink-0"
                        style={{ color: "var(--health-bad)" }}>
                        {r.subscription_status.replace("_", " ")}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
        </Panel>
      </div>

      {/* ── Every customer, scored ────────────────────────────────────────── */}
      <div>
        <SectionHeading
          title="Customer health"
          description={
            atRisk > 0
              ? `${atRisk} account${atRisk === 1 ? "" : "s"} need attention — worst first`
              : "Scored on connectivity, engagement, deployment and reliability"
          }
          action={
            <Link href="/platform/organizations" className="text-xs" style={{ color: "var(--accent)" }}>
              All organizations →
            </Link>
          }
        />
        {analyticsQ.isLoading ? <Panel><LoadingBlock height={220} /></Panel>
          : analyticsQ.isError ? <Panel><ErrorNote text="Couldn't load customer health." /></Panel>
            : <HealthTable rows={analytics?.org_health ?? []} currency={currency} />}
      </div>

      {/* ── Growth + operations ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel className="lg:col-span-2">
          <SectionHeading title="New organizations" description="Sign-ups per month, last 12 months" />
          {reportsQ.isLoading ? <LoadingBlock height={150} />
            : reportsQ.isError ? <ErrorNote text="Couldn't load growth history." />
              : <GrowthChart data={reports?.signups_by_month ?? []} />}
        </Panel>

        <Panel>
          <SectionHeading title="Platform operations" description="Across every customer" />
          <div className="grid grid-cols-2 gap-4">
            <Metric icon={Building2} label="Customers" value={overview?.total_organizations ?? "…"}
              sub={`${overview?.signups_30d ?? 0} new in 30d`} />
            <Metric icon={Monitor} label="Devices" value={overview?.total_devices ?? "…"}
              sub={`${overview?.online_devices ?? 0} online now`} />
            <Metric icon={Users} label="Users" value={overview?.total_users ?? "…"}
              sub={`${overview?.licenses_sold ?? 0} seats sold`} />
            <Metric icon={Zap} label="Fix success"
              value={reports?.remediation_success_rate != null ? `${reports.remediation_success_rate}%` : "—"}
              sub={`${reports?.remediation_total_30d ?? 0} run in 30d`} />
            <Metric icon={MessageSquare} label="AI chats" value={reports?.conversations_30d ?? "…"}
              sub={`${reports?.messages_30d ?? 0} messages, 30d`} />
            <Metric icon={Cpu} label="Awaiting approval" value={overview?.remediation_pending ?? "…"}
              sub="Fixes needing a human" />
          </div>
          {(overview?.remediation_pending ?? 0) > 0 && (
            <p className="text-xs mt-4 pt-3 flex items-center gap-1.5"
              style={{ borderTop: "1px solid var(--border)", color: "var(--health-warn)" }}>
              <AlertTriangle size={12} />
              Approvals are queued inside each customer's own portal.
            </p>
          )}
        </Panel>
      </div>

      {analytics && analytics.org_health.length > 0 && (
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Health is scored server-side from connectivity, engagement, seat deployment and
          remediation reliability. Billing trouble overrides the score.
          {reportsQ.dataUpdatedAt
            ? ` Updated ${formatRelativeTime(new Date(reportsQ.dataUpdatedAt).toISOString())}.`
            : ""}
        </p>
      )}
    </div>
  );
}
