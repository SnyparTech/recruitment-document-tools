/**
 * Snypar Resdex Form Auto-Filler Content Script
 * Runs inside the authenticated Naukri Resdex tab opened by Naukri Launcher.
 *
 * Strategy:
 *  - Each keyword is typed character-by-character, then confirmed with Enter / suggestion click
 *  - Before clicking "Search Candidates", verifies DOM state: chips exist for keywords,
 *    experience fields have values, etc. — NOT time-based.
 */

// Base backend hosts, tried in order. Kept as bases (not full endpoint URLs) so
// adding a new endpoint (e.g. /search/results) doesn't require a second,
// independently-drifting copy of this list — see fetchFromBackend/postToBackend.
const BACKEND_BASE_URLS = [
  "https://recruitment-document-tools.onrender.com",
  "http://127.0.0.1:8001",
  "http://localhost:8001",
];
let lastProcessedTimestamp = 0;
let isFilling = false;
let isPaused = false;
let lastFillCompletedAt = 0;
const FILL_COOLDOWN_MS = 90_000;
const FILL_CACHE_KEY = "snypar_last_fill_ts";

const RESDEX_FORM_URL = "https://resdex.naukri.com/v3?activeTab=advSrch";

function isOnResultsPage() {
  return window.location.href.includes("/v3/search");
}

function isOnFormPage() {
  return !isOnResultsPage();
}

async function fetchFromBackend(path) {
  for (const base of BACKEND_BASE_URLS) {
    try {
      const res = await fetch(base + path);
      if (res.ok) return await res.json();
    } catch (e) {}
  }
  return null;
}

async function postToBackend(path, body) {
  for (const base of BACKEND_BASE_URLS) {
    try {
      const res = await fetch(base + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) return await res.json();
      console.warn(`[Snypar Bot] POST ${path} to ${base} returned ${res.status}`);
    } catch (e) {}
  }
  return null;
}

// ─── Floating Status Widget ──────────────────────────────────────────────────

function createFloatingWidget() {
  if (document.getElementById("snypar-resdex-floating-badge")) return;
  const badge = document.createElement("div");
  badge.id = "snypar-resdex-floating-badge";
  badge.innerHTML = `
    <span class="snypar-badge-dot" id="snypar-dot"></span>
    <span id="snypar-status-text" style="font-weight:500;">⚡ Snypar Bot Active</span>
    <button class="snypar-badge-btn pause" id="snypar-pause-btn" style="display:none;" title="Pause auto-fill">⏸ Pause</button>
    <button class="snypar-badge-btn resume" id="snypar-resume-btn" style="display:none;" title="Resume auto-fill">▶ Resume</button>
  `;
  document.body.appendChild(badge);

  document.getElementById("snypar-pause-btn").addEventListener("click", () => {
    isPaused = true;
    updateWidgetStatus("⏸ Paused — click Resume to continue", "busy");
    showToast("⏸ Auto-fill paused. Click Resume to continue.");
  });

  document.getElementById("snypar-resume-btn").addEventListener("click", () => {
    isPaused = false;
    updateWidgetStatus("▶ Resuming...", "busy");
    showToast("▶ Auto-fill resumed.");
  });
}

function updateWidgetStatus(text, state = "online", buttonMode = "none") {
  const dot = document.getElementById("snypar-dot");
  const label = document.getElementById("snypar-status-text");
  const pauseBtn = document.getElementById("snypar-pause-btn");
  const resumeBtn = document.getElementById("snypar-resume-btn");
  if (!dot || !label) return;

  label.innerText = text;
  dot.className =
    "snypar-badge-dot " +
    (state === "offline" ? "offline" : state === "busy" ? "busy" : "");

  if (pauseBtn) pauseBtn.style.display  = buttonMode === "filling" ? "flex" : "none";
  if (resumeBtn) resumeBtn.style.display = buttonMode === "paused"  ? "flex" : "none";
}

function showToast(message) {
  const existing = document.querySelector(".snypar-toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = "snypar-toast";
  toast.innerText = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = "opacity 0.5s ease";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 500);
  }, 4000);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─── Per-Step Isolation & Diagnostics ────────────────────────────────────────
// Wraps each logical form-fill step (keywords, experience, location, ...) so a
// failure in one step (missing selector, unexpected exception) is recorded and
// logged but does NOT abort the remaining, independent steps. Pure function —
// no DOM access — so it's unit-testable without a browser/jsdom.
async function runStep(name, fn) {
  const start = Date.now();
  try {
    await fn();
    return { name, status: "ok", ms: Date.now() - start };
  } catch (err) {
    console.error(`[Snypar Bot] Step "${name}" failed:`, err);
    return { name, status: "failed", error: String(err && err.message || err), ms: Date.now() - start };
  }
}

function summarizeStepResults(results) {
  const failed = results.filter((r) => r.status === "failed");
  const ok = results.filter((r) => r.status === "ok");
  return { ok: ok.map((r) => r.name), failed: failed.map((r) => ({ name: r.name, error: r.error })) };
}

// Polls a selector's value instead of a blind fixed-duration sleep, so we move
// on as soon as the value is registered (React state committed) rather than
// always waiting the full timeout, while still being bounded.
async function waitForFieldValue(selector, expectedValue, timeoutMs = 1000, stepMs = 100) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const el = document.querySelector(selector);
    if (el && String(el.value) === String(expectedValue)) return true;
    await sleep(stepMs);
  }
  return fieldHasValue(selector);
}

async function pausableSleep(ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    await sleep(Math.min(300, end - Date.now()));
  }
  while (isPaused) {
    updateWidgetStatus("⏸ Paused — click Resume to continue", "busy", "paused");
    await sleep(300);
  }
}

// ─── React-Compatible Value Setter ──────────────────────────────────────────

function setNativeValue(el, value) {
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  ).set;
  nativeSetter.call(el, value);
}

// ─── Shared suggestion selectors ─────────────────────────────────────────────
const SUGGESTION_SELECTORS = [
  "div.sug-item", "li.sug-item", "span.sug-item",
  "div.sug-text", "span.sug-text",
  "div.tuple", "div.tuple-wrap", "span.tuple-wrap",
  "li.suggestion-item", "div.suggestion-item",
  "div.keyword-sug", "li.keyword-sug",
  "ul.suggestor-list li", "div.suggestor-list div",
  "li[role='option']", "div[role='option']",
  "div[class*='dropdown'] div", "div[class*='dropdown'] li", "div[class*='dropdown'] span",
  "div[class*='suggestor'] li", "div[class*='suggestor'] div", "div[class*='suggestor'] span",
  "div[class*='sugItem']", "li[class*='sugItem']", "span[class*='sugItem']",
  "div[class*='sug-container'] *",
  "div[class*='option']", "li[class*='option']",
  "div.location-item", "li.location-item",
  "[role='listbox'] [role='option']", "[role='listbox'] li", "[role='listbox'] div",
  "div[class*='dropdown-menu'] *",
  "div[class*='menu'] li", "div[class*='menu'] div",
  "div[class*='aiKeyword']", "span[class*='aiKeyword']", "button[class*='aiKeyword']",
  "div[class*='ai-keyword']", "span[class*='ai-keyword']", "button[class*='ai-keyword']",
  "div[class*='suggestedKeyword'] span", "div[class*='suggestedKeyword'] button", "div[class*='suggestedKeyword']",
  "div[class*='suggested-keyword'] span", "div[class*='suggested-keyword'] button", "div[class*='suggested-keyword']",
  "div[class*='keywordSuggest'] span", "div[class*='keywordSuggest'] button",
  "div[class*='aiSuggest'] span", "div[class*='aiSuggest'] button",
  "div[class*='recommend'] span", "div[class*='recommend'] button",
].join(", ");

async function waitForDropdown(maxMs = 1500) {
  const step = 150;
  let elapsed = 0;
  while (elapsed < maxMs) {
    await sleep(step);
    elapsed += step;
    const sugs = document.querySelectorAll(SUGGESTION_SELECTORS);
    if (Array.from(sugs).some(s => s.offsetParent !== null)) return true;
  }
  return false;
}

