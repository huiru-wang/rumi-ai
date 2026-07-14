const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const GENERIC_API_ERROR = "服务暂时不可用，请稍后重试。";
const FILE_LOAD_ERROR = "文件加载失败，请稍后重试。";
const FILE_DOWNLOAD_ERROR = "文件下载失败，请稍后重试。";
const UPLOAD_ERROR = "上传失败，请稍后重试。";

/**
 * Unified API response envelope.
 * All business endpoints return HTTP 200 with this structure.
 */
interface ApiResponse<T = unknown> {
  data: T;
  code: number;
  message: string;
  error?: BusinessErrorPayload;
}

export interface BusinessErrorPayload {
  code: number;
  message: string;
  type: string;
  retryable: boolean;
  stage?: string;
}

export class ApiError extends Error {
  code: number;
  error: BusinessErrorPayload;

  constructor(code: number, message: string, error?: BusinessErrorPayload) {
    super(message || `API error: code ${code}`);
    this.name = "ApiError";
    this.code = code;
    this.error = error ?? {
      code,
      message: message || "服务暂时不可用，请稍后重试。",
      type: "legacy_api_error",
      retryable: false,
    };
  }
}

export function getBusinessErrorMessage(
  error: unknown,
  fallback = "服务暂时不可用，请稍后重试。",
): string {
  if (typeof error === "string") return error || fallback;
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message) return message;
  }
  return fallback;
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const method = options?.method || "GET";
  console.log(`[API] ${method} ${path}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...options?.headers },
      ...options,
    });
  } catch (error) {
    console.error(`[API] ${method} ${path} network error:`, error);
    throw new Error(GENERIC_API_ERROR);
  }
  if (!response.ok) {
    console.error(`[API] ${method} ${path} http error: status=${response.status}`);
    throw new Error(GENERIC_API_ERROR);
  }
  let body: ApiResponse<T>;
  try {
    body = await response.json();
  } catch (error) {
    console.error(`[API] ${method} ${path} invalid json:`, error);
    throw new Error(GENERIC_API_ERROR);
  }
  if (body.code !== 0) {
    console.error(`[API] ${method} ${path} biz error: code=${body.code} message=${body.message}`);
    throw new ApiError(body.code, body.message, body.error);
  }
  console.log(`[API] ${method} ${path} →`, Array.isArray(body.data) ? `${body.data.length} items` : body.data);
  return body.data;
}

function getWebOrigin(): string {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "http://localhost:3000";
}

function toApiUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl;
  }
  return `${API_BASE}${pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`}`;
}

function toWebUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl;
  }
  return `${getWebOrigin()}${pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`}`;
}

// --- Workspace ---

export interface InviteClaim {
  user_id: string;
  nickname: string;
}

export function claimInvite(code: string): Promise<InviteClaim> {
  return request("/api/invites/claim", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

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
  run_id: string | null;
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

export interface HistoryRun {
  run_id: string | null;
  thread_id: string;
  workspace_id: string | null;
  first_row_id: number;
  last_row_id: number;
  created_at: string;
  updated_at: string;
  messages: ThreadMessage[];
}

export interface HistoryRunsPage {
  runs: HistoryRun[];
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

/**
 * List thread history grouped by LangGraph run.
 * ``limit`` controls the number of history runs. ``before`` is the oldest
 * loaded HistoryRun.first_row_id.
 */
export function listThreadHistoryRuns(
  threadId: string,
  options: { limit?: number; before?: number | null } = {}
): Promise<HistoryRunsPage> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 10));
  if (options.before) params.set("before", String(options.before));
  return request(`/api/threads/${encodeURIComponent(threadId)}/history-runs?${params.toString()}`);
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
  progress?: DocumentProgress;
  created_at: string;
  updated_at: string;
}

export interface DocumentProgress {
  stage: string;
  stage_label: string;
  percent: number;
  message: string;
  current: number;
  total: number;
  estimated_minutes?: number;
  estimate_note?: string;
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
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE}/api/workspaces/${workspaceId}/documents`,
      { method: "POST", body: formData }
    );
  } catch (error) {
    console.error("[API] document upload network error:", error);
    throw new Error(UPLOAD_ERROR);
  }
  if (!response.ok) {
    console.error(`[API] document upload http error: status=${response.status}`);
    throw new Error(UPLOAD_ERROR);
  }
  let body: ApiResponse<Document>;
  try {
    body = await response.json();
  } catch (error) {
    console.error("[API] document upload invalid json:", error);
    throw new Error(UPLOAD_ERROR);
  }
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
  result_data: Record<string, unknown> | string | null;
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

