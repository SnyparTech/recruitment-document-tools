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

function isOnPreviewPage() {
  // Candidate detail/preview page (e.g. /v3/preview?tabKey=profile&sid=...).
  // Not the search form and not the results list — the extension must not
  // try to fill a form here (there isn't one), which is what caused
  // "Form not detected within timeout" while HR was just viewing a profile.
  const href = window.location.href;
  return href.includes("/v3/preview") || href.includes("tabKey=profile");
}

function isOnFormPage() {
  return !isOnResultsPage() && !isOnPreviewPage();
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
// Employment Details section: fill Notice Period only, skip everything else.
const EMPLOYMENT_NOTICE_ONLY = true;

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

// Real Resdex suggestion/dropdown items (skills, designations, locations) are
// always short single values — never multi-hundred-character text. Without this
// cap, the broad class-substring selectors above (e.g. div[class*='option'])
// can accidentally match an unrelated on-page element like a "similar
// candidates" preview card (which can run to 1000+ characters of bio text)
// and, if clicked as a false-positive "suggestion", trigger a real navigation
// away from the form mid-fill. Confirmed live: a candidate bio card containing
// the substring "AI Engineer" was matched and clicked instead of the actual
// Designation dropdown option, navigating the page to /v3/search prematurely.
const MAX_SUGGESTION_TEXT_LENGTH = 150;

function isPlausibleSuggestionElement(el) {
  const text = el.textContent.trim();
  return text.length > 0 && text.length <= MAX_SUGGESTION_TEXT_LENGTH;
}

async function waitForDropdown(maxMs = 1500) {
  const step = 150;
  let elapsed = 0;
  while (elapsed < maxMs) {
    await sleep(step);
    elapsed += step;
    const sugs = document.querySelectorAll(SUGGESTION_SELECTORS);
    if (Array.from(sugs).some(s => s.offsetParent !== null && isPlausibleSuggestionElement(s))) return true;
  }
  return false;
}

// Real typeahead dropdowns render directly below/above the field that opened
// them. SUGGESTION_SELECTORS queries the whole document, so without this
// proximity filter it also matches unrelated, still-visible text elsewhere on
// the page (leftover chips from another field, sidebar filters, "recommended
// skills" widgets) — confirmed live: designation lookups matched a sidebar
// "Engineering - Software & QA" filter and a concatenated keyword-chip blob
// instead of the real dropdown option, because both scored high enough on
// substring/token overlap alone.
const DROPDOWN_PROXIMITY_PX = 400;

// Naukri's combobox inputs (role="combobox") point at their real option list
// via aria-owns/aria-controls, rendered as a separate DOM subtree elsewhere in
// the page — not matched by any of SUGGESTION_SELECTORS' class-name guesses.
// Confirmed live: minExp/maxExp inputs carry aria-owns="mu6xgaf9xxk6w" etc.,
// and the actual numeric options only ever live inside that element. When
// available this is authoritative and replaces the generic/proximity search
// entirely, instead of just narrowing it.
function getComboboxListbox(el) {
  if (!el) return null;
  const id = el.getAttribute('aria-owns') || el.getAttribute('aria-controls');
  if (!id) return null;
  return document.getElementById(id);
}

function clickBestSuggestion(targetText, nearEl = null, minScore = 70) {
  if (!targetText) return false;
  const target = targetText.toLowerCase().trim();
  const targetNorm = target.replace(/[^a-z0-9]/g, '');
  const tokens = target.split(/[\s\/\-_,]+/).filter(w => w.length >= 2);

  const listbox = getComboboxListbox(nearEl);
  let all;

  if (listbox) {
    let opts = Array.from(listbox.querySelectorAll("[role='option'], li"))
      .filter(s => s.offsetParent !== null);
    if (opts.length === 0) {
      opts = Array.from(listbox.querySelectorAll("div, span"))
        .filter(s => s.offsetParent !== null && s.children.length === 0);
    }
    all = opts.filter(isPlausibleSuggestionElement);
  } else {
    all = Array.from(document.querySelectorAll(SUGGESTION_SELECTORS))
      .filter(s => s.offsetParent !== null && isPlausibleSuggestionElement(s));

    if (nearEl) {
      const anchorRect = nearEl.getBoundingClientRect();
      all = all.filter((s) => {
        const r = s.getBoundingClientRect();
        return Math.abs(r.top - anchorRect.bottom) <= DROPDOWN_PROXIMITY_PX
          || Math.abs(anchorRect.top - r.bottom) <= DROPDOWN_PROXIMITY_PX;
      });
    }
  }

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

  // 70 = "startsWith"/"includes" tier (real value, real widget). The 40-69
  // token-overlap tier below it is too permissive — it clicked unrelated
  // page text sharing one word (see DROPDOWN_PROXIMITY_PX comment above), so
  // anything scoring under 70 is treated as no match and falls through to
  // the free-text confirm path in typeAndSelectFromDropdown instead.
  if (bestItem && bestScore >= minScore) {
    console.log(`[Snypar Bot] Selected suggestion: "${bestItem.textContent.trim()}" (score: ${Math.round(bestScore)}) for "${targetText}"`);
    bestItem.click();
    return true;
  }
  return false;
}

// Confirm/advance with Tab, as a human does. Never dispatch Enter: Naukri's
// form-level listener treats it as "submit search".
function pressTab(el) {
  const init = { key: 'Tab', code: 'Tab', keyCode: 9, which: 9, bubbles: true, cancelable: true };
  el.dispatchEvent(new KeyboardEvent('keydown', init));
  el.dispatchEvent(new KeyboardEvent('keyup', init));
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

  // Listbox can vanish/re-render while typing (seen for Location) — retry.
  let selected = false;
  for (let attempt = 0; attempt < 6 && !selected; attempt++) {
    if (clickBestSuggestion(cleanText, input)) {
      await sleep(400);
      selected = true;
      console.log(`[Snypar Bot] ✓ "${cleanText}" selected (${fieldLabel})`);
    } else {
      await sleep(250);
    }
  }

  if (!selected) {
    // Tab (never Enter — Enter triggers Naukri's form-level search submit).
    pressTab(input);
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

  // Keywords: only accept an (almost) exact suggestion; otherwise type it as-is and Tab,
  // so "Databricks" never turns into "Databricks Unified Data Analytics".
  if (clickBestSuggestion(cleanKw, kwInput, 95)) {
    await sleep(400);
    if (hasKeywordChip(cleanKw) || countKeywordChipsInContainer(container) > chipsBefore || kwInput.value === '') {
      confirmed = true;
      console.log(`[Snypar Bot] ✓ "${cleanKw}" added via suggestion click`);
    }
  }

  if (!confirmed) {
    pressTab(kwInput);
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
    .filter(el => el.offsetParent !== null && isPlausibleSuggestionElement(el));

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
  // Naukri collapsers: div.naukri-collapser(-collapsed|-expanded) with a header row.
  const want = sectionName.toLowerCase();
  const collapsers = Array.from(document.querySelectorAll("div.naukri-collapser"));
  const collapser = collapsers.find((c) => {
    const h = c.querySelector(".naukri-collapser-header-row");
    return h && h.textContent.toLowerCase().includes(want);
  });
  if (collapser) {
    if (collapser.classList.contains("naukri-collapser-collapsed")) {
      const header = collapser.querySelector(".naukri-collapser-header-row");
      header.scrollIntoView({ block: "center" });
      header.click();
      await sleep(500);
      console.log(`[Snypar Bot] ✓ Expanded section "${sectionName}"`);
    }
    return;
  }

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
  if (!el) {
    // Selector list is a guess at Naukri's DOM — log every "exp"-related
    // element still on the page so a failed match is diagnosable from the
    // console instead of silently no-oping the whole experience filter.
    const candidates = Array.from(document.querySelectorAll(
      "[id*='exp' i], [name*='exp' i], [class*='exp' i]"
    )).map(e => ({
      tag: e.tagName.toLowerCase(),
      id: e.id || null,
      name: e.getAttribute("name") || null,
      cls: (e.className && e.className.toString()) || null,
    }));
    console.warn(
      `[Snypar Bot] Experience selector matched nothing ("${selector}"). ` +
      `exp-like elements on page:`, candidates
    );
    return false;
  }

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
    // Human opens the dropdown by clicking the input first; without that the
    // aria-owns listbox stays empty (seen in recorder trace).
    for (const type of ["mousedown", "mouseup", "click"]) {
      el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
    }
    el.focus();
    await sleep(300);
    setNativeValue(el, valStr);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(300);

    // el is a role="combobox" input whose real option list lives in a separate
    // aria-owns/aria-controls element (see getComboboxListbox) — confirmed live
    // via DOM dump (aria-owns="mu6xgaf9xxk6w"), not matched by any class-name
    // guess. That listbox populates asynchronously after the input event, so
    // poll briefly instead of reading it once. Only fall back to the generic
    // proximity-filtered scan (which was matching leftover keyword/designation
    // suggestion text, not real numbers) when there's no aria-owns/aria-controls
    // to resolve at all.
    const listbox = getComboboxListbox(el);
    let visibleOptions = [];
    if (listbox) {
      for (let waited = 0; waited < 1200; waited += 150) {
        visibleOptions = Array.from(listbox.querySelectorAll("[role='option'], li"))
          .filter(o => o.offsetParent !== null);
        if (visibleOptions.length === 0) {
          visibleOptions = Array.from(listbox.querySelectorAll("div, span"))
            .filter(o => o.offsetParent !== null && o.children.length === 0);
        }
        if (visibleOptions.length > 0) break;
        await sleep(150);
      }
    }
    if (visibleOptions.length === 0) {
      const elRect = el.getBoundingClientRect();
      visibleOptions = Array.from(document.querySelectorAll(
        "div.sug-item, li.suggestion-item, div[class*='option'], li[class*='option'], ul li"
      )).filter((opt) => {
        if (opt.offsetParent === null) return false;
        const r = opt.getBoundingClientRect();
        return Math.abs(r.top - elRect.bottom) <= DROPDOWN_PROXIMITY_PX
          || Math.abs(elRect.top - r.bottom) <= DROPDOWN_PROXIMITY_PX;
      });
    }
    console.log(
      `[Snypar Bot] setExperience("${selector}", "${valStr}") — ${visibleOptions.length} visible option(s):`,
      visibleOptions.slice(0, 10).map(o => o.textContent.trim())
    );

    // Exact text match first (handles plain "5"), then a numeric match that
    // tolerates suffixes like "5 Years"/"5+ Yrs" — the exact-only check was
    // silently matching nothing for fields whose options render with a suffix.
    let opt = visibleOptions.find(o => o.textContent.trim() === valStr);
    if (!opt) {
      const numVal = parseFloat(valStr);
      opt = visibleOptions.find(o => parseFloat(o.textContent.trim()) === numVal);
    }
    if (opt) {
      console.log(`[Snypar Bot] setExperience matched option "${opt.textContent.trim()}" — clicking.`);
      opt.click();
      await sleep(200);
      const ok = fieldHasValue(selector);
      console.log(`[Snypar Bot] setExperience("${selector}") after option click — value="${document.querySelector(selector)?.value}" verified=${ok}`);
      return ok;
    }

    console.warn(`[Snypar Bot] setExperience("${selector}") — no matching option found, falling back to Tab key.`);
    // Dump the real markup around this field once, on the failing path only —
    // fieldHasValue() only reads el.value, which setNativeValue() already set
    // directly; that makes verification pass even when Naukri's own dropdown
    // widget never registered a real selection (its confirm handler may live
    // on a bubble-phase wrapper, not on the input itself). Until real DOM is
    // captured from a live run, we can't tell which case this is — log it.
    const wrapper = el.closest("div, li") || el.parentElement;
    console.log(
      `[Snypar Bot] setExperience("${selector}") DOM dump — el.outerHTML:`,
      el.outerHTML,
      "wrapper.outerHTML:",
      wrapper ? wrapper.outerHTML.slice(0, 1500) : null
    );
    // bubbles:false — same reasoning as the keyword/dropdown Enter fallbacks.
    pressTab(el);
    await sleep(200);
    const ok = fieldHasValue(selector);
    console.log(`[Snypar Bot] setExperience("${selector}") after Tab fallback — value="${document.querySelector(selector)?.value}" verified=${ok}`);
    return ok;
  }
}

// ─── Click Pill Button ───────────────────────────────────────────────────────

async function clickPill(sectionName, pillText) {
  if (!pillText) return false;
  await ensureSectionExpanded(sectionName);
  await sleep(300);

  // Same guard as isPlausibleSuggestionElement (see clickBestSuggestion) — a real
  // pill label is always a short value ("Female candidates", "Any UG
  // qualification"), never paragraph-length text. Without this, the broad
  // "span, div, button, label, a, li" query below can match an unrelated
  // candidate-card element elsewhere on the page and click it instead of the
  // intended pill, exactly like the clickBestSuggestion bug found in a live run.
  const allElements = Array.from(document.querySelectorAll(
    "span, div, button, label, a, li"
  )).filter(el => el.offsetParent !== null && isPlausibleSuggestionElement(el));

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

  // Naukri custom dropdown: opener span.selected-value; options li#option-N > div.dropdown-tuple > span.pre-wrap
  const wrap = document.querySelector("div.active-in-wrap");
  if (wrap) {
    const m = String(value).toLowerCase().match(/(\d+)\s*(day|week|month|year)/);
    let want = String(value).toLowerCase().trim();
    if (m) {
      let n = parseInt(m[1], 10);
      let unit = m[2];
      if (unit === "week") { n *= 7; unit = "day"; }
      want = `${n} ${unit}${n === 1 ? "" : "s"}`;
    }
    const norm2 = (t) => (t || "").replace(/\s+/g, " ").trim().toLowerCase();
    // The real interactive element is div.naukri-suggestor-wrapper[role=button]
    // [aria-haspopup=listbox] — dropdown-head/selected-value are just display
    // children inside it. Try that as the primary opener; keep the old
    // children as fallbacks in case markup varies.
    const openers = () => [
      wrap.querySelector("div.naukri-suggestor-wrapper[role='button']"),
      wrap.querySelector("div.naukri-suggestor-wrapper"),
      wrap.querySelector("span.selected-value"),
      wrap.querySelector("span.dropdown-head-value"),
      wrap.querySelector("div.dropdown-head"),
      wrap.querySelector("i.ico-expand"),
      wrap,
    ].filter(Boolean);
    const findOpt = () => {
      // Prefer options inside a listbox the opener now points to via aria-owns
      // /aria-controls, if React set one after opening.
      const owner = wrap.querySelector("[aria-owns], [aria-controls]");
      const owned = owner ? getComboboxListbox(owner) : null;
      const scopes = [owned, document].filter(Boolean);
      for (const scope of scopes) {
        const candidates = Array.from(scope.querySelectorAll(
          "li span.pre-wrap, li div.dropdown-tuple, li, div[role='option'], span.suggestor-tag, div.suggestor-tag"
        )).filter((sp) => sp.offsetParent !== null);
        const exact = candidates.find((sp) => norm2(sp.textContent) === want);
        if (exact) return exact;
      }
      return null;
    };
    const dispatchFullClick = (el) => {
      for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
        try {
          el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
        } catch (e) {
          el.dispatchEvent(new Event(type, { bubbles: true, cancelable: true }));
        }
      }
    };
    // Drop focus/suggestions left over from the keyword field first.
    document.activeElement && document.activeElement.blur && document.activeElement.blur();
    for (const opener of openers()) {
      let opt = findOpt();
      if (!opt) {
        opener.scrollIntoView({ block: "center" });
        opener.click();
        dispatchFullClick(opener);
        await sleep(500);
        opt = findOpt();
        if (!opt) {
          // Give React one more tick, then look at whether the wrapper actually
          // flipped open before giving up on this opener.
          await sleep(400);
          opt = findOpt();
        }
      }
      if (opt) {
        const li = opt.closest("li") || opt;
        li.scrollIntoView({ block: "nearest" });
        li.click();
        dispatchFullClick(li);
        await sleep(400);
        const shown = norm2(wrap.querySelector("span.selected-value")?.textContent);
        console.log(`[Snypar Bot] Active-in "${value}" -> option "${want}", now showing "${shown}"`);
        if (shown.includes(want)) return true;
      }
    }
    const wrapperEl = wrap.querySelector("div.naukri-suggestor-wrapper");
    console.warn(
      `[Snypar Bot] active-in "${want}" could not be selected; aria-expanded=${wrapperEl?.getAttribute("aria-expanded")} wrap html:`,
      wrap.outerHTML.slice(0, 2500)
    );
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

    // Strategy 0: exact chip in #displayDetailsSection (per recorder trace)
    const exactChip = Array.from(document.querySelectorAll(
      "#displayDetailsSection .suggestor-tag.selectable-chip"
    )).find(c => c.textContent.trim().toLowerCase().includes(searchText));
    if (exactChip) {
      const before = exactChip.className;
      exactChip.scrollIntoView({ block: "center" });
      exactChip.click();
      await sleep(200);
      console.log(`[Snypar Bot] ✓ Show-only chip "${target.key}" class before="${before}" after="${exactChip.className}"`);
      ticked++;
      continue;
    }

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
    // Employment Details: ONLY Notice Period is handled (step 6). Designation,
    // dept/role, industry and company fields are intentionally ignored — Naukri
    // auto-suggests those from keywords and filling them narrows results.
    if (plan.notice_period && plan.notice_period.length > 0) {
      updateWidgetStatus("Expanding Employment Details...", "busy", "filling");
      await ensureSectionExpanded("Employment Details");
      await sleep(500);
    }
    if (EMPLOYMENT_NOTICE_ONLY) return;

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
      await ensureSectionExpanded("Employment Details");
      await sleep(500);

      const noticePeriodDisplayMap = {
        "0-15 days": "0 - 15 days",
        "1 month": "1 month",
        "2 months": "2 months",
        "3 months": "3 months",
        "more than 3 months": "more than 3 months",
        "currently serving notice period": "currently serving notice period",
        "any": "any",
      };
      const norm = (t) => t.replace(/\s+/g, " ").trim().toLowerCase();

      // Multi-select: every requested option, plus "Currently serving notice
      // period" which is mandatory whenever a notice period is set.
      const wanted = [];
      for (const np of [...plan.notice_period, "Currently serving notice period"]) {
        const disp = norm(noticePeriodDisplayMap[norm(np)] || np);
        if (!wanted.includes(disp)) wanted.push(disp);
      }

      const chipRoot = document.querySelector("#noticePeriodTags");
      const getChips = () => chipRoot
        ? Array.from(chipRoot.querySelectorAll(".suggestor-tag.selectable-chip"))
        : [];
      if (!getChips().length) {
        console.warn("[Snypar Bot] #noticePeriodTags chips not found — notice period not set");
      }
      for (const disp of wanted) {
        const chip = getChips().find((c) => norm(c.textContent) === disp);
        if (!chip) {
          console.warn(`[Snypar Bot] Notice period chip "${disp}" not found`);
          continue;
        }
        const before = chip.className;
        chip.scrollIntoView({ block: "center" });
        chip.click();
        await sleep(300);
        console.log(`[Snypar Bot] ✓ Notice period chip "${disp}" class before="${before}" after="${chip.className}"`);
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
      console.warn("[Snypar Bot] Field verification failed — blocking auto-submit so the search doesn't run on an incomplete form.");
      showToast("⚠ Some fields did not register (see console) — search NOT submitted. Fix the form and click Search manually.");
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

    if (autoSubmit && !verified) {
      updateWidgetStatus("⚠ Verification failed — search not submitted", "offline", "none");
    } else if (autoSubmit) {
      updateWidgetStatus("Clicking Search Candidates...", "busy");
      await sleep(400);

      // Strategy 1: precise CSS selectors
      const preciseSelectors = [
        "button#adv-search-btn",
        "button#searchButton",
        "button[data-testid='search-btn']",
        "button[data-testid='searchButton']",
        "button.search-btn",
        "button[class*='searchBtn']",
        "button[class*='search-btn']",
        "button[class*='SearchBtn']",
        "button[class*='srchBtn']",
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
    } else if (autoSubmit && !verified) {
      searchVerified = false;
      showToast("⚠ Form incomplete (see console) — please fix the flagged fields and click Search manually.");
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
      fieldsVerified: verified,
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

// ─── Dynamic mandatory-keyword refinement ───────────────────────────────────
// HR toggles which of the already-generated keywords are mandatory on the
// profile-bot website (moving a keyword between plan.keywords.required and
// .preferred). The backend marks that update `_keyword_sync_only: true` —
// rather than re-running the full fillResdexForm (which would retype every
// keyword into a form that already has chips for them, risking duplicates),
// this only flips the star on each EXISTING chip to match the new mandatory
// set, then re-clicks Search Candidates.
async function syncKeywordStarsOnForm(plan) {
  const requiredKws = (plan.keywords && plan.keywords.required) || [];
  const preferredKws = (plan.keywords && plan.keywords.preferred) || [];
  const mandatoryNorm = requiredKws.map((k) => k.toLowerCase().trim().replace(/[^a-z0-9]/g, ""));
  const optionalNorm = preferredKws.map((k) => k.toLowerCase().trim().replace(/[^a-z0-9]/g, ""));

  const chips = document.querySelectorAll(
    "div[class*='chip'], span[class*='chip'], div[class*='tag'], span[class*='tag'], li[class*='chip'], li[class*='tag'], div[class*='pill'], span[class*='pill'], [class*='tuple']"
  );
  let toggled = 0;
  for (const chip of chips) {
    const chipNorm = chip.textContent.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (!chipNorm) continue;

    let want = null;
    if (mandatoryNorm.some((kw) => kw && chipNorm.includes(kw))) want = true;
    else if (optionalNorm.some((kw) => kw && chipNorm.includes(kw))) want = false;
    if (want === null) continue; // chip isn't one of our tracked keywords — leave it

    const star = chip.querySelector(
      "[class*='star'], [class*='Star'], [title*='Mandatory'], [title*='mandatory'], [title*='Must have'], svg, button"
    );
    if (!star) continue;
    const cls = (star.className && star.className.toString()) || "";
    const pressed = star.getAttribute("aria-pressed");
    const isActive = cls.includes("active") || cls.includes("selected") || cls.includes("starred") || pressed === "true";
    if (isActive !== want) {
      star.click();
      toggled++;
      await sleep(200);
    }
  }
  console.log(`[Snypar Bot] Keyword mandatory sync: ${toggled} star(s) toggled.`);
  return toggled;
}

async function clickSearchButtonAndVerify() {
  updateWidgetStatus("Re-running search with updated keywords...", "busy");
  await sleep(300);
  const allBtns = Array.from(document.querySelectorAll(
    "button#adv-search-btn, button, a[role='button'], input[type='submit'], input[type='button']"
  ));
  const searchBtn = allBtns.find((b) => {
    const txt = (b.value || b.textContent || "").trim().toLowerCase();
    return b.id === "adv-search-btn" ||
      ((txt.includes("search candidate") || txt === "search" || txt === "search candidates") && b.offsetParent !== null);
  });
  if (!searchBtn) {
    updateWidgetStatus("⚠ Search button not found", "offline");
    return false;
  }
  searchBtn.scrollIntoView({ behavior: "smooth", block: "center" });
  await sleep(300);
  searchBtn.click();
  const verified = await waitForResultsPageVerified(10000);
  updateWidgetStatus(verified ? "✓ Search re-run with updated keywords" : "⚠ Search click unconfirmed", verified ? "online" : "offline");
  return verified;
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
  // Leaf-most match only: an outer wrapper whose class merely contains e.g.
  // "role" would otherwise return the whole card's text truncated to 120 chars.
  const matches = (el) => {
    const cls = (el.className && el.className.toString() || "").toLowerCase();
    return hints.some((h) => cls.includes(h));
  };
  const all = container.querySelectorAll("*");
  for (const el of all) {
    if (!matches(el)) continue;
    if (Array.from(el.querySelectorAll("*")).some(matches)) continue;
    const t = safeText(el);
    if (t && t.length <= 100) return t;
  }
  return null;
}

// Label/pattern based fallback on the card's visible text — independent of
// Naukri's (unknown, unstable) class names. Lines like "Current: Sr Engineer at
// Acme", "Education: B.Tech", "Notice period: 15 days", "Key skills: a, b".
function splitSkills(text) {
  return text.split(/[,|•·]/).map((x) => x.trim()).filter((x) => x && x.length < 60 && !/^more$/i.test(x)).slice(0, 40);
}

function parseCardText(container) {
  const raw = (container.innerText || container.textContent || "");
  const lines = raw.split(/\n+/).map((l) => l.replace(/\s+/g, " ").trim()).filter(Boolean);
  const out = { title: null, company: null, location: null, education: null, notice_period: null, skills: [], experience: null };
  const labelVal = (line, labels) => {
    const m = line.match(new RegExp("^(?:" + labels + ")(?:\\s*[:\\-–]\\s*|\\s+)(\\S.*)$", "i"));
    return m ? m[1].trim() : null;
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const next = lines[i + 1] || null;
    // Value can be on the same line after the label, or on the next line.
    const val = (labels) => labelVal(line, labels) ||
      (new RegExp("^(?:" + labels + ")\\s*:?$", "i").test(line) ? next : null);

    if (!out.title || !out.company) {
      const cur = val("current(?: designation| company)?|designation|current role|previous");
      if (cur) {
        const m = cur.match(/^(.+?)\s+at\s+(.+)$/i);
        if (m) { out.title = out.title || m[1].trim(); out.company = out.company || m[2].trim(); }
        else if (!out.title) out.title = cur;
      }
    }
    if (!out.company) {
      const c = val("current company|company|employer|previous company");
      if (c) out.company = c;
    }
    if (!out.location) {
      const l = val("current location|location|current loc|pref(?:erred|\\.)? ?locations?");
      if (l) out.location = l;
    }
    if (!out.education) {
      const e = val("education|qualification|highest qualification");
      if (e) out.education = e;
    }
    if (!out.notice_period) {
      const n = val("notice period|availability to join|notice");
      if (n) out.notice_period = n;
    }
    if (!out.skills.length) {
      const k = val("key ?skills?|skills|keywords");
      if (k) {
        // Skill list can wrap onto following lines; read until the next labelled row.
        let full = k;
        const stop = /^(?:current|previous|education|pref|may also know|key ?skills?|\d+ similar profiles)/i;
        for (let j = i + (labelVal(line, "key ?skills?|skills|keywords") ? 1 : 2); j < lines.length && !stop.test(lines[j]); j++) full += " | " + lines[j];
        out.skills = splitSkills(full);
      }
    }
    const may = val("may also know");
    if (may) out.also_know = splitSkills(may);
  }
  for (const line of lines) {
    const hm = line.match(/^(\d{1,2}\s*y(?:\s*\d{1,2}\s*m)?)\s*(?:[|•·]\s*)?(?:(?:₹|Rs\.?)\s*[\d.,]+\s*(?:Lacs?|LPA|Lakhs?)\s*(?:[|•·]\s*)?)?(.*)$/i);
    if (hm) {
      out.experience = out.experience || hm[1].trim();
      const loc = hm[2].trim();
      if (!out.location && loc && loc.length < 60) out.location = loc;
      break;
    }
  }
  // "5 Yrs | ₹ 12 Lacs | Hyderabad" style summary rows: split on separators.
  if (!out.location || !out.experience) {
    for (const line of lines) {
      if (!/[|•·]/.test(line)) continue;
      const parts = line.split(/[|•·]/).map((x) => x.trim()).filter(Boolean);
      for (const part of parts) {
        if (!out.experience && /^\d{1,2}(?:\.\d+)?\s*(?:yrs?|years?)/i.test(part)) out.experience = part;
        else if (!out.location && /^[A-Za-z][A-Za-z .,&\/-]{2,60}$/.test(part) &&
                 !/lacs?|lpa|yrs?|years?|months?|days?|notice/i.test(part) &&
                 parts.some((p) => /\d\s*(?:yrs?|years?)/i.test(p))) {
          out.location = part;
        }
      }
    }
  }
  return out;
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
  const text = (container.innerText || container.textContent || "").replace(/\s+/g, " ");
  const match =
    text.match(/(\d{1,2}(?:\.\d{1,2})?)\s*(?:yrs?|years?|y)(?:\s*,?\s*\d{1,2}\s*(?:months?|mos?|m))?/i);
  if (match) return match[0].trim();
  // 0-experience Resdex cards show the literal word "Fresher" instead of a
  // "Xy Ym" pattern — the regex above never matches that, so these candidates
  // fell through with no experience value at all (noisy dump + ranking marks
  // the dimension "unavailable" instead of correctly scoring 0 years).
  // Backend's parse_experience_years() has a matching "fresher" -> 0.0 case.
  if (/\bfresher\b/i.test(text)) return "Fresher";
  return null;
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

  // Neither known strategy matched. Distinguish "Naukri genuinely returned 0
  // results" from "our selectors miss the real markup" without guessing at
  // more selectors — log what's actually on the page so the next console
  // paste is conclusive instead of another round of blind selector tweaks.
  const bodyText = (document.body.textContent || "").slice(0, 2000);
  const looksLikeNoResults = /\bno\s+(matching\s+)?(candidates?|results?|profiles?)\b/i.test(bodyText);
  console.log(
    "[Snypar Bot] findCandidateContainers — no containers via known selectors.",
    "looksLikeNoResultsMessage:", looksLikeNoResults,
    "url:", window.location.href,
    "bodyTextSample:", bodyText.slice(0, 300)
  );

  return {
    pairs: [],
    strategy: "none",
    warnings: [
      looksLikeNoResults
        ? "Naukri appears to show a genuine 'no results' state for this search."
        : "No candidate containers detected with any known strategy — selectors likely stale; see DOM dump logged above.",
    ],
  };
}

function extractOneCandidate(container, anchor) {
  const name = anchor ? safeText(anchor, 100) : (
    findChildTextByClassHints(container, ["name", "candidatename"]) ||
    safeText(container.querySelector("h1, h2, h3, strong"), 100)
  );
  if (!name) return null;

  const txt = parseCardText(container);
  const skills = findSkillsInContainer(container);
  const result = {
    name,
    title: txt.title || findChildTextByClassHints(container, FIELD_CLASS_HINTS.title),
    company: txt.company || findChildTextByClassHints(container, FIELD_CLASS_HINTS.company),
    experience: extractExperienceText(container) || txt.experience,
    location: txt.location || findChildTextByClassHints(container, FIELD_CLASS_HINTS.location),
    skills: [...new Set([...(txt.skills.length ? txt.skills : skills), ...(txt.also_know || [])])],
    education: txt.education || findChildTextByClassHints(container, FIELD_CLASS_HINTS.education),
    notice_period: txt.notice_period || findChildTextByClassHints(container, FIELD_CLASS_HINTS.notice_period),
    profile_url: anchor && anchor.href ? anchor.href : null,
    resdex_candidate_id: extractResdexCandidateId(anchor),
  };
  // One-time calibration dump: if the key fields are still empty, log the real
  // card markup/text so selectors can be written from it instead of guessed.
  if (!window.__snyCardDumped && (!result.experience || !result.notice_period || result.skills.length < 2)) {
    window.__snyCardDumped = true;
    console.log("[Snypar Bot] Card is missing experience/notice/skills. Card innerText:",
      (container.innerText || "").slice(0, 1200), "\nCard outerHTML:", container.outerHTML.slice(0, 3000));
  }
  return result;
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

const SUBMIT_CHUNK_SIZE = 50;       // backend accepts at most 50 candidates per request
const AUTOPAGE_KEY = "snypar_autopage_active";
const AUTOPAGE_MAX_PAGES = 200;      // safety cap on pages walked per search
const COMPLETED_SIDS_KEY = "snypar_completed_sids";
const COMPLETED_SIDS_MAX = 50; // bounded ring buffer, oldest dropped first

function isSidCompleted(sid) {
  try {
    const list = JSON.parse(localStorage.getItem(COMPLETED_SIDS_KEY) || "[]");
    return list.includes(sid);
  } catch (e) {
    return false;
  }
}

function markSidCompleted(sid) {
  try {
    let list = JSON.parse(localStorage.getItem(COMPLETED_SIDS_KEY) || "[]");
    list = list.filter((s) => s !== sid);
    list.push(sid);
    if (list.length > COMPLETED_SIDS_MAX) list = list.slice(list.length - COMPLETED_SIDS_MAX);
    localStorage.setItem(COMPLETED_SIDS_KEY, JSON.stringify(list));
  } catch (e) {
    // localStorage unavailable — non-fatal, just means the anti-repagination
    // guard won't persist across reloads for this session.
  }
}

function currentResultsPageNo() {
  const n = parseInt(new URL(window.location.href).searchParams.get("pageNo") || "1", 10);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function currentResPerPage() {
  const n = parseInt(new URL(window.location.href).searchParams.get("resPerPage") || "40", 10);
  return Number.isFinite(n) && n > 0 ? n : 40;
}

async function postCandidatesInChunks(candidates, diagnostics, page, searchId) {
  let lastResult = null;
  for (let i = 0; i < candidates.length; i += SUBMIT_CHUNK_SIZE) {
    const chunk = candidates.slice(i, i + SUBMIT_CHUNK_SIZE);
    const result = await postToBackend("/search/results", {
      search_id: searchId || undefined,
      page,
      candidates: chunk,
      diagnostics: i === 0 ? diagnostics : undefined,
    });
    if (!result) return null;
    lastResult = result;
  }
  return lastResult;
}

function currentSearchId() {
  return new URL(window.location.href).searchParams.get("sid");
}

function readTotalResultPages() {
  // Resdex shows "Page 1 of 24" next to the pager.
  const m = (document.body.innerText || "").match(/Page\s+\d+\s+of\s+(\d+)/i);
  return m ? parseInt(m[1], 10) : null;
}

let extractionInFlight = false;

async function extractAndSubmitCandidatesIfNeeded(forced = false) {
  const currentUrl = window.location.href;
  if (!forced && lastExtractedResultsUrl === currentUrl) {
    return; // already extracted this exact results view
  }
  if (extractionInFlight) return; // the 2s poll must not start a second overlapping run
  extractionInFlight = true;
  try {
    await extractAndSubmitOnce(currentUrl);
  } finally {
    extractionInFlight = false;
  }
}

async function extractAndSubmitOnce(currentUrl) {
  // A different search id (user pressed Modify / ran a new search) means fresh results:
  // collect every page of it too — UNLESS this sid was already walked to completion
  // before (e.g. HR paged back to page 1 of the same search). localStorage (not
  // sessionStorage) so it survives a full page reload / new tab, since that's exactly
  // when this matters: without it, revisiting page 1 of an already-fully-collected
  // search re-triggers the whole auto-pagination walk and re-posts every page.
  const sid = currentSearchId();
  const alreadyCompleted = sid && isSidCompleted(sid);
  if (sid && sessionStorage.getItem("snypar_last_sid") !== sid) {
    sessionStorage.setItem("snypar_last_sid", sid);
    if (!alreadyCompleted && sessionStorage.getItem(AUTOPAGE_KEY) !== "1") {
      sessionStorage.setItem(AUTOPAGE_KEY, "1");
      sessionStorage.removeItem("snypar_autopage_total");
    }
  }
  if (alreadyCompleted) {
    // Still extract+submit the currently visible page (keeps a manual re-search or a
    // page revisit in sync — dedup on the backend makes this idempotent), but never
    // resume the multi-page walk for a search we already finished collecting.
    sessionStorage.removeItem(AUTOPAGE_KEY);
  }

  // SPA pagination swaps cards after the URL changes; wait for the card count to settle.
  let prev = -1;
  for (let i = 0; i < 20; i++) {
    const n = findCandidateContainers().pairs.length;
    if (n > 0 && n === prev) break;
    prev = n;
    await sleep(700);
  }

  const { candidates, diagnostics } = extractCandidatesFromResultsPage();

  if (candidates.length === 0) {
    updateWidgetStatus("⚠ No candidates detected on results page", "offline");
    return; // keep the auto-pagination flag; the next poll retries
  }

  const pageNo = currentResultsPageNo();
  const result = await postCandidatesInChunks(candidates, diagnostics, pageNo, sid);

  if (!result) {
    console.warn("[Snypar Bot] Failed to submit extracted candidates to backend — will retry on next poll.");
    updateWidgetStatus("⚠ Could not submit candidates to server", "offline");
    return;
  }

  lastExtractedResultsUrl = currentUrl;
  const total = result.total_stored ?? candidates.length;
  const totalPages = readTotalResultPages();
  updateWidgetStatus(`✓ Page ${pageNo}${totalPages ? "/" + totalPages : ""}: ${candidates.length} found (${total} total stored)`, "online");

  if (sessionStorage.getItem(AUTOPAGE_KEY) !== "1") return;

  // Last page: known total, else a short page.
  const lastPage = totalPages ? pageNo >= totalPages
                              : candidates.length < currentResPerPage();
  if (lastPage || pageNo >= AUTOPAGE_MAX_PAGES) {
    console.log(`[Snypar Bot] Auto-pagination finished at page ${pageNo} (${total} candidates stored).`);
    sessionStorage.removeItem(AUTOPAGE_KEY);
    sessionStorage.removeItem("snypar_autopage_total");
    if (sid) markSidCompleted(sid);
    updateWidgetStatus(`✓ Done: ${total} candidates from ${pageNo} page(s)`, "online");
    return;
  }

  console.log(`[Snypar Bot] Auto-pagination: going to page ${pageNo + 1}${totalPages ? " of " + totalPages : ""}`);
  await sleep(1200);
  const nextUrl = new URL(window.location.href);
  nextUrl.searchParams.set("pageNo", String(pageNo + 1));
  window.location.href = nextUrl.toString();
}

async function fetchAndFill(forced = false) {
  if (isFilling) return;

  if (isOnPreviewPage()) {
    updateWidgetStatus("Viewing candidate profile", "online");
    return;
  }

  if (isOnResultsPage()) {
    updateWidgetStatus("✓ Search Results Active", "online");
    await extractAndSubmitCandidatesIfNeeded(forced);
    // A keyword-mandatory change made on the website while HR is looking at
    // results won't be picked up by the plan-fetch branch below (that branch
    // is skipped whenever we're on the results page) — check for it here and
    // hop back to the form so the next poll (now on the form) can apply it.
    const pending = await fetchFromBackend("/search/active-plan");
    if (pending && pending.has_plan && pending.plan?._keyword_sync_only &&
        pending.timestamp > lastProcessedTimestamp) {
      updateWidgetStatus("Applying updated mandatory keywords...", "busy");
      await ensureOnFormPage();
    }
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

      if (fetchedData.plan?._keyword_sync_only) {
        // HR only changed which keywords are mandatory — flip stars on the
        // existing chips instead of retyping the whole form.
        await syncKeywordStarsOnForm(fetchedData.plan);
        const verified = await clickSearchButtonAndVerify();
        if (verified) {
          sessionStorage.setItem(AUTOPAGE_KEY, "1");
          sessionStorage.removeItem("snypar_autopage_total");
          sessionStorage.setItem(FILL_CACHE_KEY, planTs);
        } else {
          console.warn("[Snypar Bot] Keyword sync search re-run not verified — will retry on next eligible poll.");
        }
        return;
      }

      if (shouldSubmit) {
        sessionStorage.setItem(AUTOPAGE_KEY, "1");
        sessionStorage.removeItem("snypar_autopage_total");
      }
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