function clickBestSuggestion(targetText) {
  if (!targetText) return false;
  const target = targetText.toLowerCase().trim();
  const targetNorm = target.replace(/[^a-z0-9]/g, '');
  const tokens = target.split(/[\s\/\-_,]+/).filter(w => w.length >= 2);

  const all = Array.from(document.querySelectorAll(SUGGESTION_SELECTORS))
    .filter(s => s.offsetParent !== null && s.textContent.trim().length > 0);

  if (all.length === 0) return false;

  let bestScore = -1;
  let bestItem = null;

  for (const item of all) {
    const text = item.textContent.trim().toLowerCase();
    const textNorm = text.replace(/[^a-z0-9]/g, '');
    let score = 0;

    if (text === target) {
      score = 100;
    } else if (textNorm === targetNorm && targetNorm.length > 0) {
      score = 95;
    } else if (text.startsWith(target) || (targetNorm.length >= 3 && textNorm.startsWith(targetNorm))) {
      score = 80;
    } else if (text.includes(target) || (targetNorm.length >= 3 && textNorm.includes(targetNorm))) {
      score = 70;
    } else if (tokens.length > 0) {
      const matchTokens = tokens.filter(t => text.includes(t) || textNorm.includes(t));
      if (matchTokens.length > 0) {
        score = 40 + (matchTokens.length / tokens.length) * 30;
      }
    }

    if (score > bestScore) {
      bestScore = score;
      bestItem = item;
    }
  }

  if (bestItem && bestScore >= 40) {
    console.log(`[Snypar Bot] Selected suggestion: "${bestItem.textContent.trim()}" (score: ${Math.round(bestScore)}) for "${targetText}"`);
    bestItem.click();
    return true;
  }
  return false;
}

async function typeAndSelectFromDropdown(input, text, fieldLabel = '') {
  if (!text || !text.trim()) return false;
  const cleanText = text.trim();
  input.focus();
  await sleep(150);

  input.select();
  document.execCommand('selectAll');
  document.execCommand('delete');
  if (input.value) {
    setNativeValue(input, '');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
  await sleep(100);

  const inserted = document.execCommand('insertText', false, cleanText);
  if (!inserted || input.value !== cleanText) {
    setNativeValue(input, cleanText);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const appeared = await waitForDropdown(1500);
  console.log(`[Snypar Bot] ${fieldLabel} dropdown ${appeared ? '✓' : '✗'} for "${cleanText}"`);

  let selected = false;
  if (clickBestSuggestion(cleanText)) {
    await sleep(400);
    selected = true;
    console.log(`[Snypar Bot] ✓ "${cleanText}" selected (${fieldLabel})`);
  }

  if (!selected) {
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
    input.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
    input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
    await sleep(200);

    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new Event('blur', { bubbles: true }));
    console.log(`[Snypar Bot] ✓ Confirmed "${cleanText}" as custom ${fieldLabel}`);
  }

  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true }));
  await sleep(200);
  return true;
}

// ─── Keyword Helpers ─────────────────────────────────────────────────────────

function getKeywordContainer(kwInput) {
  return kwInput.closest(
    ".keyword-container, .chip-container, .input-container, .tags-input, .suggestor-wrapper, div[class*='keyword'], div[class*='chip'], div[class*='tag']"
  ) || kwInput.parentElement?.parentElement || kwInput.parentElement || document;
}

function countKeywordChipsInContainer(container) {
  const chips = container.querySelectorAll(
    "div[class*='chip'], span[class*='chip'], div[class*='tag'], span[class*='tag'], li[class*='chip'], li[class*='tag'], div[class*='pill'], span[class*='pill']"
  );
  return chips.length;
}

function hasKeywordChip(keyword) {
  if (!keyword) return false;
  const norm = keyword.toLowerCase().replace(/[^a-z0-9]/g, '');
  if (!norm) return false;
  const candidates = document.querySelectorAll(
    "div[class*='chip'], span[class*='chip'], div[class*='tag'], span[class*='tag'], li[class*='chip'], li[class*='tag'], div[class*='pill'], span[class*='pill'], [class*='tuple']"
  );
  for (const c of candidates) {
    const textNorm = c.textContent.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (textNorm.includes(norm)) {
      return true;
    }
  }
  return false;
}

async function typeAndConfirmKeyword(kwInput, keyword) {
  if (!keyword || !keyword.trim()) return;
  const cleanKw = keyword.trim();
  kwInput.focus();
  await sleep(150);

  kwInput.select();
  document.execCommand('selectAll');
  document.execCommand('delete');
  if (kwInput.value) {
    setNativeValue(kwInput, '');
    kwInput.dispatchEvent(new Event('input', { bubbles: true }));
  }
  await sleep(100);

  const inserted = document.execCommand('insertText', false, cleanKw);
  if (!inserted || kwInput.value !== cleanKw) {
    setNativeValue(kwInput, cleanKw);
    kwInput.dispatchEvent(new Event('input', { bubbles: true }));
    kwInput.dispatchEvent(new Event('change', { bubbles: true }));
  }
  await sleep(300);

  await waitForDropdown(1000);

  const container = getKeywordContainer(kwInput);
  const chipsBefore = countKeywordChipsInContainer(container);
  let confirmed = false;

  if (clickBestSuggestion(cleanKw)) {
    await sleep(400);
    if (hasKeywordChip(cleanKw) || countKeywordChipsInContainer(container) > chipsBefore || kwInput.value === '') {
      confirmed = true;
      console.log(`[Snypar Bot] ✓ "${cleanKw}" added via suggestion click`);
    }
  }

  if (!confirmed) {
    kwInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
    kwInput.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
    kwInput.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
    await sleep(350);

    if (hasKeywordChip(cleanKw) || countKeywordChipsInContainer(container) > chipsBefore || kwInput.value === '') {
      confirmed = true;
      console.log(`[Snypar Bot] ✓ "${cleanKw}" added via Enter key`);
    }
  }

  if (!confirmed) {
    kwInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', code: 'Tab', keyCode: 9, which: 9, bubbles: true, cancelable: true }));
    kwInput.dispatchEvent(new KeyboardEvent('keyup', { key: 'Tab', code: 'Tab', keyCode: 9, which: 9, bubbles: true, cancelable: true }));
    await sleep(300);

    if (hasKeywordChip(cleanKw) || countKeywordChipsInContainer(container) > chipsBefore || kwInput.value === '') {
      confirmed = true;
      console.log(`[Snypar Bot] ✓ "${cleanKw}" added via Tab key`);
    }
  }

  if (!confirmed) {
    document.execCommand('insertText', false, ',');
    kwInput.dispatchEvent(new KeyboardEvent('keydown', { key: ',', code: 'Comma', keyCode: 188, which: 188, bubbles: true, cancelable: true }));
    kwInput.dispatchEvent(new KeyboardEvent('keyup', { key: ',', code: 'Comma', keyCode: 188, which: 188, bubbles: true, cancelable: true }));
    await sleep(300);

    if (hasKeywordChip(cleanKw) || countKeywordChipsInContainer(container) > chipsBefore || kwInput.value === '') {
      confirmed = true;
      console.log(`[Snypar Bot] ✓ "${cleanKw}" added via comma`);
    }
  }

  if (confirmed || hasKeywordChip(cleanKw) || kwInput.value === '') {
    console.log(`[Snypar Bot] ✓ Keyword "${cleanKw}" successfully confirmed`);
  } else {
    kwInput.dispatchEvent(new Event('change', { bubbles: true }));
    kwInput.dispatchEvent(new Event('blur', { bubbles: true }));
    await sleep(200);

    if (hasKeywordChip(cleanKw) || kwInput.value === '') {
      console.log(`[Snypar Bot] ✓ Keyword "${cleanKw}" confirmed via blur`);
    } else {
      console.warn(`[Snypar Bot] ⚠ Keyword "${cleanKw}" could not be chipped; clearing input for next entry.`);
      kwInput.focus();
      kwInput.select();
      document.execCommand('selectAll');
      document.execCommand('delete');
    }
  }
  await sleep(150);
}

// ─── AI Suggested Keywords ───────────────────────────────────────────────────

async function selectRelevantAISuggestedKeywords(requiredKws, preferredKws, mandatorySet) {
  const allTargets = [...(requiredKws || []), ...(preferredKws || [])].map(k => k.toLowerCase().trim());
  if (allTargets.length === 0) return;

  const aiChipSelectors = [
    "div[class*='aiKeyword']", "span[class*='aiKeyword']", "button[class*='aiKeyword']",
    "div[class*='ai-keyword']", "span[class*='ai-keyword']", "button[class*='ai-keyword']",
    "div[class*='suggestedKeyword'] span", "div[class*='suggestedKeyword'] button", "div[class*='suggestedKeyword']",
    "div[class*='suggested-keyword'] span", "div[class*='suggested-keyword'] button", "div[class*='suggested-keyword']",
    "div[class*='keywordSuggest'] span", "div[class*='keywordSuggest'] button",
    "div[class*='aiSuggest'] span", "div[class*='aiSuggest'] button",
    "div[class*='recommend'] span", "div[class*='recommend'] button",
  ];

  const chips = Array.from(document.querySelectorAll(aiChipSelectors.join(", ")))
    .filter(el => el.offsetParent !== null && el.textContent.trim().length > 0);

  for (const chip of chips) {
    const raw = chip.textContent.replace(/^[+\s]+/, "").trim().toLowerCase();
    const rawNorm = raw.replace(/[^a-z0-9]/g, "");
    if (!rawNorm) continue;

    const match = allTargets.find(t => {
      const tNorm = t.replace(/[^a-z0-9]/g, "");
      return tNorm === rawNorm || rawNorm.includes(tNorm) || tNorm.includes(rawNorm);
    });

    if (match && !hasKeywordChip(raw)) {
      console.log(`[Snypar Bot] Clicking AI Suggested Keyword: "${chip.textContent.trim()}"`);
      chip.click();
      await sleep(350);
      if (mandatorySet && mandatorySet.has(match)) {
        await clickKeywordStar(raw);
      }
    }
  }
}

