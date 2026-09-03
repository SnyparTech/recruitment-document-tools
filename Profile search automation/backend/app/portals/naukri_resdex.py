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

        try:
            driver = self.driver_manager.driver
            executor = ResdexFormExecutor(driver=driver, wait=self.driver_manager.wait)

            # Step 1: Navigate to Resdex Search page
            print(f"\n[1/5] Navigating to Naukri Resdex: {ResdexSelectors.SEARCH_PAGE_URL}", flush=True)
            self.driver_manager.navigate_to(ResdexSelectors.SEARCH_PAGE_URL)
            time.sleep(2)

            # Step 2: Handle login gateway if not already authenticated
            self._handle_auth_if_needed(driver)

            # Step 3: Check for security challenges
            self._check_challenges(driver)

            print("\n[2/5] Filling Basic Search Criteria...", flush=True)

            # Step 4: Fill Basic Search - Keywords
            if plan.keywords:
                if plan.keywords.required:
                    kw_str = " ".join(plan.keywords.required)
                    if executor.fill_text(ResdexSelectors.KEYWORD_INPUT, kw_str):
                        fields_filled.append("keywords.required")
                        print(f"  [+] Keywords filled: '{kw_str}'", flush=True)

                if plan.keywords.mandatory is not None:
                    if executor.fill_checkbox(
                        ResdexSelectors.MANDATORY_KEYWORDS_CHECKBOX, plan.keywords.mandatory
                    ):
                        fields_filled.append("keywords.mandatory")
                        print(f"  [+] Mandatory checkbox set: {plan.keywords.mandatory}", flush=True)

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

            # Step 5: Fill Basic Search - Experience Range
            if plan.min_experience is not None or plan.max_experience is not None:
                if executor.fill_range(
                    min_selector=ResdexSelectors.MIN_EXP_INPUT,
                    max_selector=ResdexSelectors.MAX_EXP_INPUT,
                    min_val=plan.min_experience,
                    max_val=plan.max_experience,
                ):
                    fields_filled.append("experience_range")
                    print(f"  [+] Experience range: {plan.min_experience} to {plan.max_experience} years", flush=True)

            # Step 6: Fill Basic Search - Location
            if plan.current_location:
                if executor.select_multiple(
                    ResdexSelectors.LOCATION_INPUT, plan.current_location
                ):
                    fields_filled.append("current_location")
                    print(f"  [+] Target locations: {plan.current_location}", flush=True)

            if plan.include_relocation is not None:
                if executor.fill_checkbox(
                    ResdexSelectors.INCLUDE_RELOCATION_CHECKBOX, plan.include_relocation
                ):
                    fields_filled.append("include_relocation")
                    print("  [+] Include relocation checked", flush=True)

            if plan.exclude_anywhere_location is not None:
                if executor.fill_checkbox(
                    ResdexSelectors.EXCLUDE_ANYWHERE_CHECKBOX, plan.exclude_anywhere_location
                ):
                    fields_filled.append("exclude_anywhere_location")
                    print("  [+] Exclude anywhere location checked", flush=True)

            # Step 7: Fill Basic Search - Salary
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
                        print(f"  [+] Salary range: {plan.salary.min} to {plan.salary.max} Lakhs ({plan.salary.currency})", flush=True)

                if plan.salary.include_unspecified is not None:
                    executor.fill_checkbox(
                        ResdexSelectors.INCLUDE_UNSPECIFIED_SALARY_CHECKBOX,
                        plan.salary.include_unspecified,
                    )

            print("\n[3/5] Filling Employment & Notice Period Details...", flush=True)

            # Step 8: Expand & Fill Employment Details
            has_emp = plan.department_role or plan.industry or plan.company or plan.designation
            if has_emp:
                try:
                    executor.select_option(ResdexSelectors.EMPLOYMENT_SECTION_TOGGLE, "Employment Details", by=By.XPATH)
                    time.sleep(0.4)
                except Exception:
                    pass

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

            # Step 9: Fill Notice Period
            if plan.notice_period:
                for np in plan.notice_period:
                    np_xpath = ResdexSelectors.NOTICE_PERIOD_OPTION_TEMPLATE.format(option=np)
                    if executor.select_option(np_xpath, np, by=By.XPATH):
                        fields_filled.append(f"notice_period.{np}")
                        print(f"  [+] Notice period option: '{np}'", flush=True)

            # Step 10: Expand & Fill Diversity & Additional Filters
            has_diversity = plan.gender or plan.career_break or plan.differently_abled or plan.defence_background
            if has_diversity:
                try:
                    executor.select_option(ResdexSelectors.DIVERSITY_SECTION_TOGGLE, "Diversity", by=By.XPATH)
                    time.sleep(0.4)
                except Exception:
                    pass
                if plan.gender:
                    executor.select_option(ResdexSelectors.GENDER_SELECT, plan.gender)
                    fields_filled.append("gender")
                    print(f"  [+] Gender: {plan.gender}", flush=True)

            if plan.job_type:
                executor.select_option(ResdexSelectors.JOB_TYPE_SELECT, plan.job_type)
                fields_filled.append("job_type")
                print(f"  [+] Job type: {plan.job_type}", flush=True)

            if plan.employment_type:
                executor.select_option(
                    ResdexSelectors.EMPLOYMENT_TYPE_SELECT, plan.employment_type
                )
                fields_filled.append("employment_type")
                print(f"  [+] Employment type: {plan.employment_type}", flush=True)

            # Step 11: Display & Active In
            if plan.candidate_display:
                executor.select_option(
                    ResdexSelectors.CANDIDATE_DISPLAY_SELECT, plan.candidate_display
                )

            if plan.active_in:
                executor.select_option(
                    ResdexSelectors.ACTIVE_IN_SELECT, plan.active_in
                )
                fields_filled.append("active_in")
                print(f"  [+] Active in period: {plan.active_in}", flush=True)

            # Step 12: Search Submission (Only if explicitly enabled)
            submitted = False
            if submit_search:
                print("\n[4/5] Submitting Candidate Search...", flush=True)
                submitted = executor.submit_form(ResdexSelectors.SEARCH_SUBMIT_BUTTON)
                print("  [+] Search button clicked.", flush=True)
            else:
                print("\n[4/5] Inspection Mode (submit_search = False):", flush=True)
                print("=" * 80, flush=True)
                print("[+] RESDEX FORM SUCCESSFULLY FILLED BY THE AGENT!", flush=True)
                print(f"[+] Total fields filled: {len(fields_filled)} -> {fields_filled}", flush=True)
                print("[+] Pausing for 15 seconds so you can inspect the filled form in Chrome...", flush=True)
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
                    else f"Resdex form filled successfully ({len(fields_filled)} fields). Search not submitted (inspection mode)."
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
