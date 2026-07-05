import assert from "node:assert/strict";
import test from "node:test";

import {
  PPT_STYLE_CATEGORIES,
  getPptStyleCategoryGroups,
} from "./style-categories.ts";

test("ppt style categories contain the seven requested usage groups", () => {
  assert.deepEqual(
    PPT_STYLE_CATEGORIES.map((category) => category.id),
    ["academic", "business", "product", "report", "data", "creative", "custom"],
  );
});

test("ppt style category groups keep empty categories visible", () => {
  const groups = getPptStyleCategoryGroups([
    { id: "sys-swiss-modern", category: "business" },
  ]);

  assert.equal(groups.length, 7);
  assert.deepEqual(
    groups.map((group) => group.id),
    ["academic", "business", "product", "report", "data", "creative", "custom"],
  );
  assert.deepEqual(groups.find((group) => group.id === "report")?.styles, []);
});

test("unknown style categories are shown under custom", () => {
  const groups = getPptStyleCategoryGroups([
    { id: "old-style", category: "light" },
  ]);

  assert.deepEqual(
    groups.find((group) => group.id === "custom")?.styles.map((style) => style.id),
    ["old-style"],
  );
});
