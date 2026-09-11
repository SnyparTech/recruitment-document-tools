/**
 * Snypar Resdex Form Auto-Filler Content Script
 * Runs inside the authenticated Naukri Resdex tab opened by Naukri Launcher.
 *
 * Strategy:
 *  - Each keyword is typed character-by-character, then confirmed with Enter / suggestion click
 *  - Before clicking "Search Candidates", verifies DOM state: chips exist for keywords,
 *    experience fields have values, etc. — NOT time-based.
 */

const BACKEND_URLS = [
  "http://127.0.0.1:8001/search/active-plan",
  "http://localhost:8001/search/active-plan",
];
let lastProcessedTimestamp = 0;
let isFilling = false;

// Naukri Resdex URL patterns  (ground truth from selectors.py)
// Form page:    https://resdex.naukri.com/v3?activeTab=advSrch
// Results page: https://resdex.naukri.com/v3/search?sid=...
const RESDEX_FORM_URL = "https://resdex.naukri.com/v3?activeTab=advSrch";
const RESDEX_BASE_URL = "https://resdex.naukri.com";

function isOnResultsPage() {
  const href = window.location.href;
  // Results page always has /v3/search in the path (the form page is /v3 without /search)
  return href.includes("/v3/search");
}

function isOnFormPage() {
  return !isOnResultsPage();
}

// ─── Floating Status Widget ──────────────────────────────────────────────────

function createFloatingWidget() {
  if (document.getElementById("snypar-resdex-floating-badge")) return;
  const badge = document.createElement("div");
  badge.id = "snypar-resdex-floating-badge";
  badge.innerHTML = `
    <span class="snypar-badge-dot" id="snypar-dot"></span>
    <span id="snypar-status-text" style="font-weight:500;">⚡ Snypar Bot Active</span>
  `;
  document.body.appendChild(badge);
}

function updateWidgetStatus(text, state = "online") {
  const dot = document.getElementById("snypar-dot");
  const label = document.getElementById("snypar-status-text");
  if (!dot || !label) return;
  label.innerText = text;
  dot.className =
    "snypar-badge-dot " +
    (state === "offline" ? "offline" : state === "busy" ? "busy" : "");
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

// ─── React-Compatible Value Setter ──────────────────────────────────────────

function setNativeValue(el, value) {
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value"
  ).set;
  nativeSetter.call(el, value);
}

// ─── Shared suggestion selectors (autocomplete + AI suggested keywords) ────────
// Covers Naukri's regular autocomplete items AND the "✨ AI suggested keywords" chips.
const SUGGESTION_SELECTORS = [
  // Regular autocomplete items
  "div.sug-item", "li.sug-item",
  "li.suggestion-item", "div.suggestion-item",
  "div.keyword-sug", "ul.suggestor-list li",
  "li[role='option']", "div[role='option']",
  "div[class*='dropdown'] li",
  // AI suggested keywords panel chips (various class-name patterns Naukri may use)
  "div[class*='aiKeyword']", "span[class*='aiKeyword']",
  "div[class*='ai-keyword']", "span[class*='ai-keyword']",
  "div[class*='suggestedKeyword'] span", "div[class*='suggestedKeyword'] button",
  "div[class*='suggested-keyword'] span", "div[class*='suggested-keyword'] button",
  "div[class*='keywordSuggest'] span", "div[class*='keyword-suggest'] span",
  "div[class*='aiSuggest'] span",  "div[class*='ai-suggest'] span",
].join(", ");

