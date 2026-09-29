/**
 * Tests for pause/resume of the auto-pagination walk in extension/content.js.
 *
 * Pagination advances by full page navigation (window.location.href = ...),
 * which wipes any in-memory flag — so pausing it (unlike form-fill pausing,
 * which uses the in-memory `isPaused`) has to persist across that navigation
 * via sessionStorage. This drives the real extractAndSubmitOnce() with a
 * mocked backend and a synthetic candidate card (same pattern as
 * content_candidate_extraction.test.js) to prove: pausing mid-walk stores
 * the next-page URL and does NOT navigate; the saved URL is what Resume
 * would navigate to.
 *
 * Run with: node --test tests/extension/content_pagination_pause.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

class FakeEl {
  constructor({ tag = "div", className = "", text = "", href = null, children = [] } = {}) {
    this.tagName = tag.toUpperCase();
    this.className = className;
    this._text = text;
    this.href = href;
    this.children = children;
    children.forEach((c) => (c.parentElement = this));
    this.parentElement = null;
    this.offsetParent = {};
  }
  get textContent() {
    if (this._text) return this._text;
    return this.children.map((c) => c.textContent).join(" ");
  }
  get innerText() { return this.textContent; }
  get outerHTML() { return this.textContent; }
  querySelectorAll(selector) {
    const all = [];
    const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
    walk(this);
    return all.filter((el) => selector.toLowerCase().includes(el.tagName.toLowerCase()));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  getAttribute() { return null; }
}

function makeSessionStorage() {
  const store = new Map();
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
}

function loadSandbox({ pageNo = 1, resultsCount = 40, initialSessionStorage = {} } = {}) {
  const anchor = new FakeEl({ tag: "a", className: "candidateName", text: "Test Candidate", href: "https://resdex.naukri.com/profile/1?candidateId=1" });
  const card = new FakeEl({ tag: "div", className: "candidateCard", children: [anchor] });
  anchor.parentElement = card;

  const sessionStorage = makeSessionStorage();
  for (const [k, v] of Object.entries(initialSessionStorage)) sessionStorage.setItem(k, v);

  const locationHref = { value: `https://resdex.naukri.com/v3/search?sid=abc123&pageNo=${pageNo}&resPerPage=40` };

  const sandbox = {
    window: {
      get location() {
        return {
          get href() { return locationHref.value; },
          set href(v) { locationHref.value = v; },
        };
      },
      addEventListener() {},
      getSelection() { return { removeAllRanges() {} }; },
      HTMLInputElement: { prototype: {} },
    },
    document: {
      readyState: "complete",
      body: { innerText: "Page 1 of 5", appendChild() {} },
      addEventListener() {},
      getElementById(id) {
        if (id === "snypar-resdex-floating-badge") return null; // let createFloatingWidget build it once
        return { addEventListener() {}, style: {}, innerText: "" }; // fake widget buttons/labels
      },
      querySelector() { return null; },
      querySelectorAll(selector) {
        if (selector.trim().startsWith("a[")) return [anchor];
        return [];
      },
      createElement() {
        return { addEventListener() {}, style: {}, appendChild() {} };
      },
      activeElement: null,
    },
    sessionStorage,
    localStorage: makeSessionStorage(),
    chrome: undefined,
    console,
    setTimeout,
    setInterval: () => {}, // don't actually start the 2s poll loop in tests
    Date,
    fetch: async (url, opts) => {
      if (String(url).includes("/search/results") && opts && opts.method === "POST") {
        return { ok: true, json: async () => ({ status: "success", total_stored: resultsCount }) };
      }
      return { ok: false };
    },
    URL,
  };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: "content.js" });
  return { sandbox, locationHrefRef: locationHref };
}

test("pausing mid-pagination stores the next-page URL and does not navigate", async () => {
  const { sandbox, locationHrefRef } = loadSandbox({
    pageNo: 1,
    resultsCount: 40, // == resPerPage, so NOT treated as the last (short) page
    initialSessionStorage: {
      snypar_autopage_active: "1",
      snypar_pagination_paused: "1", // operator already clicked Pause
    },
  });

  const startingHref = locationHrefRef.value;
  await sandbox.extractAndSubmitOnce(startingHref);

  assert.equal(locationHrefRef.value, startingHref, "must NOT navigate while paused");
  assert.equal(sandbox.sessionStorage.getItem("snypar_pagination_paused"), "1");
  const savedNext = sandbox.sessionStorage.getItem("snypar_pagination_next_url");
  assert.ok(savedNext, "the next-page URL must be saved so Resume knows where to go");
  assert.ok(savedNext.includes("pageNo=2"), `expected saved URL to target page 2, got: ${savedNext}`);
});

test("when not paused, pagination navigates to the next page directly", async () => {
  const { sandbox, locationHrefRef } = loadSandbox({
    pageNo: 1,
    resultsCount: 40,
    initialSessionStorage: {
      snypar_autopage_active: "1",
    },
  });

  await sandbox.extractAndSubmitOnce(locationHrefRef.value);

  assert.ok(locationHrefRef.value.includes("pageNo=2"), `expected navigation to page 2, got: ${locationHrefRef.value}`);
  assert.equal(sandbox.sessionStorage.getItem("snypar_pagination_next_url"), null);
});
