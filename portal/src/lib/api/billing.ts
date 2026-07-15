import { apiClient } from "./client";
import type { BillingStatus } from "./types";

export const getBillingStatus = () =>
  apiClient.get<BillingStatus>("/billing/status").then((r) => r.data);

// Returns a Stripe-hosted Checkout URL to redirect the browser to.
export const startCheckout = () =>
  apiClient.post<{ url: string }>("/billing/checkout").then((r) => r.data.url);

// Returns a Stripe Billing Portal URL (manage card / plan / cancel).
export const openBillingPortal = () =>
  apiClient.post<{ url: string }>("/billing/portal").then((r) => r.data.url);

export const syncSeats = () =>
  apiClient
    .post<{ synced: boolean; seat_count: number; detail: string }>("/billing/sync-seats")
    .then((r) => r.data);
