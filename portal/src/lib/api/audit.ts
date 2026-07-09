import { apiClient } from "./client";
import type { AuditLog } from "./types";

export const listAuditLogs = () =>
  apiClient.get<AuditLog[]>("/audit-logs").then((r) => r.data);
