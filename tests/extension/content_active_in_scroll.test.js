/**
 * Regression test for a real bug: Active In got set to "1 day" instead of
 * "15 days" because the option list only renders a few items at a time —
 * "15 days" (5th in the list: "All resumes", "1 day", "3 days", "7 days",
 * "15 days", ...) isn't in the DOM right after opening, so the old
 * findOpt()-only search never saw it. Fix: scroll the list's own internal
 * scroll container in steps, re-checking after each, until the real target
 * either renders or the list bottoms out.
 *
 * This drives the ACTUAL setActiveIn() against a synthetic fake DOM that
 * simulates lazy/virtualized rendering: "15 days" only becomes "visible"
 * (offsetParent !== null) once the scroll container's scrollTop passes a
 * threshold, same as a real virtualized list would behave.
 *
 * Run with: node --test tests/extension/content_active_in_scroll.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

class FakeEl {
  constructor({ tag = "div", className = "", text = "", attrs = {}, children = [] } = {}) {
    this.tagName = tag.toUpperCase();
    this.className = className;
    this._text = text;
    this._attrs = { ...attrs };
    this.children = children;
    children.forEach((c) => (c.parentElement = this));
    this.parentElement = null;
    this._scrollTop = 0;
    this._visible = true;
  }
  get offsetParent() { return this._visible ? {} : null; }
  get textContent() {
    if (this._text) return this._text;
    return this.children.map((c) => c.textContent).join(" ");
  }
  get scrollTop() { return this._scrollTop; }
  set scrollTop(v) { this._scrollTop = v; }
  getAttribute(name) { return this._attrs[name] ?? null; }
  setAttribute(name, value) { this._attrs[name] = String(value); }
  closest(selector) {
    let el = this;
    while (el) {
      if (selector.includes("li") && el.tagName === "LI") return el;
      if (selector.includes("custom-scroll") && (el.className || "").includes("custom-scroll")) return el;
      el = el.parentElement;
    }
    return null;
  }
  querySelectorAll(selector) {
    const all = [];
    const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
    walk(this);
    if (selector.includes("aria-owns") || selector.includes("aria-controls")) return [];
    return all.filter((el) => {
      if (selector.includes("li") && el.tagName === "LI") return true;
      return false;
    });
  }
  querySelector(selector) {
    if (selector.includes("i.ico-expand")) {
      const all = [];
      const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
      walk(this);
      return all.find((e) => (e.className || "").includes("ico-expand")) || null;
    }
    if (selector.includes("naukri-suggestor-wrapper")) {
      const all = [];
      const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
      walk(this);
      return all.find((e) => (e.className || "").includes("naukri-suggestor-wrapper")) || null;
    }
    if (selector.includes("selected-value")) {
      const all = [];
      const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
      walk(this);
      return all.find((e) => (e.className || "").includes("selected-value")) || null;
    }
    return this.querySelectorAll(selector)[0] || null;
  }
  scrollIntoView() {}
  focus() {}
  click() {
    this.setAttribute("aria-expanded", "true"); // opening the real dropdown flips this
  }
  dispatchEvent(evt) {
    if ((evt.type === "keydown" || evt.type === "click") && (evt.key === "Enter" || evt.key === undefined)) {
      this.setAttribute("aria-expanded", "true");
    }
    return true;
  }
}

function buildActiveInWrap({ revealAfterScrollTop = 180 } = {}) {
  const selectedValueSpan = new FakeEl({ tag: "span", className: "selected-value", text: "6 months" });
  const icon = new FakeEl({ tag: "i", className: "ico ico-expand" });
  const opener = new FakeEl({
    tag: "div",
    className: "naukri-suggestor-wrapper drop-down",
    attrs: { "aria-expanded": "false", "aria-haspopup": "listbox", role: "button", tabindex: "0" },
    children: [icon, selectedValueSpan],
  });

  const allOptionLabels = ["All resumes", "1 day", "3 days", "7 days", "15 days", "30 days"];
  const optionEls = allOptionLabels.map((label) => new FakeEl({ tag: "li", text: label }));
  // Simulate virtualization: only the first 2 items ("All resumes", "1 day")
  // are "rendered" (visible) until the list is scrolled.
  optionEls.forEach((el, i) => { el._visible = i < 2; });

  const scrollArea = new FakeEl({ tag: "div", className: "custom-scroll-area", children: optionEls });
  // Reveal more items as scrollTop increases, mimicking lazy rendering.
  Object.defineProperty(scrollArea, "scrollTop", {
    get() { return this._scrollTop || 0; },
    set(v) {
      this._scrollTop = v;
      const revealCount = Math.min(optionEls.length, 2 + Math.floor(v / 90));
      optionEls.forEach((el, i) => { el._visible = i < revealCount; });
    },
  });

  const wrap = new FakeEl({
    tag: "div",
    className: "active-in-wrap",
    children: [opener, scrollArea],
  });
  return { wrap, opener, scrollArea, optionEls, selectedValueSpan };
}

function loadSandbox(wrap, scrollArea) {
  // findOpt() (in the real content.js) searches `document` (not scoped to
  // `wrap`), since in a real page `wrap` is attached to the live document
  // tree. Mimic that here by walking `wrap` for document-level queries too.
  const walkAll = (root) => {
    const all = [];
    const walk = (el) => { for (const c of el.children || []) { all.push(c); walk(c); } };
    walk(root);
    return all;
  };

  const sandbox = {
    window: { location: { href: "" }, addEventListener() {}, getSelection() { return { removeAllRanges() {} }; }, HTMLInputElement: { prototype: {} } },
    document: {
      readyState: "loading",
      addEventListener() {},
      getElementById() { return null; },
      activeElement: { blur() {} },
      querySelector(selector) {
        if (selector.includes("active-in-wrap")) return wrap;
        if (selector.includes("custom-scroll")) return scrollArea;
        return null;
      },
      querySelectorAll(selector) {
        if (selector.includes("li")) return walkAll(wrap).filter((el) => el.tagName === "LI");
        return [];
      },
      body: { appendChild() {} },
    },
    chrome: undefined,
    console,
    setTimeout,
    Date,
    Event: class { constructor(type, opts) { this.type = type; Object.assign(this, opts); } },
    MouseEvent: class { constructor(type, opts) { this.type = type; Object.assign(this, opts); } },
    KeyboardEvent: class { constructor(type, opts) { this.type = type; Object.assign(this, opts); } },
  };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: "content.js" });
  return sandbox;
}

test("setActiveIn finds and selects an option that only renders after scrolling, instead of settling for an earlier wrong one", async () => {
  const { wrap, scrollArea, selectedValueSpan } = buildActiveInWrap();
  const sandbox = loadSandbox(wrap, scrollArea);

  // Selecting an option updates the displayed value, same as the real widget.
  for (const el of scrollArea.children) {
    const originalClick = el.click.bind(el);
    el.click = () => { selectedValueSpan._text = el.textContent; originalClick(); };
  }

  const result = await sandbox.setActiveIn("15 days");

  assert.equal(result, true, "must succeed once '15 days' renders after scrolling");
  assert.equal(selectedValueSpan.textContent, "15 days", "must select the real target, not an earlier-rendered wrong option like '1 day'");
});
