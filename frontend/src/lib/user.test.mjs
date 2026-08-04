import assert from "node:assert/strict";
import test from "node:test";

import {
  clearCurrentUser,
  getOpenUser,
  getUserSource,
  setAccessUser,
} from "./user.ts";

function installStorage() {
  const values = new Map();
  const localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  globalThis.localStorage = localStorage;
  globalThis.window = {
    localStorage,
  };
}

test("open identity survives clearing the current user", () => {
  installStorage();
  setAccessUser("open-user", "访客 ABCD", "open");

  clearCurrentUser();

  assert.deepEqual(getOpenUser(), { userId: "open-user", nickname: "访客 ABCD" });
});

test("invite identity records its source without replacing open backup", () => {
  installStorage();
  setAccessUser("open-user", "访客 ABCD", "open");
  setAccessUser("invite-user", "邀请用户", "invite");

  assert.equal(getUserSource(), "invite");
  assert.deepEqual(getOpenUser(), { userId: "open-user", nickname: "访客 ABCD" });
});
