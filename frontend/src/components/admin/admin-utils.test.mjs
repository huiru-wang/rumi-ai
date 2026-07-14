import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTrendPolyline,
  readAdminToken,
  writeAdminToken,
} from "./admin-utils.ts";

test("buildTrendPolyline scales values into the chart viewport", () => {
  assert.equal(buildTrendPolyline([0, 5, 10], 100, 40), "0,40 50,20 100,0");
});

test("buildTrendPolyline keeps an all-zero trend on the baseline", () => {
  assert.equal(buildTrendPolyline([0, 0], 100, 40), "0,40 100,40");
});

test("admin token helpers use session storage without storing credentials", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };

  writeAdminToken(storage, "signed-token");
  assert.equal(readAdminToken(storage), "signed-token");

  writeAdminToken(storage, null);
  assert.equal(readAdminToken(storage), null);
});
