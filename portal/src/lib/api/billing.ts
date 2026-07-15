import { apiClient } from "./client";
import type { BillingStatus } from "./types";

export const getBillingStatus = () =>
  apiClient.get<BillingStatus>("/billing/status").then((r) => r.data);

// Returns a Stripe-hosted Checkout URL to redirect the browser to.
export const startCheckout = (quantity: number) =>
  apiClient.post<{ url: string }>("/billing/checkout", { quantity }).then((r) => r.data.url);

// Returns a Stripe Billing Portal URL (manage card / plan / cancel).
export const openBillingPortal = () =>
  apiClient.post<{ url: string }>("/billing/portal").then((r) => r.data.url);

// Add or remove licenses on an existing subscription (Stripe prorates).
export const setLicenses = (count: number) =>
  apiClient
    .post<{ licenses: number; seats_used: number; detail: string }>("/billing/licenses", { count })
    .then((r) => r.data);
