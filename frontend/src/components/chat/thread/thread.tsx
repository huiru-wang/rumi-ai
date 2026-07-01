"use client";

import { useRef, useCallback, useLayoutEffect, useEffect } from "react";
import { useStreamContext, useMessageContext } from "../assistant";
import { isNearBottom, isStreamingContent, isHiddenMessage } from "./helpers";
import { EmptyState, TypingIndicator } from "./message-actions";
import { InterruptBlock } from "./interrupt-block";
import { ChatInput } from "./chat-input";
import { MessageList } from "./message-list";
import type { DisplayRun } from "./types";

// ============================================================
// Thread (root container — scroll management + layout)
// ============================================================

export function Thread({
  visibleMessages,
  visibleRuns,
  isLoading,
  interrupt,
}: {
  visibleMessages: any[];
  visibleRuns: DisplayRun[];
  isLoading: boolean;
  interrupt?: { value?: unknown };
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const {
    error,
    loadOlderMessages,
    hasOlderMessages,
    isLoadingOlderMessages,
  } = useStreamContext();
  const shouldStickToBottom = useRef(true);
  const historyPrependSnapshot = useRef<{ scrollHeight: number; scrollTop: number } | null>(null);
  const initialScrollDone = useRef(false);
  const hasMessages = visibleMessages.length > 0;

  // Reset initial scroll flag when messages clear (e.g. workspace switch)
  useEffect(() => {
    if (visibleMessages.length === 0) {
      initialScrollDone.current = false;
    }
  }, [visibleMessages.length]);

  // Derive a stable boolean for whether an interrupt form is present.
  const hasInterrupt = !!(interrupt && interrupt.value !== undefined);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const prependSnapshot = historyPrependSnapshot.current;
    if (prependSnapshot) {
      el.scrollTop =
        el.scrollHeight - prependSnapshot.scrollHeight + prependSnapshot.scrollTop;
      historyPrependSnapshot.current = null;
      return;
    }

    // First load: jump to bottom instantly so user always sees latest messages
    if (!initialScrollDone.current && visibleMessages.length > 0) {
      el.scrollTo({ top: el.scrollHeight, behavior: "instant" });
      initialScrollDone.current = true;
      return;
    }

    // When an interrupt form appears, always scroll to show it.
    if (hasInterrupt || shouldStickToBottom.current) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [visibleMessages.length, isLoading, hasInterrupt]);

  const handleScroll = useCallback(async () => {
    const el = scrollRef.current;
    if (!el) return;

    shouldStickToBottom.current = isNearBottom(el);
    if (el.scrollTop > 80 || !hasOlderMessages || isLoadingOlderMessages) {
      return;
    }

    historyPrependSnapshot.current = {
      scrollHeight: el.scrollHeight,
      scrollTop: el.scrollTop,
    };
    await loadOlderMessages();
    requestAnimationFrame(() => {
      const currentEl = scrollRef.current;
      const prependSnapshot = historyPrependSnapshot.current;
      if (currentEl && prependSnapshot) {
        currentEl.scrollTop =
          currentEl.scrollHeight - prependSnapshot.scrollHeight + prependSnapshot.scrollTop;
        historyPrependSnapshot.current = null;
      }
    });
  }, [hasOlderMessages, isLoadingOlderMessages, loadOlderMessages]);

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-6 space-y-4">
          {isLoadingOlderMessages && (
            <div className="py-2 text-center text-xs text-muted-foreground">
              加载历史中...
            </div>
          )}
          {!hasMessages && <EmptyState />}
          <MessageList messages={visibleMessages} runs={visibleRuns} />
          <InterruptBlock />
          {isLoading && !isStreamingContent(visibleMessages) && <TypingIndicator />}
          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              出错了：{error.message}
            </div>
          )}
        </div>
      </div>
      <div className="border-t border-border px-4 py-3">
        <div className="mx-auto max-w-2xl">
          <ChatInput />
        </div>
      </div>
    </div>
  );
}

// ============================================================
// StableMessageList (subscribes to throttled MessageContext)
// ============================================================

export function StableMessageList() {
  const { messages, runs } = useMessageContext();
  const { isLoading, interrupt } = useStreamContext();
  const visibleMessages = messages.filter((m: any) => !isHiddenMessage(m));
  const visibleRuns = runs
    .map((run) => ({
      ...run,
      messages: run.messages.filter((m: any) => !isHiddenMessage(m)),
    }))
    .filter((run) => run.messages.length > 0);
  return (
    <Thread
      visibleMessages={visibleMessages}
      visibleRuns={visibleRuns}
      isLoading={isLoading}
      interrupt={interrupt}
    />
  );
}
