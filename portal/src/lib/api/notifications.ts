import { apiClient } from "./client";
import type { Notification } from "./types";

export const listNotifications = (unreadOnly = false) =>
  apiClient
    .get<Notification[]>("/notifications", { params: { unread_only: unreadOnly } })
    .then((r) => r.data);

export const getUnreadCount = () =>
  apiClient.get<{ unread_count: number }>("/notifications/unread-count").then((r) => r.data.unread_count);

export const markNotificationRead = (id: string) =>
  apiClient.post<Notification>(`/notifications/${id}/read`).then((r) => r.data);

export const markAllNotificationsRead = () =>
  apiClient.post<{ marked: number }>("/notifications/read-all").then((r) => r.data);