export interface TaskShareInfo {
  enabled: boolean;
  token: string | null;
  path?: string | null;
  url: string | null;
  type: string | null;
}

function withShareUrl(share: TaskShareInfo): TaskShareInfo {
  if (!share.enabled || !share.token) {
    return { ...share, url: null };
  }
  return {
    ...share,
    path: share.path || `/share/${encodeURIComponent(share.token)}`,
    url: toWebUrl(share.path || `/share/${encodeURIComponent(share.token)}`),
  };
}

export async function getTaskShare(taskId: string): Promise<TaskShareInfo> {
  return withShareUrl(await request(`/api/tasks/${encodeURIComponent(taskId)}/share`));
}

export async function createTaskShare(taskId: string): Promise<TaskShareInfo> {
  return withShareUrl(
    await request(`/api/tasks/${encodeURIComponent(taskId)}/share`, {
      method: "POST",
    })
  );
}

export function deleteTaskShare(taskId: string): Promise<{ ok: boolean; revoked: number }> {
  return request(`/api/tasks/${encodeURIComponent(taskId)}/share`, {
    method: "DELETE",
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
    if (!res.ok) {
      console.error(`[API] style extraction upload http error: status=${res.status}`);
      throw new Error(UPLOAD_ERROR);
    }
    let body: ApiResponse<Task>;
    try {
      body = await res.json();
    } catch (error) {
      console.error("[API] style extraction upload invalid json:", error);
      throw new Error(UPLOAD_ERROR);
    }
    if (body.code !== 0) {
      throw new ApiError(body.code, body.message);
    }
    return body.data;
  }).catch((error) => {
    if (error instanceof ApiError) throw error;
    if (error instanceof Error && error.message === UPLOAD_ERROR) throw error;
    console.error("[API] style extraction upload network error:", error);
    throw new Error(UPLOAD_ERROR);
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

/** Build a URL for PPT task preview by task id. */
export function getTaskPreviewUrl(taskId: string, thumb = false): string {
  const qs = thumb ? `?thumb=1` : "";
  return `${API_BASE}/api/tasks/${encodeURIComponent(taskId)}/preview${qs}`;
}

/** Build a URL for a narration slide audio by task id and slide number. */
export function getTaskAudioUrl(taskId: string, slideNumber: number): string {
  return `${API_BASE}/api/tasks/${encodeURIComponent(taskId)}/audio/${encodeURIComponent(String(slideNumber))}`;
}

/** Build a URL for PPT style preview by style id. */
export function getPptStylePreviewUrl(styleId: string, thumb = false): string {
  const qs = thumb ? `?thumb=1` : "";
  return `${API_BASE}/api/ppt-styles/${encodeURIComponent(styleId)}/preview${qs}`;
}

/** Build a URL for completed style extraction task preview by task id. */
export function getStyleExtractionPreviewUrl(taskId: string, thumb = false): string {
  const qs = thumb ? `?thumb=1` : "";
  return `${API_BASE}/api/tasks/${encodeURIComponent(taskId)}/style-preview${qs}`;
}

export interface ShareSlide {
  number: number;
  title?: string;
  text?: string;
  has_audio: boolean;
  audio_url?: string;
}

export interface ShareDetail {
  type: "ppt" | "narration";
  title: string;
  ppt: {
    title: string;
    html_url: string;
  };
  narration?: {
    title: string;
    voice_name: string;
    slides: ShareSlide[];
  };
}

function withShareDetailUrls(detail: ShareDetail): ShareDetail {
  return {
    ...detail,
    ppt: {
      ...detail.ppt,
      html_url: toApiUrl(detail.ppt.html_url),
    },
    narration: detail.narration
      ? {
          ...detail.narration,
          slides: detail.narration.slides.map((slide) => ({
            ...slide,
            audio_url: slide.audio_url ? toApiUrl(slide.audio_url) : slide.audio_url,
          })),
        }
      : detail.narration,
  };
}

export async function getShareDetail(token: string): Promise<ShareDetail> {
  return withShareDetailUrls(await request(`/api/shares/${encodeURIComponent(token)}`));
}

/**
 * Trigger a real browser download for a task's output file.
 * Backend resolves the file path from the task record — frontend only needs taskId.
 * Uses fetch + Blob URL to work across origins.
 */
export async function downloadTaskFile(taskId: string, filename = "download"): Promise<void> {
  const url = `${API_BASE}/api/tasks/${taskId}/download?t=${Date.now()}`;
  let res: Response;
  try {
    res = await fetch(url);
  } catch (error) {
    console.error("[API] download network error:", error);
    throw new Error(FILE_DOWNLOAD_ERROR);
  }
  if (!res.ok) {
    console.error(`[API] download http error: status=${res.status}`);
    throw new Error(FILE_DOWNLOAD_ERROR);
  }
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
  let response: Response;
  try {
    response = await fetch(fileUrl);
  } catch (error) {
    console.error("[API] file fetch network error:", error);
    throw new Error(FILE_LOAD_ERROR);
  }
  if (!response.ok) {
    console.error(`[API] file fetch http error: status=${response.status}`);
    throw new Error(FILE_LOAD_ERROR);
  }
  return response.text();
}

// --- Admin ---

export interface AdminTrendPoint {
  date: string;
  active_users: number;
  human_messages: number;
  documents: number;
  completed_ppts: number;
  completed_narrations: number;
}

export interface AdminDashboard {
  range_days: 7 | 30;
  kpis: {
    total_users: number;
    active_today: number;
    active_7d: number;
    core_conversion_rate: number;
    completed_ppts: number;
    completed_narrations: number;
  };
  trends: AdminTrendPoint[];
}

export interface AdminUserSummary {
  user_id: string;
  nickname: string;
  claimed_at: string;
  last_claimed_at: string;
  last_active_at: string | null;
  enabled: boolean;
  workspace_count: number;
  document_count: number;
  message_count: number;
  ppt_count: number;
  narration_count: number;
  share_count: number;
}

export interface AdminInvite {
  id: string;
  user_id: string;
  nickname: string;
  enabled: boolean;
  expires_at: string | null;
  claimed_at: string | null;
  last_claimed_at: string | null;
  claim_count: number;
  code_masked: string;
  created_at: string;
}

export interface AdminPage<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

async function adminRequest<T>(
  path: string,
  token: string | null,
  options?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options?.headers,
      },
    });
  } catch {
    throw new Error(GENERIC_API_ERROR);
  }
  let body: (ApiResponse<T> & { detail?: string }) | null = null;
  try {
    body = await response.json();
  } catch {
    // The status fallback below is safe and user-facing.
  }
  if (!response.ok) {
    throw new Error(body?.detail || (response.status === 401 ? "请重新登录管理后台" : GENERIC_API_ERROR));
  }
  if (!body || body.code !== 0) {
    throw new Error(body?.message || GENERIC_API_ERROR);
  }
  return body.data;
}

