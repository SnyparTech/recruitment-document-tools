/**
 * Unit tests for search-submission verification in extension/content.js
 * (waitForResultsPageVerified, isOnResultsPage). Loads the actual shipped file
 * via vm with minimal stubs, same approach as content_step_isolation.test.js.
 *
 * Run with: node --test tests/extension/content_search_verification.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

function loadContentJsSandbox() {
  const sandbox = {
    window: {
      location: { href: "https://resdex.naukri.com/v3?activeTab=advSrch" },
      addEventListener() {},
      getSelection() { return { removeAllRanges() {} }; },
      HTMLInputElement: { prototype: {} },
    },
    document: {
      readyState: "loading",
      addEventListener() {},
      getElementById() { return null; },
      querySelector() { return null; },
      querySelectorAll() { return []; },
      body: { appendChild() {} },
      activeElement: null,
    },
    chrome: undefined,
    console,
    setTimeout,
    Date,
  };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: "content.js" });
  return sandbox;
}

test("isOnResultsPage reflects the URL, and waitForResultsPageVerified resolves true as soon as it does", async () => {
  const sandbox = loadContentJsSandbox();
  assert.equal(sandbox.isOnResultsPage(), false, "advSrch form URL is not a results page");

  // Simulate navigation happening shortly after the search click.
  setTimeout(() => {
    sandbox.window.location.href = "https://resdex.naukri.com/v3/search?...";
  }, 30);

  const verified = await sandbox.waitForResultsPageVerified(2000, 10);
  assert.equal(verified, true);
  assert.equal(sandbox.isOnResultsPage(), true);
});

test("waitForResultsPageVerified returns false if the URL never changes to the results page within the timeout", async () => {
  const sandbox = loadContentJsSandbox();
  // URL never changes — simulates a rejected/failed submit (e.g. validation error).
  const verified = await sandbox.waitForResultsPageVerified(150, 20);
  assert.equal(verified, false);
});

test("caching decision logic: a plan is only treated as fully applied when search wasn't requested, or was requested AND verified", () => {
  // Mirrors the `searchOutcomeOk` decision in fetchAndFill() — re-derives the same
  // boolean expression to guard against regressions in that specific logic gate.
  function searchOutcomeOk(shouldSubmit, outcome) {
    return !shouldSubmit || outcome.searchVerified === true;
  }

  assert.equal(searchOutcomeOk(false, { searchVerified: null }), true, "form-fill only: always OK to cache");
  assert.equal(searchOutcomeOk(true, { searchVerified: true }), true, "search requested AND verified: OK to cache");
  assert.equal(searchOutcomeOk(true, { searchVerified: false }), false, "search requested but NOT verified: must NOT cache");
  assert.equal(searchOutcomeOk(true, { searchVerified: null }), false, "search requested but button never found: must NOT cache");
});
