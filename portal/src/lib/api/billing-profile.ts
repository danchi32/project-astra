import { apiClient } from "./client";
import type { BillingProfile, Invoice, Page, PageParams } from "./types";

export const getBillingProfile = () =>
  apiClient.get<BillingProfile>("/billing/profile").then((r) => r.data);

export const updateBillingProfile = (data: Partial<BillingProfile>) =>
  apiClient.patch<BillingProfile>("/billing/profile", data).then((r) => r.data);

/** This organization's own billing history. Scoped to the caller's org by the token — there
 *  is no id in the request to tamper with. */
export const listInvoices = (
  params: PageParams & {
    q?: string; status?: string[]; issued_from?: string; issued_to?: string;
    sort?: string; desc?: boolean;
  } = {},
) =>
  apiClient
    .get<Page<Invoice>>("/billing/invoices", { params, paramsSerializer: { indexes: null } })
    .then((r) => r.data);
