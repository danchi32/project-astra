import { apiClient } from "./client";
import type {
  HelpArticle, HelpArticleSummary, SupportRequestDetail, SupportRequestPriority,
  SupportRequestStatus, SupportRequestSummary,
} from "./types";

// ── Help centre ───────────────────────────────────────────────────────────
// ASTRA's own support documentation. Every organization sees the same articles; the
// server serves only published, global ones.

export const searchHelpArticles = (params: {
  q?: string; category?: string; error_code?: string;
} = {}) =>
  apiClient.get<HelpArticleSummary[]>("/help/articles", { params }).then((r) => r.data);

export const getHelpArticle = (id: string) =>
  apiClient.get<HelpArticle>(`/help/articles/${id}`).then((r) => r.data);

/** Categories that actually have something published in them — an empty section in a
 *  browse UI reads as a broken page. */
export const getHelpCategories = () =>
  apiClient.get<Record<string, number>>("/help/categories").then((r) => r.data);

/** The full vocabulary, including empty sections — for the operator's authoring form. */
export const getHelpCategoryOptions = () =>
  apiClient.get<string[]>("/help/category-options").then((r) => r.data);

// ── Support requests ──────────────────────────────────────────────────────

export const listSupportRequests = (status?: SupportRequestStatus) =>
  apiClient
    .get<SupportRequestSummary[]>("/support/requests", {
      params: status ? { request_status: status } : {},
    })
    .then((r) => r.data);

export const getSupportRequest = (id: string) =>
  apiClient.get<SupportRequestDetail>(`/support/requests/${id}`).then((r) => r.data);

/** Diagnostics are captured server-side — nothing about the fleet is sent from here. */
export const createSupportRequest = (data: {
  subject: string;
  body: string;
  category?: string | null;
  priority?: SupportRequestPriority;
}) => apiClient.post<SupportRequestDetail>("/support/requests", data).then((r) => r.data);

export const replyToSupportRequest = (id: string, body: string) =>
  apiClient
    .post<SupportRequestDetail>(`/support/requests/${id}/replies`, { body })
    .then((r) => r.data);
