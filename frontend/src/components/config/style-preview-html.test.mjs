import assert from "node:assert/strict";
import test from "node:test";

import {
  STYLE_PREVIEW_NAV_SCRIPT,
  prepareStylePreviewHtml,
} from "./style-preview-html.ts";

test("prepareStylePreviewHtml injects read-only navigation before body close", () => {
  const html = "<html><body><section class=\"slide\">A</section></body></html>";
  const prepared = prepareStylePreviewHtml(html);

  assert.match(prepared, /style-preview:navigate/);
  assert.match(prepared, /style-preview-state/);
  assert.match(prepared, /removeAttribute\('contenteditable'\)/);
  assert.ok(prepared.indexOf("<script>") < prepared.indexOf("</body>"));
});

test("prepareStylePreviewHtml supports html fragments without body", () => {
  const prepared = prepareStylePreviewHtml("<section class=\"slide\">A</section>");

  assert.match(prepared, /<script>/);
  assert.match(prepared, /style-preview-state/);
});

test("style preview navigation script keeps single-slide previews compatible", () => {
  assert.match(STYLE_PREVIEW_NAV_SCRIPT, /slides\.length <= 1/);
  assert.match(STYLE_PREVIEW_NAV_SCRIPT, /Math\.max\(slides\.length, 1\)/);
});