async function clickKeywordStar(skillName) {
  if (!skillName) return false;
  const clean = skillName.toLowerCase().trim();
  const cleanNorm = clean.replace(/[^a-z0-9]/g, '');
  const chips = document.querySelectorAll(
    "div[class*='chip'], span[class*='chip'], div[class*='tag'], span[class*='tag'], li[class*='chip'], li[class*='tag'], div[class*='pill'], span[class*='pill'], [class*='tuple']"
  );
  for (const chip of chips) {
    const chipNorm = chip.textContent.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (chipNorm.includes(cleanNorm)) {
      const star = chip.querySelector(
        "[class*='star'], [class*='Star'], [title*='Mandatory'], [title*='mandatory'], [title*='Must have'], svg, button"
      );
      if (star) {
        const cls = (star.className && star.className.toString()) || "";
        const pressed = star.getAttribute("aria-pressed");
        if (!cls.includes("active") && !cls.includes("selected") && !cls.includes("starred") && pressed !== "true") {
          star.click();
          await sleep(200);
          return true;
        }
      }
    }
  }
  return false;
}

function countKeywordChips() {
  return document.querySelectorAll(
    "div[class*='chip'], span[class*='chip'], div[class*='tag'], span[class*='tag'], li[class*='chip'], li[class*='tag'], div[class*='pill'], span[class*='pill']"
  ).length;
}

// ─── Section Expand ──────────────────────────────────────────────────────────

async function ensureSectionExpanded(sectionName) {
  const toggles = Array.from(
    document.querySelectorAll(
      "h2, h3, div[class*='accordion'], div[class*='section-header'], button, span[class*='header'], a"
    )
  ).filter((el) => el.textContent.toLowerCase().includes(sectionName.toLowerCase()));

  for (const t of toggles) {
    const isExpanded =
      t.getAttribute("aria-expanded") === "true" ||
      t.classList.contains("expanded") ||
      t.classList.contains("open");
    if (!isExpanded && t.offsetParent !== null) {
      t.click();
      await sleep(500);
      break;
    }
  }
}

function fieldHasValue(selector) {
  const el = document.querySelector(selector);
  if (!el) return false;
  if (el.tagName.toLowerCase() === "select") return el.selectedIndex > 0;
  return el.value && el.value.trim().length > 0;
}

// ─── Set Experience ───────────────────────────────────────────────────────────

async function setExperience(selector, value) {
  if (value === null || value === undefined) return false;
  const valStr = String(value);
  const el = document.querySelector(selector);
  if (!el) return false;

  if (el.tagName && el.tagName.toLowerCase() === "select") {
    for (let i = 0; i < el.options.length; i++) {
      if (el.options[i].value === valStr || el.options[i].text.trim() === valStr) {
        el.selectedIndex = i;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
    for (let i = 0; i < el.options.length; i++) {
      if (parseFloat(el.options[i].text) === parseFloat(valStr)) {
        el.selectedIndex = i;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
    return false;
  } else {
    el.focus();
    setNativeValue(el, valStr);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(300);

    const options = document.querySelectorAll(
      "div.sug-item, li.suggestion-item, div[class*='option'], li[class*='option'], ul li"
    );
    for (const opt of options) {
      if (opt.textContent.trim() === valStr && opt.offsetParent !== null) {
        opt.click();
        await sleep(200);
        return true;
      }
    }

    el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", keyCode: 13, bubbles: true }));
    await sleep(200);
    return fieldHasValue(selector);
  }
}

// ─── Click Pill Button ───────────────────────────────────────────────────────

async function clickPill(sectionName, pillText) {
  if (!pillText) return false;
  await ensureSectionExpanded(sectionName);
  await sleep(300);

  const allElements = Array.from(document.querySelectorAll(
    "span, div, button, label, a, li"
  )).filter(el => el.offsetParent !== null);

  // Try exact match first
  for (const el of allElements) {
    const text = el.textContent.trim();
    if (text.toLowerCase() === pillText.toLowerCase()) {
      const cls = (el.className && el.className.toString()) || "";
      const ariaPressed = el.getAttribute("aria-pressed");
      if (!cls.includes("active") && !cls.includes("selected") && ariaPressed !== "true") {
        el.click();
        console.log(`[Snypar Bot] ✓ Clicked pill "${pillText}" in ${sectionName}`);
        await sleep(200);
      } else {
        console.log(`[Snypar Bot] ✓ Pill "${pillText}" already active in ${sectionName}`);
      }
      return true;
    }
  }

  // Try contains match
  for (const el of allElements) {
    const text = el.textContent.trim().toLowerCase();
    if (text.includes(pillText.toLowerCase())) {
      el.click();
      console.log(`[Snypar Bot] ✓ Clicked pill "${pillText}" via contains match in ${sectionName}`);
      await sleep(200);
      return true;
    }
  }

  console.warn(`[Snypar Bot] ⚠ Pill "${pillText}" not found in ${sectionName}`);
  return false;
}

// ─── Set Select/Dropdown ─────────────────────────────────────────────────────

async function setSelectDropdown(selectors, value) {
  if (!value) return false;
  const selectorList = Array.isArray(selectors) ? selectors : [selectors];

  for (const sel of selectorList) {
    const el = document.querySelector(sel);
    if (!el) continue;

    if (el.tagName.toLowerCase() === "select") {
      for (let i = 0; i < el.options.length; i++) {
        if (el.options[i].text.toLowerCase().includes(value.toLowerCase()) ||
            el.options[i].value.toLowerCase().includes(value.toLowerCase())) {
          el.selectedIndex = i;
          el.dispatchEvent(new Event("change", { bubbles: true }));
          console.log(`[Snypar Bot] ✓ Set "${value}" in ${sel}`);
          return true;
        }
      }
    }
  }
  return false;
}

// ─── Set Active In ───────────────────────────────────────────────────────────

async function setActiveIn(value) {
  if (!value) return false;

  const selectors = [
    "select#activeIn", "select[name='activeIn']", "select#searchActivePeriod",
    "select[name='searchActivePeriod']"
  ];

  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el && el.tagName.toLowerCase() === "select") {
      for (let i = 0; i < el.options.length; i++) {
        if (el.options[i].text.toLowerCase().includes(value.toLowerCase())) {
          el.selectedIndex = i;
          el.dispatchEvent(new Event("change", { bubbles: true }));
          console.log(`[Snypar Bot] ✓ Set active_in "${value}"`);
          return true;
        }
      }
    }
  }

  // Try React custom dropdown
  const triggers = Array.from(document.querySelectorAll(
    "span, div, button"
  )).filter(el => el.textContent.trim().toLowerCase().includes("active in") && el.offsetParent !== null);

  if (triggers.length > 0) {
    triggers[0].click();
    await sleep(400);

    const options = Array.from(document.querySelectorAll(
      "li, div[role='option'], span"
    )).filter(el => el.textContent.trim().toLowerCase().includes(value.toLowerCase()) && el.offsetParent !== null);

    if (options.length > 0) {
      options[0].click();
      console.log(`[Snypar Bot] ✓ Set active_in "${value}" via dropdown`);
      await sleep(200);
      return true;
    }
  }

  return false;
}

// ─── Tick Checkbox ───────────────────────────────────────────────────────────

async function tickCheckbox(selector, checked) {
  if (checked === null || checked === undefined) return false;
  const el = document.querySelector(selector);
  if (!el) return false;
  if (checked && !el.checked) {
    el.click();
    console.log(`[Snypar Bot] ✓ Ticked checkbox ${selector}`);
    await sleep(100);
  } else if (!checked && el.checked) {
    el.click();
    console.log(`[Snypar Bot] ✓ Unticked checkbox ${selector}`);
    await sleep(100);
  }
  return true;
}

// ─── Tick Show-Only Pills (verified mobile, verified email, attached resume) ──
// On Naukri, these are pill buttons with '+' icon, NOT checkboxes.
// Strategy: find element containing the text, check if already active, click if not.

async function tickShowOnlyCheckboxes(plan) {
  const targets = [];
  if (plan?.verified_mobile) {
    targets.push({ key: "verified mobile" });
  }
  if (plan?.verified_email) {
    targets.push({ key: "verified email" });
  }
  if (plan?.attached_resume) {
    targets.push({ key: "attached resume" });
  }

  if (targets.length === 0) return 0;

  let ticked = 0;

  // First expand Additional Details section if needed
  await ensureSectionExpanded("Additional Details");
  await sleep(300);

  for (const target of targets) {
    const searchText = target.key.toLowerCase();
    let success = false;

    // Strategy 1: Find pill/chip/tag button with exact or contains text match
    const allClickable = Array.from(document.querySelectorAll(
      "span, div, button, label, a, li"
    )).filter(el => {
      const text = el.textContent.trim().toLowerCase();
      const isButton = el.tagName === "BUTTON" || el.tagName === "A" ||
                       el.getAttribute("role") === "button" || el.getAttribute("role") === "checkbox";
      const isPill = el.className && (
        el.className.toString().includes("chip") ||
        el.className.toString().includes("pill") ||
        el.className.toString().includes("tag") ||
        el.className.toString().includes("btn") ||
        el.className.toString().includes("option")
      );
      return (text.includes(searchText) || text === searchText) &&
             el.offsetParent !== null &&
             (isButton || isPill || el.tagName === "LABEL" || el.tagName === "LI");
    });

    for (const el of allClickable) {
      const cls = (el.className && el.className.toString()) || "";
      const ariaPressed = el.getAttribute("aria-pressed");
      const isChecked = cls.includes("active") || cls.includes("selected") ||
                        cls.includes("checked") || ariaPressed === "true";

      if (!isChecked) {
        el.click();
        console.log(`[Snypar Bot] ✓ Clicked show-only pill "${target.key}"`);
        success = true;
        await sleep(300);
        break;
      } else {
        console.log(`[Snypar Bot] ✓ Show-only pill "${target.key}" already active`);
        success = true;
        break;
      }
    }

    // Strategy 2: Try checkbox input as fallback
    if (!success) {
      const cbSelectors = [
        "input#verifiedMobile", "input[name='verifiedMobile']",
        "input#verifiedEmail", "input[name='verifiedEmail']",
        "input#attachedResume", "input[name='attachedResume']"
      ];
      for (const sel of cbSelectors) {
        const cb = document.querySelector(sel);
        if (cb && !cb.checked) {
          cb.click();
          console.log(`[Snypar Bot] ✓ Ticked checkbox "${target.key}"`);
          success = true;
          await sleep(100);
          break;
        }
      }
    }

    // Strategy 3: Find by label text and click associated checkbox or pill
    if (!success) {
      const labels = Array.from(document.querySelectorAll("label"));
      const label = labels.find(l => l.textContent.trim().toLowerCase().includes(searchText) && l.offsetParent !== null);
      if (label) {
        const cb = label.querySelector("input[type='checkbox']");
        if (cb) {
          if (!cb.checked) cb.click();
          console.log(`[Snypar Bot] ✓ Ticked checkbox via label "${target.key}"`);
          success = true;
        } else {
          label.click();
          console.log(`[Snypar Bot] ✓ Clicked label "${target.key}"`);
          success = true;
        }
        await sleep(100);
      }
    }

    if (success) ticked++;
  }

  return ticked;
}

// ─── DOM-State Verification ──────────────────────────────────────────────────

async function waitForFieldsVerified(plan, timeoutMs = 12000) {
  const start = Date.now();
  const requiredKws = (plan.keywords && plan.keywords.required) || [];
  const preferredKws = (plan.keywords && plan.keywords.preferred) || [];
  const totalKws = [...new Set([...requiredKws, ...preferredKws])].length;

  while (Date.now() - start < timeoutMs) {
    const checks = [];

    if (totalKws > 0) {
      checks.push({
        name: "keywords",
        ok: countKeywordChips() > 0,
      });
    }

    if (plan.min_experience !== null && plan.min_experience !== undefined) {
      checks.push({
        name: "min_experience",
        ok: fieldHasValue("input[name='minExp'], input#minExp, select#minExp, select[name='minExp']"),
      });
    }
    if (plan.max_experience !== null && plan.max_experience !== undefined) {
      checks.push({
        name: "max_experience",
        ok: fieldHasValue("input[name='maxExp'], input#maxExp, select#maxExp, select[name='maxExp']"),
      });
    }

    const failed = checks.filter((c) => !c.ok).map((c) => c.name);
    if (failed.length === 0) {
      console.log("[Snypar Bot] ✓ All field checks passed.");
      return true;
    }

    console.log(`[Snypar Bot] Waiting for: ${failed.join(", ")} (${Math.round((Date.now()-start)/1000)}s)`);
    updateWidgetStatus(`Verifying: ${failed.join(", ")}...`, "busy");
    await sleep(600);
  }

  console.warn("[Snypar Bot] Verification timeout — proceeding anyway.");
  return false;
}

// ─── Search Submission Verification ──────────────────────────────────────────
// Clicking a button is not evidence the search actually ran — Resdex may reject
// the submit, show a validation error, or simply not navigate. isOnResultsPage()
// (URL contains "/v3/search") is the one objective, already-established signal
// used elsewhere in this file for results-page detection, so we reuse it here
// rather than inventing new results-container selectors we can't verify.
async function waitForResultsPageVerified(timeoutMs = 10000, stepMs = 300) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (isOnResultsPage()) return true;
    await sleep(stepMs);
  }
  return false;
}

