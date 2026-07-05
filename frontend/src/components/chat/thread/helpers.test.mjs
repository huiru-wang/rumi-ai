import assert from "node:assert/strict";
import test from "node:test";

import {
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
