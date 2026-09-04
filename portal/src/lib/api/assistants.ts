import { apiClient } from "./client";
import type {
  Assistant,
  AssistantDetail,
  AssistantTool,
  AssistantVersion,
  AssistantVersionInput,
} from "./types";

export const listAssistants = () =>
  apiClient.get<Assistant[]>("/assistants").then((r) => r.data);

export const getAssistant = (id: string) =>
  apiClient.get<AssistantDetail>(`/assistants/${id}`).then((r) => r.data);

/** The grantable tool catalogue, read from the schemas the engine advertises — never
 *  hardcoded here, or it goes stale the first time a tool is added. */
export const listAssistantTools = () =>
  apiClient.get<AssistantTool[]>("/assistants/tools").then((r) => r.data);

export const createAssistant = (name: string, description?: string) =>
  apiClient.post<Assistant>("/assistants", { name, description }).then((r) => r.data);

export const archiveAssistant = (id: string) =>
  apiClient.delete(`/assistants/${id}`).then((r) => r.data);

/** Always creates a DRAFT. There is no way to create something already live. */
export const createVersion = (id: string, body: AssistantVersionInput) =>
  apiClient.post<AssistantVersion>(`/assistants/${id}/versions`, body).then((r) => r.data);

/** Publishing an older version again is the rollback — there is no separate endpoint. */
export const publishVersion = (id: string, versionId: string) =>
  apiClient
    .post<Assistant>(`/assistants/${id}/versions/${versionId}/publish`)
    .then((r) => r.data);
