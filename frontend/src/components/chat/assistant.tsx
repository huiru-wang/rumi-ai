"use client";

import React, { useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { updateWorkspaceThreadId, getWorkspace, listThreadMessages, type ThreadMessage } from "@/lib/api";

const LANGGRAPH_API_URL =
  process.env.NEXT_PUBLIC_LANGGRAPH_API_URL || "http://localhost:2024";
// Number of *turns* to load per page (a turn = 1 human message + all following AI/tool messages)
const MESSAGE_HISTORY_LIMIT = 3;

// --- External command (for programmatic pill injection from parent components) ---

export interface ExternalCommand {
  command: string;
  label: string;
  icon: ReactNode;
  subtitle?: string;
  metadata?: Record<string, string>;
}

// --- Split contexts: control vs messages ---
// Splitting prevents ChatInput / InterruptBlock from re-rendering on every message update.

interface StreamControlValue {
  isLoading: boolean;
  interrupt: { value?: unknown } | undefined;
  submit: (content: string) => void;
  stop: () => void;
  error: Error | null;
  loadOlderMessages: () => Promise<void>;
  hasOlderMessages: boolean;
  isLoadingOlderMessages: boolean;
  externalCommand: ExternalCommand | null;
  onExternalCommandConsumed?: () => void;
  threadId: string | null;
}

interface MessageContextValue {
  messages: any[];
}

const StreamControlContext = React.createContext<StreamControlValue>({
  isLoading: false,
  interrupt: undefined,
  submit: () => { },
  stop: () => { },
  error: null,
  loadOlderMessages: async () => { },
  hasOlderMessages: false,
  isLoadingOlderMessages: false,
  externalCommand: null,
  threadId: null,
});

const MessageContext = React.createContext<MessageContextValue>({ messages: [] });

/** For control-only consumers (ChatInput, InterruptBlock) — does NOT re-render on message changes. */
export function useStreamContext() {
  return useContext(StreamControlContext);
}

/** For message list consumers — re-renders on throttled message updates. */
export function useMessageContext() {
  return useContext(MessageContext);
}

// --- Resume context (for interrupt forms) ---

const ResumeContext = React.createContext<
  (values: Record<string, string | string[]>) => Promise<void>
>(async () => { });
export function useResume() {
  return useContext(ResumeContext);
}

// --- Assistant ---

interface AssistantProps {
  workspaceId: string;
  pptStyle?: string;
  voiceId?: string;
  currentPptTaskId?: string;
  onPptTaskIdConsumed?: () => void;
  externalCommand?: ExternalCommand | null;
  onExternalCommandConsumed?: () => void;
  children: ReactNode;
}

export function Assistant({ workspaceId, pptStyle, voiceId, currentPptTaskId, onPptTaskIdConsumed, externalCommand, onExternalCommandConsumed, children }: AssistantProps) {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [historyMessages, setHistoryMessages] = useState<any[]>([]);
  const [historyNextCursor, setHistoryNextCursor] = useState<number | null>(null);
  const [isLoadingOlderMessages, setIsLoadingOlderMessages] = useState(false);
  const summarizedIds = useRef<Set<string>>(new Set());

  const loadHistoryMessages = useCallback(async (targetThreadId: string) => {
    const page = await listThreadMessages(targetThreadId, { limit: MESSAGE_HISTORY_LIMIT });
    setHistoryMessages(page.messages.map(toLangGraphMessage).filter((message) => !isHiddenMessage(message)));
    setHistoryNextCursor(page.next_cursor);
  }, []);

  const loadOlderMessages = useCallback(async () => {
    if (!threadId || !historyNextCursor || isLoadingOlderMessages) return;

    setIsLoadingOlderMessages(true);
    try {
      const page = await listThreadMessages(threadId, {
        limit: MESSAGE_HISTORY_LIMIT,
        before: historyNextCursor,
      });
      const olderMessages = page.messages
        .map(toLangGraphMessage)
        .filter((message) => !isHiddenMessage(message));
      setHistoryMessages((current) => mergeMessages(olderMessages, current));
      setHistoryNextCursor(page.next_cursor);
    } finally {
      setIsLoadingOlderMessages(false);
    }
  }, [historyNextCursor, isLoadingOlderMessages, threadId]);

  // Load threadId from server
  useEffect(() => {
    getWorkspace(workspaceId)
      .then((ws) => {
        if (ws.thread_id) setThreadId(ws.thread_id);
      })
      .catch(() => { });
  }, [workspaceId]);

  useEffect(() => {
    if (!threadId) {
      setHistoryMessages([]);
      setHistoryNextCursor(null);
      return;
    }
    let cancelled = false;
    loadHistoryMessages(threadId).catch(() => {
      if (!cancelled) {
        setHistoryMessages([]);
        setHistoryNextCursor(null);
      }
    });
    return () => { cancelled = true; };
  }, [threadId, loadHistoryMessages]);

  // Stable callbacks via refs — prevents useStream from seeing new references each render
  const threadIdRef = useRef(threadId);
  threadIdRef.current = threadId;
  const workspaceIdRef = useRef(workspaceId);
  workspaceIdRef.current = workspaceId;

  const handleThreadId = useCallback((newThreadId: string) => {
    if (newThreadId !== threadIdRef.current) {
      setThreadId(newThreadId);
      updateWorkspaceThreadId(workspaceIdRef.current, newThreadId).catch(() => { });
    }
  }, []);

  // Snapshot of stream messages for summarization diff (updated during render)
  const streamMessagesSnapshotRef = useRef<any[]>([]);

  const handleUpdateEvent = useCallback((data: unknown) => {
    const sumMsgs = getSummarizationMessages(data);
    if (!sumMsgs || sumMsgs.length < 2) return;

    for (const m of sumMsgs) {
      if (m.name === "summary" && m.type === "human") {
        summarizedIds.current.add(m.id ?? "");
      }
    }

    const firstRetained = sumMsgs
      .filter((m: any) => m.type !== "remove")
      .filter((m: any) => !isHiddenMessage(m))
      .map(messageIdentity)
      .find(Boolean);

    const current = [...streamMessagesSnapshotRef.current];
    const moved: any[] = [];
    for (const m of current) {
      if (firstRetained && messageIdentity(m) === firstRetained) break;
      if (!summarizedIds.current.has(m.id ?? "")) {
        moved.push(m);
      }
    }
    if (moved.length > 0) {
      setHistoryMessages((prev) => mergeMessages(prev, moved));
    }
  }, []);

  const stream = useStream({
    apiUrl: LANGGRAPH_API_URL,
    assistantId: "main_agent",
    threadId,
    onThreadId: handleThreadId,
    onUpdateEvent: handleUpdateEvent,
  });

  // Keep snapshot ref in sync (used by handleUpdateEvent callback)
  if (stream.messages.length >= streamMessagesSnapshotRef.current.length) {
    streamMessagesSnapshotRef.current = stream.messages;
  }

  // Auto-recover from stale threadId
  useEffect(() => {
    if (!stream.error) return;
    const msg =
      stream.error instanceof Error
        ? stream.error.message
        : String(stream.error);
    // CancelledError = 主动取消（组件卸载/stop()），属于预期行为，无需报错
    if (msg.includes("CancelledError")) return;
    console.error("[Assistant] stream error:", stream.error);
    if (
      msg.includes("404") ||
      msg.includes("not found") ||
      msg.includes("Thread")
    ) {
      setThreadId(null);
    }
  }, [stream.error]);

  // ─── RAF-throttled + reference-stabilized message display ───────────
  // stream.messages returns a NEW array (and new objects) on every access.
  // Without throttling, each streaming token triggers an expensive full-tree
  // re-render. We batch updates to ~60fps via requestAnimationFrame and
  // stabilize message references so React.memo in child components works.
  const [displayedMessages, setDisplayMessages] = useState<any[]>([]);
  const messageCacheRef = useRef<Map<string, any>>(new Map());
  const latestStreamRef = useRef<{ messages: any[]; isLoading: boolean }>({
    messages: [],
    isLoading: false,
  });
  latestStreamRef.current = { messages: stream.messages, isLoading: stream.isLoading };
  const rafIdRef = useRef<number | null>(null);

  useEffect(() => {
    const scheduleUpdate = () => {
      if (rafIdRef.current !== null) return;
      rafIdRef.current = requestAnimationFrame(() => {
        rafIdRef.current = null;
        const { messages: rawMsgs, isLoading: loading } = latestStreamRef.current;
        const cache = messageCacheRef.current;
        const sm = rawMsgs ?? [];

        // 1) Filter hidden
        const visible = sm.filter((m: any) => !isHiddenMessage(m));

        // 2) Stabilize references: cache by id + content length + tool_calls
        const stableMessages: any[] = [];
        for (const msg of visible) {
          const id = msg?.id || msg?.message_id || "";
          const len = typeof msg?.content === "string" ? msg.content.length : JSON.stringify(msg?.content ?? "").length;
          // Include tool_calls in cache key so that newly arrived tool calls
          // invalidate the cache and return the updated message reference.
          const tcs = Array.isArray(msg?.tool_calls) ? msg.tool_calls.length : 0;
          const tcIds = tcs > 0 ? `:${msg.tool_calls.map((tc: any) => tc?.id || tc?.name || "").join(",")}` : "";
          // Include args length fingerprint so that streaming arg updates
          // invalidate the cache and the UI shows real-time parameters.
          const tcArgsLen = tcs > 0 ? `:${msg.tool_calls.map((tc: any) => JSON.stringify(tc?.args ?? {}).length).join(",")}` : "";
          const key = `${id}|${len}|${tcs}${tcIds}${tcArgsLen}`;
          const cached = cache.get(key);
          if (cached) {
            stableMessages.push(cached);
          } else {
            cache.set(key, msg);
            stableMessages.push(msg);
          }
        }

        // 3) Filter against history (inline liveMessages)
        const historyKeys = new Set(historyMessages.map(messageKey));
        const live = stableMessages.filter((m: any) => !historyKeys.has(messageKey(m)));

        // 4) Merge history + live
        const merged = mergeMessages(historyMessages, live);

        // 5) Skip update if content is identical (avoids redundant render)
        setDisplayMessages((prev) => {
          if (
            prev.length === merged.length &&
            prev.every((m, i) => m === merged[i])
          ) {
            return prev;
          }
          return merged;
        });

        // Chain another RAF if stream is still active (ensures smooth 60fps)
        if (loading) {
          rafIdRef.current = requestAnimationFrame(() => {
            rafIdRef.current = null;
            scheduleUpdate();
          });
        }
      });
    };

    scheduleUpdate();

    // Force immediate sync when loading ends (don't wait for next RAF)
    if (!stream.isLoading) {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      const { messages: rawMsgs } = latestStreamRef.current;
      const sm = rawMsgs ?? [];
      const visible = sm.filter((m: any) => !isHiddenMessage(m));
      const historyKeys = new Set(historyMessages.map(messageKey));
      const live = visible.filter((m: any) => !historyKeys.has(messageKey(m)));
      setDisplayMessages(mergeMessages(historyMessages, live));
    }

    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.messages.length, stream.isLoading, historyMessages]);

  // ─── Stable submit / stop callbacks (prevent context value churn) ─────
  const streamRef = useRef(stream);
  streamRef.current = stream;
  const submitStateRef = useRef({ workspaceId, pptStyle, voiceId, currentPptTaskId, onPptTaskIdConsumed });
  submitStateRef.current = { workspaceId, pptStyle, voiceId, currentPptTaskId, onPptTaskIdConsumed };

  const stableSubmit = useCallback((content: string) => {
    const s = submitStateRef.current;
    streamRef.current.submit(
      {
        messages: [{ type: "human", content }],
        workspace_id: s.workspaceId,
        ppt_style: s.pptStyle || "",
        voice_id: s.voiceId || "",
        current_ppt_task_id: s.currentPptTaskId || "",
      },
      { config: { recursion_limit: 30 } },
    );
    if (s.currentPptTaskId) {
      s.onPptTaskIdConsumed?.();
    }
  }, []);

  const stableStop = useCallback(() => {
    streamRef.current.stop();
  }, []);

  const handleResume = useCallback(async (values: Record<string, string | string[]>) => {
    await streamRef.current.submit(null, { command: { resume: values } });
  }, []);

  // ─── Memoized context values (only re-render consumers when data actually changes) ─────
  const controlValue = useMemo<StreamControlValue>(() => {
    const streamErrorMsg = stream.error != null ? String(stream.error) : "";
    const isUserCancelled = streamErrorMsg.includes("CancelledError");
    return {
      isLoading: stream.isLoading,
      interrupt: stream.interrupt,
      submit: stableSubmit,
      stop: stableStop,
      // CancelledError = 用户主动中断，不视为错误，不传递 error UI
      error: isUserCancelled ? null : stream.error != null ? new Error(streamErrorMsg) : null,
      loadOlderMessages,
      hasOlderMessages: historyNextCursor !== null,
      isLoadingOlderMessages,
      externalCommand: externalCommand ?? null,
      onExternalCommandConsumed,
      threadId,
    };
  }, [
    stream.isLoading, stream.interrupt, stableSubmit, stableStop, stream.error,
    loadOlderMessages, historyNextCursor, isLoadingOlderMessages,
    externalCommand, onExternalCommandConsumed, threadId,
  ]);

  const messageValue = useMemo<MessageContextValue>(() => ({
    messages: displayedMessages,
  }), [displayedMessages]);

  return (
    <StreamControlContext.Provider value={controlValue}>
      <MessageContext.Provider value={messageValue}>
        <ResumeContext.Provider value={handleResume}>
          {children}
        </ResumeContext.Provider>
      </MessageContext.Provider>
    </StreamControlContext.Provider>
  );
}

function toLangGraphMessage(message: ThreadMessage) {
  return {
    id: message.message_id,
    _rowId: message.id, // database auto-increment id for stable ordering
    type: message.type || message.role,
    content: message.content,
    tool_calls: message.tool_calls ?? [],
    tool_call_id: message.tool_call_id ?? undefined,
    name: message.name ?? undefined,
    additional_kwargs: message.additional_kwargs ?? {},
    response_metadata: message.response_metadata ?? {},
  };
}

function messageKey(message: any): string {
  const type = message?._getType?.() || message?.type || message?.role || "message";
  const id = message?.id || message?.message_id;
  if (id) return `${type}:${id}`;
  return `${type}:${JSON.stringify(message?.content ?? "")}`;
}

function isHiddenMessage(message: any): boolean {
  // 1. name field check (most reliable)
  if (message?.name === "summary") return true;
  // 2. additional_kwargs check
  const kwargs = message?.additional_kwargs;
  if (kwargs?.message_hidden) return true;
  if (kwargs?.lc_source === "summarization") return true;
  // 3. content fallback
  const content = typeof message?.content === "string" ? message.content : "";
  if (content.startsWith("Here is a summary of the conversation to date:")) return true;
  return false;
}

const SUMMARIZATION_UPDATE_KEYS = new Set([
  "SummarizationMiddleware.before_model",
]);

function getSummarizationMessages(data: unknown): any[] | undefined {
  if (typeof data !== "object" || data === null) return undefined;
  for (const [key, update] of Object.entries(data)) {
    if (!SUMMARIZATION_UPDATE_KEYS.has(key)) continue;
    const messages = (update as any)?.messages;
    if (Array.isArray(messages)) return [...messages];
  }
  return undefined;
}

function messageIdentity(message: any): string | undefined {
  if (message?.tool_call_id) return `tool:${message.tool_call_id}`;
  if (message?.id) return `message:${message.id}`;
  return undefined;
}

function mergeMessages(history: any[], live: any[]) {
  const merged = [...history];
  const seen = new Set(history.map(messageKey));
  for (const message of live) {
    const key = messageKey(message);
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(message);
  }
  // Sort by database row id (_rowId) for stable chronological order.
  // History messages carry _rowId (auto-increment int); live stream messages
  // without _rowId are placed at the end (they are always the newest).
  merged.sort((a, b) => {
    const aId = typeof a._rowId === "number" ? a._rowId : Number.MAX_SAFE_INTEGER;
    const bId = typeof b._rowId === "number" ? b._rowId : Number.MAX_SAFE_INTEGER;
    if (aId !== bId) return aId - bId;
    // Both without _rowId: preserve insertion order (stable sort)
    return 0;
  });
  return merged;
}
