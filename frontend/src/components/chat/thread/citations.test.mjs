import assert from "node:assert/strict";
import test from "node:test";

import { replaceCitationMarkers } from "./citations.ts";

test("replaces structured ref markers and formats citation detail", () => {
  const result = replaceCitationMarkers(
    "内存分为多个区域。[ref:代码随想录.pdf|第48页|C++基础|内存分区]",
  );

  assert.equal(result.text, "内存分为多个区域。[⟦1⟧](#__cite__1)");
  assert.deepEqual(result.citations, [
    {
      docName: "代码随想录.pdf",
      detail: "第48页｜C++基础｜内存分区",
    },
  ]);
});

test("supports missing titles with page placeholder", () => {
  const result = replaceCitationMarkers("权限模型如下。[ref:产品需求文档.docx|-]");

  assert.equal(result.text, "权限模型如下。[⟦1⟧](#__cite__1)");
  assert.deepEqual(result.citations, [
    {
      docName: "产品需求文档.docx",
      detail: "-",
    },
  ]);
});

test("keeps compatibility with legacy brace ref markers", () => {
  const result = replaceCitationMarkers("结论如下。{{ref:旧文档.pdf|条款 48}}");

  assert.equal(result.text, "结论如下。[⟦1⟧](#__cite__1)");
  assert.deepEqual(result.citations, [
    {
      docName: "旧文档.pdf",
      detail: "条款 48",
    },
  ]);
});
