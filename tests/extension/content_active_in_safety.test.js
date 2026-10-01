/**
 * Regression test for a real bug found via a live trace (JSON click
 * recorder): setActiveIn()'s final fallback searched the ENTIRE document for
 * any element whose text merely CONTAINED the target value ("15 days") and
 * clicked the first match, unconditionally logging success. With the real
 * Active In dropdown never actually opening (aria-expanded stuck false
 * across every click attempt), that fallback matched and clicked the Notice
 * Period "0 - 15 days" chip instead — a completely different field — while
 * falsely reporting "✓ Set active_in" and leaving Active In stuck on
 * Resdex's own default ("6 months").
 *
 * Confirmed from the trace:
 *   79015-80858  bot clicks various parts of the Active In wrapper; every
 *                capture shows the dropdown-head text still "6 months"
 *   82201        click lands on `div#noticePeriodTags > ... > span.txt.ellipsis`
 *                text="0 - 15 days" — the wrong field entirely
 *
 * Fix: the unscoped document-wide fallback is removed outright. A keyboard-
 * based open/select attempt (scoped to the Active In wrapper only, via the
 * same findOpt() used by the mouse-click path) replaces it, and failure is
 * now honest (returns false, surfaced as a real step failure) instead of a
 * false "success" log.
 *
 * This can't be exercised end-to-end without a live Resdex session (the
 * underlying cause — why aria-expanded never flips on a real click — is a
 * live-DOM question, not something a synthetic fixture can prove either
 * way), so this asserts directly on the source: the dangerous pattern must
 * be gone, and the safer pattern must be present.
 *
 * Run with: node --test tests/extension/content_active_in_safety.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

function extractFunctionBody(fnName) {
  const marker = `async function ${fnName}(`;
  const start = source.indexOf(marker);
  assert.ok(start !== -1, `could not find ${marker} in content.js`);
  // Next top-level "async function " or "function " marks the end of this one.
  const nextFn = source.indexOf("\nasync function ", start + marker.length);
  const nextFn2 = source.indexOf("\nfunction ", start + marker.length);
  const candidates = [nextFn, nextFn2].filter((n) => n !== -1);
  const end = candidates.length ? Math.min(...candidates) : source.length;
  return source.slice(start, end);
}

test("setActiveIn no longer searches the whole document for elements containing the target text", () => {
  const body = extractFunctionBody("setActiveIn");

  // The dangerous pattern: querying "span, div, button" / "li, div[role='option'], span"
  // against `document` (not a scoped `wrap`) and filtering by substring text match.
  assert.doesNotMatch(
    body,
    /document\.querySelectorAll\(\s*["']span, div, button["']/,
    "the unscoped 'triggers' search over the whole document must be removed"
  );
  assert.doesNotMatch(
    body,
    /document\.querySelectorAll\(\s*["']li, div\[role='option'\], span["']/,
    "the unscoped 'options' search over the whole document must be removed"
  );
});

test("setActiveIn has a keyboard-based fallback scoped to the active-in wrapper", () => {
  const body = extractFunctionBody("setActiveIn");

  assert.match(body, /KeyboardEvent/, "should attempt a keyboard-based open as a mouse-click fallback");
  assert.match(body, /findOpt\(\)/, "the keyboard fallback must reuse the same scoped option-finder, not an unscoped search");
});

test("setActiveIn ends with an honest `return false` when every attempt fails (no unconditional success log)", () => {
  const body = extractFunctionBody("setActiveIn");
  assert.match(
    body,
    /return false;\s*\n\}/,
    "setActiveIn's final statement must be an honest \"return false;\" immediately before its closing brace"
  );
  // And nothing after that closing brace (within the extracted body) claims
  // success unconditionally the way the removed fallback used to.
  const afterLastReturnFalse = body.slice(body.lastIndexOf("return false;"));
  assert.doesNotMatch(afterLastReturnFalse, /console\.log\(`\[Snypar Bot\] ✓ Set active_in/);
});

test("the active_in form-fill step throws (surfaces as a real failure) when setActiveIn returns false", () => {
  const stepMarker = 'runStep("active_in"';
  const start = source.indexOf(stepMarker);
  assert.ok(start !== -1, "could not find the active_in step in content.js");
  const end = source.indexOf("}));", start);
  const stepBody = source.slice(start, end);

  assert.match(stepBody, /const activeInSet = await setActiveIn/);
  assert.match(stepBody, /if \(!activeInSet\)/);
  assert.match(stepBody, /throw new Error/);
});
