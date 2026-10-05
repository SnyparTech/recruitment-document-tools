/**
 * Regression test for a real UX gap: Naukri's AI-generated candidate summary
 * is truncated in the DOM ("...Chang...") and only shows its full text in a
 * tooltip that Resdex renders on mouse hover (confirmed via user screenshots).
 * The old extractAiSummary() only ever read the static (truncated) title
 * attribute. Fix: detect truncation, simulate a real hover event sequence,
 * read whatever tooltip-like element appears, and use it if it's longer than
 * the truncated excerpt — falling back to the static text otherwise so
 * non-truncated / no-tooltip cases don't regress.
 *
 * Run with: node --test tests/extension/content_ai_summary_hover.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const contentJsPath = path.join(__dirname, "..", "..", "extension", "content.js");
const source = fs.readFileSync(contentJsPath, "utf-8");

class FakeEl {
  constructor({ tag = "div", className = "", text = "", attrs = {}, children = [], visible = true } = {}) {
    this.tagName = tag.toUpperCase();
    this.className = className;
    this._text = text;
    this._attrs = { ...attrs };
    this.children = children;
    children.forEach((c) => (c.parentElement = this));
    this.parentElement = null;
    this._visible = visible;
    this._listeners = {};
  }
  get offsetParent() { return this._visible ? {} : null; }
  get textContent() {
    if (this._text) return this._text;
    return this.children.map((c) => c.textContent).join(" ");
  }
  getAttribute(name) { return this._attrs[name] ?? null; }
  setAttribute(name, value) { this._attrs[name] = String(value); }
  querySelectorAll(selector) {
    const all = [];
    const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
    walk(this);
    if (selector.includes("candidate-profile-summary")) {
      return all.filter((el) => (el.className || "").includes("candidate-profile-summary"));
    }
    return [];
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
  dispatchEvent(evt) {
    (this._listeners[evt.type] || []).forEach((fn) => fn(evt));
    return true;
  }
  addEventListener(type, fn) {
    this._listeners[type] = this._listeners[type] || [];
    this._listeners[type].push(fn);
  }
}

function loadSandbox({ onTriggerHover } = {}) {
  const tooltipHost = new FakeEl({ tag: "div", className: "doc-body" });

  const sandbox = {
    window: { location: { href: "" }, addEventListener() {}, getSelection() { return { removeAllRanges() {} }; }, HTMLInputElement: { prototype: {} } },
    document: {
      readyState: "loading",
      addEventListener() {},
      getElementById() { return null; },
      querySelector() { return null; },
      querySelectorAll(selector) {
        if (selector.includes("tooltip")) return tooltipHost.children.filter((el) => el._visible);
        return [];
      },
      body: { appendChild() {} },
      activeElement: null,
    },
    chrome: undefined,
    console,
    setTimeout,
    Date,
    MouseEvent: class { constructor(type, opts) { this.type = type; Object.assign(this, opts); } },
  };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: "content.js" });
  return { sandbox, tooltipHost };
}

test("extractAiSummary uses the full hover-revealed tooltip text when the static title is truncated", async () => {
  const fullText = "ServiceNow, ITSM, ITOM, CMDB, Incident Management, Change Management, Problem Management, Service Catalog, JavaScript, Glide API, Flow Designer, Service Portal, REST API, SOAP, LDAP, SSO, MID Server, Discovery, Service Mapping, ACL, Agile Scrum, UAT.";
  const truncated = "ServiceNow, ITSM, ITOM, CMDB, Incident Management, Chang...";

  const { sandbox, tooltipHost } = loadSandbox();
  const trigger = new FakeEl({
    tag: "a",
    className: "candidate-profile-summary link ext",
    attrs: { title: truncated },
  });
  const container = new FakeEl({ tag: "div", className: "candidateCard", children: [trigger] });

  trigger.addEventListener("mouseover", () => {
    const tip = new FakeEl({ tag: "div", className: "naukri-tooltip", text: fullText, visible: true });
    tooltipHost.children.push(tip);
  });

  const summary = await sandbox.extractAiSummary(container);
  assert.equal(summary, fullText);
});

test("extractAiSummary falls back to the static title when no tooltip appears on hover", async () => {
  const truncated = "ServiceNow, ITSM, ITOM, CMDB, Incident Management, Chang...";
  const { sandbox } = loadSandbox();
  const trigger = new FakeEl({
    tag: "a",
    className: "candidate-profile-summary link ext",
    attrs: { title: truncated },
  });
  const container = new FakeEl({ tag: "div", className: "candidateCard", children: [trigger] });

  const summary = await sandbox.extractAiSummary(container);
  assert.equal(summary, truncated, "must not regress below the already-available static text");
});

test("extractAiSummary skips the hover simulation entirely when the static text isn't truncated", async () => {
  const complete = "Python, Django, REST API.";
  const { sandbox } = loadSandbox();
  let hovered = false;
  const trigger = new FakeEl({
    tag: "a",
    className: "candidate-profile-summary link ext",
    attrs: { title: complete },
  });
  trigger.addEventListener("mouseover", () => { hovered = true; });
  const container = new FakeEl({ tag: "div", className: "candidateCard", children: [trigger] });

  const summary = await sandbox.extractAiSummary(container);
  assert.equal(summary, complete);
  assert.equal(hovered, false, "no need to hover when the static text already looks complete");
});

test("extractAiSummary returns null when there is no AI-summary element at all", async () => {
  const { sandbox } = loadSandbox();
  const container = new FakeEl({ tag: "div", className: "candidateCard", children: [] });
  assert.equal(await sandbox.extractAiSummary(container), null);
});
