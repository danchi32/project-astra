import type { Asset, AssetCategory, AssetStatus } from "./api/types";

export type WarrantyBucket = "all" | "expiring_30" | "expiring_60" | "expired" | "none";

export const WARRANTY_BUCKETS: { key: WarrantyBucket; label: string }[] = [
  { key: "all", label: "All" },
  { key: "expiring_30", label: "Expiring ≤30 days" },
  { key: "expiring_60", label: "Expiring ≤60 days" },
  { key: "expired", label: "Expired" },
  { key: "none", label: "No warranty set" },
];

export interface AssetFilters {
  categories: AssetCategory[];
  statuses: AssetStatus[];
  locations: string[];
  manufacturers: string[];
  warranty: WarrantyBucket;
}

export const EMPTY_ASSET_FILTERS: AssetFilters = {
  categories: [],
  statuses: [],
  locations: [],
  manufacturers: [],
  warranty: "all",
};

/** Distinct, sorted, non-empty values of a string field across the given assets. */
export function uniqueValues(assets: Asset[], key: "location" | "manufacturer"): string[] {
  const set = new Set<string>();
  for (const a of assets) {
    const v = a[key];
    if (v) set.add(v);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

function daysUntil(iso: string, now: Date): number {
  const expiry = new Date(iso).getTime();
  return (expiry - now.getTime()) / (1000 * 60 * 60 * 24);
}

function warrantyMatches(asset: Asset, bucket: WarrantyBucket, now: Date): boolean {
  if (bucket === "all") return true;
  if (bucket === "none") return !asset.warranty_expiry;
  if (!asset.warranty_expiry) return false;
  const diffDays = daysUntil(asset.warranty_expiry, now);
  if (bucket === "expired") return diffDays < 0;
  if (bucket === "expiring_30") return diffDays >= 0 && diffDays <= 30;
  if (bucket === "expiring_60") return diffDays >= 0 && diffDays <= 60;
  return true;
}

/** Client-side filtering over an already-fetched asset list. Pure, no backend calls. */
export function filterAssets(assets: Asset[], filters: AssetFilters, now: Date = new Date()): Asset[] {
  return assets.filter((a) => {
    if (filters.categories.length && !filters.categories.includes(a.category)) return false;
    if (filters.statuses.length && !filters.statuses.includes(a.status)) return false;
    if (filters.locations.length && !(a.location && filters.locations.includes(a.location))) return false;
    if (filters.manufacturers.length && !(a.manufacturer && filters.manufacturers.includes(a.manufacturer))) return false;
    if (!warrantyMatches(a, filters.warranty, now)) return false;
    return true;
  });
}

export function activeFilterCount(filters: AssetFilters): number {
  return (
    filters.categories.length +
    filters.statuses.length +
    filters.locations.length +
    filters.manufacturers.length +
    (filters.warranty !== "all" ? 1 : 0)
  );
}

export interface ComputedAssetSummary {
  total: number;
  totalValue: number;
  inRepair: number;
  warrantyExpiringSoon: number;
}

/** Recomputes the same shape as the backend's AssetSummary, from a (possibly filtered) list. */
export function computeAssetSummary(assets: Asset[], now: Date = new Date()): ComputedAssetSummary {
  let total = 0;
  let totalValue = 0;
  let inRepair = 0;
  let warrantyExpiringSoon = 0;
  for (const a of assets) {
    total += 1;
    if (a.purchase_cost != null) totalValue += a.purchase_cost;
    if (a.status === "in_repair") inRepair += 1;
    if (a.warranty_expiry) {
      const diffDays = daysUntil(a.warranty_expiry, now);
      if (diffDays >= 0 && diffDays <= 60) warrantyExpiringSoon += 1;
    }
  }
  return { total, totalValue, inRepair, warrantyExpiringSoon };
}

/** Counts assets grouped by a categorical field, e.g. for chart data. */
export function countByField(assets: Asset[], key: "category" | "status"): Record<string, number> {
  const out: Record<string, number> = {};
  for (const a of assets) {
    const v = a[key];
    out[v] = (out[v] ?? 0) + 1;
  }
  return out;
}