// Poll until any visible suggestion appears (up to maxMs)
async function waitForDropdown(maxMs = 2000) {
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

// Click the best-matching visible suggestion for targetText.
// Priority: exact match → starts-with (5 chars) → any word match → first visible.
// NEVER fires Enter — Enter submits the Naukri search form.
function clickBestSuggestion(targetText) {
  const target = targetText.toLowerCase().trim();
  const words  = target.split(' ').filter(w => w.length > 2);
  const all    = Array.from(document.querySelectorAll(SUGGESTION_SELECTORS))
                      .filter(s => s.offsetParent !== null && s.textContent.trim().length > 0);

  const match =
    all.find(s => s.textContent.trim().toLowerCase() === target)                                          ||
    all.find(s => s.textContent.trim().toLowerCase().startsWith(target.substring(0, Math.min(5, target.length)))) ||
    all.find(s => words.some(w => s.textContent.toLowerCase().includes(w)))                               ||
    all[0]; // fallback: first visible suggestion

  if (match) { match.click(); return true; }
  return false;
}

// Generic: type into any autocomplete field and select from dropdown (location, designation, role)
async function typeAndSelectFromDropdown(input, text, fieldLabel = '') {
  input.focus();
  await sleep(150);

  // Clear via execCommand
  input.select();
  document.execCommand('selectAll');
  document.execCommand('delete');
  await sleep(100);

  // Insert via execCommand (trusted InputEvent → triggers autocomplete)
  const inserted = document.execCommand('insertText', false, text);
  if (!inserted) {
    setNativeValue(input, '');
    for (const char of text) {
      const cc = char.charCodeAt(0);
      input.dispatchEvent(new KeyboardEvent('keydown', { key: char, keyCode: cc, which: cc, bubbles: true, cancelable: true }));
      setNativeValue(input, input.value + char);
      input.dispatchEvent(new InputEvent('input', { inputType: 'insertText', data: char, bubbles: true, cancelable: true }));
      input.dispatchEvent(new KeyboardEvent('keyup', { key: char, keyCode: cc, which: cc, bubbles: true }));
      await sleep(50);
    }
  }

  // Wait for dropdown
  const appeared = await waitForDropdown(2000);
  console.log(`[Snypar Bot] ${fieldLabel} dropdown ${appeared ? '✓' : '✗'} for "${text}"`);

  // Click the best matching suggestion
  if (clickBestSuggestion(text, 0)) {
    await sleep(400);
    console.log(`[Snypar Bot] ✓ "${text}" selected (${fieldLabel})`);
  } else {
    console.warn(`[Snypar Bot] ✗ No suggestion clicked for "${text}" (${fieldLabel})`);
  }

  await sleep(200);
  return true;
}

// KEY FIX: Use document.execCommand('insertText') for isTrusted=true events.
// NEVER use Enter in keyword field — it submits the form, not creates a chip.
async function typeAndConfirmKeyword(kwInput, keyword) {
  kwInput.focus();
  await sleep(150);

  // Clear field via execCommand
  kwInput.select();
  document.execCommand('selectAll');
  document.execCommand('delete');
  await sleep(100);

  // Insert text (trusted InputEvent → triggers React autocomplete)
  const inserted = document.execCommand('insertText', false, keyword);
  if (!inserted) {
    setNativeValue(kwInput, '');
    for (const char of keyword) {
      const cc = char.charCodeAt(0);
      kwInput.dispatchEvent(new KeyboardEvent('keydown', { key: char, keyCode: cc, which: cc, bubbles: true, cancelable: true }));
      setNativeValue(kwInput, kwInput.value + char);
      kwInput.dispatchEvent(new InputEvent('input', { inputType: 'insertText', data: char, bubbles: true, cancelable: true }));
      kwInput.dispatchEvent(new KeyboardEvent('keyup', { key: char, keyCode: cc, which: cc, bubbles: true }));
      await sleep(60);
    }
  }

  // Wait for suggestions (autocomplete or AI suggested keywords panel)
  const appeared = await waitForDropdown(2000);
  console.log(`[Snypar Bot] Suggestion panel ${appeared ? '✓' : '✗'} for "${keyword}"`);

  const chipsBefore = countKeywordChips();
  let confirmed = false;

  // Strategy 1: Click best-matching suggestion (NO Enter — submits form!)
  if (clickBestSuggestion(keyword, chipsBefore)) {
    await sleep(500);
    if (countKeywordChips() > chipsBefore) {
      confirmed = true;
      console.log(`[Snypar Bot] ✓ "${keyword}" added via suggestion click`);
    }
  }

  // Strategy 2: Comma via execCommand (trusted, doesn't submit)
  if (!confirmed) {
    document.execCommand('insertText', false, ',');
    await sleep(500);
    if (countKeywordChips() > chipsBefore) {
      confirmed = true;
      console.log(`[Snypar Bot] ✓ "${keyword}" added via comma`);
    }
  }

  if (!confirmed) {
    console.warn(`[Snypar Bot] ✗ "${keyword}" not confirmed (chips: ${chipsBefore}→${countKeywordChips()})`);
  }

  // Clear for next keyword
  kwInput.focus();
  kwInput.select();
  document.execCommand('selectAll');
  document.execCommand('delete');
  await sleep(200);
}


// ─── Click Mandatory Star on a Keyword Chip ──────────────────────────────────


async function clickKeywordStar(skillName) {
  const clean = skillName.toLowerCase().trim();
  const chips = document.querySelectorAll(
    "div[class*='chip'], span[class*='chip'], div[class*='tag'], span[class*='tag'], li[class*='chip'], li[class*='tag']"
  );
  for (const chip of chips) {
    if (chip.textContent.toLowerCase().includes(clean)) {
      const star = chip.querySelector(
        "[class*='star'], [class*='Star'], [title*='Mandatory'], [title*='mandatory'], svg, button"
      );
      if (star) {
        const cls = (star.className && star.className.toString()) || "";
        const pressed = star.getAttribute("aria-pressed");
        if (!cls.includes("active") && !cls.includes("selected") && pressed !== "true") {
          star.click();
          await sleep(200);
          return true;
        }
      }
    }
  }
  return false;
}

// ─── Count keyword chips currently added ─────────────────────────────────────

function countKeywordChips() {
  return document.querySelectorAll(
    "div[class*='chip'], span[class*='chip'], div[class*='tag'], span[class*='tag'], li[class*='chip'], li[class*='tag']"
  ).length;
}

// ─── Expand Section ───────────────────────────────────────────────────────────

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

// ─── Verify a field has a value (DOM-state check) ────────────────────────────

function fieldHasValue(selector) {
  const el = document.querySelector(selector);
  if (!el) return false;
  if (el.tagName.toLowerCase() === "select") return el.selectedIndex > 0;
  return el.value && el.value.trim().length > 0;
}

// ─── Verify keyword chips were added ─────────────────────────────────────────

function verifyKeywordsAdded(expectedCount) {
  const chips = countKeywordChips();
  return chips >= expectedCount;
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
    // Try closest numeric match
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

    // Try clicking matching option in dropdown
    const options = document.querySelectorAll(
      "div.sug-item, li.suggestion-item, div[class*='option'], li[class*='option'], ul li"
    );
    for (const opt of options) {
      if (
        opt.textContent.trim() === valStr &&
        opt.offsetParent !== null
      ) {
        opt.click();
        await sleep(200);
        return true;
      }
    }

    // Press Enter to confirm
    el.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", keyCode: 13, bubbles: true })
    );
    await sleep(200);
    return fieldHasValue(selector);
  }
}

