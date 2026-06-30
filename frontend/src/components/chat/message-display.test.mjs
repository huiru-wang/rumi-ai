import assert from "node:assert/strict";
import test from "node:test";

import {
  createMessageDebugSnapshot,
  getLiveMessagesAfterHistory,
  shouldPreserveDisplayedMessages,
  shouldUseLiveMessages,
} from "./message-display.ts";

test("does not use live stream messages while persisted history is loading", () => {
  assert.equal(
    shouldUseLiveMessages({
      threadId: "thread-1",
      isInitialHistoryLoading: true,
    }),
    false,
  );
});

test("uses live stream messages once persisted history has loaded", () => {
  assert.equal(
    shouldUseLiveMessages({
      threadId: "thread-1",
      isInitialHistoryLoading: false,
    }),
    true,
  );
});

test("uses live stream messages before a thread exists", () => {
  assert.equal(
    shouldUseLiveMessages({
      threadId: null,
      isInitialHistoryLoading: true,
    }),
    true,
  );
});

test("only uses stream messages after the last persisted history message", () => {
  const historyMessages = [
    { id: "confirm", type: "human" },
    { id: "generated", type: "ai" },
    { id: "hi", type: "human" },
    { id: "reply", type: "ai" },
    { id: "name", type: "human" },
    { id: "name-reply", type: "ai" },
  ];
  const streamMessages = [
    { id: "outline", type: "ai" },
    { id: "confirm", type: "human" },
    { id: "generated", type: "ai" },
    { id: "hi", type: "human" },
    { id: "reply", type: "ai" },
    { id: "name", type: "human" },
    { id: "name-reply", type: "ai" },
    { id: "new-live", type: "ai" },
  ];

  assert.deepEqual(
    getLiveMessagesAfterHistory({
      historyMessages,
      streamMessages,
      getMessageKey: (message) => `${message.type}:${message.id}`,
    }),
    [{ id: "new-live", type: "ai" }],
  );
});

test("does not treat checkpoint history as live when no history anchor exists", () => {
  assert.deepEqual(
    getLiveMessagesAfterHistory({
      historyMessages: [{ id: "missing-from-stream", type: "human" }],
      streamMessages: [{ id: "old-checkpoint-message", type: "ai" }],
      getMessageKey: (message) => `${message.type}:${message.id}`,
    }),
    [],
  );
});

test("message debug snapshot summarizes counts and missing history anchor", () => {
  assert.deepEqual(
    createMessageDebugSnapshot({
      phase: "immediate",
      threadId: "thread-1",
      isLoading: false,
      historyMessages: [{ id: "history-last", type: "ai", content: "persisted message" }],
      streamMessages: [{ id: "stream-last", type: "ai", content: "streamed message" }],
      liveMessages: [],
      displayedMessages: [{ id: "history-last", type: "ai", content: "persisted message" }],
      optimisticMessages: [],
      getMessageKey: (message) => `${message.type}:${message.id}`,
    }),
    {
      phase: "immediate",
      threadId: "thread-1",
      isLoading: false,
      history: {
        count: 1,
        last: {
          type: "ai",
          id: "history-last",
          rowId: undefined,
          contentLength: 17,
          toolCalls: 0,
          name: undefined,
        },
      },
      stream: {
        count: 1,
        last: {
          type: "ai",
          id: "stream-last",
          rowId: undefined,
          contentLength: 16,
          toolCalls: 0,
          name: undefined,
        },
      },
      live: { count: 0, last: undefined },
      displayed: {
        count: 1,
        last: {
          type: "ai",
          id: "history-last",
          rowId: undefined,
          contentLength: 17,
          toolCalls: 0,
          name: undefined,
        },
      },
      optimistic: { count: 0, last: undefined },
      anchor: {
        lastHistoryKey: "ai:history-last",
        indexInStream: -1,
        reason: "missing-history-anchor",
      },
    },
  );
});

test("preserves displayed messages when completion sync temporarily loses the live anchor", () => {
  assert.equal(
    shouldPreserveDisplayedMessages({
      isLoading: false,
      historyMessages: [{ id: "persisted-old", type: "ai" }],
      streamMessages: [{ id: "final-ai", type: "ai" }],
      liveMessages: [],
      nextDisplayedMessages: [{ id: "persisted-old", type: "ai" }],
      previousDisplayedMessages: [
        { id: "persisted-old", type: "ai" },
        { id: "final-ai", type: "ai" },
      ],
      getMessageKey: (message) => `${message.type}:${message.id}`,
    }),
    true,
  );
});

test("does not preserve displayed messages when the next merge includes the live suffix", () => {
  assert.equal(
    shouldPreserveDisplayedMessages({
      isLoading: false,
      historyMessages: [{ id: "persisted-old", type: "ai" }],
      streamMessages: [
        { id: "persisted-old", type: "ai" },
        { id: "final-ai", type: "ai" },
      ],
      liveMessages: [{ id: "final-ai", type: "ai" }],
      nextDisplayedMessages: [
        { id: "persisted-old", type: "ai" },
        { id: "final-ai", type: "ai" },
      ],
      previousDisplayedMessages: [{ id: "persisted-old", type: "ai" }],
      getMessageKey: (message) => `${message.type}:${message.id}`,
    }),
    false,
  );
});
