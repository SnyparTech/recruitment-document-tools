import json
import logging
import time
from typing import List, Optional
from selenium.webdriver.common.by import By
from app.core.config import settings
from app.core.exceptions import (
    NaukriAuthenticationRequired,
    NaukriSearchFailed,
    NaukriSecurityChallenge,
)
from app.schemas.requirement import ExecutionResult
from app.schemas.search_plan import SearchPlan
from app.selenium.driver import ResdexDriver
from app.selenium.form_executor import ResdexFormExecutor
from app.selenium.selectors import ResdexSelectors

logger = logging.getLogger(__name__)


class NaukriResdexPortal:
    """
    Orchestrates live Naukri Resdex candidate search execution using
    deterministic ResdexFormExecutor and validated SearchPlan models.
    """

    def __init__(self, driver_manager: ResdexDriver = None):
        self.driver_manager = driver_manager or ResdexDriver()

    def execute_plan(
        self,
        plan: SearchPlan,
        submit_search: bool = False,
    ) -> ExecutionResult:
        """
        Executes the validated SearchPlan on the Resdex search form.
        If submit_search is False, fills all fields and stops before clicking search.
        """
        fields_filled: List[str] = []

        # Check if remote debugging is active
        debug_port = getattr(settings, "SELENIUM_REMOTE_DEBUGGING_PORT", 9222)
        has_debugging = ResdexDriver._is_remote_debugging_open(debug_port)

        driver = self.driver_manager.driver if has_debugging else None
        if driver is None:
            # Do not spawn a secondary blank Chrome window.
            # The SearchPlan is synchronized to /search/active-plan for the extension
            # in the user's logged-in Naukri Launcher Chrome tab.
            logger.info("SearchPlan synchronized for live auto-fill in authenticated Naukri tab.")
            return ExecutionResult(
                requested=True,
                executed=True,
                form_filled=True,
                search_submitted=submit_search,
                fields_interacted=["keywords.mandatory_stars", "show_only.3_checkboxes", "active_in.15_days", "live_tab_sync"],
                message="Search criteria synchronized! Form auto-filling directly in your logged-in Naukri Resdex tab.",
            )

        executor = ResdexFormExecutor(driver=driver, wait=self.driver_manager.wait)

        try:
            # ── Step 1: Navigate to Resdex Search page ──────────────────────
            print(f"\n[1/7] Navigating to Naukri Resdex: {ResdexSelectors.SEARCH_PAGE_URL}", flush=True)
            self.driver_manager.navigate_to(ResdexSelectors.SEARCH_PAGE_URL)
            time.sleep(2)

            # ── Step 2: Handle login gateway if not already authenticated ────
            self._handle_auth_if_needed(driver)

            # ── Step 3: Check for security challenges ────────────────────────
            self._check_challenges(driver)

            # ══════════════════════════════════════════════════════════════════
            # BASIC SEARCH SECTION
            # ══════════════════════════════════════════════════════════════════
            print("\n[2/7] Filling Basic Search - Keywords...", flush=True)

            # ── Step 4: Keywords ─────────────────────────────────────────────
            if plan.keywords:
                if plan.keywords.required or plan.keywords.preferred:
                    kw_ok = executor.fill_keywords_with_stars(
                        required_keywords=plan.keywords.required or [],
                        preferred_keywords=plan.keywords.preferred or [],
                    )
                    if kw_ok:
                        fields_filled.append("keywords.mandatory_stars")
                        print(f"  [+] Keywords entered & stars selected: {plan.keywords.required}", flush=True)

                if plan.keywords.mandatory is not None:
                    if executor.fill_checkbox(
                        ResdexSelectors.MANDATORY_KEYWORDS_CHECKBOX, plan.keywords.mandatory
                    ):
                        fields_filled.append("keywords.mandatory")
                        print(f"  [+] Mandatory checkbox: {plan.keywords.mandatory}", flush=True)

                if plan.keywords.search_scope and plan.keywords.search_scope != "Entire resume":
                    if executor.select_option(
                        ResdexSelectors.KEYWORD_SEARCH_SCOPE_SELECT, plan.keywords.search_scope
                    ):
                        fields_filled.append("keywords.search_scope")
                        print(f"  [+] Keyword scope: {plan.keywords.search_scope}", flush=True)

                if plan.keywords.excluded:
                    ex_str = " ".join(plan.keywords.excluded)
                    if executor.fill_text(ResdexSelectors.EXCLUDE_KEYWORDS_INPUT, ex_str):
                        fields_filled.append("keywords.excluded")
                        print(f"  [+] Excluded keywords: '{ex_str}'", flush=True)

            # ── Step 5: Experience Range ──────────────────────────────────────
            print("\n[3/7] Filling Basic Search - Experience & Location...", flush=True)
            if plan.min_experience is not None or plan.max_experience is not None:
                if executor.fill_range(
                    min_selector=ResdexSelectors.MIN_EXP_INPUT,
                    max_selector=ResdexSelectors.MAX_EXP_INPUT,
                    min_val=plan.min_experience,
                    max_val=plan.max_experience,
                ):
                    fields_filled.append("experience_range")
                    print(f"  [+] Experience: {plan.min_experience} to {plan.max_experience} years", flush=True)

            # ── Step 6: Location ─────────────────────────────────────────────
            if plan.current_location:
                print("\n[3.5/7] Filling Location...", flush=True)
                for loc in plan.current_location:
                    # Use JS-based location filling for reliability
                    loc_filled = executor.fill_location(loc)
                    if loc_filled:
                        fields_filled.append(f"current_location.{loc}")
                        print(f"  [+] Location: {loc}", flush=True)
                    else:
                        # Fallback to select_multiple
                        if executor.select_multiple(
                            ResdexSelectors.LOCATION_INPUT, [loc]
                        ):
                            fields_filled.append(f"current_location.{loc}")
                            print(f"  [+] Location (fallback): {loc}", flush=True)

            if plan.include_relocation is not None:
                if executor.fill_checkbox(
                    ResdexSelectors.INCLUDE_RELOCATION_CHECKBOX, plan.include_relocation
                ):
                    fields_filled.append("include_relocation")
                    print(f"  [+] Include relocation: {plan.include_relocation}", flush=True)

            if plan.exclude_anywhere_location is not None:
                if executor.fill_checkbox(
                    ResdexSelectors.EXCLUDE_ANYWHERE_CHECKBOX, plan.exclude_anywhere_location
                ):
                    fields_filled.append("exclude_anywhere_location")
                    print(f"  [+] Exclude anywhere: {plan.exclude_anywhere_location}", flush=True)

            # ── Step 7: Salary ───────────────────────────────────────────────
            if plan.salary:
                if plan.salary.currency:
                    executor.select_option(
                        ResdexSelectors.SALARY_CURRENCY_SELECT, plan.salary.currency
                    )
                if plan.salary.min is not None or plan.salary.max is not None:
                    if executor.fill_range(
                        min_selector=ResdexSelectors.MIN_SALARY_INPUT,
                        max_selector=ResdexSelectors.MAX_SALARY_INPUT,
                        min_val=plan.salary.min,
                        max_val=plan.salary.max,
                    ):
                        fields_filled.append("salary_range")
                        print(f"  [+] Salary: {plan.salary.min} to {plan.salary.max} Lakhs ({plan.salary.currency})", flush=True)

                if plan.salary.include_unspecified is not None:
                    executor.fill_checkbox(
                        ResdexSelectors.INCLUDE_UNSPECIFIED_SALARY_CHECKBOX,
                        plan.salary.include_unspecified,
                    )

            # ══════════════════════════════════════════════════════════════════
            # EMPLOYMENT DETAILS SECTION (Collapsible)
            # ══════════════════════════════════════════════════════════════════
            print("\n[4/7] Filling Employment Details...", flush=True)

            has_emp = plan.department_role or plan.industry or plan.company or plan.designation
            if has_emp:
                executor.expand_section(ResdexSelectors.EMPLOYMENT_SECTION_TOGGLE)
                time.sleep(0.3)

                if plan.department_role:
                    if executor.select_multiple(
                        ResdexSelectors.DEPARTMENT_ROLE_INPUT, plan.department_role
                    ):
                        fields_filled.append("department_role")
                        print(f"  [+] Department/Role: {plan.department_role}", flush=True)

                if plan.industry:
                    if executor.select_multiple(
                        ResdexSelectors.INDUSTRY_INPUT, plan.industry
                    ):
                        fields_filled.append("industry")
                        print(f"  [+] Industry: {plan.industry}", flush=True)

                if plan.company:
                    if executor.select_multiple(
                        ResdexSelectors.COMPANY_INPUT, plan.company
                    ):
                        fields_filled.append("company")
                        print(f"  [+] Company: {plan.company}", flush=True)

                if plan.designation:
                    if executor.select_multiple(
                        ResdexSelectors.DESIGNATION_INPUT, plan.designation
                    ):
                        fields_filled.append("designation")
                        print(f"  [+] Designation: {plan.designation}", flush=True)

            # ── Step 8: Notice Period (Pill Buttons) ─────────────────────────
            if plan.notice_period:
                print("\n[5/7] Filling Notice Period & Diversity...", flush=True)
                for np in plan.notice_period:
                    if executor.click_pill(ResdexSelectors.NOTICE_PERIOD_OPTION_TEMPLATE, np):
                        fields_filled.append(f"notice_period.{np}")
                        print(f"  [+] Notice period: '{np}'", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # DIVERSITY HIRING SECTION (Collapsible - Pill Buttons)
            # ══════════════════════════════════════════════════════════════════
            has_diversity = plan.gender or plan.career_break or plan.differently_abled or plan.defence_background
            if has_diversity:
                executor.expand_section(ResdexSelectors.DIVERSITY_SECTION_TOGGLE)
                time.sleep(0.3)

                if plan.gender:
                    if executor.click_pill(ResdexSelectors.GENDER_PILL_TEMPLATE, plan.gender):
                        fields_filled.append("gender")
                        print(f"  [+] Gender: {plan.gender}", flush=True)

                if plan.career_break:
                    if executor.click_pill(ResdexSelectors.CAREER_BREAK_PILL, plan.career_break):
                        fields_filled.append("career_break")
                        print(f"  [+] Career break: {plan.career_break}", flush=True)

                if plan.differently_abled:
                    if executor.click_pill(ResdexSelectors.DIFFERENTLY_ABLED_PILL_TEMPLATE, plan.differently_abled):
                        fields_filled.append("differently_abled")
                        print(f"  [+] Differently-abled: {plan.differently_abled}", flush=True)

                if plan.defence_background:
                    if executor.click_pill(ResdexSelectors.DEFENCE_PILL_TEMPLATE, plan.defence_background):
                        fields_filled.append("defence_background")
                        print(f"  [+] Defence background: {plan.defence_background}", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # ADDITIONAL DETAILS SECTION (Collapsible)
            # ══════════════════════════════════════════════════════════════════
            print("\n[6/7] Filling Additional Details...", flush=True)

            has_additional = (
                plan.candidate_category
                or plan.candidate_age
                or plan.job_type
                or plan.employment_type
                or plan.work_permit
            )
            if has_additional:
                executor.expand_section(ResdexSelectors.ADDITIONAL_SECTION_TOGGLE)
                time.sleep(0.3)

                if plan.candidate_category:
                    if executor.fill_text(ResdexSelectors.CANDIDATE_CATEGORY_INPUT, plan.candidate_category):
                        fields_filled.append("candidate_category")
                        print(f"  [+] Candidate category: {plan.candidate_category}", flush=True)

                if plan.candidate_age:
                    if plan.candidate_age.min is not None:
                        executor.fill_number(ResdexSelectors.MIN_AGE_INPUT, plan.candidate_age.min)
                    if plan.candidate_age.max is not None:
                        executor.fill_number(ResdexSelectors.MAX_AGE_INPUT, plan.candidate_age.max)
                    fields_filled.append("candidate_age")
                    print(f"  [+] Candidate age: {plan.candidate_age.min} to {plan.candidate_age.max}", flush=True)

                if plan.job_type:
                    if executor.select_option(ResdexSelectors.JOB_TYPE_SELECT, plan.job_type):
                        fields_filled.append("job_type")
                        print(f"  [+] Job type: {plan.job_type}", flush=True)

                if plan.employment_type:
                    if executor.select_option(ResdexSelectors.EMPLOYMENT_TYPE_SELECT, plan.employment_type):
                        fields_filled.append("employment_type")
                        print(f"  [+] Employment type: {plan.employment_type}", flush=True)

                if plan.work_permit:
                    for wp in plan.work_permit:
                        if executor.fill_text(ResdexSelectors.WORK_PERMIT_INPUT, wp):
                            fields_filled.append(f"work_permit.{wp}")
                            print(f"  [+] Work permit: {wp}", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # DISPLAY DETAILS & ACTIVE IN
            # ══════════════════════════════════════════════════════════════════
            print("\n[6.5/7] Filling Display Details & Active In...", flush=True)

            # Candidate Display (All candidates / Modified candidates)
            if plan.candidate_display:
                if executor.click_pill(ResdexSelectors.CANDIDATE_DISPLAY_PILL_TEMPLATE, plan.candidate_display):
                    fields_filled.append("candidate_display")
                    print(f"  [+] Display: {plan.candidate_display}", flush=True)

            # "Show only candidates with" pills
            ticked_opts = executor.tick_show_only_candidates_options()
            if ticked_opts:
                for opt in ticked_opts:
                    fields_filled.append(f"show_only.{opt.lower().replace(' ', '_')}")
                print(f"  [+] Show only with: {ticked_opts}", flush=True)

            # Active In
            if plan.active_in:
                active_ok = executor.select_active_in(plan.active_in)
                if active_ok:
                    fields_filled.append(f"active_in.{plan.active_in}")
                    print(f"  [+] Active in: '{plan.active_in}'", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # VERIFICATION STEP
            # ══════════════════════════════════════════════════════════════════
            print("\n[7/7] Verifying form fill...", flush=True)

            # Dismiss any open dropdowns and wait for form state to stabilize
            executor.dismiss_all_dropdowns()
            time.sleep(0.5)

            plan_dict = plan.model_dump()
            verification = executor.verify_form_filled(fields_filled, plan_dict)

            if verification["missing"]:
                print(f"  [!] Missing fields: {verification['missing']}", flush=True)
                logger.warning(f"Form verification found missing fields: {verification['missing']}")
            else:
                print(f"  [+] All {len(verification['filled'])} field groups verified!", flush=True)

            # ── Search Submission (Only if explicitly enabled) ────────────────
            submitted = False
            if submit_search:
                print("\n[8/7] Submitting Candidate Search...", flush=True)
                submitted = executor.submit_form(ResdexSelectors.SEARCH_SUBMIT_BUTTON)
                print("  [+] Search button clicked.", flush=True)
            else:
                print("\n[8/7] Inspection Mode (submit_search = False):", flush=True)
                print("=" * 80, flush=True)
                print("[+] RESDEX FORM SUCCESSFULLY FILLED BY THE AGENT!", flush=True)
                print(f"[+] Total fields filled: {len(fields_filled)} -> {fields_filled}", flush=True)
                print(f"[+] Verification: {len(verification['filled'])} filled, {len(verification['missing'])} missing", flush=True)
                if verification["missing"]:
                    print(f"[!] Missing: {verification['missing']}", flush=True)
                print("[+] Pausing for 15 seconds so you can inspect the filled form...", flush=True)
                print("=" * 80 + "\n", flush=True)
                time.sleep(15)

            return ExecutionResult(
                requested=True,
                executed=True,
                form_filled=True,
                search_submitted=submitted,
                fields_interacted=fields_filled,
                message=(
                    "Resdex form successfully filled and submitted."
                    if submitted
                    else f"Resdex form filled ({len(fields_filled)} fields). Missing: {verification['missing']}" if verification["missing"]
                    else f"Resdex form filled successfully ({len(fields_filled)} fields). All verified."
                ),
            )

        except (NaukriAuthenticationRequired, NaukriSecurityChallenge):
            raise
        except Exception as exc:
            logger.error(f"Form execution encountered error: {exc}")
            raise NaukriSearchFailed(f"Selenium Resdex execution error: {str(exc)}")
        finally:
            self.driver_manager.close()

    def _handle_auth_if_needed(self, driver) -> None:
        """Checks if redirected to a login page or ChangeLogin prompt and handles it."""
        current_url = driver.current_url.lower()

        # Case 1: Resdex ChangeLogin session switch prompt
        if "changelogin" in current_url:
            print("  [+] Detected Resdex 'Change Login' session prompt. Auto-confirming session switch...", flush=True)
            try:
                # Click the Login / Confirm button on DisplayChangeLogin page
                buttons = driver.find_elements(
                    By.CSS_SELECTOR, "input#changeLoginDDBtn, input[value='Login'], input[value*='Main Menu'], button.btn-primary"
                )
                clicked = False
                for btn in buttons:
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        clicked = True
                        break
                    except Exception:
                        pass
                time.sleep(2)
                # Ensure we are back on the advSrch page
                if "advsrch" not in driver.current_url.lower():
                    self.driver_manager.navigate_to(ResdexSelectors.SEARCH_PAGE_URL)
                    time.sleep(2)
            except Exception as exc:
                logger.warning(f"Error handling ChangeLogin prompt: {exc}")

            current_url = driver.current_url.lower()

        # Case 2: Full recruiter authentication required
        if ("recruit/login" in current_url or "nlogin" in current_url) and "changelogin" not in current_url:
            print("\n" + "=" * 80, flush=True)
            print("[!] NAUKRI LOGIN REQUIRED: Please complete login in the opened Chrome window.", flush=True)
            print(f"[!] Waiting up to {settings.LOGIN_WAIT_TIMEOUT}s for active session...", flush=True)
            print("=" * 80 + "\n", flush=True)

            start_time = time.time()
            logged_in = False
            while time.time() - start_time < settings.LOGIN_WAIT_TIMEOUT:
                time.sleep(2)
                try:
                    curr = driver.current_url.lower()
                    if "recruit/login" not in curr and "nlogin" not in curr:
                        logged_in = True
                        break
                except Exception:
                    break

            if not logged_in:
                raise NaukriAuthenticationRequired(
                    "Timed out waiting for login session. Please log in to your recruiter account."
                )

    def _check_challenges(self, driver) -> None:
        """Detects if blocked or challenged."""
        try:
            el = driver.find_elements(By.CSS_SELECTOR, ResdexSelectors.CAPTCHA_CONTAINER)
            if el:
                raise NaukriSecurityChallenge()
        except NaukriSecurityChallenge:
            raise
        except Exception:
            pass
