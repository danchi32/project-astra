import { describe, it, expect } from "vitest";
import {
  filterAssets, activeFilterCount, computeAssetSummary, countByField, uniqueValues,
  statusByLocation, assetLocation, UNASSIGNED_LOCATION,
  EMPTY_ASSET_FILTERS, type AssetFilters,
} from "./asset-filters";
import type { Asset } from "./api/types";

const NOW = new Date("2026-07-10T00:00:00Z");

function makeAsset(overrides: Partial<Asset>): Asset {
  return {
    id: overrides.id ?? Math.random().toString(),
    org_id: "org-1",
    asset_tag: null,
    name: "Asset",
    category: "laptop",
    status: "in_use",
    assigned_to_user_id: null,
    device_id: null,
    assigned_to_name: null,
    device_hostname: null,
    manufacturer: null,
    model: null,
    serial_number: null,
    location: null,
    purchase_date: null,
    warranty_expiry: null,
    purchase_cost: null,
    notes: null,
    acknowledgement_status: "not_required",
    acknowledged_at: null,
    archived_at: null,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    ...overrides,
  };
}

const ASSETS: Asset[] = [
  makeAsset({ id: "1", category: "laptop", status: "in_use", location: "NYC", manufacturer: "Dell", purchase_cost: 1000, warranty_expiry: "2026-07-15" }), // +5d
  makeAsset({ id: "2", category: "desktop", status: "in_repair", location: "SF", manufacturer: "HP", purchase_cost: 500, warranty_expiry: "2026-08-01" }), // +22d
  makeAsset({ id: "3", category: "laptop", status: "retired", location: "NYC", manufacturer: "Dell", purchase_cost: 200, warranty_expiry: "2026-01-01" }), // expired
  makeAsset({ id: "4", category: "monitor", status: "in_use", location: null, manufacturer: null, purchase_cost: null, warranty_expiry: null }), // no warranty
  makeAsset({ id: "5", category: "server", status: "in_use", location: "SF", manufacturer: "Dell", purchase_cost: 3000, warranty_expiry: "2026-09-15" }), // +67d
];

describe("uniqueValues", () => {
  it("returns sorted, deduped, non-empty values", () => {
    expect(uniqueValues(ASSETS, "location")).toEqual(["NYC", "SF"]);
    expect(uniqueValues(ASSETS, "manufacturer")).toEqual(["Dell", "HP"]);
  });
});

describe("statusByLocation", () => {
  it("groups by location with a status breakdown, value, and Unassigned bucket", () => {
    const rows = statusByLocation(ASSETS);
    // NYC (2) and SF (2) tie; Unassigned (1) last.
    expect(rows.map((r) => r.location)).toEqual(["NYC", "SF", UNASSIGNED_LOCATION]);
    const nyc = rows.find((r) => r.location === "NYC")!;
    expect(nyc.total).toBe(2);
    expect(nyc.value).toBe(1200);
    expect(nyc.byStatus.in_use).toBe(1);
    expect(nyc.byStatus.retired).toBe(1);
    const unassigned = rows.find((r) => r.location === UNASSIGNED_LOCATION)!;
    expect(unassigned.total).toBe(1);
    expect(unassigned.byStatus.in_use).toBe(1);
  });

  it("normalizes blank/whitespace locations to Unassigned", () => {
    expect(assetLocation(makeAsset({ location: "   " }))).toBe(UNASSIGNED_LOCATION);
    expect(assetLocation(makeAsset({ location: "Berlin" }))).toBe("Berlin");
  });
});

describe("filterAssets", () => {
  it("returns all assets when no filters are active", () => {
    expect(filterAssets(ASSETS, EMPTY_ASSET_FILTERS, NOW)).toHaveLength(5);
  });

  it("filters by category", () => {
    const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, categories: ["laptop"] };
    const result = filterAssets(ASSETS, filters, NOW);
    expect(result.map((a) => a.id)).toEqual(["1", "3"]);
  });

  it("filters by status", () => {
    const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, statuses: ["in_repair"] };
    expect(filterAssets(ASSETS, filters, NOW).map((a) => a.id)).toEqual(["2"]);
  });

  it("filters by location", () => {
    const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, locations: ["SF"] };
    expect(filterAssets(ASSETS, filters, NOW).map((a) => a.id)).toEqual(["2", "5"]);
  });

  it("filters by manufacturer", () => {
    const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, manufacturers: ["Dell"] };
    expect(filterAssets(ASSETS, filters, NOW).map((a) => a.id)).toEqual(["1", "3", "5"]);
  });

  it("combines multiple filters with AND semantics", () => {
    const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, categories: ["laptop"], locations: ["NYC"] };
    expect(filterAssets(ASSETS, filters, NOW).map((a) => a.id)).toEqual(["1", "3"]);
  });

  describe("warranty buckets", () => {
    it("expiring_30 matches assets expiring within 30 days", () => {
      const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, warranty: "expiring_30" };
      expect(filterAssets(ASSETS, filters, NOW).map((a) => a.id)).toEqual(["1", "2"]);
    });

    it("expiring_60 matches assets expiring within 60 days", () => {
      const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, warranty: "expiring_60" };
      expect(filterAssets(ASSETS, filters, NOW).map((a) => a.id)).toEqual(["1", "2"]);
    });

    it("expired matches assets past their warranty date", () => {
      const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, warranty: "expired" };
      expect(filterAssets(ASSETS, filters, NOW).map((a) => a.id)).toEqual(["3"]);
    });

    it("none matches assets with no warranty date set", () => {
      const filters: AssetFilters = { ...EMPTY_ASSET_FILTERS, warranty: "none" };
      expect(filterAssets(ASSETS, filters, NOW).map((a) => a.id)).toEqual(["4"]);
    });
  });
});

describe("activeFilterCount", () => {
  it("is 0 for the empty filter set", () => {
    expect(activeFilterCount(EMPTY_ASSET_FILTERS)).toBe(0);
  });

  it("counts each active dimension", () => {
    const filters: AssetFilters = {
      categories: ["laptop", "desktop"],
      statuses: ["in_use"],
      locations: [],
      manufacturers: [],
      warranty: "expired",
    };
    expect(activeFilterCount(filters)).toBe(4);
  });
});

describe("computeAssetSummary", () => {
  it("recomputes total, value, in-repair count and warranty-expiring-soon over the given list", () => {
    const summary = computeAssetSummary(ASSETS, NOW);
    expect(summary.total).toBe(5);
    expect(summary.totalValue).toBe(1000 + 500 + 200 + 3000);
    expect(summary.inRepair).toBe(1);
    expect(summary.warrantyExpiringSoon).toBe(2); // ids 1 and 2, within 60 days
  });

  it("reflects a filtered subset, not the full list", () => {
    const laptopsOnly = ASSETS.filter((a) => a.category === "laptop");
    const summary = computeAssetSummary(laptopsOnly, NOW);
    expect(summary.total).toBe(2);
    expect(summary.totalValue).toBe(1200);
  });
});

describe("countByField", () => {
  it("counts assets grouped by category", () => {
    expect(countByField(ASSETS, "category")).toEqual({
      laptop: 2, desktop: 1, monitor: 1, server: 1,
    });
  });

  it("counts assets grouped by status", () => {
    expect(countByField(ASSETS, "status")).toEqual({
      in_use: 3, in_repair: 1, retired: 1,
    });
  });
});