// ─── Set Active In Dropdown ───────────────────────────────────────────────────

async function setActiveIn(value) {
  const selects = document.querySelectorAll(
    "select#activeIn, select[name='activeIn'], select#searchActivePeriod"
  );
  for (const sel of selects) {
    for (let i = 0; i < sel.options.length; i++) {
      if (sel.options[i].text.toLowerCase().includes(value.toLowerCase())) {
        sel.selectedIndex = i;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
  }
  return false;
}

// ─── Tick Show-Only Checkboxes ────────────────────────────────────────────────

async function tickShowOnlyCheckboxes() {
  const labels = Array.from(document.querySelectorAll("label, span, div"));
  const targets = [
    { key: "verified mobile", selector: "input#verifiedMobile, input[name='verifiedMobile']" },
    { key: "verified email",  selector: "input#verifiedEmail,  input[name='verifiedEmail']"  },
    { key: "attached resume", selector: "input#attachedResume, input[name='attachedResume']" },
  ];

  let ticked = 0;
  for (const target of targets) {
    let input = document.querySelector(target.selector);
    if (input) {
      if (!input.checked) input.click();
      ticked++;
    } else {
      const lbl = labels.find((l) =>
        l.textContent.toLowerCase().includes(target.key)
      );
      if (lbl) {
        const cb = lbl.querySelector("input[type='checkbox']");
        if (cb) {
          if (!cb.checked) cb.click();
        } else {
          lbl.click();
        }
        ticked++;
        await sleep(100);
      }
    }
  }
  return ticked;
}

// ─── DOM-State Verification Before Search ────────────────────────────────────

async function waitForFieldsVerified(plan, timeoutMs = 12000) {
  const start = Date.now();
  const requiredKws = (plan.keywords && plan.keywords.required) || [];
  const preferredKws = (plan.keywords && plan.keywords.preferred) || [];
  const totalKws = [...new Set([...requiredKws, ...preferredKws])].length;

  while (Date.now() - start < timeoutMs) {
    const checks = [];

    // 1. Keywords chips (selectors.py: KEYWORD_CHIP)
    if (totalKws > 0) {
      checks.push({
        name: "keywords",
        ok: countKeywordChips() >= Math.min(totalKws, 1),
      });
    }

    // 2. Experience (selectors.py: MIN_EXP_INPUT uses input[name='minExp'])
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

// ─── Main Form Fill ───────────────────────────────────────────────────────────

async function fillResdexForm(plan) {
  if (isFilling) return;
  isFilling = true;
  console.log("[Snypar Bot] Starting auto-fill with SearchPlan:", plan);

  try {
    // ── STEP 1: Keywords ────────────────────────────────────────────────────
    const requiredKws  = (plan.keywords && plan.keywords.required)  || [];
    const preferredKws = (plan.keywords && plan.keywords.preferred) || [];
    const allKws = [...new Set([...requiredKws, ...preferredKws])];
    const mandatorySet = new Set(requiredKws.map((k) => k.toLowerCase().trim()));

    if (allKws.length > 0) {
      updateWidgetStatus(`Keywords (0/${allKws.length})...`, "busy");

      // Ground-truth selector from selectors.py: KEYWORD_INPUT
      const kwInput = document.querySelector(
        "input[name='ezKeywordsAny'], input[placeholder*='Enter keywords like skills'], " +
        "input#keywords, input.keyword-input, input[name='keyword'], input[id*='keyword']"
      );

      if (kwInput) {
        kwInput.scrollIntoView({ behavior: "smooth", block: "center" });
        await sleep(400);

        for (let i = 0; i < allKws.length; i++) {
          const kw = allKws[i];
          updateWidgetStatus(`Keyword ${i + 1}/${allKws.length}: "${kw}"`, "busy");
          await typeAndConfirmKeyword(kwInput, kw);

          if (mandatorySet.has(kw.toLowerCase().trim())) {
            await sleep(200);
            await clickKeywordStar(kw);
          }

          await sleep(200);
        }

        // Tick global mandatory checkbox if present (selectors.py: MANDATORY_KEYWORDS_CHECKBOX)
        const mustHaveCheck = document.querySelector(
          "input#must-have-checkbox, input[name='must-have-checkbox'], " +
          "input#mandatoryKeywords, input[id*='mustHave'], input[id*='mandatory']"
        );
        if (mustHaveCheck && !mustHaveCheck.checked) {
          mustHaveCheck.click();
          await sleep(200);
        }
      } else {
        console.warn("[Snypar Bot] Keyword input not found. Available inputs:",
          Array.from(document.querySelectorAll("input")).map(i => `${i.name || i.id || i.type} placeholder=${i.placeholder}`).join(", ")
        );
      }
    }

    await sleep(500);

    // ── STEP 2: Experience ──────────────────────────────────────────────────
    // selectors.py: MIN_EXP_INPUT = "input[name='minExp']...", MAX_EXP_INPUT = "input[name='maxExp']..."
    if (plan.min_experience !== null && plan.min_experience !== undefined) {
      updateWidgetStatus("Experience (Min)...", "busy");
      await setExperience(
        "input[name='minExp'], input[placeholder*='Min experience'], input#minExp, select#minExp, select[name='minExp']",
        plan.min_experience
      );
      await sleep(300);
    }
    if (plan.max_experience !== null && plan.max_experience !== undefined) {
      updateWidgetStatus("Experience (Max)...", "busy");
      await setExperience(
        "input[name='maxExp'], input[placeholder*='Max experience'], input#maxExp, select#maxExp, select[name='maxExp']",
        plan.max_experience
      );
      await sleep(300);
    }

    await sleep(400);

    // ── STEP 3: Location ────────────────────────────────────────────────────
    if (plan.current_location && plan.current_location.length > 0) {
      const locInput = document.querySelector(
        "input[name='locations'], input[placeholder*='Add location'], input#location"
      );
      if (locInput) {
        for (let i = 0; i < plan.current_location.length; i++) {
          const loc = plan.current_location[i];
          updateWidgetStatus(`Location ${i + 1}/${plan.current_location.length}: "${loc}"`, "busy");
          await typeAndSelectFromDropdown(locInput, loc, 'Location');
        }
      }
    }



    if (plan.include_relocation) {
      const reloCb = document.querySelector(
        "input#prefLocCheckbox, input[name='prefLocCheckbox'], input#includeRelocation"
      );
      if (reloCb && !reloCb.checked) reloCb.click();
    }

    await sleep(400);

    // ── STEP 4: Salary ──────────────────────────────────────────────────────
    if (plan.salary) {
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
          await sleep(300);
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
          await sleep(300);
        }
      }
    }

    await sleep(400);

    // ── STEP 5: Employment Details — Designation ────────────────────────────
    if (plan.designation && plan.designation.length > 0) {
      updateWidgetStatus("Expanding Employment Details...", "busy");
      await ensureSectionExpanded("Employment Details");
      await sleep(500);

      const desigInput = document.querySelector(
        "input[name='designation'], input#designation, input[placeholder*='Designation'], input[placeholder*='designation']"
      );
      if (desigInput) {
        for (let i = 0; i < plan.designation.length; i++) {
          const desig = plan.designation[i];
          updateWidgetStatus(`Designation ${i + 1}/${plan.designation.length}: "${desig}"`, "busy");
          await typeAndSelectFromDropdown(desigInput, desig, 'Designation');
        }
      }
    }

    // ── STEP 6: Department Role ─────────────────────────────────────────────
    if (plan.department_role && plan.department_role.length > 0) {
      updateWidgetStatus("Expanding Employment Details...", "busy");
      await ensureSectionExpanded("Employment Details");
      await sleep(400);

      const roleInput = document.querySelector(
        "input[name='departmentRole'], input#departmentRole, input[placeholder*='Department'], input[placeholder*='Role']"
      );
      if (roleInput) {
        for (let i = 0; i < plan.department_role.length; i++) {
          const role = plan.department_role[i];
          updateWidgetStatus(`Dept/Role ${i + 1}/${plan.department_role.length}: "${role}"`, "busy");
          await typeAndSelectFromDropdown(roleInput, role, 'Dept/Role');
        }
      }
    }

    await sleep(400);

    // ── STEP 7: Notice Period ───────────────────────────────────────────────
    if (plan.notice_period && plan.notice_period.length > 0) {
      updateWidgetStatus("Notice Period...", "busy");
      await ensureSectionExpanded("Notice Period");
      await sleep(500);

      const labels = Array.from(document.querySelectorAll("label, span, div.checkbox, li"));
      for (const np of plan.notice_period) {
        const npClean = np.toLowerCase();
        const match = labels.find((l) =>
          l.textContent.toLowerCase().includes(npClean)
        );
        if (match) {
          const cb = match.querySelector("input[type='checkbox']");
          if (cb) {
            if (!cb.checked) cb.click();
          } else {
            match.click();
          }
          await sleep(200);
        }
      }
    }

    await sleep(400);

    // ── STEP 8: Additional Details ──────────────────────────────────────────
    updateWidgetStatus("Additional Details...", "busy");
    await ensureSectionExpanded("Additional Details");
    await sleep(500);
    const ticked = await tickShowOnlyCheckboxes();
    console.log(`[Snypar Bot] Ticked ${ticked} show-only checkboxes`);

    await sleep(300);

    // ── STEP 9: Active In ───────────────────────────────────────────────────
    updateWidgetStatus("Active In...", "busy");
    await setActiveIn(plan.active_in || "15 days");
    await sleep(300);

    // ── STEP 10: DOM-STATE VERIFICATION (not time-based) ───────────────────
    updateWidgetStatus("⚙ Verifying all fields...", "busy");
    showToast("⚡ Verifying all fields are complete before searching...");
    const verified = await waitForFieldsVerified(plan, 12000);

    if (!verified) {
      showToast("⚠ Some fields may not have registered — check the form.");
    }

    // ── STEP 11: Click Search Candidates ────────────────────────────────────
    updateWidgetStatus("Clicking Search Candidates...", "busy");
    await sleep(500);

    let searchClicked = false;

    // Try known selectors first
    const submitBtn = document.querySelector(
      "button#searchButton, button[data-testid='search-btn'], a.searchProfiles, button.searchProfiles, button.search-btn, input[value*='Search Candidates'], input[value*='Search']"
    );
    if (submitBtn && submitBtn.offsetParent !== null) {
      submitBtn.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(400);
      submitBtn.click();
      searchClicked = true;
    }

    if (!searchClicked) {
      // Fallback: find any button whose text contains "search candidate"
      const allBtns = Array.from(
        document.querySelectorAll("button, input[type='button'], input[type='submit'], a.btn")
      );
      const searchBtn = allBtns.find((b) =>
        b.textContent.toLowerCase().includes("search candidate") ||
        b.value?.toLowerCase().includes("search candidate")
      );
      if (searchBtn && searchBtn.offsetParent !== null) {
        searchBtn.scrollIntoView({ behavior: "smooth", block: "center" });
        await sleep(400);
        searchBtn.click();
        searchClicked = true;
      }
    }

    if (searchClicked) {
      updateWidgetStatus("✓ Search Submitted!", "online");
      showToast("✓ 'Search Candidates' executed successfully on Naukri Resdex!");
    } else {
      updateWidgetStatus("✓ All Fields Filled!", "online");
      showToast("✓ All criteria completed — manually click 'Search Candidates' if needed.");
    }
  } catch (err) {
    console.error("[Snypar Bot] Auto-fill error:", err);
    updateWidgetStatus("⚠ Error During Fill", "offline");
    showToast(`⚠ Error: ${err.message}`);
  } finally {
    isFilling = false;
  }
}

// ─── Real-Time Sync Loop (Fully Automatic, No Manual Button) ─────────────────

// Wait for keyword input field to appear (form DOM ready)
async function waitForFormReady(timeoutMs = 20000) {
  const start = Date.now();
  // Ground-truth selectors from selectors.py
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
    // Also check if we accidentally ended up on results page
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

// Navigate to search form page if we're on the results page
async function ensureOnFormPage() {
  if (isOnResultsPage()) {
    updateWidgetStatus("Navigating to Search Form...", "busy");
    showToast("⚡ Snypar Bot: Going to search form to fill criteria...");
    console.log("[Snypar Bot] On results page — navigating to form:", RESDEX_FORM_URL);

    // First try clicking the 'Modify' link on the results page
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
      // Navigate directly to form page
      window.location.href = RESDEX_FORM_URL;
    }
    // Navigation will reload the page — the content script reinitialises on new page
    return false; // Signal: do not proceed with fill on this page
  }
  return true; // Already on form page
}

async function fetchAndFill(forced = false) {
  let fetchedData = null;
  for (const url of BACKEND_URLS) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        fetchedData = await res.json();
        break;
      }
    } catch (e) {}
  }

  if (!fetchedData) {
    updateWidgetStatus("Server Offline", "offline");
    return;
  }

  try {
    if (fetchedData.has_plan && fetchedData.plan) {
      if (forced || fetchedData.timestamp > lastProcessedTimestamp) {
        // Check if we're on the form page before trying to fill
        if (isOnResultsPage()) {
          // We're on results — navigate to form and stop here.
          // The script will reinitialise on the form page and pick up the plan.
          await ensureOnFormPage();
          return;
        }

        // We're on the form page — wait for the form DOM to be ready
        updateWidgetStatus("Waiting for form...", "busy");
        const formReady = await waitForFormReady(15000);
        if (!formReady) {
          updateWidgetStatus("⚠ Form not found", "offline");
          showToast("⚠ Could not find Resdex search form. Please navigate to the Resdex search page.");
          return;
        }

        lastProcessedTimestamp = fetchedData.timestamp;
        showToast("⚡ Snypar Bot: Auto-filling candidate search criteria...");
        await fillResdexForm(fetchedData.plan);
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
    }
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
