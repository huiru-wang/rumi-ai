"use client";

import React, { useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import {
  updateWorkspaceThreadId,
  getWorkspace,
  listThreadHistoryRuns,
  type HistoryRun,
  type ThreadMessage,
} from "@/lib/api";
import {
  createMessageDebugSnapshot,
  selectLiveMessagesForDisplay,
  shouldUseLiveMessages,
} from "./message-display";
import type { DisplayRun } from "./thread/types";

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
  runs: DisplayRun[];
}

interface OptimisticHumanMessage {
  id: string;
  type: "human";
  content: string;
  _optimistic: true;
  pending: true;
}

type ChatHistoryRun = Omit<HistoryRun, "messages"> & { messages: any[] };

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

const MessageContext = React.createContext<MessageContextValue>({ messages: [], runs: [] });

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
  const [historyRuns, setHistoryRuns] = useState<ChatHistoryRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeRunMessages, setActiveRunMessages] = useState<any[]>([]);
  const [optimisticMessages, setOptimisticMessages] = useState<OptimisticHumanMessage[]>([]);
  const [historyNextCursor, setHistoryNextCursor] = useState<number | null>(null);
  const [isInitialHistoryLoading, setIsInitialHistoryLoading] = useState(false);
  const [isLoadingOlderMessages, setIsLoadingOlderMessages] = useState(false);
  const summarizedIds = useRef<Set<string>>(new Set());
  const restoredThreadRef = useRef<string | null>(null);

  const loadHistoryRuns = useCallback(async (targetThreadId: string) => {
    debugMessageLog("history-load-start", { threadId: targetThreadId });
    const page = await listThreadHistoryRuns(targetThreadId, { limit: MESSAGE_HISTORY_LIMIT });
    const runs = page.runs.map(toChatHistoryRun).filter((run) => run.messages.length > 0);
    const messages = flattenHistoryRuns(runs);
    debugMessageLog("history-load-success", {
      threadId: targetThreadId,
      runCount: runs.length,
      count: messages.length,
      last: summarizeMessageForLog(messages[messages.length - 1]),
      nextCursor: page.next_cursor,
    });
    setHistoryRuns(runs);
    setHistoryNextCursor(page.next_cursor);
  }, []);

  const loadOlderMessages = useCallback(async () => {
    if (!threadId || !historyNextCursor || isLoadingOlderMessages) return;

    setIsLoadingOlderMessages(true);
    try {
      const page = await listThreadHistoryRuns(threadId, {
        limit: MESSAGE_HISTORY_LIMIT,
        before: historyNextCursor,
      });
      const olderRuns = page.runs.map(toChatHistoryRun).filter((run) => run.messages.length > 0);
      setHistoryRuns((current) => mergeHistoryRuns(olderRuns, current));
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
      setHistoryRuns([]);
      setActiveRunId(null);
      setActiveRunMessages([]);
      restoredThreadRef.current = null;
      setHistoryNextCursor(null);
      setIsInitialHistoryLoading(false);
      return;
    }
    let cancelled = false;
    setIsInitialHistoryLoading(true);
    loadHistoryRuns(threadId)
      .catch(() => {
        if (!cancelled) {
          setHistoryRuns([]);
          setActiveRunId(null);
          setActiveRunMessages([]);
          setHistoryNextCursor(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsInitialHistoryLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [threadId, loadHistoryRuns]);

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
      setActiveRunMessages((prev) => mergeMessages(prev, moved));
    }
  }, []);

  const handleRunCreated = useCallback((meta: { run_id?: string; thread_id?: string }) => {
    if (meta.run_id) {
      setActiveRunId(meta.run_id);
      setActiveRunMessages([]);
    }
  }, []);

  const stream = useStream({
    apiUrl: LANGGRAPH_API_URL,
    assistantId: "main_agent",
    threadId,
    onThreadId: handleThreadId,
    onUpdateEvent: handleUpdateEvent,
    onCreated: handleRunCreated,
    reconnectOnMount: true,
  });

  // Keep snapshot ref in sync (used by handleUpdateEvent callback)
  if (stream.messages.length >= streamMessagesSnapshotRef.current.length) {
    streamMessagesSnapshotRef.current = stream.messages;
  }

  const joinedRunRef = useRef<string | null>(null);
  useEffect(() => {
    if (!threadId || stream.isLoading) return;
    if (restoredThreadRef.current === threadId) return;
    restoredThreadRef.current = threadId;
    let cancelled = false;
    stream.client.runs
      .list(threadId, { status: "running", limit: 1 })
      .then((runs) => {
        if (cancelled) return;
        const run = runs[0];
        if (!run || joinedRunRef.current === run.run_id) return;
        joinedRunRef.current = run.run_id;
        setActiveRunId(run.run_id);
        stream.joinStream(run.run_id).catch((error) => {
          debugMessageLog("active-run-join-error", {
            threadId,
            runId: run.run_id,
            error: error instanceof Error ? error.message : String(error),
          });
        });
      })
      .catch((error) => {
        debugMessageLog("active-run-list-error", {
          threadId,
          error: error instanceof Error ? error.message : String(error),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [threadId, stream.client, stream.isLoading, stream.joinStream]);

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
  const [displayedRuns, setDisplayRuns] = useState<DisplayRun[]>([]);
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
        const canUseLiveMessages = shouldUseLiveMessages({
          threadId,
          isInitialHistoryLoading,
        });
        const sm = canUseLiveMessages ? rawMsgs ?? [] : [];
        const historyMessages = flattenHistoryRuns(historyRuns);

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

        const liveMessages = selectLiveMessagesForDisplay({
          canUseLiveMessages,
          historyMessages,
          streamMessages: stableMessages,
          getMessageKey: messageKey,
        });

        setActiveRunMessages(liveMessages);
        const optimistic = filterConfirmedOptimisticMessages(optimisticMessages, stableMessages);
        const runs = buildDisplayedRuns({
          historyRuns,
          activeRunId,
          activeRunMessages: liveMessages,
          optimisticMessages: optimistic,
        });
        const merged = flattenDisplayRuns(runs);
        debugMessageSnapshotLog("display-raf", () =>
          createMessageDebugSnapshot({
            phase: "display-raf",
            threadId,
            isLoading: loading,
            historyMessages,
            streamMessages: stableMessages,
            liveMessages,
            displayedMessages: merged,
            optimisticMessages: optimistic,
            getMessageKey: messageKey,
          }),
        );

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
        setDisplayRuns(runs);

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
      const canUseLiveMessages = shouldUseLiveMessages({
        threadId,
        isInitialHistoryLoading,
      });
      const sm = canUseLiveMessages ? rawMsgs ?? [] : [];
      const historyMessages = flattenHistoryRuns(historyRuns);
      const visible = sm.filter((m: any) => !isHiddenMessage(m));
      const liveMessages = selectLiveMessagesForDisplay({
        canUseLiveMessages,
        historyMessages,
        streamMessages: visible,
        getMessageKey: messageKey,
      });
      setActiveRunMessages(liveMessages);
      const optimistic = filterConfirmedOptimisticMessages(optimisticMessages, visible);
      const runs = buildDisplayedRuns({
        historyRuns,
        activeRunId,
        activeRunMessages: liveMessages,
        optimisticMessages: optimistic,
      });
      const merged = flattenDisplayRuns(runs);
      debugMessageLog("display-immediate", () =>
        createMessageDebugSnapshot({
          phase: "display-immediate",
          threadId,
          isLoading: stream.isLoading,
          historyMessages,
          streamMessages: visible,
          liveMessages,
          displayedMessages: merged,
          optimisticMessages: optimistic,
          getMessageKey: messageKey,
        }),
      );
      setDisplayMessages(merged);
      setDisplayRuns(runs);
    }

    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.messages.length, stream.isLoading, historyRuns, activeRunId, optimisticMessages, threadId, isInitialHistoryLoading]);

  const wasLoadingRef = useRef(stream.isLoading);
  useEffect(() => {
    const wasLoading = wasLoadingRef.current;
    wasLoadingRef.current = stream.isLoading;
    if (!wasLoading || stream.isLoading) return;
    debugMessageLog("stream-loading-finished", {
      threadId,
      stream: {
        count: stream.messages.length,
        last: summarizeMessageForLog(stream.messages[stream.messages.length - 1]),
      },
      history: {
        count: flattenHistoryRuns(historyRuns).length,
        last: summarizeMessageForLog(flattenHistoryRuns(historyRuns).at(-1)),
      },
      displayed: {
        count: displayedMessages.length,
        last: summarizeMessageForLog(displayedMessages[displayedMessages.length - 1]),
      },
      error: stream.error instanceof Error ? stream.error.message : stream.error ? String(stream.error) : null,
    });
    if (threadId && !isUserCancelledError(stream.error)) {
      loadHistoryRuns(threadId).then(() => {
        setActiveRunId(null);
        setActiveRunMessages([]);
        setOptimisticMessages([]);
        joinedRunRef.current = null;
      }).catch((error) => {
        debugMessageLog("history-load-after-finish-error", {
          threadId,
          error: error instanceof Error ? error.message : String(error),
        });
      });
    }
  }, [stream.isLoading, stream.messages, historyRuns, displayedMessages, threadId, stream.error, loadHistoryRuns]);

  useEffect(() => {
    setOptimisticMessages((current) => {
      const next = filterConfirmedOptimisticMessages(current, stream.messages);
      return next.length === current.length ? current : next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.messages.length]);

  // ─── Stable submit / stop callbacks (prevent context value churn) ─────
  const streamRef = useRef(stream);
  streamRef.current = stream;
  const submitStateRef = useRef({ workspaceId, pptStyle, voiceId, currentPptTaskId, onPptTaskIdConsumed });
  submitStateRef.current = { workspaceId, pptStyle, voiceId, currentPptTaskId, onPptTaskIdConsumed };

  const stableSubmit = useCallback((content: string) => {
    const s = submitStateRef.current;
    const optimisticMessage = createOptimisticHumanMessage(content);
    debugMessageLog("submit", {
      threadId: threadIdRef.current,
      workspaceId: s.workspaceId,
      contentLength: content.length,
      optimisticId: optimisticMessage.id,
    });
    setOptimisticMessages((current) => [...current, optimisticMessage]);
    try {
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
    } catch (error) {
      setOptimisticMessages((current) =>
        current.filter((message) => message.id !== optimisticMessage.id),
      );
      throw error;
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
    const friendlyErrorMsg = stream.error != null ? getFriendlyStreamErrorMessage(stream.error) : "";
    return {
      isLoading: stream.isLoading,
      interrupt: stream.interrupt,
      submit: stableSubmit,
      stop: stableStop,
      // CancelledError = 用户主动中断，不视为错误，不传递 error UI
      error: isUserCancelled ? null : stream.error != null ? new Error(friendlyErrorMsg) : null,
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
    runs: displayedRuns,
  }), [displayedMessages, displayedRuns]);

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
    _runId: message.run_id,
    run_id: message.run_id,
    type: message.type || message.role,
    content: message.content,
    tool_calls: message.tool_calls ?? [],
    tool_call_id: message.tool_call_id ?? undefined,
    name: message.name ?? undefined,
    additional_kwargs: message.additional_kwargs ?? {},
    response_metadata: message.response_metadata ?? {},
  };
}

function toChatHistoryRun(run: HistoryRun): ChatHistoryRun {
  return {
    ...run,
    messages: run.messages
      .map(toLangGraphMessage)
      .filter((message) => !isHiddenMessage(message)),
  };
}

function flattenHistoryRuns(runs: ChatHistoryRun[]) {
  return runs.flatMap((run) => run.messages);
}

function historyRunKey(run: ChatHistoryRun) {
  return run.run_id ? `run:${run.run_id}` : `legacy:${run.first_row_id}`;
}

function mergeHistoryRuns(olderRuns: ChatHistoryRun[], currentRuns: ChatHistoryRun[]) {
  const seen = new Set<string>();
  const merged: ChatHistoryRun[] = [];
  for (const run of [...olderRuns, ...currentRuns]) {
    const key = historyRunKey(run);
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(run);
  }
  merged.sort((a, b) => a.first_row_id - b.first_row_id);
  return merged;
}

function buildDisplayedRuns({
  historyRuns,
  activeRunId,
  activeRunMessages,
  optimisticMessages,
}: {
  historyRuns: ChatHistoryRun[];
  activeRunId: string | null;
  activeRunMessages: any[];
  optimisticMessages: OptimisticHumanMessage[];
}): DisplayRun[] {
  const activeRawMessages = mergeMessages(activeRunMessages, optimisticMessages);
  const shouldPreferActiveRun = activeRunId != null && activeRawMessages.length > 0;
  const persistedRuns =
    !shouldPreferActiveRun
      ? historyRuns
      : historyRuns.filter((run) => run.run_id !== activeRunId);
  const displayRuns: DisplayRun[] = persistedRuns.map((run) => ({
    key: historyRunKey(run),
    run_id: run.run_id,
    status: "history",
    messages: run.messages,
  }));
  const persistedMessageKeys = new Set(
    persistedRuns.flatMap((run) => run.messages).map(messageKey),
  );
  const activeMessages = activeRawMessages.filter(
    (message) => !persistedMessageKeys.has(messageKey(message)),
  );
  if (activeMessages.length > 0) {
    displayRuns.push({
      key: activeRunId ? `active:${activeRunId}` : "active:pending",
      run_id: activeRunId,
      status: "active",
      messages: activeMessages,
    });
  }
  return displayRuns;
}

function flattenDisplayRuns(runs: DisplayRun[]) {
  return runs.flatMap((run) => run.messages);
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

function createOptimisticHumanMessage(content: string): OptimisticHumanMessage {
  return {
    id: `optimistic-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    type: "human",
    content,
    _optimistic: true,
    pending: true,
  };
}

function filterConfirmedOptimisticMessages(
  optimisticMessages: OptimisticHumanMessage[],
  streamMessages: any[],
) {
  if (optimisticMessages.length === 0) return optimisticMessages;
  const confirmedCounts = new Map<string, number>();
  for (const message of streamMessages) {
    if ((message?._getType?.() || message?.type || message?.role) !== "human") continue;
    if (typeof message?.content !== "string" || !message.content) continue;
    confirmedCounts.set(message.content, (confirmedCounts.get(message.content) ?? 0) + 1);
  }
  if (confirmedCounts.size === 0) return optimisticMessages;

  return optimisticMessages.filter((message) => {
    const confirmedCount = confirmedCounts.get(message.content) ?? 0;
    if (confirmedCount <= 0) return true;
    confirmedCounts.set(message.content, confirmedCount - 1);
    return false;
  });
}

function getFriendlyStreamErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  const lower = message.toLowerCase();

  if (lower.includes("authentication") || lower.includes("api key") || lower.includes("401")) {
    return "模型服务认证失败，请联系管理员检查 API Key 配置。";
  }

  if (lower.includes("quota") || lower.includes("billing") || lower.includes("insufficient")) {
    return "模型服务额度不足，请稍后重试或联系管理员检查额度。";
  }

  if (lower.includes("rate limit") || lower.includes("429")) {
    return "模型服务当前请求过于频繁，请稍后再试。";
  }

  if (lower.includes("timeout") || lower.includes("timed out")) {
    return "模型响应超时，请稍后重试。";
  }

  if (
    lower.includes("failed to fetch") ||
    lower.includes("network") ||
    lower.includes("connection") ||
    lower.includes("econnrefused")
  ) {
    return "无法连接对话服务，请确认 LangGraph 服务已启动后重试。";
  }

  if (lower.includes("404") || lower.includes("not found") || lower.includes("thread")) {
    return "当前会话已失效，请重新发送消息。";
  }

  return "对话服务暂时不可用，请稍后再试。";
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

function debugMessageLog(label: string, payload: unknown | (() => unknown)) {
  if (!isMessageDebugEnabled()) return;
  const value = typeof payload === "function" ? (payload as () => unknown)() : payload;
  console.debug(`[RumiMessages] ${label}`, value);
}

function debugMessageSnapshotLog(label: string, payload: () => any) {
  if (!isMessageDebugEnabled()) return;
  const value = payload();
  if (label === "display-raf" && value?.anchor?.reason !== "missing-history-anchor") return;
  console.debug(`[RumiMessages] ${label}`, value);
}

function isMessageDebugEnabled() {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem("rumi-debug-messages") === "1";
  } catch {
    return false;
  }
}

function summarizeMessageForLog(message: any) {
  if (!message) return undefined;
  const content = message?.content;
  return {
    type: message?._getType?.() || message?.type || message?.role || "message",
    id: message?.id || message?.message_id,
    rowId: message?._rowId,
    contentLength: typeof content === "string" ? content.length : JSON.stringify(content ?? "").length,
    toolCalls: Array.isArray(message?.tool_calls) ? message.tool_calls.length : 0,
    name: message?.name,
  };
}

function isUserCancelledError(error: unknown) {
  const message = error instanceof Error ? error.message : error ? String(error) : "";
  return message.includes("CancelledError");
}
