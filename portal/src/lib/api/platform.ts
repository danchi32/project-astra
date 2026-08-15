import { apiClient } from "./client";
import type {
  Asset, Device, GlobalFix, HelpArticleAdmin, KnowledgeArticle, OrganizationAdmin,
  PlatformAnalytics, PlatformAuditEntry, PlatformBilling,
  PlatformOverview, PlatformReports,
  RemediationActionOption, RemediationTask, SubscriptionStatus, User,
  Page, PageParams, Invoice, BillingProfile,
  SupportQueue, SupportRequestDetail, SupportRequestPriority, SupportRequestStatus,
  SupportRequestSummary,
} from "./types";

export const getPlatformOverview = () =>
  apiClient.get<PlatformOverview>("/platform/overview").then((r) => r.data);

// Platform-wide revenue rollup — MRR/ARR, provider mix, per-org economics.
export const getPlatformBilling = () =>
  apiClient.get<PlatformBilling>("/platform/billing").then((r) => r.data);

// Revenue history from invoices + per-customer health scoring. Distinct from /reports:
// this is the "where is this going" layer, not the "what is true now" one.
export const getPlatformAnalytics = () =>
  apiClient.get<PlatformAnalytics>("/platform/analytics").then((r) => r.data);

// Cross-org analytics — growth, self-healing outcomes, fleet, AI volume.
export const getPlatformReports = () =>
  apiClient.get<PlatformReports>("/platform/reports").then((r) => r.data);

// The operator's own action trail across all orgs.
export const getPlatformAudit = (limit = 100) =>
  apiClient.get<PlatformAuditEntry[]>(`/platform/audit?limit=${limit}`).then((r) => r.data);

// Operator provisions a new customer org + its first admin (initial password set here).
export const createOrganizationAsAdmin = (data: {
  organization_name: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
}) => apiClient.post<OrganizationAdmin>("/platform/organizations", data).then((r) => r.data);

// Mint a read-only token to browse an org's full portal, then enter view-as mode.
export const createViewToken = (id: string) =>
  apiClient
    .post<{ access_token: string; org_id: string; org_name: string }>(`/platform/organizations/${id}/view-token`)
    .then((r) => r.data);

export const listOrganizations = (
  params: PageParams & {
    q?: string; plan?: string; subscription_status?: string; country?: string;
    sort?: string; desc?: boolean;
  } = {},
) =>
  apiClient
    .get<Page<OrganizationAdmin>>("/platform/organizations", { params })
    .then((r) => r.data);

/** Billing history across every organization, for the operator console. */
export const getPlatformInvoices = (
  params: PageParams & {
    org_id?: string; q?: string; status?: string[];
    issued_from?: string; issued_to?: string; sort?: string; desc?: boolean;
  } = {},
) =>
  apiClient
    .get<Page<Invoice>>("/platform/invoices", { params, paramsSerializer: { indexes: null } })
    .then((r) => r.data);

/** An organization's billing and tax details — read-only for the operator. The customer
 *  owns their own legal identity; an operator editing it silently is how a wrong tax number
 *  reaches an invoice with nobody able to say who typed it. */
export const getOrgBillingProfile = (id: string) =>
  apiClient.get<BillingProfile>(`/platform/organizations/${id}/billing-profile`).then((r) => r.data);

export const getOrganization = (id: string) =>
  apiClient.get<OrganizationAdmin>(`/platform/organizations/${id}`).then((r) => r.data);

export const getOrgUsers = (id: string) =>
  apiClient.get<User[]>(`/platform/organizations/${id}/users`).then((r) => r.data);

export const getOrgDevices = (id: string) =>
  apiClient.get<Device[]>(`/platform/organizations/${id}/devices`).then((r) => r.data);

export const getOrgRemediation = (id: string) =>
  apiClient.get<RemediationTask[]>(`/platform/organizations/${id}/remediation`).then((r) => r.data);

