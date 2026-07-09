import { apiClient } from "./client";
import type { KnowledgeArticle } from "./types";

export const listArticles = () =>
  apiClient.get<KnowledgeArticle[]>("/knowledge").then((r) => r.data);

export const createArticle = (title: string, content: string) =>
  apiClient.post<KnowledgeArticle>("/knowledge", { title, content }).then((r) => r.data);

export const deleteArticle = (id: string) =>
  apiClient.delete(`/knowledge/${id}`).then((r) => r.data);
