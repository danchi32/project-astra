import { apiClient } from "./client";
import type { Notification, Page, PageParams } from "./types";

export const listNotifications = (
  params: PageParams & { unread_only?: boolean } = {},
) => apiClient.get<Page<Notification>>("/notifications", { params }).then((r) => r.data);

export const getUnreadCount = () =>
  apiClient.get<{ unread_count: number }>("/notifications/unread-count").then((r) => r.data.unread_count);

export const markNotificationRead = (id: string) =>
  apiClient.post<Notification>(`/notifications/${id}/read`).then((r) => r.data);

export const markAllNotificationsRead = () =>
  apiClient.post<{ marked: number }>("/notifications/read-all").then((r) => r.data);
