/**
 * Regression test for a real bug report: after clicking "Update (Modify +
 * Sync)" on the website, Resdex's results refreshed but auto-pagination got
 * stuck on page 1 instead of walking every page.
 *
 * Root cause: Naukri doesn't always mint a new `sid` after a Modify +
 * re-search — the fresh results can land on the SAME sid a previous search
 * had already fully paginated. extractAndSubmitOnce's own isSidCompleted(sid)
 * guard then immediately strips AUTOPAGE_KEY back off on the very next
 * extraction tick, undoing what the keyword-sync success handler had just
 * set, because nothing ever told it "this sid isn't actually done anymore".
 *
 * Fix: unmarkSidCompleted(sid) — called right after a verified keyword-sync/
 * broaden re-search — removes the sid from the completed list so the next
 * extraction tick doesn't immediately re-block pagination.
 *
 * Run with: node --test tests/extension/content_pagination_sid_reset.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

function loadSandbox() {
  const localStore = {};
  const sandbox = {
    window: { location: { href: "" }, addEventListener() {}, getSelection() { return { removeAllRanges() {} }; }, HTMLInputElement: { prototype: {} } },
    document: {
      readyState: "loading",
      addEventListener() {},
      getElementById() { return null; },
      querySelector() { return null; },
      querySelectorAll() { return []; },
      body: { appendChild() {}, innerText: "" },
      activeElement: null,
    },
    localStorage: {
      getItem: (k) => (k in localStore ? localStore[k] : null),
      setItem: (k, v) => { localStore[k] = String(v); },
      removeItem: (k) => { delete localStore[k]; },
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

test("unmarkSidCompleted removes exactly the given sid, leaving others intact", () => {
  const sandbox = loadSandbox();
  sandbox.markSidCompleted("sid-1");
  sandbox.markSidCompleted("sid-2");

  assert.equal(sandbox.isSidCompleted("sid-1"), true);
  assert.equal(sandbox.isSidCompleted("sid-2"), true);

  sandbox.unmarkSidCompleted("sid-1");

  assert.equal(sandbox.isSidCompleted("sid-1"), false, "the re-synced sid must no longer be treated as fully paginated");
  assert.equal(sandbox.isSidCompleted("sid-2"), true, "an unrelated sid must not be affected");
});

test("unmarkSidCompleted on a sid that was never marked is a harmless no-op", () => {
  const sandbox = loadSandbox();
  sandbox.markSidCompleted("sid-1");

  sandbox.unmarkSidCompleted("never-marked-sid");

  assert.equal(sandbox.isSidCompleted("sid-1"), true);
  assert.equal(sandbox.isSidCompleted("never-marked-sid"), false);
});