// ─── Main Form Fill ───────────────────────────────────────────────────────────

async function fillResdexForm(plan, autoSubmit = false) {
  if (isFilling) return;
  isFilling = true;
  console.log("[Snypar Bot] Starting auto-fill with SearchPlan:", plan);

  const blockSubmit = (e) => {
    e.preventDefault();
    e.stopImmediatePropagation();
    console.log("[Snypar Bot] Intercepted and blocked premature form submit");
  };
  window.addEventListener("submit", blockSubmit, true);

  const stepResults = [];

  try {
    // ── STEP 1: Keywords (required, preferred, excluded, mandatory, search_scope) ──
    stepResults.push(await runStep("keywords", async () => {
    const requiredKws  = (plan.keywords && plan.keywords.required)  || [];
    const preferredKws = (plan.keywords && plan.keywords.preferred) || [];
    const excludedKws  = (plan.keywords && plan.keywords.excluded)  || [];
    const allKws = [...new Set([...requiredKws, ...preferredKws])];
    const mandatorySet = new Set(requiredKws.map((k) => k.toLowerCase().trim()));

    if (allKws.length > 0) {
      updateWidgetStatus(`Keywords (0/${allKws.length})...`, "busy", "filling");

      const kwInput = document.querySelector(
        "input[name='ezKeywordsAny'], input[placeholder*='Enter keywords like skills'], " +
        "input#keywords, input.keyword-input, input[name='keyword'], input[id*='keyword']"
      );

      if (kwInput) {
        kwInput.scrollIntoView({ behavior: "smooth", block: "center" });
        await sleep(400);

        for (let i = 0; i < allKws.length; i++) {
          const kw = allKws[i];
          updateWidgetStatus(`Keyword ${i + 1}/${allKws.length}: "${kw}"`, "busy", "filling");
          await typeAndConfirmKeyword(kwInput, kw);

          if (mandatorySet.has(kw.toLowerCase().trim())) {
            await sleep(200);
            await clickKeywordStar(kw);
          }

          await pausableSleep(200);
        }

        // AI Suggested Keywords
        updateWidgetStatus("Checking AI Suggested Keywords...", "busy", "filling");
        await selectRelevantAISuggestedKeywords(requiredKws, preferredKws, mandatorySet);
        await sleep(200);

        // Mandatory keywords checkbox
        const mustHaveCheck = document.querySelector(
          "input#must-have-checkbox, input[name='must-have-checkbox'], " +
          "input#mandatoryKeywords, input[id*='mustHave'], input[id*='mandatory']"
        );
        if (mustHaveCheck && !mustHaveCheck.checked) {
          mustHaveCheck.click();
          await sleep(200);
        }
      } else {
        console.warn("[Snypar Bot] Keyword input not found.");
      }
    }

    // Excluded keywords
    if (excludedKws.length > 0) {
      const excludeInput = document.querySelector(
        "input[name='ezKeywordsExclude'], input#excludeKeywords, input[name='excludeKeyword'], " +
        "input[placeholder*='exclude']"
      );
      if (excludeInput) {
        for (const kw of excludedKws) {
          await typeAndConfirmKeyword(excludeInput, kw);
          await sleep(200);
        }
      }
    }

    // Keyword search scope
    if (plan.keywords && plan.keywords.search_scope && plan.keywords.search_scope !== "Entire resume") {
      await setSelectDropdown([
        "select#keywordScope", "select[name='keywordScope']"
      ], plan.keywords.search_scope);
    }
    }));

    await pausableSleep(500);

    // ── STEP 2: Experience ──────────────────────────────────────────────────
    stepResults.push(await runStep("experience", async () => {
    if (plan.min_experience !== null && plan.min_experience !== undefined) {
      updateWidgetStatus("Experience (Min)...", "busy", "filling");
      await setExperience(
        "input[name='minExp'], input[placeholder*='Min experience'], input#minExp, select#minExp, select[name='minExp']",
        plan.min_experience
      );
      await sleep(300);
    }
    if (plan.max_experience !== null && plan.max_experience !== undefined) {
      updateWidgetStatus("Experience (Max)...", "busy", "filling");
      await setExperience(
        "input[name='maxExp'], input[placeholder*='Max experience'], input#maxExp, select#maxExp, select[name='maxExp']",
        plan.max_experience
      );
      await sleep(300);
    }
    }));

    await pausableSleep(400);

    // ── STEP 3: Location (current_location, include_relocation, exclude_anywhere) ──
    stepResults.push(await runStep("location", async () => {
    if (plan.current_location && plan.current_location.length > 0) {
      const locInput = document.querySelector(
        "input[name='locations'], input[placeholder*='Add location'], input#location"
      );
      if (locInput) {
        for (let i = 0; i < plan.current_location.length; i++) {
          const loc = plan.current_location[i];
          updateWidgetStatus(`Location ${i + 1}/${plan.current_location.length}: "${loc}"`, "busy", "filling");
          await typeAndSelectFromDropdown(locInput, loc, 'Location');
          await pausableSleep(100);
        }
      }
    }

    if (plan.include_relocation !== null && plan.include_relocation !== undefined) {
      await tickCheckbox(
        "input#prefLocCheckbox, input[name='prefLocCheckbox'], input#includeRelocation",
        plan.include_relocation
      );
    }

    if (plan.exclude_anywhere_location !== null && plan.exclude_anywhere_location !== undefined) {
      await tickCheckbox(
        "input#exact-pref-match-checkbox, input#excludeAnywhere",
        plan.exclude_anywhere_location
      );
    }
    }));

    await pausableSleep(400);

    // ── STEP 4: Salary (currency, min, max, include_unspecified) ────────────
    stepResults.push(await runStep("salary", async () => {
    if (plan.salary) {
      if (plan.salary.currency) {
        await setSelectDropdown([
          "select#salaryCurrency", "select[name='currency']"
        ], plan.salary.currency);
      }

      if (plan.salary.min !== null && plan.salary.min !== undefined) {
        updateWidgetStatus("Salary (Min)...", "busy");
        const minSalInput = document.querySelector(
          "input[name='minCtc'], input#minSalary, input[placeholder*='Min salary']"
        );
        if (minSalInput) {
          minSalInput.focus();
          setNativeValue(minSalInput, String(plan.salary.min));
          minSalInput.dispatchEvent(new Event("input", { bubbles: true }));
          minSalInput.dispatchEvent(new Event("change", { bubbles: true }));
          const ok = await waitForFieldValue(
            "input[name='minCtc'], input#minSalary, input[placeholder*='Min salary']",
            plan.salary.min, 800
          );
          if (!ok) console.warn("[Snypar Bot] ⚠ salary.min did not register on the input.");
        }
      }
      if (plan.salary.max !== null && plan.salary.max !== undefined) {
        updateWidgetStatus("Salary (Max)...", "busy");
        const maxSalInput = document.querySelector(
          "input[name='maxCtc'], input#maxSalary, input[placeholder*='Max salary']"
        );
        if (maxSalInput) {
          maxSalInput.focus();
          setNativeValue(maxSalInput, String(plan.salary.max));
          maxSalInput.dispatchEvent(new Event("input", { bubbles: true }));
          maxSalInput.dispatchEvent(new Event("change", { bubbles: true }));
          const ok = await waitForFieldValue(
            "input[name='maxCtc'], input#maxSalary, input[placeholder*='Max salary']",
            plan.salary.max, 800
          );
          if (!ok) console.warn("[Snypar Bot] ⚠ salary.max did not register on the input.");
        }
      }

      if (plan.salary.include_unspecified !== null && plan.salary.include_unspecified !== undefined) {
        await tickCheckbox(
          "input#include-candidate-ctc, input#includeUnspecifiedSalary",
          plan.salary.include_unspecified
        );
      }
    }
    }));

    await sleep(400);

    // ── STEP 5: Employment Details (designation, department_role, industry, company, exclude_company, scopes) ──
    stepResults.push(await runStep("employment_details", async () => {
    const hasEmpDetails = (plan.designation && plan.designation.length > 0) ||
                          (plan.department_role && plan.department_role.length > 0) ||
                          (plan.industry && plan.industry.length > 0) ||
                          (plan.company && plan.company.length > 0) ||
                          (plan.exclude_company && plan.exclude_company.length > 0);

    if (hasEmpDetails) {
      updateWidgetStatus("Expanding Employment Details...", "busy", "filling");
      await ensureSectionExpanded("Employment Details");
      await sleep(500);
    }

    // Designation
    if (plan.designation && plan.designation.length > 0) {
      const desigInput = document.querySelector(
        "input[name='designation'], input#designation, input[placeholder*='Designation'], input[placeholder*='designation']"
      );
      if (desigInput) {
        for (let i = 0; i < plan.designation.length; i++) {
          const desig = plan.designation[i];
          updateWidgetStatus(`Designation ${i + 1}/${plan.designation.length}: "${desig}"`, "busy", "filling");
          await typeAndSelectFromDropdown(desigInput, desig, 'Designation');
          await pausableSleep(100);
        }
      }
    }

    // Designation search scope
    if (plan.designation_search_scope && plan.designation_search_scope !== "Current designation") {
      await setSelectDropdown([
        "select#designationScope", "select[name='designationScope']"
      ], plan.designation_search_scope);
    }

    // Department Role
    if (plan.department_role && plan.department_role.length > 0) {
      const roleInput = document.querySelector(
        "input[name='departmentRole'], input#departmentRole, input[placeholder*='Department'], input[placeholder*='Role']"
      );
      if (roleInput) {
        for (let i = 0; i < plan.department_role.length; i++) {
          const role = plan.department_role[i];
          updateWidgetStatus(`Dept/Role ${i + 1}/${plan.department_role.length}: "${role}"`, "busy", "filling");
          await typeAndSelectFromDropdown(roleInput, role, 'Dept/Role');
          await pausableSleep(100);
        }
      }
    }

    // Industry
    if (plan.industry && plan.industry.length > 0) {
      const indInput = document.querySelector(
        "input[name='industry'], input#industry, input[placeholder*='industry']"
      );
      if (indInput) {
        for (let i = 0; i < plan.industry.length; i++) {
          const ind = plan.industry[i];
          updateWidgetStatus(`Industry ${i + 1}/${plan.industry.length}: "${ind}"`, "busy", "filling");
          await typeAndSelectFromDropdown(indInput, ind, 'Industry');
          await pausableSleep(100);
        }
      }
    }

    // Company
    if (plan.company && plan.company.length > 0) {
      const compInput = document.querySelector(
        "input[name='company'], input#company, input[placeholder*='company']"
      );
      if (compInput) {
        for (let i = 0; i < plan.company.length; i++) {
          const comp = plan.company[i];
          updateWidgetStatus(`Company ${i + 1}/${plan.company.length}: "${comp}"`, "busy", "filling");
          await typeAndSelectFromDropdown(compInput, comp, 'Company');
          await pausableSleep(100);
        }
      }
    }

    // Company search scope
    if (plan.company_search_scope && plan.company_search_scope !== "Current company") {
      await setSelectDropdown([
        "select#companyScope", "select[name='companyScope']"
      ], plan.company_search_scope);
    }

    // Exclude Company
    if (plan.exclude_company && plan.exclude_company.length > 0) {
      const exCompInput = document.querySelector(
        "input[name='excludeCompany'], input#excludeCompany, input[placeholder*='exclude company']"
      );
      if (exCompInput) {
        for (let i = 0; i < plan.exclude_company.length; i++) {
          const comp = plan.exclude_company[i];
          updateWidgetStatus(`Exclude Company ${i + 1}/${plan.exclude_company.length}: "${comp}"`, "busy", "filling");
          await typeAndSelectFromDropdown(exCompInput, comp, 'Exclude Company');
          await pausableSleep(100);
        }
      }
    }

    // Exclude company search scope
    if (plan.exclude_company_search_scope && plan.exclude_company_search_scope !== "Current company") {
      await setSelectDropdown([
        "select#excludeCompanyScope", "select[name='excludeCompanyScope']"
      ], plan.exclude_company_search_scope);
    }
    }));

    await pausableSleep(400);

    // ── STEP 6: Notice Period ───────────────────────────────────────────────
    stepResults.push(await runStep("notice_period", async () => {
    if (plan.notice_period && plan.notice_period.length > 0) {
      updateWidgetStatus("Notice Period...", "busy", "filling");
      await ensureSectionExpanded("Notice Period");
      await sleep(500);

      // Normalize notice period display values
      const noticePeriodDisplayMap = {
        "0-15 days": "0 - 15 days",
        "1 month": "1 Month",
        "2 months": "2 Months",
        "3 months": "3 Months",
        "more than 3 months": "More than 3 Months",
        "currently serving notice period": "Currently Serving Notice Period",
        "any": "Any",
      };

      const labels = Array.from(document.querySelectorAll("label, span, div.checkbox, li"));
      for (const np of plan.notice_period) {
        const npDisplay = noticePeriodDisplayMap[np.toLowerCase().trim()] || np;
        const npClean = np.toLowerCase();

        // Try exact match on display text first
        let match = labels.find((l) =>
          l.textContent.trim().toLowerCase() === npDisplay.toLowerCase()
        );

        // Fallback to contains match
        if (!match) {
          match = labels.find((l) =>
            l.textContent.trim().toLowerCase().includes(npClean)
          );
        }

        if (match) {
          const cb = match.querySelector("input[type='checkbox']");
          if (cb) {
            if (!cb.checked) cb.click();
          } else {
            match.click();
          }
          console.log(`[Snypar Bot] ✓ Notice period: "${npDisplay}"`);
          await sleep(200);
        }
      }
    }
    }));

    await pausableSleep(400);

    // ── STEP 7: Education Details (ug_qualification, pg_qualification) ──────
    stepResults.push(await runStep("education_details", async () => {
    if (plan.ug_qualification || plan.pg_qualification) {
      updateWidgetStatus("Education Details...", "busy", "filling");

      if (plan.ug_qualification) {
        await clickPill("Education Details", plan.ug_qualification);
      }
      if (plan.pg_qualification) {
        await clickPill("Education Details", plan.pg_qualification);
      }
      await sleep(300);
    }
    }));

    // ── STEP 8: Diversity Hiring (gender, career_break, differently_abled, defence_background) ──
    stepResults.push(await runStep("diversity_hiring", async () => {
    const hasDiversity = plan.gender || plan.career_break || plan.differently_abled || plan.defence_background;
    if (hasDiversity) {
      updateWidgetStatus("Diversity Hiring...", "busy", "filling");

      if (plan.gender) {
        await clickPill("Diversity Hiring", plan.gender);
      }
      if (plan.career_break) {
        await clickPill("Diversity Hiring", plan.career_break);
      }
      if (plan.differently_abled) {
        await clickPill("Diversity Hiring", plan.differently_abled);
      }
      if (plan.defence_background) {
        await clickPill("Diversity Hiring", plan.defence_background);
      }
      await sleep(300);
    }
    }));

    // ── STEP 9: Additional Details (candidate_category, candidate_age, job_type, employment_type, work_permit) ──
    stepResults.push(await runStep("additional_details", async () => {
    const hasAdditional = plan.candidate_category || plan.candidate_age || plan.job_type || plan.employment_type || (plan.work_permit && plan.work_permit.length > 0);
    if (hasAdditional) {
      updateWidgetStatus("Additional Details...", "busy", "filling");
      await ensureSectionExpanded("Additional Details");
      await sleep(500);

      // Candidate Category
      if (plan.candidate_category) {
        await setSelectDropdown([
          "select#candidateCategory", "select[name='candidateCategory']"
        ], plan.candidate_category);
      }

      // Candidate Age
      if (plan.candidate_age) {
        if (plan.candidate_age.min !== null && plan.candidate_age.min !== undefined) {
          const minAgeInput = document.querySelector(
            "input[name='minAge'], input#minAge, input[placeholder*='Min age']"
          );
          if (minAgeInput) {
            minAgeInput.focus();
            setNativeValue(minAgeInput, String(plan.candidate_age.min));
            minAgeInput.dispatchEvent(new Event("input", { bubbles: true }));
            minAgeInput.dispatchEvent(new Event("change", { bubbles: true }));
            const ok = await waitForFieldValue(
              "input[name='minAge'], input#minAge, input[placeholder*='Min age']",
              plan.candidate_age.min, 600
            );
            if (!ok) console.warn("[Snypar Bot] ⚠ candidate_age.min did not register on the input.");
          }
        }
        if (plan.candidate_age.max !== null && plan.candidate_age.max !== undefined) {
          const maxAgeInput = document.querySelector(
            "input[name='maxAge'], input#maxAge, input[placeholder*='Max age']"
          );
          if (maxAgeInput) {
            maxAgeInput.focus();
            setNativeValue(maxAgeInput, String(plan.candidate_age.max));
            maxAgeInput.dispatchEvent(new Event("input", { bubbles: true }));
            maxAgeInput.dispatchEvent(new Event("change", { bubbles: true }));
            const ok = await waitForFieldValue(
              "input[name='maxAge'], input#maxAge, input[placeholder*='Max age']",
              plan.candidate_age.max, 600
            );
            if (!ok) console.warn("[Snypar Bot] ⚠ candidate_age.max did not register on the input.");
          }
        }
      }

      // Job Type
      if (plan.job_type) {
        await setSelectDropdown([
          "select#jobType", "select[name='jobType']"
        ], plan.job_type);
      }

      // Employment Type
      if (plan.employment_type) {
        await setSelectDropdown([
          "select#employmentType", "select[name='employmentType']"
        ], plan.employment_type);
      }

      // Work Permit
      if (plan.work_permit && plan.work_permit.length > 0) {
        const wpInput = document.querySelector(
          "input#workPermit, input[placeholder*='Work permit'], input[placeholder*='work permit']"
        );
        if (wpInput) {
          for (const wp of plan.work_permit) {
            await typeAndSelectFromDropdown(wpInput, wp, 'Work Permit');
            await sleep(100);
          }
        }
      }
    }
    }));

    await pausableSleep(400);

    // ── STEP 10: Display Details (candidate_display, verified_mobile, verified_email, attached_resume) ──
    stepResults.push(await runStep("display_details", async () => {
    if (plan.candidate_display) {
      await clickPill("Display Details", plan.candidate_display);
    }

    if (plan.verified_mobile || plan.verified_email || plan.attached_resume) {
      updateWidgetStatus("Show Only...", "busy", "filling");
      await ensureSectionExpanded("Additional Details");
      await sleep(500);
      const ticked = await tickShowOnlyCheckboxes(plan);
      console.log(`[Snypar Bot] Ticked ${ticked} show-only checkboxes`);
      await sleep(300);
    }
    }));

    // ── STEP 11: Active In ──────────────────────────────────────────────────
    stepResults.push(await runStep("active_in", async () => {
    if (plan.active_in) {
      updateWidgetStatus("Active In...", "busy", "filling");
      await setActiveIn(plan.active_in);
      await sleep(300);
    }
    }));

    // ── Step summary: which field groups succeeded/failed, for diagnosability ──
    const stepSummary = summarizeStepResults(stepResults);
    window.snyparLastFillSummary = stepSummary;
    if (stepSummary.failed.length > 0) {
      console.warn("[Snypar Bot] Steps that failed (did NOT block other fields):", stepSummary.failed);
      showToast(`⚠ ${stepSummary.failed.length} field group(s) had errors: ${stepSummary.failed.map(f => f.name).join(", ")}`);
    }
    console.log("[Snypar Bot] Step summary:", stepSummary);

    // ── STEP 12: DOM-STATE VERIFICATION ─────────────────────────────────────
    updateWidgetStatus("⚙ Verifying all fields...", "busy", "filling");
    showToast("⚡ Verifying all fields are complete before searching...");
    const verified = await waitForFieldsVerified(plan, 12000);

    if (!verified) {
      showToast("⚠ Some fields may not have registered — check the form.");
    }

    if (isPaused) {
      updateWidgetStatus("⏸ Paused before search — resume to submit", "busy", "paused");
      while (isPaused) { await sleep(300); }
    }

    // ── STEP 13: Click Search Candidates ────────────────────────────────────
    window.removeEventListener("submit", blockSubmit, true);

    // Blur all inputs to commit React state and clear any text selection
    document.querySelectorAll("input, select, textarea").forEach(el => {
      el.dispatchEvent(new Event("blur", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
    window.getSelection().removeAllRanges();
    document.activeElement?.blur();
    await sleep(500);

    let searchClicked = false;

    if (autoSubmit) {
      updateWidgetStatus("Clicking Search Candidates...", "busy");
      await sleep(400);

      // Strategy 1: precise CSS selectors
      const preciseSelectors = [
        "button#searchButton",
        "button[data-testid='search-btn']",
        "button[data-testid='searchButton']",
        "a.searchProfiles",
        "button.searchProfiles",
        "button.search-btn",
        "button[class*='searchBtn']",
        "button[class*='search-btn']",
        "button[class*='SearchBtn']",
        "button[class*='srchBtn']",
        "a[class*='searchProfiles']",
        "input[type='submit'][value*='Search']",
        "input[type='submit'][value*='search']",
      ];
      for (const sel of preciseSelectors) {
        const btn = document.querySelector(sel);
        if (btn && btn.offsetParent !== null) {
          btn.scrollIntoView({ behavior: "smooth", block: "center" });
          await sleep(400);
          btn.click();
          searchClicked = true;
          console.log(`[Snypar Bot] ✓ Search clicked via precise selector: ${sel}`);
          break;
        }
      }

      // Strategy 2: text match on all clickable elements including input[type=submit]
      if (!searchClicked) {
        const allBtns = Array.from(document.querySelectorAll(
          "button, a[role='button'], input[type='submit'], input[type='button']"
        ));
        const searchBtn = allBtns.find((b) => {
          const txt = (b.value || b.textContent || "").trim().toLowerCase();
          return (txt.includes("search candidate") || txt === "search" || txt === "search candidates") &&
                 b.offsetParent !== null;
        });
        if (searchBtn) {
          searchBtn.scrollIntoView({ behavior: "smooth", block: "center" });
          await sleep(400);
          searchBtn.click();
          searchClicked = true;
          console.log(`[Snypar Bot] ✓ Search clicked via text match: "${(searchBtn.value || searchBtn.textContent).trim()}"`);
        }
      }

      // Strategy 3: find submit button inside the form
      if (!searchClicked) {
        const forms = document.querySelectorAll("form");
        for (const form of forms) {
          const submitBtn = form.querySelector("button[type='submit'], input[type='submit']");
          if (submitBtn && submitBtn.offsetParent !== null) {
            submitBtn.scrollIntoView({ behavior: "smooth", block: "center" });
            await sleep(400);
            submitBtn.click();
            searchClicked = true;
            console.log(`[Snypar Bot] ✓ Search clicked via form submit button`);
            break;
          }
        }
      }
    }

    let searchVerified = null; // null = not applicable (autoSubmit was false)

    if (searchClicked) {
      updateWidgetStatus("Verifying search was submitted...", "busy", "none");
      searchVerified = await waitForResultsPageVerified(10000);

      if (searchVerified) {
        updateWidgetStatus("✓ Search Submitted!", "online", "none");
        showToast("✓ 'Search Candidates' executed successfully on Naukri Resdex!");
      } else {
        // The button was clicked, but the results page never appeared — Resdex may
        // have rejected the submit or shown a validation error. Do NOT report success.
        updateWidgetStatus("⚠ Search click unconfirmed", "offline", "none");
        showToast("⚠ Clicked 'Search Candidates' but results page was not detected — please verify manually.");
        console.warn("[Snypar Bot] Search button was clicked but isOnResultsPage() never became true within timeout.");
      }
    } else if (autoSubmit) {
      searchVerified = false;
      updateWidgetStatus("⚠ Search button not found", "online", "none");
      showToast("⚠ Could not find 'Search Candidates' button — please click it manually.");
    } else {
      updateWidgetStatus("✓ All Fields Filled!", "online", "none");
      showToast("✓ All criteria filled — click 'Search Candidates' to execute search.");
    }

    const fillOutcome = {
      formFilled: true,
      searchRequested: autoSubmit,
      searchClicked,
      searchVerified,
      stepSummary,
    };
    window.snyparLastFillSummary = fillOutcome;
    return fillOutcome;
  } catch (err) {
    console.error("[Snypar Bot] Auto-fill error:", err);
    updateWidgetStatus("⚠ Error During Fill", "offline", "none");
    showToast(`⚠ Error: ${err.message}`);
    const fillOutcome = {
      formFilled: false,
      searchRequested: autoSubmit,
      searchClicked: false,
      searchVerified: false,
      error: String(err && err.message || err),
    };
    window.snyparLastFillSummary = fillOutcome;
    return fillOutcome;
  } finally {
    window.removeEventListener("submit", blockSubmit, true);
    isPaused = false;
    isFilling = false;
    lastFillCompletedAt = Date.now();
  }
}

// ─── Real-Time Sync Loop ─────────────────────────────────────────────────────

async function waitForFormReady(timeoutMs = 20000) {
  const start = Date.now();
  const formInputSelectors = [
    "input[name='ezKeywordsAny']",
    "input[placeholder*='Enter keywords like skills']",
    "input[placeholder*='keyword']",
    "input[placeholder*='Enter skills']",
    "input#keywords",
    "input.keyword-input",
    "input[name='keyword']",
    "input[id*='keyword']",
  ];
  while (Date.now() - start < timeoutMs) {
    for (const sel of formInputSelectors) {
      const el = document.querySelector(sel);
      if (el && el.offsetParent !== null) {
        console.log(`[Snypar Bot] ✓ Form ready — keyword input found: ${sel}`);
        return true;
      }
    }
    if (isOnResultsPage()) {
      console.log("[Snypar Bot] Still on results page after navigation — retrying...");
      await ensureOnFormPage();
      return false;
    }
    updateWidgetStatus(`Waiting for form... (${Math.round((Date.now()-start)/1000)}s)`, "busy");
    await sleep(700);
  }
  console.warn("[Snypar Bot] Form not detected within timeout.");
  return false;
}

async function ensureOnFormPage() {
  if (isOnResultsPage()) {
    updateWidgetStatus("Navigating to Search Form...", "busy");
    showToast("⚡ Snypar Bot: Going to search form to fill criteria...");

    const modifyLinks = Array.from(
      document.querySelectorAll("a, button, span")
    ).filter(
      (el) =>
        el.textContent.trim().toLowerCase() === "modify" ||
        el.getAttribute("href")?.includes("advanced-search")
    );
    if (modifyLinks.length > 0 && modifyLinks[0].offsetParent !== null) {
      console.log("[Snypar Bot] Clicking Modify link...");
      modifyLinks[0].click();
    } else {
      window.location.href = RESDEX_FORM_URL;
    }
    return false;
  }
  return true;
}

// ─── Candidate Extraction (Resdex Results Page) ──────────────────────────────
// No captured real Resdex results-page HTML exists in this repo, so these
// selectors are best-effort heuristics, not confirmed markup. Every step is
// designed to fail soft (a missing field yields null, not a thrown error) and
// to self-report what it found via `diagnostics`, so a live run against the
// real page is diagnosable/calibratable rather than a silent miss. V1 scope:
// current visible page only — no pagination/infinite-scroll handling yet.

const PROFILE_LINK_SELECTORS = [
  "a[href*='/profile']", "a[href*='candidateId']", "a[href*='candidate/']",
  "a[data-testid*='candidate']", "a[data-testid*='profile']",
  "a[class*='candidateName']", "a[class*='candidate-name']", "a[class*='profileLink']",
].join(", ");

const GENERIC_CARD_SELECTORS = [
  "div[class*='candidateCard']", "div[class*='candidate-card']",
  "div[class*='resultCard']", "div[class*='result-card']",
  "div[class*='profileCard']", "div[class*='profile-card']",
  "li[class*='candidate']", "div[class*='dashboardCard']",
].join(", ");

const FIELD_CLASS_HINTS = {
  title: ["title", "designation", "role"],
  company: ["company", "employer", "organisation", "organization"],
  location: ["location", "city"],
  education: ["education", "qualification", "degree"],
  notice_period: ["notice"],
};

function safeText(el, maxLen = 120) {
  if (!el) return null;
  const t = (el.textContent || "").trim();
  if (!t) return null;
  return t.length > maxLen ? t.slice(0, maxLen) : t;
}

function findChildTextByClassHints(container, hints) {
  const all = container.querySelectorAll("*");
  for (const el of all) {
    const cls = (el.className && el.className.toString() || "").toLowerCase();
    if (hints.some((h) => cls.includes(h))) {
      const t = safeText(el);
      if (t) return t;
    }
  }
  return null;
}

function findSkillsInContainer(container, maxSkills = 15) {
  const els = container.querySelectorAll(
    "[class*='skill'], [class*='tag'], [class*='chip']"
  );
  const skills = [];
  for (const el of els) {
    const t = safeText(el, 60);
    if (t && !skills.includes(t)) skills.push(t);
    if (skills.length >= maxSkills) break;
  }
  return skills;
}

function extractExperienceText(container) {
  const text = container.textContent || "";
  const match = text.match(/\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:yrs?|years?)\b(?:\s*,?\s*\d{1,2}\s*(?:months?|mos?)\b)?/i);
  return match ? match[0].trim() : null;
}

function extractResdexCandidateId(anchor) {
  if (!anchor || !anchor.href) return null;
  const idMatch = anchor.href.match(/[?&](?:candidateId|profileId|id)=([^&#]+)/i);
  return idMatch ? decodeURIComponent(idMatch[1]) : null;
}

function findCandidateContainers() {
  // Strategy 1: profile-link anchors, walked up to a plausible "card" ancestor.
  const anchors = Array.from(document.querySelectorAll(PROFILE_LINK_SELECTORS))
    .filter((a) => a.offsetParent !== null && a.textContent.trim().length > 1);

  if (anchors.length > 0) {
    const seen = new Set();
    const pairs = [];
    for (const anchor of anchors) {
      let node = anchor;
      let depth = 0;
      while (node.parentElement && depth < 6) {
        node = node.parentElement;
        depth++;
        if (node.children.length >= 3 || (node.textContent || "").trim().length > 60) break;
      }
      if (!seen.has(node)) {
        seen.add(node);
        pairs.push({ container: node, anchor });
      }
    }
    return { pairs, strategy: "profile-link-anchor", warnings: [] };
  }

  // Strategy 2: generic card-class fallback (no profile link found).
  const cards = Array.from(document.querySelectorAll(GENERIC_CARD_SELECTORS))
    .filter((el) => el.offsetParent !== null);
  if (cards.length > 0) {
    return {
      pairs: cards.map((c) => ({ container: c, anchor: null })),
      strategy: "generic-card-class",
      warnings: ["No profile-link anchors found; used generic card class selectors. profile_url will be unavailable."],
    };
  }

  return { pairs: [], strategy: "none", warnings: ["No candidate containers detected with any known strategy."] };
}

function extractOneCandidate(container, anchor) {
  const name = anchor ? safeText(anchor, 100) : (
    findChildTextByClassHints(container, ["name", "candidatename"]) ||
    safeText(container.querySelector("h1, h2, h3, strong"), 100)
  );
  if (!name) return null;

  return {
    name,
    title: findChildTextByClassHints(container, FIELD_CLASS_HINTS.title),
    company: findChildTextByClassHints(container, FIELD_CLASS_HINTS.company),
    experience: extractExperienceText(container),
    location: findChildTextByClassHints(container, FIELD_CLASS_HINTS.location),
    skills: findSkillsInContainer(container),
    education: findChildTextByClassHints(container, FIELD_CLASS_HINTS.education),
    notice_period: findChildTextByClassHints(container, FIELD_CLASS_HINTS.notice_period),
    profile_url: anchor && anchor.href ? anchor.href : null,
    resdex_candidate_id: extractResdexCandidateId(anchor),
  };
}

function extractCandidatesFromResultsPage() {
  const { pairs, strategy, warnings } = findCandidateContainers();
  const candidates = [];
  const fieldHitCounts = {};
  const extractionWarnings = [...warnings];

  for (const { container, anchor } of pairs) {
    try {
      const candidate = extractOneCandidate(container, anchor);
      if (!candidate) {
        extractionWarnings.push("A candidate container had no extractable name; skipped.");
        continue;
      }
      candidates.push(candidate);
      for (const [key, val] of Object.entries(candidate)) {
        const found = Array.isArray(val) ? val.length > 0 : val !== null && val !== undefined;
        if (found) fieldHitCounts[key] = (fieldHitCounts[key] || 0) + 1;
      }
    } catch (err) {
      // One bad container must not abort extraction of the rest.
      extractionWarnings.push(`Extraction error on one container: ${err.message}`);
    }
  }

  const diagnostics = {
    containers_detected: pairs.length,
    candidates_extracted: candidates.length,
    field_hit_counts: fieldHitCounts,
    selector_strategy: strategy,
    warnings: extractionWarnings,
  };

  // Deliberately log only structural diagnostics (counts), never candidate content.
  console.log("[Snypar Bot] Candidate extraction diagnostics:", diagnostics);

  return { candidates, diagnostics };
}

let lastExtractedResultsUrl = null;

async function extractAndSubmitCandidatesIfNeeded(forced = false) {
  const currentUrl = window.location.href;
  if (!forced && lastExtractedResultsUrl === currentUrl) {
    return; // already extracted this exact results view
  }

  const { candidates, diagnostics } = extractCandidatesFromResultsPage();

  if (candidates.length === 0) {
    updateWidgetStatus("⚠ No candidates detected on results page", "offline");
    return;
  }

  const result = await postToBackend("/search/results", {
    page: 1,
    candidates,
    diagnostics,
  });

  if (result) {
    lastExtractedResultsUrl = currentUrl;
    updateWidgetStatus(`✓ ${candidates.length} candidate(s) found (${result.total_stored ?? candidates.length} total stored)`, "online");
  } else {
    console.warn("[Snypar Bot] Failed to submit extracted candidates to backend — will retry on next poll.");
    updateWidgetStatus("⚠ Could not submit candidates to server", "offline");
  }
}

async function fetchAndFill(forced = false) {
  if (isFilling) return;

  if (isOnResultsPage()) {
    updateWidgetStatus("✓ Search Results Active", "online");
    await extractAndSubmitCandidatesIfNeeded(forced);
    return;
  }

  const fetchedData = await fetchFromBackend("/search/active-plan");

  if (!fetchedData) {
    updateWidgetStatus("Server Offline", "offline");
    return;
  }

  try {
    if (fetchedData.has_plan && fetchedData.plan) {
      const planTs = String(fetchedData.timestamp);

      const cachedTs = sessionStorage.getItem(FILL_CACHE_KEY);
      if (!forced && cachedTs === planTs) {
        updateWidgetStatus("✓ Plan Already Applied", "online");
        return;
      }

      const msSinceFill = Date.now() - lastFillCompletedAt;
      if (!forced && lastFillCompletedAt > 0 && msSinceFill < FILL_COOLDOWN_MS) {
        const secLeft = Math.ceil((FILL_COOLDOWN_MS - msSinceFill) / 1000);
        updateWidgetStatus(`⏳ Cooldown (${secLeft}s)`, "busy");
        return;
      }

      if (!forced && fetchedData.timestamp <= lastProcessedTimestamp) {
        updateWidgetStatus("✓ Plan Already Applied", "online");
        return;
      }

      updateWidgetStatus("Waiting for form...", "busy");
      const formReady = await waitForFormReady(15000);
      if (!formReady) {
        updateWidgetStatus("⚠ Form not found", "offline");
        showToast("⚠ Could not find Resdex search form. Please navigate to the Resdex search page.");
        return;
      }

      lastProcessedTimestamp = fetchedData.timestamp;
      const shouldSubmit = fetchedData.plan?._submit_search === true;
      showToast("⚡ Snypar Bot: Auto-filling candidate search criteria...");
      const outcome = await fillResdexForm(fetchedData.plan, shouldSubmit);

      // Only mark this plan as "fully applied" (and stop retrying) if either:
      //  - search submission wasn't requested (form-fill-only is complete once fillResdexForm returns), or
      //  - search submission WAS requested and we verified the results page actually loaded.
      // If a search was requested but never verified, deliberately leave the cache
      // unset so the next eligible poll (after cooldown) retries the click instead
      // of silently reporting success on a search that may not have run.
      const searchOutcomeOk = !shouldSubmit || outcome.searchVerified === true;
      if (searchOutcomeOk) {
        sessionStorage.setItem(FILL_CACHE_KEY, planTs);
      } else {
        console.warn("[Snypar Bot] Search was requested but not verified — plan will be retried on next eligible poll instead of being cached as applied.");
      }

    } else {
      updateWidgetStatus("⚡ Snypar Bot Active", "online");
    }
  } catch (err) {
    console.error("[Snypar Bot] Processing error:", err);
  }
}

// Listen for messages from popup
if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
  chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
    if (req.action === "TRIGGER_FILL") {
      fetchAndFill(true);
      sendResponse({ status: "filling" });

    } else if (req.action === "FORCE_FILL") {
      sessionStorage.removeItem(FILL_CACHE_KEY);
      lastFillCompletedAt = 0;
      lastProcessedTimestamp = 0;
      isPaused = false;
      console.log("[Snypar Bot] Force Re-fill triggered — cache cleared.");
      fetchAndFill(true);
      sendResponse({ status: "force-filling" });

    } else if (req.action === "PAUSE") {
      isPaused = true;
      updateWidgetStatus("⏸ Paused — click Resume to continue", "busy", "paused");
      showToast("⏸ Auto-fill paused.");
      sendResponse({ status: "paused" });

    } else if (req.action === "RESUME") {
      isPaused = false;
      updateWidgetStatus("▶ Resuming...", "busy", "filling");
      showToast("▶ Auto-fill resumed.");
      sendResponse({ status: "resumed" });

    } else if (req.action === "GET_STATUS") {
      sendResponse({
        isFilling,
        isPaused,
        onResultsPage: isOnResultsPage(),
        lastFillSummary: window.snyparLastFillSummary || null,
      });
    }
    return true;
  });
}

// ─── Initialize on Page Load ──────────────────────────────────────────────────

let syncIntervalStarted = false;
function initSync() {
  if (syncIntervalStarted) return;
  syncIntervalStarted = true;
  createFloatingWidget();
  setInterval(() => fetchAndFill(false), 2000);
  fetchAndFill(false);
}

if (window.location.href.includes("resdex.naukri.com")) {
  if (document.readyState === "complete" || document.readyState === "interactive") {
    initSync();
  } else {
    window.addEventListener("DOMContentLoaded", initSync);
    window.addEventListener("load", initSync);
  }
}