export function loginAdmin(username: string, password: string): Promise<{ token: string; username: string }> {
  return adminRequest("/api/admin/session", null, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getAdminDashboard(token: string, days: 7 | 30): Promise<AdminDashboard> {
  return adminRequest(`/api/admin/dashboard?days=${days}`, token);
}

export function listAdminUsers(
  token: string,
  options: { page?: number; pageSize?: number; keyword?: string } = {},
): Promise<AdminPage<AdminUserSummary>> {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    page_size: String(options.pageSize ?? 20),
    keyword: options.keyword ?? "",
  });
  return adminRequest(`/api/admin/users?${params}`, token);
}

export function listAdminInvites(
  token: string,
  page = 1,
): Promise<AdminPage<AdminInvite>> {
  return adminRequest(`/api/admin/invites?page=${page}&page_size=20`, token);
}

export function createAdminInvite(
  token: string,
  nickname: string,
  expiresAt: string | null,
): Promise<AdminInvite & { code: string }> {
  return adminRequest("/api/admin/invites", token, {
    method: "POST",
    body: JSON.stringify({ nickname, expires_at: expiresAt }),
  });
}

export function updateAdminInvite(
  token: string,
  inviteId: string,
  enabled: boolean,
): Promise<AdminInvite> {
  return adminRequest(`/api/admin/invites/${encodeURIComponent(inviteId)}`, token, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });
}
