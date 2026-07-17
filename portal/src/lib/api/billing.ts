import { apiClient } from "./client";
import type { BillingProvider, BillingStatus } from "./types";

export const getBillingStatus = () =>
  apiClient.get<BillingStatus>("/billing/status").then((r) => r.data);

// Returns the chosen rail's hosted checkout/approval URL to redirect the browser to.
export const startCheckout = (quantity: number, provider?: BillingProvider) =>
  apiClient.post<{ url: string }>("/billing/checkout", { quantity, provider }).then((r) => r.data.url);

// Hosted management page (Paddle); Razorpay/PayPal have none — use cancelSubscription.
export const openBillingPortal = () =>
  apiClient.post<{ url: string }>("/billing/portal").then((r) => r.data.url);

export const cancelSubscription = () => apiClient.post("/billing/cancel").then((r) => r.data);

// Add or remove licenses on an existing subscription (Stripe prorates).
export const setLicenses = (count: number) =>
  apiClient
    .post<{ licenses: number; seats_used: number; detail: string }>("/billing/licenses", { count })
    .then((r) => r.data);
