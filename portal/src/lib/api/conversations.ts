import { apiClient } from "./client";
import type { Conversation, Message } from "./types";

export const listConversations = () =>
  apiClient.get<Conversation[]>("/conversations").then((r) => r.data);

export const createConversation = (title: string) =>
  apiClient.post<Conversation>("/conversations", { title }).then((r) => r.data);

export const getMessages = (conversationId: string) =>
  apiClient.get<Message[]>(`/conversations/${conversationId}/messages`).then((r) => r.data);

export const sendMessage = (conversationId: string, content: string) =>
  apiClient
    .post<{ user_message: Message; assistant_message: Message }>(
      `/conversations/${conversationId}/messages`,
      { content }
    )
    .then((r) => r.data);
