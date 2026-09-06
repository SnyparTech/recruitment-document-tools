"""
Decoupled Resdex Form Selectors mapped to semantic Field IDs.
Selectors are kept strictly separate from the LLM and schema.
Ground-truth tested against Naukri Resdex v3.
"""


class ResdexSelectors:
    """CSS and XPath selectors for Naukri Resdex Candidate Search form (v3)."""

    # Portal URLs
    SEARCH_PAGE_URL = "https://resdex.naukri.com/v3?activeTab=advSrch"
    BASE_PORTAL_URL = "https://resdex.naukri.com"

    # Security & Login Check
    LOGIN_INPUT = "input[name='username'], input[type='email'], input#usernameField"
    CAPTCHA_CONTAINER = "div.captcha-container, iframe[src*='captcha'], div#captcha"

    # Basic Search: Keywords
    KEYWORD_INPUT = (
        "input[name='ezKeywordsAny'], input[placeholder*='Enter keywords like skills'], "
        "input#keywords, input.keyword-input, input[name='keyword']"
    )
    MANDATORY_KEYWORDS_CHECKBOX = (
        "input#must-have-checkbox, input[name='must-have-checkbox'], "
        "input#mandatoryKeywords, label:has(input#must-have-checkbox)"
    )
    KEYWORD_SEARCH_SCOPE_SELECT = "select#keywordScope, select[name='keywordScope']"
    EXCLUDE_KEYWORDS_INPUT = "input[name='ezKeywordsExclude'], input#excludeKeywords, input[name='excludeKeyword']"

    # Basic Search: Experience
    MIN_EXP_INPUT = "input[name='minExp'], input[placeholder*='Min experience'], input#minExp"
    MAX_EXP_INPUT = "input[name='maxExp'], input[placeholder*='Max experience'], input#maxExp"

    # Basic Search: Location & Relocation
    LOCATION_INPUT = "input[name='locations'], input[placeholder*='Add location'], input#location"
    LOCATION_SUGGESTION_ITEM = "div.sug-item, li.suggestion-item, div.location-item"
    INCLUDE_RELOCATION_CHECKBOX = "input#prefLocCheckbox, input[name='prefLocCheckbox'], input#includeRelocation"
    EXCLUDE_ANYWHERE_CHECKBOX = "input#exact-pref-match-checkbox, input#excludeAnywhere"

    # Basic Search: Salary
    SALARY_CURRENCY_SELECT = "select#salaryCurrency, select[name='currency']"
    MIN_SALARY_INPUT = "input[name='minCtc'], input[placeholder*='Min salary'], input#minSalary"
    MAX_SALARY_INPUT = "input[name='maxCtc'], input[placeholder*='Max salary'], input#maxSalary"
    INCLUDE_UNSPECIFIED_SALARY_CHECKBOX = "input#include-candidate-ctc, input#includeUnspecifiedSalary"

    # Employment Details
    DEPARTMENT_ROLE_INPUT = "input[name='departmentRole'], input[placeholder*='Department'], input#departmentRole"
    INDUSTRY_INPUT = "input[name='industry'], input[placeholder*='Industry'], input#industry"
    COMPANY_INPUT = "input[name='company'], input[placeholder*='Company'], input#company"
    COMPANY_SCOPE_SELECT = "select#companyScope, select[name='companyScope']"
    EXCLUDE_COMPANY_INPUT = "input[name='excludeCompany'], input#excludeCompany"
    DESIGNATION_INPUT = "input[name='designation'], input[placeholder*='Designation'], input#designation"
    DESIGNATION_SCOPE_SELECT = "select#designationScope, select[name='designationScope']"

    # Notice Period
    NOTICE_PERIOD_CONTAINER = "div.notice-period-container, div#noticePeriodSection"
    NOTICE_PERIOD_OPTION_TEMPLATE = "//label[contains(text(), '{option}')] | //input[@value='{option}']"

    # Collapsible Sections
    EMPLOYMENT_SECTION_TOGGLE = "//h2[contains(text(), 'Employment Details')]"
    DIVERSITY_SECTION_TOGGLE = "//h2[contains(text(), 'Diversity Hiring')]"
    ADDITIONAL_SECTION_TOGGLE = "//h2[contains(text(), 'Additional Details')]"

    # Diversity Hiring
    GENDER_SELECT = "select#gender, input[name='gender']"
    CAREER_BREAK_CHECKBOX = "input#careerBreak, input[name='careerBreak']"
    DIFFERENTLY_ABLED_SELECT = "select#differentlyAbled, input[name='differentlyAbled']"
    DEFENCE_SELECT = "select#defence, input[name='defence']"

    # Additional Details
    ADDITIONAL_SECTION_TOGGLE = "div#additionalDetailsToggle, button#additionalToggle"
    CANDIDATE_CATEGORY_SELECT = "select#candidateCategory, input[name='category']"
    MIN_AGE_INPUT = "input#minAge, input[name='minAge']"
    MAX_AGE_INPUT = "input#maxAge, input[name='maxAge']"
    JOB_TYPE_SELECT = "select#jobType, input[name='jobType']"
    EMPLOYMENT_TYPE_SELECT = "select#employmentType, input[name='employmentType']"
    WORK_PERMIT_INPUT = "input#workPermit, input[placeholder*='Work permit']"

    # Display & Search Active Period
    CANDIDATE_DISPLAY_SELECT = "select#candidateDisplay, input[name='candidateDisplay']"
    VERIFIED_MOBILE_CHECKBOX = "input#verifiedMobile, input[name='verifiedMobile']"
    VERIFIED_EMAIL_CHECKBOX = "input#verifiedEmail, input[name='verifiedEmail']"
    ATTACHED_RESUME_CHECKBOX = "input#attachedResume, input[name='attachedResume']"
    ACTIVE_IN_SELECT = "select#activeIn, select[name='activeIn']"

    # Search Submission Button
    SEARCH_SUBMIT_BUTTON = (
        "button#searchButton, button[type='submit'], "
        "button[data-testid='search-btn'], a.searchProfiles, button.searchProfiles"
    )