export const getOrgAssets = (id: string) =>
  apiClient.get<Asset[]>(`/platform/organizations/${id}/assets`).then((r) => r.data);

// ── Support queue: customers asking ASTRA itself for help ─────────────────

export const getSupportQueue = (params: {
  request_status?: SupportRequestStatus; org_id?: string;
} = {}) => apiClient.get<SupportQueue>("/platform/support-requests", { params }).then((r) => r.data);

export const getPlatformSupportRequest = (id: string) =>
  apiClient.get<SupportRequestDetail>(`/platform/support-requests/${id}`).then((r) => r.data);

/** Replying notifies the customer and hands the thread back to them. */
export const replyAsOperator = (id: string, body: string) =>
  apiClient
    .post<SupportRequestDetail>(`/platform/support-requests/${id}/replies`, { body })
    .then((r) => r.data);

export const updateSupportRequest = (
  id: string,
  data: { status?: SupportRequestStatus; priority?: SupportRequestPriority },
) =>
  apiClient
    .patch<SupportRequestSummary>(`/platform/support-requests/${id}`, data)
    .then((r) => r.data);

// Global problem→solution knowledge applied to every organization. The same rows are
// ASTRA's customer-facing help articles when they carry a category or an error code.
export const listGlobalKnowledge = () =>
  apiClient.get<HelpArticleAdmin[]>("/platform/knowledge").then((r) => r.data);

export const createGlobalKnowledge = (data: {
  title: string;
  content: string;
  help_category?: string | null;
  error_code?: string | null;
}) => apiClient.post<HelpArticleAdmin>("/platform/knowledge", data).then((r) => r.data);

/** Partial edit. Sending a key as null clears it; omitting it leaves it alone — which is
 *  why callers must not spread a whole form object in here. */
export const updateGlobalKnowledge = (
  id: string,
  data: Partial<{
    title: string;
    content: string;
    help_category: string | null;
    error_code: string | null;
    published: boolean;
  }>,
) => apiClient.patch<HelpArticleAdmin>(`/platform/knowledge/${id}`, data).then((r) => r.data);

export const deleteGlobalKnowledge = (id: string) =>
  apiClient.delete(`/platform/knowledge/${id}`).then((r) => r.data);

// Global auto-apply fixes: problem → remediation action, applied for every org.
export const listRemediationActions = () =>
  apiClient.get<RemediationActionOption[]>("/platform/remediation-actions").then((r) => r.data);

export const listGlobalFixes = () =>
  apiClient.get<GlobalFix[]>("/platform/fixes").then((r) => r.data);

export const createGlobalFix = (data: {
  problem: string;
  action_id: string;
  process_name?: string;
  service_name?: string;
}) => apiClient.post<GlobalFix>("/platform/fixes", data).then((r) => r.data);

export const deleteGlobalFix = (id: string) =>
  apiClient.delete(`/platform/fixes/${id}`).then((r) => r.data);

export const updateOrganization = (
  id: string,
  data: Partial<{
    plan: string;
    subscription_status: SubscriptionStatus;
    trial_ends_at: string | null;
    current_period_end: string | null;
    extend_trial_days: number;
    ai_pro: boolean;
    entitlement_overrides: Record<string, boolean>;
  }>
) => apiClient.patch<OrganizationAdmin>(`/platform/organizations/${id}`, data).then((r) => r.data);

export const deleteOrganization = (id: string) =>
  apiClient.delete(`/platform/organizations/${id}`).then((r) => r.data);

// Operator-set bulk discount (percentage) applied to an org's subscription.
export const setOrgDiscount = (id: string, percent: number) =>
  apiClient.post<OrganizationAdmin>(`/platform/organizations/${id}/discount`, { percent }).then((r) => r.data);

export const clearOrgDiscount = (id: string) =>
  apiClient.delete<OrganizationAdmin>(`/platform/organizations/${id}/discount`).then((r) => r.data);
