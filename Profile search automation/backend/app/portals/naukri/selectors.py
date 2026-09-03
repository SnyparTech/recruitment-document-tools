"""
Naukri Candidate Portal Centralized CSS / XPath Selectors Configuration.

This module defines selectors specifically targeting Candidate Resume / Candidate Profile tuples
on Naukri Resdex and recruiter candidate search interfaces.
"""


class NaukriSelectors:
    """Centralized DOM selectors for Naukri Candidate Profile Search."""

    # --- Candidate Search Form Selectors (Resdex / Candidate Search) ---
    # Keyword / Skill / Role input
    SEARCH_INPUT: str = "input#keyword, input[placeholder*='skills'], input[placeholder*='designation'], input.keyword-input, input[name='keyword'], input#keyword-search"
    
    # Location input
    LOCATION_INPUT: str = "input#location, input[placeholder*='location'], input.location-input, input[name='location'], input#location-search"
    
    # Experience inputs / dropdowns
    EXPERIENCE_MIN_INPUT: str = "input#expMin, select#exp-min, input[name='expMin']"
    EXPERIENCE_MAX_INPUT: str = "input#expMax, select#exp-max, input[name='expMax']"
    
    # Candidate Search Trigger
    SEARCH_BUTTON: str = "button#search-btn, button.search-btn, button[type='submit'], input[type='submit'][value*='Search']"

    # --- Candidate Resume / Profile Card Selectors ---
    # Candidate Card / Tuple Container
    RESULT_CARD: str = "div.tuple-wrapper, div.tuple, div.resdexTuple, div.candidate-card, div.resume-tuple, div.tuple-body, article.candidateTuple"
    
    # Candidate Full Name
    CANDIDATE_NAME: str = "span.name, a.name, a.candidate-name, .cand-name, span.candidate-name, h2.cand-title, .tuple-header span"
    
    # Candidate Current Designation / Title
    TITLE: str = "span.designation, span.current-title, .tuple-sub-title, span.role, .cand-designation, .designation"
    
    # Candidate Current Organization / Company
    CURRENT_COMPANY: str = "span.company-name, span.company, span.current-company, .company, span.org"
    
    # Candidate Total Experience (e.g. '2.5 Yrs', '3 yrs 2 months')
    EXPERIENCE: str = "span.exp, span.experience, .exp-wrap, span.experience-tuple, span.total-exp, .exp"
    
    # Candidate Current City / Location
    LOCATION: str = "span.loc, span.location, .loc-wrap, span.current-location, .location"
    
    # Candidate Key Skills
    SKILLS_CONTAINER: str = "ul.skill-tags, div.key-skills, .skills-list, ul.tags-gt, .tags"
    SKILL_ITEM: str = "li.skill-item, li.tag-li, .tag, .chip, ul.skill-tags li, div.key-skills span"
    
    # Candidate Highest Qualification / Degree
    EDUCATION: str = "span.edu, span.education, .education-tuple, span.qualification, .edu"
    
    # Candidate Resume / Profile Link
    PROFILE_LINK: str = "a.candidate-link, a.view-profile, a.name-link, a.candidate-name, a[href*='candidate'], a[href*='resume'], a[href*='profile']"

    # --- Verification & Challenge Detectors ---
    LOGIN_PROMPT: str = "//a[contains(text(), 'Login') or contains(@href, 'login')]"
    CAPTCHA_CONTAINER: str = "div#captcha, iframe[src*='captcha'], div.recaptcha, div#g-recaptcha, iframe[title*='reCAPTCHA']"
    BLOCKED_PAGE_INDICATOR: str = "div.access-denied, div.blocked-page, h1:contains('Access Denied'), h1:contains('Cloudflare')"
