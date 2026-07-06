import assert from "node:assert/strict";
import test from "node:test";

import { keepDocumentProgressMonotonic } from "./document-progress-display.ts";

test("keeps displayed document progress from moving backward", () => {
  const maxById = new Map([["doc-1", 56]]);
  const docs = [
    {
      id: "doc-1",
      status: "parsing",
      progress: { percent: 20, stage: "parsing" },
    },
  ];

  const result = keepDocumentProgressMonotonic(docs, maxById);

  assert.equal(result[0].progress.percent, 56);
});

test("forces ready documents to 100 percent", () => {
  const maxById = new Map([["doc-1", 56]]);
  const docs = [
    {
      id: "doc-1",
      status: "ready",
      progress: { percent: 88, stage: "ready" },
    },
  ];

  const result = keepDocumentProgressMonotonic(docs, maxById);

  assert.equal(result[0].progress.percent, 100);
  assert.equal(maxById.get("doc-1"), 100);
});
