import assert from "node:assert/strict";
import test from "node:test";

import { shouldFocusAfterLoadingChange } from "./chat-input-focus.ts";

test("focuses after agent loading changes from active to idle", () => {
  assert.equal(
    shouldFocusAfterLoadingChange({ wasLoading: true, isLoading: false }),
    true,
  );
});

test("does not focus while loading starts or remains unchanged", () => {
  assert.equal(
    shouldFocusAfterLoadingChange({ wasLoading: false, isLoading: true }),
    false,
  );
  assert.equal(
    shouldFocusAfterLoadingChange({ wasLoading: true, isLoading: true }),
    false,
  );
  assert.equal(
    shouldFocusAfterLoadingChange({ wasLoading: false, isLoading: false }),
    false,
  );
});
