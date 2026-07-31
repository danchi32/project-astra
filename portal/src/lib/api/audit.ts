import { apiClient } from "./client";
import type { AuditLog, Page, PageParams } from "./types";

export const listAuditLogs = (params: PageParams = {}) =>
  apiClient.get<Page<AuditLog>>("/audit-logs", { params }).then((r) => r.data);
