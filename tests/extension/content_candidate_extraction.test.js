/**
 * Unit tests for the candidate-extraction architecture in extension/content.js
 * (findCandidateContainers, extractOneCandidate, extractCandidatesFromResultsPage).
 *
 * IMPORTANT: this uses a small SYNTHETIC fake-DOM fixture built for this test only —
 * it is NOT real Naukri Resdex markup (none is available in this repo). These tests
 * validate the extraction architecture's behavior (fail-soft per field, per-container
 * error isolation, diagnostics reporting, dedup-relevant container selection) against
 * plausible generic markup shapes, not the real Resdex DOM structure. Selector
 * calibration against the real page still has to happen in a live session.
 *
 * Run with: node --test tests/extension/content_candidate_extraction.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

// ─── Minimal synthetic fake-DOM element ──────────────────────────────────────
class FakeEl {
  constructor({ tag = "div", className = "", text = "", href = null, children = [], visible = true } = {}) {
    this.tagName = tag.toUpperCase();
    this.className = className;
    this._text = text;
    this.href = href;
    this.children = children;
    children.forEach((c) => (c.parentElement = this));
    this.parentElement = null;
    this.offsetParent = visible ? {} : null;
  }
  get textContent() {
    if (this._text) return this._text;
    return this.children.map((c) => c.textContent).join(" ");
  }
  // Only "*" (all descendants) and simple class/tag "contains" queries used by
  // content.js's extractor are supported — enough to drive the real functions
  // under test without building a full CSS selector engine.
  querySelectorAll(selector) {
    const all = [];
    const walk = (el) => {
      for (const c of el.children) {
        all.push(c);
        walk(c);
      }
    };
    walk(this);
    if (selector === "*") return all;
    if (selector.includes("skill") || selector.includes("tag") || selector.includes("chip")) {
      return all.filter((el) => /skill|tag|chip/i.test(el.className));
    }
    return all.filter((el) => selector.toLowerCase().includes(el.tagName.toLowerCase()));
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

function loadContentJsSandbox(documentQuerySelectorAllBySelector) {
  const fakeDocument = {
    readyState: "loading",
    addEventListener() {},
    getElementById() { return null; },
    querySelector() { return null; },
    querySelectorAll(selector) {
      for (const [key, els] of Object.entries(documentQuerySelectorAllBySelector || {})) {
        if (selector.includes(key)) return els;
      }
      return [];
    },
    body: { appendChild() {} },
    activeElement: null,
  };
  const sandbox = {
    window: {
      location: { href: "https://resdex.naukri.com/v3/search?x=1" },
      addEventListener() {},
      getSelection() { return { removeAllRanges() {} }; },
      HTMLInputElement: { prototype: {} },
    },
    document: fakeDocument,
    chrome: undefined,
    console,
    setTimeout,
    Date,
  };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: "content.js" });
  return sandbox;
}

function buildCandidateCard({ name, title, company, location, skillNames = [], experienceText = "" }) {
  const anchor = new FakeEl({ tag: "a", className: "candidateName", text: name, href: `https://resdex.naukri.com/profile/abc?candidateId=${encodeURIComponent(name)}` });
  const titleEl = title ? new FakeEl({ tag: "span", className: "designation", text: title }) : null;
  const companyEl = company ? new FakeEl({ tag: "span", className: "company", text: company }) : null;
  const locationEl = location ? new FakeEl({ tag: "span", className: "location", text: location }) : null;
  const skillEls = skillNames.map((s) => new FakeEl({ tag: "span", className: "skill-chip", text: s }));
  const expEl = experienceText ? new FakeEl({ tag: "span", className: "meta", text: experienceText }) : null;

  const children = [anchor, titleEl, companyEl, locationEl, expEl, ...skillEls].filter(Boolean);
  // Card container needs >=3 children within 6 ancestor levels for the anchor-walk heuristic to select it.
  const card = new FakeEl({ tag: "div", className: "candidateCard", children });
  return { card, anchor };
}

test("extractOneCandidate pulls all fields when present, and only the ones present when not", () => {
  const sandbox = loadContentJsSandbox();
  const { card, anchor } = buildCandidateCard({
    name: "Ravi Kumar",
    title: "Senior Python Developer",
    company: "TCS",
    location: "Bengaluru",
    skillNames: ["Python", "Django"],
    experienceText: "6 yrs 2 months experience",
  });

  const candidate = sandbox.extractOneCandidate(card, anchor);
  assert.equal(candidate.name, "Ravi Kumar");
  assert.equal(candidate.title, "Senior Python Developer");
  assert.equal(candidate.company, "TCS");
  assert.equal(candidate.location, "Bengaluru");
  assert.equal(JSON.stringify(candidate.skills), JSON.stringify(["Python", "Django"]));
  assert.match(candidate.experience, /6\s*yrs/i);
  assert.equal(candidate.profile_url, anchor.href);
  assert.equal(candidate.resdex_candidate_id, "Ravi Kumar");

  const sparse = buildCandidateCard({ name: "Priya Singh" });
  const sparseCandidate = sandbox.extractOneCandidate(sparse.card, sparse.anchor);
  assert.equal(sparseCandidate.name, "Priya Singh");
  assert.equal(sparseCandidate.title, null);
  assert.equal(sparseCandidate.company, null);
  assert.equal(JSON.stringify(sparseCandidate.skills), JSON.stringify([]));
});

test("extractOneCandidate returns null (fail-soft, not throw) when no name can be derived", () => {
  const sandbox = loadContentJsSandbox();
  const emptyCard = new FakeEl({ tag: "div", className: "candidateCard", children: [] });
  assert.equal(sandbox.extractOneCandidate(emptyCard, null), null);
});

test("extractCandidatesFromResultsPage isolates a per-container error: one bad card doesn't stop the others", () => {
  const good1 = buildCandidateCard({ name: "Ravi Kumar", title: "Dev" });
  const good2 = buildCandidateCard({ name: "Priya Singh", company: "Acme" });

  // A "poisoned" container whose querySelectorAll throws, simulating an unexpected DOM shape.
  const poisoned = new FakeEl({ tag: "div", className: "candidateCard", children: [
    new FakeEl({ tag: "a", className: "candidateName", text: "Broken Candidate", href: "https://x/broken" }),
  ] });
  poisoned.querySelectorAll = () => { throw new Error("unexpected DOM shape"); };

  const sandbox = loadContentJsSandbox({
    "profile": [good1.anchor, poisoned.children[0]],
  });

  // Wire up parentElement chains so the anchor-walk in findCandidateContainers lands on our cards.
  good1.anchor.parentElement = good1.card;
  poisoned.children[0].parentElement = poisoned;
  // Second good candidate's anchor is found via the fallback generic-card path in this simplified fixture,
  // so instead we directly exercise extractCandidatesFromResultsPage's aggregation via two anchors both
  // resolving through the profile-link strategy.
  good2.anchor.parentElement = good2.card;
  sandbox.document.querySelectorAll = (selector) => {
    if (selector.includes("profile")) return [good1.anchor, good2.anchor, poisoned.children[0]];
    return [];
  };

  const { candidates, diagnostics } = sandbox.extractCandidatesFromResultsPage();

  assert.equal(diagnostics.containers_detected, 3);
  assert.equal(candidates.length, 2, "the poisoned container must be skipped, not abort the whole batch");
  const names = candidates.map((c) => c.name).sort();
  assert.equal(JSON.stringify(names), JSON.stringify(["Priya Singh", "Ravi Kumar"]));
  assert.ok(diagnostics.warnings.some((w) => w.includes("Extraction error")), "the poisoned container's failure must be recorded in diagnostics");
  assert.equal(diagnostics.selector_strategy, "profile-link-anchor");
});

test("findCandidateContainers falls back to generic card selectors and reports it when no profile links exist", () => {
  const cardA = new FakeEl({ tag: "div", className: "resultCard", children: [
    new FakeEl({ tag: "span", className: "name", text: "No Link Person" }),
  ], visible: true });

  const sandbox = loadContentJsSandbox();
  sandbox.document.querySelectorAll = (selector) => {
    if (selector.trim().startsWith("a[")) return []; // PROFILE_LINK_SELECTORS: no anchors at all
    if (selector.includes("resultCard")) return [cardA]; // GENERIC_CARD_SELECTORS fallback
    return [];
  };

  const result = sandbox.findCandidateContainers();
  assert.equal(result.strategy, "generic-card-class");
  assert.equal(result.pairs.length, 1);
  assert.equal(result.pairs[0].anchor, null);
  assert.ok(result.warnings.some((w) => w.includes("profile_url will be unavailable")));
});
