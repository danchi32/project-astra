import type {
  AssetCategory,
  AssetStatus,
  RemediationStatus,
  RemediationTier,
} from "./api/types";

export const ASSET_CATEGORIES: AssetCategory[] = [
  "laptop", "desktop", "server", "monitor", "phone", "tablet",
  "peripheral", "network", "license", "software", "other",
];

export const ASSET_STATUSES: AssetStatus[] = [
  "in_use", "in_storage", "in_repair", "retired", "lost",
];

export const ASSET_STATUS_LABELS: Record<AssetStatus, string> = {
  in_use: "In use",
  in_storage: "In storage",
  in_repair: "In repair",
  retired: "Retired",
  lost: "Lost",
};

export const ASSET_STATUS_COLORS: Record<AssetStatus, string> = {
  in_use: "#10b981",
  in_storage: "#3b82f6",
  in_repair: "#f59e0b",
  retired: "#64748b",
  lost: "#ef4444",
};

const CATEGORY_PALETTE = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#64748b", "#84cc16", "#f97316", "#14b8a6",
];

export const CATEGORY_COLORS: Record<AssetCategory, string> = ASSET_CATEGORIES.reduce(
  (acc, category, i) => {
    acc[category] = CATEGORY_PALETTE[i % CATEGORY_PALETTE.length];
    return acc;
  },
  {} as Record<AssetCategory, string>,
);

export const REMEDIATION_STATUSES: RemediationStatus[] = [
  "pending_approval", "approved", "dispatched", "succeeded", "failed", "rejected",
];

export const REMEDIATION_STATUS_LABELS: Record<RemediationStatus, string> = {
  pending_approval: "Pending approval",
  approved: "Approved",
  dispatched: "Dispatched",
  succeeded: "Succeeded",
  failed: "Failed",
  rejected: "Rejected",
};

export const REMEDIATION_STATUS_COLORS: Record<RemediationStatus, string> = {
  pending_approval: "#f59e0b",
  approved: "#3b82f6",
  dispatched: "#3b82f6",
  succeeded: "#10b981",
  failed: "#ef4444",
  rejected: "#64748b",
};

export const REMEDIATION_TIERS: RemediationTier[] = [
  "automatic", "approval_required", "admin_only",
];

export const REMEDIATION_TIER_LABELS: Record<RemediationTier, string> = {
  automatic: "Automatic",
  approval_required: "Approval required",
  admin_only: "Admin only",
};
