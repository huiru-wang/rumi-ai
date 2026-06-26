const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/**
 * Unified API response envelope.
 * All business endpoints return HTTP 200 with this structure.
 */
interface ApiResponse<T = unknown> {
  data: T;
  code: number;
  message: string;
}

export class ApiError extends Error {
  code: number;

  constructor(code: number, message: string) {
    super(message || `API error: code ${code}`);
    this.name = "ApiError";
    this.code = code;
  }
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const method = options?.method || "GET";
  console.log(`[API] ${method} ${path}`);
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  const body: ApiResponse<T> = await response.json();
  if (body.code !== 0) {
    console.error(`[API] ${method} ${path} biz error: code=${body.code} message=${body.message}`);
    throw new ApiError(body.code, body.message);
  }
  console.log(`[API] ${method} ${path} →`, Array.isArray(body.data) ? `${body.data.length} items` : body.data);
  return body.data;
}

// --- Workspace ---

export interface Workspace {
  id: string;
  user_id: string;
  name: string;
  thread_id: string | null;
  ext_data: Record<string, unknown>;
  created_at: string;
}

export function createWorkspace(
  userId: string,
  name: string
): Promise<Workspace> {
  return request("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, name }),
  });
}

export function listWorkspaces(userId: string): Promise<Workspace[]> {
  return request(`/api/workspaces?user_id=${encodeURIComponent(userId)}`);
}

export function getWorkspace(workspaceId: string): Promise<Workspace> {
  return request(`/api/workspaces/${workspaceId}`);
}

export function deleteWorkspace(workspaceId: string): Promise<void> {
  return request(`/api/workspaces/${workspaceId}`, { method: "DELETE" });
}

export function updateWorkspaceThreadId(workspaceId: string, threadId: string): Promise<{ ok: boolean }> {
  return request(`/api/workspaces/${workspaceId}/thread`, {
    method: "PATCH",
    body: JSON.stringify({ thread_id: threadId }),
  });
}

export function updateWorkspaceConfig(
  workspaceId: string,
  key: string,
  value: unknown
): Promise<{ ok: boolean; ext_data: Record<string, unknown> }> {
  return request(`/api/workspaces/${workspaceId}/config`, {
    method: "PATCH",
    body: JSON.stringify({ key, value }),
  });
}

// --- Messages ---

export interface ThreadMessage {
  id: number;
  thread_id: string;
  workspace_id: string | null;
  message_id: string;
  role: string;
  type: string;
  content: unknown;
  tool_calls: Array<{ id?: string | null; name?: string | null; args?: Record<string, unknown> }>;
  tool_call_id: string | null;
  name: string | null;
  additional_kwargs: Record<string, unknown>;
  response_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ThreadMessagesPage {
  messages: ThreadMessage[];
  next_cursor: number | null;
}

/**
 * List thread messages with turn-based pagination.
 * ``limit`` controls the number of *turns* (a turn = 1 human + following AI/tool messages).
 */
export function listThreadMessages(
  threadId: string,
  options: { limit?: number; before?: number | null } = {}
): Promise<ThreadMessagesPage> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 10));
  if (options.before) params.set("before", String(options.before));
  return request(`/api/threads/${encodeURIComponent(threadId)}/messages?${params.toString()}`);
}

export function getMessageDetail(
  threadId: string,
  messageId: string,
): Promise<ThreadMessage> {
  return request(
    `/api/threads/${encodeURIComponent(threadId)}/messages/${encodeURIComponent(messageId)}`,
  );
}

// --- Documents ---

