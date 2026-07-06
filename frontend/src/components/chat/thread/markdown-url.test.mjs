import assert from "node:assert/strict";
import test from "node:test";

import { normalizeMarkdownAssetUrl } from "./markdown-url.ts";

test("rewrites historical localhost API asset urls to origin-relative paths", () => {
  assert.equal(
    normalizeMarkdownAssetUrl(
      "http://localhost:8000/api/documents/26518a49-6151-4940-ad62-f58367b3c46c/asset/image_3311.png",
    ),
    "/api/documents/26518a49-6151-4940-ad62-f58367b3c46c/asset/image_3311.png",
  );
});

test("keeps non-localhost urls unchanged", () => {
  assert.equal(
    normalizeMarkdownAssetUrl("https://rumi.robinverse.me/api/documents/doc/asset/image.png"),
    "https://rumi.robinverse.me/api/documents/doc/asset/image.png",
  );
});
