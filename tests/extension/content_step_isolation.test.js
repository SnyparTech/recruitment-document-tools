/**
 * Unit tests for the per-step isolation/diagnostics helpers in extension/content.js
 * (runStep, summarizeStepResults). These are pure functions with no DOM dependency,
 * so they're loaded via vm with minimal window/document stubs (just enough for the
 * file's top-level guards to evaluate without a real browser) rather than duplicating
 * the logic here — this way the test exercises the actual shipped implementation.
 *
 * Run with: node --test tests/extension/content_step_isolation.test.js
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
      location: { href: "" }, // not resdex.naukri.com -> init block is skipped
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

test("runStep isolates failures: one failing step does not throw or block others", async () => {
  const sandbox = loadContentJsSandbox();
  const results = [];

  results.push(await sandbox.runStep("keywords", async () => {
    // succeeds
  }));
  results.push(await sandbox.runStep("experience", async () => {
    throw new Error("selector not found");
  }));
  results.push(await sandbox.runStep("location", async () => {
    // this must still run even though "experience" above threw
  }));

  assert.equal(results.length, 3, "all three steps must have run and recorded a result");
  assert.equal(results[0].status, "ok");
  assert.equal(results[1].status, "failed");
  assert.equal(results[1].error, "selector not found");
  assert.equal(results[2].status, "ok", "step after a failure must still execute (no abort)");
});

test("summarizeStepResults groups ok vs failed step names correctly", async () => {
  const sandbox = loadContentJsSandbox();
  const results = [
    { name: "keywords", status: "ok" },
    { name: "experience", status: "failed", error: "boom" },
    { name: "location", status: "ok" },
    { name: "salary", status: "failed", error: "missing input" },
  ];

  const summary = sandbox.summarizeStepResults(results);
  // Objects cross the vm sandbox boundary with a different Object prototype, so
  // compare via JSON rather than assert.deepEqual (which checks prototype identity).
  assert.equal(JSON.stringify(summary.ok), JSON.stringify(["keywords", "location"]));
  assert.equal(
    JSON.stringify(summary.failed),
    JSON.stringify([
      { name: "experience", error: "boom" },
      { name: "salary", error: "missing input" },
    ])
  );
});

test("waitForFieldValue resolves true as soon as the polled selector's value matches", async () => {
  const sandbox = loadContentJsSandbox();
  let callCount = 0;
  const fakeInput = { value: "" };
  sandbox.document.querySelector = (sel) => {
    callCount++;
    if (callCount >= 2) fakeInput.value = "5"; // simulate React committing state after a tick
    return fakeInput;
  };

  const ok = await sandbox.waitForFieldValue("input#minExp", "5", 1000, 10);
  assert.equal(ok, true);
  assert.ok(callCount >= 2, "should have polled more than once before succeeding");
});

test("waitForFieldValue times out and falls back to fieldHasValue (non-empty, not exact-match) when the expected value never appears", async () => {
  const sandbox = loadContentJsSandbox();

  // Case A: fallback sees a non-empty (but wrong) value -> still reports true,
  // since fieldHasValue only checks "something is there", not exact match.
  sandbox.document.querySelector = () => ({ value: "wrong", tagName: "input" });
  assert.equal(await sandbox.waitForFieldValue("input#minExp", "5", 100, 10), true);

  // Case B: fallback sees a genuinely empty field -> reports falsy.
  sandbox.document.querySelector = () => ({ value: "", tagName: "input" });
  assert.ok(!(await sandbox.waitForFieldValue("input#minExp", "5", 100, 10)));
});