export interface Document {
  id: string;
  workspace_id: string;
  filename: string;
  file_type: string;
  summary: string | null;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export type DocumentStatus =
  | "uploaded"
  | "processing"
  | "parsing"
  | "parsed"
  | "chunking"
  | "indexing"
  | "summarizing"
  | "ready"
  | "error";

export function listDocuments(workspaceId: string): Promise<Document[]> {
  return request(`/api/workspaces/${workspaceId}/documents`);
}

export async function uploadDocument(
  workspaceId: string,
  file: File
): Promise<Document> {
  console.log(`[API] POST /api/workspaces/${workspaceId}/documents file=${file.name} size=${file.size}`);
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(
    `${API_BASE}/api/workspaces/${workspaceId}/documents`,
    { method: "POST", body: formData }
  );
  const body: ApiResponse<Document> = await response.json();
  if (body.code !== 0) {
    throw new ApiError(body.code, body.message);
  }
  console.log(`[API] upload result: id=${body.data.id} status=${body.data.status}`);
  return body.data;
}

export function deleteDocument(
  workspaceId: string,
  docId: string
): Promise<void> {
  return request(`/api/workspaces/${workspaceId}/documents/${docId}`, {
    method: "DELETE",
  });
}

// --- Tasks ---

export interface Task {
  id: string;
  workspace_id: string;
  type: string;
  title: string | null;
  status: string;
  result_data: string | null;
  parent_task_id?: string | null;
  children?: Task[];
  created_at: string;
}

export function listTasks(workspaceId: string): Promise<Task[]> {
  return request(`/api/workspaces/${workspaceId}/tasks`);
}

export function deleteTask(workspaceId: string, taskId: string): Promise<{ ok: boolean }> {
  return request(`/api/workspaces/${workspaceId}/tasks/${taskId}`, {
    method: "DELETE",
  });
}

export function saveTaskFile(
  workspaceId: string,
  taskId: string,
  content: string
): Promise<{ ok: boolean }> {
  return request(`/api/workspaces/${workspaceId}/tasks/${taskId}/file`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

// --- PPT Styles ---

export interface PptStyleInfo {
  id: string;
  user_id: string;
  category: string;
  name: string;
  name_en: string;
  description: string;
  preview_path: string;
  created_at: string;
}

export function listPptStyles(userId: string): Promise<PptStyleInfo[]> {
  return request(`/api/ppt-styles?user_id=${encodeURIComponent(userId)}`);
}

export function deletePptStyle(styleId: string): Promise<{ ok: boolean }> {
  return request(`/api/ppt-styles/${styleId}`, { method: "DELETE" });
}

// --- Voices ---

export interface VoiceInfo {
  id: string;
  name: string;
  gender: string;
  trait: string;
  audio_url: string;
}

export function listVoices(): Promise<VoiceInfo[]> {
  return request("/api/voices");
}

// --- Style Extraction ---

export function submitStyleExtraction(
  workspaceId: string,
  file: File
): Promise<Task> {
  const formData = new FormData();
  formData.append("file", file);
  return fetch(
    `${API_BASE}/api/workspaces/${workspaceId}/style-extraction`,
    { method: "POST", body: formData }
  ).then(async (res) => {
    const body: ApiResponse<Task> = await res.json();
    if (body.code !== 0) {
      throw new ApiError(body.code, body.message);
    }
    return body.data;
  });
}

export function getTask(
  workspaceId: string,
  taskId: string
): Promise<Task> {
  return request(`/api/workspaces/${workspaceId}/tasks/${taskId}`);
}

export function deleteStyleExtraction(
  workspaceId: string,
  taskId: string
): Promise<{ ok: boolean }> {
  return request(`/api/workspaces/${workspaceId}/style-extraction/${taskId}`, {
    method: "DELETE",
  });
}

export function saveStyleFromExtraction(
  taskId: string,
  userId: string
): Promise<PptStyleInfo> {
  return request(`/api/style-extraction/${taskId}/save`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

// --- Files ---

/**
 * Encode each path segment individually while preserving `/` separators.
 * Required for `fetch()` which does NOT auto-encode URLs (unlike browser navigation).
 */
function encodeFilePath(filePath: string): string {
  return filePath.split("/").map(encodeURIComponent).join("/");
}

/** Build a URL for inline file preview (served with Content-Disposition: inline). */
export function getFileViewUrl(filePath: string, thumb = false): string {
  const qs = thumb ? `?thumb=1` : "";
  return `${API_BASE}/api/file-view/${encodeFilePath(filePath)}${qs}`;
}

/**
 * Trigger a real browser download for a task's output file.
 * Backend resolves the file path from the task record — frontend only needs taskId.
 * Uses fetch + Blob URL to work across origins.
 */
export async function downloadTaskFile(taskId: string, filename: string): Promise<void> {
  const url = `${API_BASE}/api/tasks/${taskId}/download?t=${Date.now()}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);
}

export async function fetchFileContent(fileUrl: string): Promise<string> {
  const response = await fetch(fileUrl);
  if (!response.ok) throw new Error(`Failed to fetch file: ${response.status}`);
  return response.text();
}
