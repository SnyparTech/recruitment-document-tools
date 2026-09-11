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
    KEYWORD_SEARCH_SCOPE_SELECT = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search keyword in')]/following::select[1] | "
        "select#keywordScope, select[name='keywordScope']"
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
    # ──────────────────────────────────────────────────────────────────────
    NOTICE_PERIOD_ANY = "//*[normalize-space()='Any']"
    NOTICE_PERIOD_OPTION_TEMPLATE = (
        "//*[normalize-space()='{option}']"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Education Details (Collapsible Section)
    # ──────────────────────────────────────────────────────────────────────
    EDUCATION_SECTION_TOGGLE = (
        "//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'education details')]"
    )
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
    # Display Details (Pill Buttons + Checkboxes)
    # ──────────────────────────────────────────────────────────────────────
    CANDIDATE_DISPLAY_PILL_TEMPLATE = (
        "//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show')]/following::*[normalize-space()='{option}'][1]"
    )
    VERIFIED_MOBILE_PILL = (
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verified mobile')]"
    )
    VERIFIED_EMAIL_PILL = (
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verified email')]"
    )
    ATTACHED_RESUME_PILL = (
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'attached resume')]"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Active In & Search Button (Footer)
    # ──────────────────────────────────────────────────────────────────────
    ACTIVE_IN_SELECT = (
        "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::select[1] | "
        "select#activeIn, select[name='activeIn'], select#searchActivePeriod, select[name='searchActivePeriod']"
    )
    SEARCH_SUBMIT_BUTTON = (
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search candidates')] | "
        "button#searchButton, button[type='submit'], "
        "button[data-testid='search-btn'], a.searchProfiles, button.searchProfiles"
    )
