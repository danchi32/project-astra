import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Extract a human string from an API error. FastAPI returns `detail` as a string for our
 * service errors but as an ARRAY of objects for request-validation (422) errors — rendering that
 * array as a React child crashes the page, so always coerce to a string. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((e) => (e && typeof e === "object" && "msg" in e ? String((e as { msg: unknown }).msg) : ""))
      .filter(Boolean);
    if (msgs.length) return msgs.join("; ");
  }
  return fallback;
}

/** Format megabytes as GB for display, e.g. 16065 -> "16 GB". */
export function formatRam(mb: number | null): string {
  if (mb == null || mb <= 0) return "—";
  return `${Math.round(mb / 1024)} GB`;
}

/** Format a GB storage figure, e.g. 476.9 -> "477 GB" or "1.0 TB". */
export function formatStorage(gb: number | null): string {
  if (gb == null || gb <= 0) return "—";
  if (gb >= 1024) return `${(gb / 1024).toFixed(1)} TB`;
  return `${Math.round(gb)} GB`;
}

/** Format a number as USD currency with no decimals, e.g. 1500 -> "$1,500". */
export function formatCurrency(n: number): string {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

/** Format minor units (cents, paise) in their own currency, e.g. 125000 -> "$1,250".
 *
 * Money reaches the operator console in whatever currency it was billed in — ASTRA sells
 * through Razorpay (INR) and Paddle (USD) — so the currency travels with the number
 * instead of being assumed. A null currency means there was nothing to denominate. */
export function formatMinor(cents: number | null | undefined, currency: string | null): string {
  if (cents == null) return "—";
  const amount = cents / 100;
  if (!currency) return amount.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return amount.toLocaleString(undefined, {
    style: "currency", currency, maximumFractionDigits: 0,
  });
}

/** A short money label for chart axes, e.g. 1_250_00 -> "$1.3k". Axis ticks have no room
 *  for grouped thousands, and an unreadable axis is worse than a rounded one. */
export function formatMinorCompact(cents: number, currency: string | null): string {
  const amount = cents / 100;
  const symbol = currency
    ? (0).toLocaleString(undefined, { style: "currency", currency, maximumFractionDigits: 0 })
        .replace(/[\d\s.,]/g, "")
    : "";
  const abs = Math.abs(amount);
  if (abs >= 1_000_000) return `${symbol}${(amount / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${symbol}${(amount / 1_000).toFixed(1)}k`;
  return `${symbol}${Math.round(amount)}`;
}

/** "2026-07" -> "Jul". Chart axes label the month; the year lives in the tooltip. */
export function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  if (!y || !m) return month;
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString(undefined, {
    month: "short", timeZone: "UTC",
  });
}

/** "2026-07" -> "July 2026", for tooltips where the full date is worth the space. */
export function monthLabelLong(month: string): string {
  const [y, m] = month.split("-").map(Number);
  if (!y || !m) return month;
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString(undefined, {
    month: "long", year: "numeric", timeZone: "UTC",
  });
}

/** Format an ISO timestamp as a short relative time, e.g. "5m ago", "3d ago". */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  const diffSec = Math.round((now.getTime() - then) / 1000);
  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return new Date(iso).toLocaleDateString();
}

const AUDIT_VERB_LABELS: Record<string, string> = {
  create: "Created",
  update: "Updated",
  delete: "Deleted",
  approve: "Approved",
  reject: "Rejected",
  login: "Logged in",
  logout: "Logged out",
  revoke: "Revoked",
  decommission: "Decommissioned",
  reactivate: "Reactivated",
  result: "Completed",
  read: "Read",
};

/** Turns a "resource.verb" audit action (e.g. "asset.create") into a human sentence fragment. */
export function humanizeAuditAction(action: string): string {
  const [resource, verbRaw] = action.split(".");
  const verb = verbRaw ?? resource;
  const verbLabel = AUDIT_VERB_LABELS[verb] ?? verb.charAt(0).toUpperCase() + verb.slice(1).replace(/_/g, " ");
  if (verb === "login" || verb === "logout") return verbLabel;
  const resourceLabel = resource.replace(/_/g, " ");
  return `${verbLabel} ${resourceLabel}`;
}
