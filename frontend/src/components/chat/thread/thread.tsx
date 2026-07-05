"use client";

import { useRef, useCallback, useLayoutEffect, useEffect, type TouchEvent, type WheelEvent } from "react";
import { useStreamContext, useMessageContext } from "../assistant";
import {
  getMessageScrollSignature,
  isNearBottom,
  isStreamingContent,
  isHiddenMessage,
  shouldDisableAutoScrollOnWheel,
  shouldRestoreAutoScrollFromPosition,
} from "./helpers";
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
  const userScrollOverride = useRef(false);
  const autoScrollingUntil = useRef(0);
  const touchStartY = useRef<number | null>(null);
  const historyPrependSnapshot = useRef<{ scrollHeight: number; scrollTop: number } | null>(null);
  const initialScrollDone = useRef(false);
  const hasMessages = visibleMessages.length > 0;
  const messageScrollSignature = getMessageScrollSignature(visibleMessages);

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
    if (hasInterrupt || (shouldStickToBottom.current && !userScrollOverride.current)) {
      autoScrollingUntil.current = Date.now() + 120;
      el.scrollTo({
        top: el.scrollHeight,
        behavior: isLoading ? "auto" : "smooth",
      });
    }
  }, [messageScrollSignature, isLoading, hasInterrupt, visibleMessages.length]);

  const handleScroll = useCallback(async () => {
    const el = scrollRef.current;
    if (!el) return;

    if (Date.now() < autoScrollingUntil.current) {
      return;
    }

    const nearBottom = isNearBottom(el);
    if (
      shouldRestoreAutoScrollFromPosition({
        userOverride: userScrollOverride.current,
        isNearBottom: nearBottom,
      })
    ) {
      userScrollOverride.current = false;
      shouldStickToBottom.current = true;
    } else if (!userScrollOverride.current) {
      shouldStickToBottom.current = nearBottom;
    }
    if (isLoading || el.scrollTop > 80 || !hasOlderMessages || isLoadingOlderMessages) {
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
  }, [hasOlderMessages, isLoadingOlderMessages, isLoading, loadOlderMessages]);

  const handleWheel = useCallback((event: WheelEvent<HTMLDivElement>) => {
    const el = scrollRef.current;
    if (!el) return;

    if (
      shouldDisableAutoScrollOnWheel({
        deltaY: event.deltaY,
        isNearBottom: isNearBottom(el),
      })
    ) {
      autoScrollingUntil.current = 0;
      userScrollOverride.current = true;
      shouldStickToBottom.current = false;
      return;
    }
  }, []);

  const handleTouchStart = useCallback((event: TouchEvent<HTMLDivElement>) => {
    touchStartY.current = event.touches[0]?.clientY ?? null;
  }, []);

  const handleTouchMove = useCallback((event: TouchEvent<HTMLDivElement>) => {
    const el = scrollRef.current;
    const startY = touchStartY.current;
    const currentY = event.touches[0]?.clientY;
    if (!el || startY == null || currentY == null) return;

    // Finger moving down scrolls the content upward to older messages.
    if (currentY > startY || !isNearBottom(el)) {
      autoScrollingUntil.current = 0;
      userScrollOverride.current = true;
      shouldStickToBottom.current = false;
    }
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        onWheel={handleWheel}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        className="flex-1 overflow-y-auto"
      >
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
