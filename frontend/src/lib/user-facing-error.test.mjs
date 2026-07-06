import assert from "node:assert/strict";
import test from "node:test";

import { toUserFacingErrorMessage } from "./user-facing-error.ts";

test("masks technical fetch and http status messages", () => {
  assert.equal(
    toUserFacingErrorMessage(new Error("Failed to fetch file: 502"), "加载失败，请稍后重试。"),
    "加载失败，请稍后重试。",
  );
  assert.equal(
    toUserFacingErrorMessage(new Error("Download failed: 502"), "下载失败，请稍后重试。"),
    "下载失败，请稍后重试。",
  );
});

test("keeps explicit business messages", () => {
  assert.equal(
    toUserFacingErrorMessage(new Error("邀请码无效或已停用"), "操作失败"),
    "邀请码无效或已停用",
  );
});
