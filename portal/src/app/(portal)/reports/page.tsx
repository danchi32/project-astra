"use client";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download, HardDrive, Wrench, Package, X } from "lucide-react";
import {
  getFleetHealthReport, getRemediationReport, getAssetReport,
  exportFleetHealthCsv, exportRemediationCsv, exportAssetsCsv,
} from "@/lib/api/reports";
import type { DeviceStatus, RemediationStatus, RemediationTier } from "@/lib/api/types";
import { formatCurrency } from "@/lib/utils";
import { MultiSelectFilter } from "@/components/multi-select-filter";
import { DonutChart, type DonutDatum } from "@/components/donut-chart";
import { StatusBarChart, type BarDatum } from "@/components/status-bar-chart";
import {
  ASSET_CATEGORIES, ASSET_STATUSES, ASSET_STATUS_LABELS, ASSET_STATUS_COLORS, CATEGORY_COLORS,
  REMEDIATION_STATUSES, REMEDIATION_STATUS_LABELS, REMEDIATION_STATUS_COLORS,
  REMEDIATION_TIERS, REMEDIATION_TIER_LABELS,
} from "@/lib/chart-colors";
import {
  type AssetFilters, EMPTY_ASSET_FILTERS, WARRANTY_BUCKETS,
  filterAssets, activeFilterCount, computeAssetSummary, countByField, uniqueValues,
  statusByLocation,
} from "@/lib/asset-filters";
import type { Asset } from "@/lib/api/types";

type Tab = "fleet" | "remediation" | "assets";

const TABS: { key: Tab; label: string; icon: typeof HardDrive }[] = [
  { key: "fleet", label: "Fleet health", icon: HardDrive },
  { key: "remediation", label: "Remediation", icon: Wrench },
  { key: "assets", label: "Assets", icon: Package },
];

