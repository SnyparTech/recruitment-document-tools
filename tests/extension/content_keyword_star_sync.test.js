/**
 * Regression test for a real bug report: un-marking a keyword as mandatory
 * on the profile-bot website didn't change anything on the live Resdex form
 * — only promoting a keyword TO mandatory ever worked.
 *
 * Root cause: the star-detection in syncKeywordStarsOnForm/clickKeywordStar
 * (a) fell back to a blind `svg, button` selector, which could grab a chip's
 * delete/remove icon instead of its actual mandatory-star toggle, and
 * (b) only recognized "active" via a narrow class-name substring check, so
 * if that never matched the real markup, isActive was permanently false —
 * meaning the demote-to-preferred case (isActive false !== want false) never
 * fired a click, while the promote-to-required case accidentally still did.
 *
 * Fix: findMandatoryStarInChip() excludes remove/delete/close-labeled
 * elements and doesn't blindly fall back to any svg/button; isStarMarkedMandatory()
 * checks multiple independent signals (aria-pressed, aria-checked,
 * data-active, several class-name patterns, and title/aria-label phrasing).
 *
 * Run with: node --test tests/extension/content_keyword_star_sync.test.js
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
    this._clicked = false;
  }
  get textContent() {
    if (this._text) return this._text;
    return this.children.map((c) => c.textContent).join(" ");
  }
  getAttribute(name) { return this._attrs[name] ?? null; }
  querySelectorAll(selector) {
    const all = [];
    const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
    walk(this);
    const lower = selector.toLowerCase();
    if (lower.includes("star") || lower.includes("mandatory") || lower.includes("must have")) {
      return all.filter((el) =>
        /star/i.test(el.className) ||
        /mandatory|must have/i.test((el._attrs.title || "")) ||
        /mandatory|must have/i.test((el._attrs["title"] || ""))
      );
    }
    if (lower.includes("chip") || lower.includes("tag") || lower.includes("pill") || lower.includes("tuple")) {
      return all.filter((el) => el._isChip);
    }
    return [];
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  click() { this._clicked = true; }
}

function loadSandbox(chips) {
  const sandbox = {
    window: { location: { href: "" }, addEventListener() {}, getSelection() { return { removeAllRanges() {} }; }, HTMLInputElement: { prototype: {} } },
    document: {
      readyState: "loading",
      addEventListener() {},
      getElementById() { return null; },
      querySelector() { return null; },
      querySelectorAll(selector) {
        const lower = selector.toLowerCase();
        if (lower.includes("chip") || lower.includes("tag") || lower.includes("pill") || lower.includes("tuple")) {
          return chips;
        }
        return [];
      },
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

function chipWithStarAndDeleteIcon(text, { starActive }) {
  const star = new FakeEl({
    tag: "button",
    className: starActive ? "star-icon active" : "star-icon",
    attrs: { title: "Mark as mandatory" },
  });
  // The delete/remove icon is also a <button>, placed BEFORE the star in DOM
  // order — this is exactly the shape that used to fool the old blind
  // `svg, button` fallback into grabbing the wrong element.
  const deleteBtn = new FakeEl({ tag: "button", className: "chip-remove-btn", attrs: { title: "Remove keyword" } });
  const chip = new FakeEl({ tag: "span", className: "chip-item", children: [deleteBtn, star] });
  chip._text = text;
  chip._isChip = true;
  chip._star = star;
  chip._deleteBtn = deleteBtn;
  return chip;
}

test("syncKeywordStarsOnForm clicks the star (not the delete button) to DEMOTE a currently-mandatory keyword", async () => {
  const chip = chipWithStarAndDeleteIcon("Python", { starActive: true });
  const sandbox = loadSandbox([chip]);

  const plan = { keywords: { required: [], preferred: ["Python"] } };
  const toggled = await sandbox.syncKeywordStarsOnForm(plan);

  assert.equal(toggled, 1, "must detect the demote as a real change");
  assert.equal(chip._star._clicked, true, "must click the actual star element");
  assert.equal(chip._deleteBtn._clicked, false, "must never click the delete/remove button");
});

test("syncKeywordStarsOnForm clicks the star to PROMOTE a currently-not-mandatory keyword", async () => {
  const chip = chipWithStarAndDeleteIcon("Django", { starActive: false });
  const sandbox = loadSandbox([chip]);

  const plan = { keywords: { required: ["Django"], preferred: [] } };
  const toggled = await sandbox.syncKeywordStarsOnForm(plan);

  assert.equal(toggled, 1);
  assert.equal(chip._star._clicked, true);
});

test("syncKeywordStarsOnForm does not click anything when state already matches", async () => {
  const alreadyRequired = chipWithStarAndDeleteIcon("Python", { starActive: true });
  const alreadyPreferred = chipWithStarAndDeleteIcon("Django", { starActive: false });
  const sandbox = loadSandbox([alreadyRequired, alreadyPreferred]);

  const plan = { keywords: { required: ["Python"], preferred: ["Django"] } };
  const toggled = await sandbox.syncKeywordStarsOnForm(plan);

  assert.equal(toggled, 0);
  assert.equal(alreadyRequired._star._clicked, false);
  assert.equal(alreadyPreferred._star._clicked, false);
});

test("waitForKeywordChipsReady polls until chips actually hydrate instead of seeing an empty form", async () => {
  // Reproduces a real bug: right after a Modify navigation, the keyword
  // INPUT renders well before Naukri re-hydrates the form's pre-existing
  // keyword CHIPS. waitForFormReady only checks for the input, so
  // syncKeywordStarsOnForm ran against a form with zero chips — not
  // "nothing needed changing", genuinely nothing there yet — confirmed
  // live via "Synced live Resdex keywords to website draft:
  // {required: Array(0), preferred: Array(0)}" right after a real sync.
  let chips = [];
  const sandbox = loadSandbox([]);
  sandbox.document.querySelectorAll = (selector) => {
    const lower = selector.toLowerCase();
    if (lower.includes("chip") || lower.includes("tag") || lower.includes("pill") || lower.includes("tuple")) {
      return chips;
    }
    return [];
  };

  setTimeout(() => {
    const realChip = new FakeEl({ tag: "span", className: "chip-item", text: "Python" });
    realChip._isChip = true;
    chips = [realChip];
  }, 250);

  const ready = await sandbox.waitForKeywordChipsReady(2000);
  assert.equal(ready, true, "must wait for chips to actually appear rather than giving up immediately");
});

test("waitForKeywordChipsReady times out honestly if chips never appear", async () => {
  const sandbox = loadSandbox([]);
  const ready = await sandbox.waitForKeywordChipsReady(300);
  assert.equal(ready, false);
});

test("getLeafChipElements excludes a genuine multi-chip wrapper but keeps a real chip whose own star/remove icon coincidentally matches the chip selector", () => {
  // Reproduces a real bug report: Resdex wraps an "AI suggested keywords...
  // Press 'Ctrl' to mark mandatory" instructional block in a container
  // whose class matches the chip selector too, nesting several real chips
  // inside it — textContent on that wrapper concatenates the hint text
  // with every nested chip's label, no separators. The first fix (exclude
  // ANY element with a matching descendant) caused a regression: a real
  // chip's own star/remove icon can share a "tag"/"chip"-style class
  // (isChip=true on the icon below, simulating that), which wrongly
  // excluded the whole real chip too — nothing ever got toggled or synced.
  const starIconSharingChipClass = new FakeEl({ tag: "span", className: "chip-star-icon", text: "" });
  starIconSharingChipClass._isChip = true; // the exact coincidental-overlap scenario
  const realChip = new FakeEl({ tag: "span", className: "chip-item", text: "Python", children: [starIconSharingChipClass] });
  realChip._isChip = true;

  const nestedKeywordChips = ["SAP", "Sap Hana", "SCM"].map((t) => {
    const c = new FakeEl({ tag: "span", className: "chip-item", text: t });
    c._isChip = true;
    return c;
  });
  const instructionalWrapper = new FakeEl({
    tag: "div",
    className: "tag-list",
    text: "AI suggested keywordsPress 'Ctrl' while selecting a keyword to mark it mandatory",
    children: nestedKeywordChips,
  });
  instructionalWrapper._isChip = true;

  const sandbox = loadSandbox([]);
  const leaves = sandbox.getLeafChipElements({
    querySelectorAll: (selector) => {
      const lower = selector.toLowerCase();
      if (lower.includes("chip") || lower.includes("tag") || lower.includes("pill") || lower.includes("tuple")) {
        const all = [];
        const walk = (el) => { for (const c of el.children) { all.push(c); walk(c); } };
        walk({ children: [realChip, instructionalWrapper] });
        return [realChip, starIconSharingChipClass, instructionalWrapper, ...nestedKeywordChips].filter((el) => el._isChip);
      }
      return [];
    },
  });

  assert.ok(leaves.includes(realChip), "a real chip with one coincidentally-matching icon must still count as a leaf");
  assert.ok(!leaves.includes(instructionalWrapper), "the multi-chip instructional wrapper must be excluded");
  assert.ok(!leaves.some((el) => /ai suggested/i.test(el.textContent)), "nothing with the instructional text should survive");
});

test("syncKeywordStarsOnForm doesn't warn or misfire when a chip's inner label independently matches the chip selector too", () => {
  // Reproduces a real live-console bug: for EVERY keyword, Resdex's chip
  // markup has a label span (e.g. class="tag-label ellipsis") that matches
  // the same broad chip selector as a SIBLING-level match alongside the
  // real interactive chip (which has the star) — not nested inside it, so
  // getLeafChipElements' "no nested match" check doesn't catch it. Both
  // elements carry the same keyword text; only the real one has a star.
  const star = new FakeEl({ tag: "button", className: "star-tag-wrapper naukri-btn-tertiary naukri-btn-zero" });
  const realChip = new FakeEl({ tag: "span", className: "chip-item", text: "Sap Btp", children: [star] });
  realChip._isChip = true;
  const labelOnlySibling = new FakeEl({ tag: "span", className: "tag-label ellipsis", text: "Sap Btp" });
  labelOnlySibling._isChip = true;

  const sandbox = loadSandbox([realChip, labelOnlySibling]);
  const warnings = [];
  sandbox.console = { ...console, warn: (...args) => warnings.push(args) };

  const plan = { keywords: { required: ["Sap Btp"], preferred: [] } };
  return sandbox.syncKeywordStarsOnForm(plan).then((toggled) => {
    assert.equal(toggled, 1, "the real chip's star must still get toggled");
    assert.equal(star._clicked, true);
    assert.equal(warnings.length, 0, "the label-only duplicate must not produce a spurious 'no star found' warning");
  });
});

test("isStarMarkedMandatory recognizes aria-pressed/aria-checked/data-active even without a matching class name", () => {
  const sandbox = loadSandbox([]);
  const byAriaPressed = new FakeEl({ tag: "button", className: "icon-xyz", attrs: { "aria-pressed": "true" } });
  const byAriaChecked = new FakeEl({ tag: "button", className: "icon-xyz", attrs: { "aria-checked": "true" } });
  const byDataActive = new FakeEl({ tag: "button", className: "icon-xyz", attrs: { "data-active": "true" } });
  const inactive = new FakeEl({ tag: "button", className: "icon-xyz", attrs: {} });

  assert.equal(sandbox.isStarMarkedMandatory(byAriaPressed), true);
  assert.equal(sandbox.isStarMarkedMandatory(byAriaChecked), true);
  assert.equal(sandbox.isStarMarkedMandatory(byDataActive), true);
  assert.equal(sandbox.isStarMarkedMandatory(inactive), false);
});
