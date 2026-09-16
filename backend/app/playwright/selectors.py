"""
Decoupled Resdex Form Selectors mapped to semantic Field IDs.
Selectors are kept strictly separate from the LLM and schema.
Ground-truth tested against Naukri Resdex v3 (current UI with pill buttons).
"""


class ResdexSelectors:
    """CSS and XPath selectors for Naukri Resdex Candidate Search form (v3)."""

    # Portal URLs
    SEARCH_PAGE_URL = "https://resdex.naukri.com/v3?activeTab=advSrch"
    BASE_PORTAL_URL = "https://resdex.naukri.com"

    # Security & Login Check
    LOGIN_INPUT = "input[name='username'], input[type='email'], input#usernameField"
    CAPTCHA_CONTAINER = "div.captcha-container, iframe[src*='captcha'], div#captcha"

    # ──────────────────────────────────────────────────────────────────────
    # Basic Search: Keywords
    # ──────────────────────────────────────────────────────────────────────
    KEYWORD_INPUT = (
        "input[placeholder*='Enter keywords like skills'], "
        "input[name='ezKeywordsAny'], "
        "input#keywords, input.keyword-input, input[name='keyword'], input[id*='keyword']"
    )
    KEYWORD_CHIP = (
        "div[class*='chip'], span[class*='chip'], div[class*='tag'], "
        "span[class*='tag'], div.chip, span.chip"
    )
    KEYWORD_STAR_ICON = (
        "[class*='star'], [class*='Star'], button[title*='Mandatory'], "
        "button[title*='Must have'], span[title*='Mandatory'], svg[class*='star'], "
        "i.icon-star, span.star, button.star-btn"
    )
    MANDATORY_KEYWORDS_CHECKBOX = (
        "//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'mark all keywords as mandatory')]//input | "
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'mark all keywords as mandatory')]/..//input | "
        "input#must-have-checkbox, input[name='must-have-checkbox'], "
        "input#mandatoryKeywords, input[id*='mustHave'], input[id*='mandatory']"
    )

    # Keyword search scope — this is a React custom <span> link, NOT a <select>.
    # Click it to open the dropdown, then click the desired option.
    KEYWORD_SCOPE_TRIGGER = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search keyword in')] | "
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search keyword in')] | "
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search keyword in')]"
    )
    # Fallback: <select> element for keyword scope (some versions)
    KEYWORD_SEARCH_SCOPE_SELECT = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search keyword in')]/following::select[1] | "
        "select#keywordScope, select[name='keywordScope']"
    )
    # Template for clicking a scope option after dropdown opens
    KEYWORD_SCOPE_OPTION_TEMPLATE = (
        "//*[normalize-space()='{option}'] | "
        "//li[contains(text(), '{option}')] | "
        "//div[contains(text(), '{option}')]"
    )

    EXCLUDE_KEYWORDS_INPUT = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add exclude keywords')]/following::input[1] | "
        "input[name='ezKeywordsExclude'], input#excludeKeywords, input[name='excludeKeyword']"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Basic Search: Experience
    # ──────────────────────────────────────────────────────────────────────
    MIN_EXP_INPUT = (
        "input[placeholder*='Min experience'], "
        "input[name='minExp'], input#minExp"
    )
    MAX_EXP_INPUT = (
        "input[placeholder*='Max experience'], "
        "input[name='maxExp'], input#maxExp"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Basic Search: Location & Relocation
    # ──────────────────────────────────────────────────────────────────────
    LOCATION_INPUT = (
        "input[placeholder*='Add location'], "
        "input[name='locations'], input#location"
    )
    LOCATION_SUGGESTION_ITEM = (
        "div.sug-item, li.suggestion-item, div.location-item, "
        "div[class*='sugItem'], li[class*='sugItem']"
    )
    INCLUDE_RELOCATION_CHECKBOX = (
        "//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'include candidates who prefer to relocate')]//input | "
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'include candidates who prefer to relocate')]/..//input | "
        "input#prefLocCheckbox, input[name='prefLocCheckbox'], input#includeRelocation"
    )
    EXCLUDE_ANYWHERE_CHECKBOX = (
        "//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'exclude candidates who have mentioned anywhere')]//input | "
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'exclude candidates who have mentioned anywhere')]/..//input | "
        "input#exact-pref-match-checkbox, input#excludeAnywhere"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Basic Search: Salary
    # ──────────────────────────────────────────────────────────────────────
    SALARY_CURRENCY_SELECT = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'annual salary')]/following::select[1] | "
        "select#salaryCurrency, select[name='currency']"
    )
    MIN_SALARY_INPUT = (
        "input[placeholder*='Min salary'], "
        "input[name='minCtc'], input#minSalary"
    )
    MAX_SALARY_INPUT = (
        "input[placeholder*='Max salary'], "
        "input[name='maxCtc'], input#maxSalary"
    )
    INCLUDE_UNSPECIFIED_SALARY_CHECKBOX = (
        "//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'include candidates who did not mention their current salary')]//input | "
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'include candidates who did not mention their current salary')]/..//input | "
        "input#include-candidate-ctc, input#includeUnspecifiedSalary"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Employment Details (Collapsible Section)
    # ──────────────────────────────────────────────────────────────────────
    EMPLOYMENT_SECTION_TOGGLE = (
        "//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'employment details')]"
    )
    DEPARTMENT_ROLE_INPUT = (
        "input[placeholder*='Add Department'], "
        "input[name='departmentRole'], input#departmentRole"
    )
    INDUSTRY_INPUT = (
        "input[placeholder*='Add industry'], "
        "input[name='industry'], input#industry"
    )
    COMPANY_INPUT = (
        "input[placeholder*='Add company name'], "
        "input[name='company'], input#company"
    )
    COMPANY_SCOPE_SELECT = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search in')]/following::select[1] | "
        "select#companyScope, select[name='companyScope']"
    )
    EXCLUDE_COMPANY_INPUT = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add exclude company')]/following::input[1] | "
        "input[name='excludeCompany'], input#excludeCompany"
    )
    DESIGNATION_INPUT = (
        "input[placeholder*='Add designation'], "
        "input[name='designation'], input#designation"
    )
    DESIGNATION_SCOPE_SELECT = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'designation')]/following::span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search in')][1]/following::select[1] | "
        "select#designationScope, select[name='designationScope']"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Notice Period (Pill Buttons)
    # Resdex displays pill text with spaces around the dash: "0 - 15 days"
    # The schema stores "0-15 days" — normalise before matching.
    # ──────────────────────────────────────────────────────────────────────
    NOTICE_PERIOD_ANY = "//*[normalize-space()='Any']"
    # Template: fill {option} with the EXACT text as shown on the pill
    NOTICE_PERIOD_OPTION_TEMPLATE = (
        "//*[normalize-space()='{option}']"
    )
    # Normalised display values (schema value → UI pill text)
    NOTICE_PERIOD_DISPLAY_MAP = {
        "0-15 days": "0 - 15 days",
        "1 month": "1 Month",
        "2 months": "2 Months",
        "3 months": "3 Months",
        "more than 3 months": "More than 3 Months",
        "currently serving notice period": "Currently Serving Notice Period",
        "any": "Any",
    }

    # ──────────────────────────────────────────────────────────────────────
    # Education Details (Collapsible Section — Pill Buttons)
    # ──────────────────────────────────────────────────────────────────────
    EDUCATION_SECTION_TOGGLE = (
        "//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'education details')]"
    )
    # UG/PG pills sit inside their respective sub-sections
    UG_QUALIFICATION_PILL_TEMPLATE = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ug qualification')]/following::*[normalize-space()='{option}'][1]"
    )
    PG_QUALIFICATION_PILL_TEMPLATE = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pg qualification')]/following::*[normalize-space()='{option}'][1]"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Diversity Hiring (Collapsible Section - Pill Buttons)
    # ──────────────────────────────────────────────────────────────────────
    DIVERSITY_SECTION_TOGGLE = (
        "//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'diversity hiring')]"
    )
    GENDER_PILL_TEMPLATE = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'gender')]/following::*[normalize-space()='{option}'][1]"
    )
    CAREER_BREAK_PILL = (
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'women returning to work')]"
    )
    DIFFERENTLY_ABLED_INPUT = (
        "input[placeholder*='Select differently abled type'], "
        "input[name='differentlyAbled']"
    )
    DIFFERENTLY_ABLED_PILL_TEMPLATE = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'differently-abled')]/following::*[normalize-space()='{option}'][1]"
    )
    DEFENCE_PILL_TEMPLATE = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'defence background')]/following::*[normalize-space()='{option}'][1]"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Additional Details (Collapsible Section)
    # ──────────────────────────────────────────────────────────────────────
    ADDITIONAL_SECTION_TOGGLE = (
        "//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'additional details')]"
    )
    CANDIDATE_CATEGORY_INPUT = (
        "input[placeholder*='Add candidate category'], "
        "input[name='category'], select#candidateCategory"
    )
    MIN_AGE_INPUT = (
        "input[placeholder*='Min age'], "
        "input#minAge, input[name='minAge']"
    )
    MAX_AGE_INPUT = (
        "input[placeholder*='Max age'], "
        "input#maxAge, input[name='maxAge']"
    )
    JOB_TYPE_SELECT = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show candidates seeking')]/following::select[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'job type')][1] | "
        "select#jobType, input[name='jobType']"
    )
    EMPLOYMENT_TYPE_SELECT = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show candidates seeking')]/following::select[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'employment type')][1] | "
        "select#employmentType, input[name='employmentType']"
    )
    WORK_PERMIT_INPUT = (
        "input[placeholder*='Choose category'], "
        "input#workPermit, input[placeholder*='Work permit']"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Display Details (Pill Buttons)
    # ──────────────────────────────────────────────────────────────────────
    CANDIDATE_DISPLAY_PILL_TEMPLATE = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show')]/following::*[normalize-space()='{option}'][1]"
    )

    # "Show only candidates with" — these are PILL buttons with a '+' icon, not checkboxes.
    # Click the pill element containing the text. Template matches the pill wrapper.
    SHOW_ONLY_PILL_TEMPLATE = (
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}') and "
        "(contains(@class, 'chip') or contains(@class, 'tag') or contains(@class, 'pill') or contains(@class, 'btn') or contains(@class, 'option') or @role='button' or @role='checkbox')]"
    )
    # Individual text fragments to search for each pill
    VERIFIED_MOBILE_TEXT = "verified mobile"
    VERIFIED_EMAIL_TEXT = "verified email"
    ATTACHED_RESUME_TEXT = "attached resume"

    # ──────────────────────────────────────────────────────────────────────
    # Active In (Custom React Dropdown — NOT a <select>)
    # Strategy: click the trigger span → a dropdown menu appears →
    # click the option text.
    # ──────────────────────────────────────────────────────────────────────
    ACTIVE_IN_SELECT = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::select[1] | "
        "select#activeIn, select[name='activeIn'], select#searchActivePeriod, select[name='searchActivePeriod']"
    )
    # The clickable trigger that opens the active-in dropdown
    ACTIVE_IN_DROPDOWN_TRIGGER = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')] | "
        "//div[contains(@class, 'activeIn') or contains(@class, 'active-in')] | "
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in') and (@role='combobox' or contains(@class, 'dropdown') or contains(@class, 'select'))]"
    )
    # After the dropdown opens, click this option template
    ACTIVE_IN_OPTION_TEMPLATE = (
        "//li[normalize-space()='{option}'] | "
        "//div[normalize-space()='{option}'] | "
        "//span[normalize-space()='{option}'] | "
        "//option[normalize-space()='{option}']"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Search Submit Button (Footer)
    # ──────────────────────────────────────────────────────────────────────
    SEARCH_SUBMIT_BUTTON = (
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search candidates')] | "
        "button#searchButton, button[type='submit'], "
        "button[data-testid='search-btn'], a.searchProfiles, button.searchProfiles"
    )