// Assets-by-location × status matrix — the BI centerpiece. Rows are sites (busiest first),
// each with a stacked bar of its status mix, per-status counts, total and value.
function LocationStatusMatrix({ assets }: { assets: Asset[] }) {
  const rows = statusByLocation(assets);
  if (rows.length === 0) return null;
  const peak = Math.max(1, ...rows.map((r) => r.total));

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
      <div className="px-4 py-2.5 flex items-center justify-between" style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}>
        <p className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Assets by location &amp; status</p>
        <div className="flex items-center gap-3 flex-wrap">
          {ASSET_STATUSES.map((s) => (
            <span key={s} className="inline-flex items-center gap-1 text-xs" style={{ color: "var(--text-secondary)" }}>
              <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: ASSET_STATUS_COLORS[s] }} />
              {ASSET_STATUS_LABELS[s]}
            </span>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
        <table className="w-full text-sm whitespace-nowrap">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Location</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wide w-[28%]" style={{ color: "var(--text-secondary)" }}>Status mix</th>
              {ASSET_STATUSES.map((s) => (
                <th key={s} className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{ASSET_STATUS_LABELS[s]}</th>
              ))}
              <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Total</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.location} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="px-4 py-2.5 font-medium" style={{ color: "var(--text-primary)" }}>{r.location}</td>
                <td className="px-4 py-2.5">
                  <div className="flex h-2.5 rounded-full overflow-hidden" style={{ background: "var(--bg)", width: `${Math.max(12, (r.total / peak) * 100)}%`, minWidth: 40 }}
                    title={ASSET_STATUSES.map((s) => `${ASSET_STATUS_LABELS[s]}: ${r.byStatus[s]}`).join("  ·  ")}>
                    {ASSET_STATUSES.map((s) => r.byStatus[s] > 0 && (
                      <span key={s} style={{ width: `${(r.byStatus[s] / r.total) * 100}%`, background: ASSET_STATUS_COLORS[s] }} />
                    ))}
                  </div>
                </td>
                {ASSET_STATUSES.map((s) => (
                  <td key={s} className="px-3 py-2.5 text-right tabular-nums" style={{ color: r.byStatus[s] ? "var(--text-primary)" : "var(--text-secondary)" }}>
                    {r.byStatus[s] || "—"}
                  </td>
                ))}
                <td className="px-3 py-2.5 text-right tabular-nums font-semibold" style={{ color: "var(--text-primary)" }}>{r.total}</td>
                <td className="px-4 py-2.5 text-right tabular-nums" style={{ color: "var(--text-secondary)" }}>{r.value ? formatCurrency(r.value) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Card({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="text-xs uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>{label}</p>
      <p className="text-2xl font-semibold mt-1" style={{ color: accent ?? "var(--text-primary)" }}>{value}</p>
    </div>
  );
}

function ExportButton({ onExport }: { onExport: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      onClick={async () => { setBusy(true); try { await onExport(); } finally { setBusy(false); } }}
      disabled={busy}
      className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
      style={{ background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
    >
      <Download size={14} /> {busy ? "Exporting…" : "Export CSV"}
    </button>
  );
}

function ClearFiltersButton({ count, onClear }: { count: number; onClear: () => void }) {
  if (count === 0) return null;
  return (
    <button
      onClick={onClear}
      className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium"
      style={{ color: "var(--text-secondary)" }}
    >
      <X size={14} /> Clear filters ({count})
    </button>
  );
}

function FleetHealthTab() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["report-fleet-health"], queryFn: getFleetHealthReport });
  const [statuses, setStatuses] = useState<DeviceStatus[]>([]);

  const filteredDevices = useMemo(() => {
    if (!data) return [];
    if (statuses.length === 0) return data.devices;
    return data.devices.filter((d) => statuses.includes(d.status));
  }, [data, statuses]);

  const stats = useMemo(() => {
    const total = filteredDevices.length;
    const online = filteredDevices.filter((d) => d.status === "online").length;
    const cpuVals = filteredDevices.map((d) => d.cpu_percent).filter((v): v is number => v != null);
    const ramVals = filteredDevices.map((d) => d.ram_percent).filter((v): v is number => v != null);
    const avgCpu = cpuVals.length ? Math.round(cpuVals.reduce((a, b) => a + b, 0) / cpuVals.length) : 0;
    const avgRam = ramVals.length ? Math.round(ramVals.reduce((a, b) => a + b, 0) / ramVals.length) : 0;
    const criticalEvents = filteredDevices.reduce((sum, d) => sum + d.critical_event_count, 0);
    const pendingUpdates = filteredDevices.reduce((sum, d) => sum + d.pending_update_count, 0);
    return { total, online, avgCpu, avgRam, criticalEvents, pendingUpdates };
  }, [filteredDevices]);

  const filterCount = statuses.length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <MultiSelectFilter
            label="Status"
            options={[{ value: "online", label: "Online" }, { value: "offline", label: "Offline" }]}
            selected={statuses}
            onChange={(v) => setStatuses(v as DeviceStatus[])}
          />
          <ClearFiltersButton count={filterCount} onClear={() => setStatuses([])} />
        </div>
        <ExportButton onExport={exportFleetHealthCsv} />
      </div>
      {isError && <ErrorBanner text="Couldn't load the fleet health report." />}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Devices" value={String(stats.total)} />
          <Card label="Online" value={String(stats.online)} accent="#10b981" />
          <Card label="Avg CPU" value={`${stats.avgCpu}%`} />
          <Card label="Avg RAM" value={`${stats.avgRam}%`} />
          <Card label="Critical events" value={String(stats.criticalEvents)}
            accent={stats.criticalEvents > 0 ? "#ef4444" : undefined} />
          <Card label="Pending updates" value={String(stats.pendingUpdates)}
            accent={stats.pendingUpdates > 0 ? "#f59e0b" : undefined} />
        </div>
      )}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Hostname", "Status", "CPU", "RAM", "Disk free (min)", "Critical events", "Pending updates", "Last seen"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={8} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !isError && !filteredDevices.length && (
                <tr><td colSpan={8} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                  {data?.devices.length ? "No devices match the selected filters." : "No devices enrolled yet."}
                </td></tr>
              )}
              {filteredDevices.map((d) => (
                <tr key={d.device_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{d.hostname}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: d.status === "online" ? "#10b981" : "#64748b", background: d.status === "online" ? "#10b9811a" : "#64748b1a" }}>
                      {d.status === "online" ? "Online" : "Offline"}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.cpu_percent != null ? `${d.cpu_percent}%` : "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.ram_percent != null ? `${d.ram_percent}%` : "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.disk_free_percent_min != null ? `${d.disk_free_percent_min}%` : "—"}</td>
                  <td className="px-4 py-3" style={{ color: d.critical_event_count > 0 ? "#ef4444" : "var(--text-secondary)" }}>{d.critical_event_count}</td>
                  <td className="px-4 py-3" style={{ color: d.pending_update_count > 0 ? "#f59e0b" : "var(--text-secondary)" }}>{d.pending_update_count}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const PERIODS = [7, 30, 90];

function RemediationTab() {
  const [days, setDays] = useState(30);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["report-remediation", days],
    queryFn: () => getRemediationReport(days),
  });
  const [tiers, setTiers] = useState<RemediationTier[]>([]);
  const [statuses, setStatuses] = useState<RemediationStatus[]>([]);

  const filteredTasks = useMemo(() => {
    if (!data) return [];
    return data.tasks.filter((t) => {
      if (tiers.length && !tiers.includes(t.tier as RemediationTier)) return false;
      if (statuses.length && !statuses.includes(t.status as RemediationStatus)) return false;
      return true;
    });
  }, [data, tiers, statuses]);

  const stats = useMemo(() => {
    const total = filteredTasks.length;
    const succeeded = filteredTasks.filter((t) => t.status === "succeeded").length;
    const failed = filteredTasks.filter((t) => t.status === "failed").length;
    const successRate = total > 0 ? Math.round((succeeded / total) * 100) : 0;
    return { total, succeeded, failed, successRate };
  }, [filteredTasks]);

  const filterCount = tiers.length + statuses.length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          {PERIODS.map((p) => (
            <button key={p} onClick={() => setDays(p)}
              className="px-3 py-1.5 rounded-md text-sm font-medium"
              style={days === p
                ? { background: "var(--accent)", color: "white" }
                : { color: "var(--text-secondary)" }}>
              Last {p}d
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <MultiSelectFilter
            label="Tier"
            options={REMEDIATION_TIERS.map((t) => ({ value: t, label: REMEDIATION_TIER_LABELS[t] }))}
            selected={tiers}
            onChange={(v) => setTiers(v as RemediationTier[])}
          />
          <MultiSelectFilter
            label="Status"
            options={REMEDIATION_STATUSES.map((s) => ({ value: s, label: REMEDIATION_STATUS_LABELS[s] }))}
            selected={statuses}
            onChange={(v) => setStatuses(v as RemediationStatus[])}
          />
          <ClearFiltersButton count={filterCount} onClear={() => { setTiers([]); setStatuses([]); }} />
          <ExportButton onExport={() => exportRemediationCsv(days)} />
        </div>
      </div>
      {isError && <ErrorBanner text="Couldn't load the remediation report." />}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card label="Total tasks" value={String(stats.total)} />
          <Card label="Succeeded" value={String(stats.succeeded)} accent="#10b981" />
          <Card label="Failed" value={String(stats.failed)} accent={stats.failed > 0 ? "#ef4444" : undefined} />
          <Card label="Success rate" value={`${stats.successRate}%`} />
        </div>
      )}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Device", "Action", "Tier", "Status", "Source", "Created", "Completed"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={7} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !isError && !filteredTasks.length && (
                <tr><td colSpan={7} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                  {data?.tasks.length ? "No tasks match the selected filters." : "No remediation activity in this period."}
                </td></tr>
              )}
              {filteredTasks.map((t) => (
                <tr key={t.task_id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{t.device_hostname ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{t.action_id}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{t.tier.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{t.status.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{t.source}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{new Date(t.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{t.completed_at ? new Date(t.completed_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function AssetsTab() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["report-assets"], queryFn: getAssetReport });
  const [filters, setFilters] = useState<AssetFilters>(EMPTY_ASSET_FILTERS);

  const assets = data?.assets ?? [];
  const locationOptions = useMemo(() => uniqueValues(assets, "location"), [assets]);
  const manufacturerOptions = useMemo(() => uniqueValues(assets, "manufacturer"), [assets]);

  const filteredAssets = useMemo(() => filterAssets(assets, filters), [assets, filters]);
  const summary = useMemo(() => computeAssetSummary(filteredAssets), [filteredAssets]);
  const locationCount = useMemo(() => statusByLocation(filteredAssets).length, [filteredAssets]);

  const categoryData: DonutDatum[] = useMemo(() => {
    const counts = countByField(filteredAssets, "category");
    return Object.entries(counts).map(([category, value]) => ({
      name: category,
      value,
      color: CATEGORY_COLORS[category as keyof typeof CATEGORY_COLORS] ?? "#64748b",
    }));
  }, [filteredAssets]);

  const statusData: BarDatum[] = useMemo(() => {
    const counts = countByField(filteredAssets, "status");
    return Object.entries(counts).map(([status, value]) => ({
      name: ASSET_STATUS_LABELS[status as keyof typeof ASSET_STATUS_LABELS] ?? status,
      value,
      color: ASSET_STATUS_COLORS[status as keyof typeof ASSET_STATUS_COLORS] ?? "#64748b",
    }));
  }, [filteredAssets]);

  const filterCount = activeFilterCount(filters);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <MultiSelectFilter
            label="Category"
            options={ASSET_CATEGORIES.map((c) => ({ value: c, label: c.replace(/_/g, " ") }))}
            selected={filters.categories}
            onChange={(v) => setFilters((f) => ({ ...f, categories: v as typeof f.categories }))}
          />
          <MultiSelectFilter
            label="Status"
            options={ASSET_STATUSES.map((s) => ({ value: s, label: ASSET_STATUS_LABELS[s] }))}
            selected={filters.statuses}
            onChange={(v) => setFilters((f) => ({ ...f, statuses: v as typeof f.statuses }))}
          />
          <MultiSelectFilter
            label="Location"
            options={locationOptions.map((l) => ({ value: l, label: l }))}
            selected={filters.locations}
            onChange={(v) => setFilters((f) => ({ ...f, locations: v }))}
          />
          <MultiSelectFilter
            label="Brand"
            options={manufacturerOptions.map((m) => ({ value: m, label: m }))}
            selected={filters.manufacturers}
            onChange={(v) => setFilters((f) => ({ ...f, manufacturers: v }))}
          />
          <select
            value={filters.warranty}
            onChange={(e) => setFilters((f) => ({ ...f, warranty: e.target.value as typeof f.warranty }))}
            className="px-3 py-2 rounded-lg text-sm font-medium outline-none"
            style={{
              background: filters.warranty !== "all" ? "rgba(37,99,235,0.1)" : "var(--bg)",
              border: "1px solid var(--border)",
              color: filters.warranty !== "all" ? "var(--accent)" : "var(--text-primary)",
            }}
          >
            {WARRANTY_BUCKETS.map((b) => (
              <option key={b.key} value={b.key}>{b.label}</option>
            ))}
          </select>
          <ClearFiltersButton count={filterCount} onClear={() => setFilters(EMPTY_ASSET_FILTERS)} />
        </div>
        <ExportButton onExport={exportAssetsCsv} />
      </div>

      {isError && <ErrorBanner text="Couldn't load the asset report." />}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Card label="Total assets" value={String(summary.total)} />
            <Card label="Total value" value={formatCurrency(summary.totalValue)} />
            <Card label="Locations" value={String(locationCount)} />
            <Card label="In repair" value={String(summary.inRepair)} accent="#f59e0b" />
            <Card label="Warranty <60d" value={String(summary.warrantyExpiringSoon)}
              accent={summary.warrantyExpiringSoon > 0 ? "#ef4444" : undefined} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <p className="text-xs font-medium uppercase tracking-wide mb-2" style={{ color: "var(--text-secondary)" }}>By category</p>
              <DonutChart data={categoryData} height={200} />
            </div>
            <div className="rounded-xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <p className="text-xs font-medium uppercase tracking-wide mb-2" style={{ color: "var(--text-secondary)" }}>By status</p>
              <StatusBarChart data={statusData} height={200} />
            </div>
          </div>

          <LocationStatusMatrix assets={filteredAssets} />
        </>
      )}

      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
        <div className="px-4 py-2.5 text-xs" style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)", color: "var(--text-secondary)" }}>
          Showing {filteredAssets.length} of {assets.length} assets
        </div>
        <div className="overflow-x-auto" style={{ background: "var(--surface)" }}>
          <table className="w-full text-sm whitespace-nowrap">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Tag", "Name", "Category", "Status", "Assigned to", "Location", "Brand", "Value", "Warranty"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                    style={{ color: "var(--text-secondary)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && <tr><td colSpan={9} className="px-4 py-8 text-center" style={{ color: "var(--text-secondary)" }}>Loading…</td></tr>}
              {!isLoading && !isError && !filteredAssets.length && (
                <tr><td colSpan={9} className="px-4 py-10 text-center" style={{ color: "var(--text-secondary)" }}>
                  {assets.length ? "No assets match the selected filters." : "No assets registered yet."}
                </td></tr>
              )}
              {filteredAssets.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.asset_tag ?? "—"}</td>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--text-primary)" }}>{a.name}</td>
                  <td className="px-4 py-3 capitalize" style={{ color: "var(--text-secondary)" }}>{a.category}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                      style={{ color: ASSET_STATUS_COLORS[a.status], background: `${ASSET_STATUS_COLORS[a.status]}1a` }}>
                      {ASSET_STATUS_LABELS[a.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.assigned_to_name ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.location ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.manufacturer ?? "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.purchase_cost != null ? formatCurrency(a.purchase_cost) : "—"}</td>
                  <td className="px-4 py-3" style={{ color: "var(--text-secondary)" }}>{a.warranty_expiry ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ErrorBanner({ text }: { text: string }) {
  return (
    <div className="rounded-lg px-4 py-3 text-sm" style={{ background: "#ef44441a", color: "#ef4444" }}>
      {text}
    </div>
  );
}

export default function ReportsPage() {
  const [tab, setTab] = useState<Tab>("fleet");
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className="p-2 rounded-lg" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
          <BarChart3 size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Reports</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-secondary)" }}>
            Fleet health, remediation activity and asset register — filterable and exportable to CSV
          </p>
        </div>
      </div>

      <div className="flex gap-1 border-b" style={{ borderColor: "var(--border)" }}>
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px"
            style={tab === key
              ? { borderColor: "var(--accent)", color: "var(--accent)" }
              : { borderColor: "transparent", color: "var(--text-secondary)" }}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {tab === "fleet" && <FleetHealthTab />}
      {tab === "remediation" && <RemediationTab />}
      {tab === "assets" && <AssetsTab />}
    </div>
  );
}
