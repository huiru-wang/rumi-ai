import assert from "node:assert/strict";
import test from "node:test";

import {
  buildToolResultMap,
  getMessageScrollSignature,
  shouldDisableAutoScrollOnWheel,
  shouldRestoreAutoScrollFromPosition,
} from "./helpers.ts";

test("message scroll signature changes when the last message content grows", () => {
  const baseMessages = [
    { id: "human-1", type: "human", content: "question" },
    { id: "ai-1", type: "ai", content: "hello" },
  ];
  const grownMessages = [
    { id: "human-1", type: "human", content: "question" },
    { id: "ai-1", type: "ai", content: "hello world" },
  ];

  assert.notEqual(
    getMessageScrollSignature(baseMessages),
    getMessageScrollSignature(grownMessages),
  );
});

test("wheel up disables auto scroll even while currently near bottom", () => {
  assert.equal(shouldDisableAutoScrollOnWheel({ deltaY: -1, isNearBottom: true }), true);
});

test("wheel down does not disable auto scroll when still near bottom", () => {
  assert.equal(shouldDisableAutoScrollOnWheel({ deltaY: 1, isNearBottom: true }), false);
});

test("auto scroll restores only when the user reaches the bottom", () => {
  assert.equal(shouldRestoreAutoScrollFromPosition({ userOverride: true, isNearBottom: false }), false);
  assert.equal(shouldRestoreAutoScrollFromPosition({ userOverride: true, isNearBottom: true }), true);
  assert.equal(shouldRestoreAutoScrollFromPosition({ userOverride: false, isNearBottom: true }), false);
});

test("tool result map indexes tool messages across runs by tool_call_id", () => {
  const toolResult = {
    type: "tool",
    name: "clarify_form",
    tool_call_id: "call_123",
    content: '{"topic":"Go Slice"}',
    run_id: "resume-run",
  };
  const messages = [
    {
      type: "ai",
      run_id: "original-run",
      tool_calls: [{ id: "call_123", name: "clarify_form", args: {} }],
    },
    toolResult,
  ];

  const resultMap = buildToolResultMap(messages);

  assert.equal(resultMap.get("call_123"), toolResult);
});
