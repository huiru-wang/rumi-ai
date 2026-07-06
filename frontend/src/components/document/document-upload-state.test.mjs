import assert from "node:assert/strict";
import test from "node:test";

import {
  createUploadingDocument,
  markUploadFailed,
  replaceUploadingDocument,
} from "./document-upload-state.ts";

test("creates an uploading placeholder document immediately", () => {
  const doc = createUploadingDocument({
    id: "temp-1",
    workspaceId: "workspace-1",
    filename: "brief.pdf",
  });

  assert.equal(doc.id, "temp-1");
  assert.equal(doc.workspace_id, "workspace-1");
  assert.equal(doc.filename, "brief.pdf");
  assert.equal(doc.status, "uploaded");
  assert.equal(doc.progress?.stage, "uploading");
  assert.equal(doc.progress?.message, "上传中...");
});

test("replaces the matching uploading placeholder with the uploaded document", () => {
  const placeholder = createUploadingDocument({
    id: "temp-1",
    workspaceId: "workspace-1",
    filename: "brief.pdf",
  });
  const existing = createUploadingDocument({
    id: "temp-2",
    workspaceId: "workspace-1",
    filename: "other.pdf",
  });
  const uploaded = {
    ...placeholder,
    id: "doc-1",
    status: "parsing",
    progress: { ...placeholder.progress, stage: "parsing", message: "正在解析" },
  };

  assert.deepEqual(
    replaceUploadingDocument([existing, placeholder], placeholder.id, uploaded),
    [existing, uploaded],
  );
});

test("marks only the matching uploading placeholder as failed", () => {
  const failed = createUploadingDocument({
    id: "temp-1",
    workspaceId: "workspace-1",
    filename: "brief.pdf",
  });
  const existing = createUploadingDocument({
    id: "temp-2",
    workspaceId: "workspace-1",
    filename: "other.pdf",
  });

  const result = markUploadFailed([failed, existing], failed.id, "上传失败");

  assert.equal(result[0].status, "error");
  assert.equal(result[0].error_message, "上传失败");
  assert.equal(result[1].status, "uploaded");
});
