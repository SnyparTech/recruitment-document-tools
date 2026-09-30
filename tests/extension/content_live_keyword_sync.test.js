/**
 * Tests for reading live keyword chips directly from the Resdex form
 * (readLiveKeywordsFromResdex) — the Resdex -> website direction of keyword
 * sync. Star state on a chip determines required vs preferred, same
 * detection logic as clickKeywordStar.
 *
 * Run with: node --test tests/extension/content_live_keyword_sync.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

class FakeEl {
  constructor({ tag = "div", className = "", text = "", children = [] } = {}) {
    this.tagName = tag.toUpperCase();
    this.className = className;
    this._text = text;
    this.children = children;
    children.forEach((c) => (c.parentElement = this));
    this.parentElement = null;
    this.offsetParent = {};
  }
  get textContent() {
    if (this._text) return this._text;
    return this.children.map((c) => c.textContent).join(" ");
  }
  querySelectorAll(selector) {
    const all = [];
    const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
    walk(this);
    if (selector.includes("chip") || selector.includes("tag") || selector.includes("pill") || selector.includes("tuple")) {
      return all.filter((el) => /chip|tag|pill|tuple/i.test(el.className) || el._isChip);
    }
    if (selector.includes("star") || selector.includes("Mandatory")) {
      return all.filter((el) => /star/i.test(el.className));
    }
    return [];
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest() { return null; } // forces getKeywordContainer's parentElement fallback
  getAttribute() { return null; }
}

function chipEl(text, { starred = null } = {}) {
  const children = [];
  if (starred !== null) {
    children.push(new FakeEl({ tag: "svg", className: starred ? "star-icon active" : "star-icon" }));
  }
  const chip = new FakeEl({ tag: "span", className: "chip-item", children });
  chip._text = text; // override getter to include only the label, not the star's own text
  chip._isChip = true;
  return chip;
}

function loadSandbox(chips) {
  const kwInput = new FakeEl({ tag: "input", className: "keyword-input" });
  const container = new FakeEl({ tag: "div", className: "chip-container", children: [kwInput, ...chips] });
  kwInput.parentElement = container;

  const sandbox = {
    window: { location: { href: "" }, addEventListener() {}, getSelection() { return { removeAllRanges() {} }; }, HTMLInputElement: { prototype: {} } },
    document: {
      readyState: "loading",
      addEventListener() {},
      getElementById() { return null; },
      querySelector(selector) {
        if (selector.trim().startsWith("input[")) return kwInput;
        return null;
      },
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

test("readLiveKeywordsFromResdex splits chips into required (starred) vs preferred (not starred)", () => {
  const chips = [
    chipEl("Python", { starred: true }),
    chipEl("Django", { starred: false }),
    chipEl("FastAPI", { starred: true }),
  ];
  const sandbox = loadSandbox(chips);

  const result = sandbox.readLiveKeywordsFromResdex();

  assert.equal(JSON.stringify([...result.required].sort()), JSON.stringify(["FastAPI", "Python"]));
  assert.equal(JSON.stringify(result.preferred), JSON.stringify(["Django"]));
});

test("readLiveKeywordsFromResdex reflects a manually removed chip (fewer chips than the bot originally typed)", () => {
  // Simulates HR deleting a chip directly in Resdex after the bot filled 3 keywords.
  const chips = [chipEl("Python", { starred: true })];
  const sandbox = loadSandbox(chips);

  const result = sandbox.readLiveKeywordsFromResdex();

  assert.equal(JSON.stringify(result.required), JSON.stringify(["Python"]));
  assert.equal(JSON.stringify(result.preferred), JSON.stringify([]));
});

test("readLiveKeywordsFromResdex returns null when no keyword input is found on the page", () => {
  const sandbox = loadSandbox([]);
  sandbox.document.querySelector = () => null;
  assert.equal(sandbox.readLiveKeywordsFromResdex(), null);
});
