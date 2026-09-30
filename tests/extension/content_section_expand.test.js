/**
 * Regression test for a real bug found via a live click trace: the Notice
 * Period step was calling ensureSectionExpanded("Employment Details")
 * (copy-pasted from the Employment Details step right above it) instead of
 * ensureSectionExpanded("Notice Period"). resdex_schema.json defines
 * notice_period as its own top-level section, separate from
 * employment_details — expanding the wrong one leaves #noticePeriodTags
 * collapsed/hidden, so the chip clicks in that step land on nothing.
 *
 * This can't be exercised end-to-end without a live Resdex session, so it
 * asserts directly on the source: the notice_period step block must expand
 * "Notice Period", not "Employment Details".
 *
 * Run with: node --test tests/extension/content_section_expand.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

function extractStepBlock(stepName) {
  const marker = `runStep("${stepName}"`;
  const start = source.indexOf(marker);
  assert.ok(start !== -1, `could not find runStep("${stepName}") in content.js`);
  // Steps are sequential `stepResults.push(await runStep(...))` calls closed
  // by a `}));` at the matching indent — the next occurrence of that exact
  // closer after `start` is this step's end.
  const end = source.indexOf("\n    }));", start);
  assert.ok(end !== -1, `could not find the closing }))  for step "${stepName}"`);
  return source.slice(start, end);
}

test("notice_period step expands the Notice Period section, not Employment Details", () => {
  const block = extractStepBlock("notice_period");
  assert.match(block, /ensureSectionExpanded\("Notice Period"\)/);
  assert.doesNotMatch(block, /ensureSectionExpanded\("Employment Details"\)/);
});

test("employment_details step still expands Employment Details (sanity check the extractor itself works)", () => {
  const block = extractStepBlock("employment_details");
  assert.match(block, /ensureSectionExpanded\("Employment Details"\)/);
});
