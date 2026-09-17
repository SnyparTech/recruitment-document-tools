/**
 * Regression test for a bug found in a live Resdex session: clickBestSuggestion's
 * broad class-substring selectors (e.g. div[class*='option']) matched an unrelated
 * "similar candidates" preview card on the page — a 1000+ character candidate bio
 * containing the substring "AI Engineer" — scored it as a plausible suggestion, and
 * clicked it. That click navigated the page to /v3/search (results) mid-fill,
 * before the Designation field (and everything after it) had actually been filled.
 *
 * Fix: isPlausibleSuggestionElement() rejects any candidate element whose text is
 * longer than a real suggestion item could ever be (skills/designations/locations
 * are always short single values, never paragraph-length bios).
 *
 * Run with: node --test tests/extension/content_suggestion_safety.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

// Real text captured from the live console log that exposed this bug.
const REAL_CANDIDATE_CARD_TEXT =
  "Abhishek Kumar5y 0m₹ 10.05 LacsBengaluruCurrentSystem Engineer at Tata Consultancy Services" +
  "EducationMCA Chandigarh University, Mohali 2024B.C.A. Bihar University 2021Pref. locations" +
  "Chandigarh, Bengaluru, Pune, Hyderabad, Noida +4 moreKey skillsPython | Machine Learning | " +
  "Fastapi | Deep Learning | Natural Language Processing | Tensorflow | Pytorch | Computer Vision | " +
  "Data Science | Django | Pandas | Numpy | Predictive Modeling | Python Development | Pytest | " +
  "Sqlalchemy | Tesseract | Python Flask | OCR | Data Extraction | AWS | Unit Testing | Langgraph | " +
  "LangchainMay also knowSQL | Flask | GIT | Scikit-Learn | Data A...morePython & AI Engineer | " +
  "5 Yrs Exp | FastAPI, GenAI, LLMs, Machine Learning, NLP & OCR Automation | BFSI Domain View " +
  "phone numberCall candidateVerified phone & email 300 similar profiles Comment | Save43395CV" +
  "Modified yesterdayActive today";

function loadContentJsSandbox(elementsBySelector) {
  const sandbox = {
    window: {
      location: { href: "" },
      addEventListener() {},
      getSelection() { return { removeAllRanges() {} }; },
      HTMLInputElement: { prototype: {} },
    },
    document: {
      readyState: "loading",
      addEventListener() {},
      getElementById() { return null; },
      querySelector() { return null; },
      querySelectorAll() { return elementsBySelector || []; },
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

function fakeEl(text) {
  return {
    offsetParent: {},
    textContent: text,
    className: "",
    getAttribute() { return null; },
    click() { this.clicked = true; },
  };
}

test("isPlausibleSuggestionElement rejects a real captured candidate-card bio and accepts a real short designation", () => {
  const sandbox = loadContentJsSandbox();
  assert.equal(sandbox.isPlausibleSuggestionElement(fakeEl(REAL_CANDIDATE_CARD_TEXT)), false);
  assert.equal(sandbox.isPlausibleSuggestionElement(fakeEl("Machine Learning Engineer")), true);
  assert.equal(sandbox.isPlausibleSuggestionElement(fakeEl("")), false);
});

test("clickBestSuggestion does not click a candidate-card element even though it substring-matches the target", () => {
  const candidateCard = fakeEl(REAL_CANDIDATE_CARD_TEXT); // contains "AI Engineer" as a substring
  const sandbox = loadContentJsSandbox([candidateCard]);

  const clicked = sandbox.clickBestSuggestion("AI Engineer");

  assert.equal(clicked, false, "must not report a successful click");
  assert.notEqual(candidateCard.clicked, true, "the oversized candidate-card element must never be clicked");
});

test("clickBestSuggestion still clicks a real, short suggestion item when one is present alongside a candidate card", () => {
  const candidateCard = fakeEl(REAL_CANDIDATE_CARD_TEXT);
  const realSuggestion = fakeEl("AI Engineer");
  const sandbox = loadContentJsSandbox([candidateCard, realSuggestion]);

  const clicked = sandbox.clickBestSuggestion("AI Engineer");

  assert.equal(clicked, true);
  assert.equal(realSuggestion.clicked, true);
  assert.notEqual(candidateCard.clicked, true);
});

test("waitForDropdown does not treat a visible candidate-card element as evidence a dropdown appeared", async () => {
  const candidateCard = fakeEl(REAL_CANDIDATE_CARD_TEXT);
  const sandbox = loadContentJsSandbox([candidateCard]);

  const appeared = await sandbox.waitForDropdown(200);
  assert.equal(appeared, false);
});

test("clickPill never clicks an oversized candidate-card element even if it contains the pill text as a substring", async () => {
  // "Female candidates" is a realistic diversity-hiring pill value that could
  // plausibly appear verbatim inside a large candidate bio blob.
  const poisonedCard = fakeEl(REAL_CANDIDATE_CARD_TEXT + " open to Female candidates only roles");
  const sandbox = loadContentJsSandbox([poisonedCard]);
  // ensureSectionExpanded queries a separate, unrelated selector list — give it nothing to expand.
  const originalQuerySelectorAll = sandbox.document.querySelectorAll;
  sandbox.document.querySelectorAll = (selector) => {
    if (selector.includes("accordion") || selector.includes("h2")) return [];
    return originalQuerySelectorAll(selector);
  };

  const clicked = await sandbox.clickPill("Diversity Hiring", "Female candidates");

  assert.equal(clicked, false, "no plausible pill element was found, so nothing should be reported as clicked");
  assert.notEqual(poisonedCard.clicked, true, "the oversized candidate-card element must never be clicked");
});

test("clickPill still clicks a real, short pill element", async () => {
  const realPill = fakeEl("Female candidates");
  const sandbox = loadContentJsSandbox([realPill]);
  const originalQuerySelectorAll = sandbox.document.querySelectorAll;
  sandbox.document.querySelectorAll = (selector) => {
    if (selector.includes("accordion") || selector.includes("h2")) return [];
    return originalQuerySelectorAll(selector);
  };

  const clicked = await sandbox.clickPill("Diversity Hiring", "Female candidates");

  assert.equal(clicked, true);
  assert.equal(realPill.clicked, true);
});
