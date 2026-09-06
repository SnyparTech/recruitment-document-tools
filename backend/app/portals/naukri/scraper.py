import logging
import re
import time
import urllib.parse
from typing import List
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import settings
from app.core.exceptions import (
    NaukriAuthenticationRequired,
    NaukriPageChanged,
    NaukriSearchFailed,
    NaukriSecurityChallenge,
)
from app.models.candidate import CandidateProfile
from app.models.requirement import GeneratedQuery, ParsedRequirement
from app.portals.naukri.client import NaukriClient
from app.portals.naukri.extractor import NaukriExtractor
from app.portals.naukri.selectors import NaukriSelectors

logger = logging.getLogger(__name__)


class NaukriScraper:
    """
    Executes live candidate/resume search on Naukri Resdex & Recruiter Portal.
    Includes visual browser support and interactive login wait time.
    """

    def __init__(self, client: NaukriClient = None, extractor: NaukriExtractor = None):
        self.client = client or NaukriClient()
        self.extractor = extractor or NaukriExtractor()

    def search(
        self, requirement: ParsedRequirement, query: GeneratedQuery
    ) -> List[CandidateProfile]:
        """
        Executes candidate profile search on live Naukri using Selenium.
        """
        try:
            # Step 1: Open Naukri Resdex Portal Page
            candidate_search_url = settings.NAUKRI_RESDEX_URL
            logger.info(f"Navigating to live Naukri Resdex portal: {candidate_search_url}")
            self.client.navigate_to(candidate_search_url)

            # Step 2: Give user time to log in if on login gateway
            self._wait_for_login_if_needed()

            # Step 3: Check for CAPTCHA / Security Challenges
            self._check_for_challenges()

            driver = self.client.driver
            wait = self.client.wait

            # Step 4: Fill candidate search parameters and submit
            card_elements = self._fill_and_submit_search(query)

            # Step 5: Check challenges again post-search
            self._check_for_challenges()

            # Step 6: Extract candidate profiles from result tuples
            candidates: List[CandidateProfile] = []
            for idx, card in enumerate(card_elements, start=1):
                extracted = self.extractor.extract_from_card(card, index=idx)
                if extracted:
                    candidates.append(extracted)

            if not candidates:
                logger.warning("No candidate profile tuples found matching current selectors.")

            return candidates

        except (NaukriAuthenticationRequired, NaukriSecurityChallenge, NaukriPageChanged):
            raise
        except Exception as exc:
            logger.error(f"Live Naukri candidate search failed: {exc}")
            raise NaukriSearchFailed(f"Live Naukri candidate search encountered an error: {str(exc)}")
        finally:
            self.client.close()

    def _wait_for_login_if_needed(self) -> None:
        """
        Detects if Naukri redirected to a login page and gives the user time
        to manually log in to their recruiter account in the opened Chrome window.
        """
        driver = self.client.driver
        current_url = driver.current_url.lower()

        # Check if currently gated by login
        if "login" in current_url or "auth" in current_url:
            print("\n" + "=" * 80)
            print("[!] NAUKRI LOGIN REQUIRED: Please complete login in the opened Chrome window.")
            print(f"[!] The automation will wait up to {settings.LOGIN_WAIT_TIMEOUT} seconds for you to log in...")
            print("=" * 80 + "\n")

            start_time = time.time()
            logged_in = False

            while time.time() - start_time < settings.LOGIN_WAIT_TIMEOUT:
                time.sleep(2)
                try:
                    curr = driver.current_url.lower()
                    if "login" not in curr and "auth" not in curr:
                        print("[+] Login detected! Resuming automated candidate search...\n")
                        logged_in = True
                        break
                except Exception:
                    break

            if not logged_in:
                raise NaukriAuthenticationRequired(
                    f"Timed out waiting for manual login ({settings.LOGIN_WAIT_TIMEOUT}s). Please log in to your recruiter account and retry."
                )

    def _fill_and_submit_search(self, query: GeneratedQuery) -> List[any]:
        """
        Enters candidate keywords, location, and experience filters, and submits candidate search.
        """
        driver = self.client.driver
        wait = self.client.wait

        try:
            # Keyword / Designation search input
            search_input = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, NaukriSelectors.SEARCH_INPUT)
                )
            )
            search_input.clear()
            search_input.send_keys(query.primary_query)

            # Location input
            if query.location:
                try:
                    loc_input = driver.find_element(
                        By.CSS_SELECTOR, NaukriSelectors.LOCATION_INPUT
                    )
                    loc_input.clear()
                    loc_input.send_keys(query.location)
                except Exception:
                    pass

            # Experience inputs
            if query.min_experience is not None:
                try:
                    min_exp_el = driver.find_element(
                        By.CSS_SELECTOR, NaukriSelectors.EXPERIENCE_MIN_INPUT
                    )
                    min_exp_el.send_keys(str(int(query.min_experience)))
                except Exception:
                    pass

            # Submit search
            try:
                btn = driver.find_element(
                    By.CSS_SELECTOR, NaukriSelectors.SEARCH_BUTTON
                )
                btn.click()
            except Exception:
                search_input.send_keys(Keys.RETURN)

            # Wait for candidate profile result tuples to load
            return wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, NaukriSelectors.RESULT_CARD)
                )
            )
        except Exception as exc:
            logger.warning(f"Candidate search interaction encountered: {exc}")
            # Try finding any existing candidate result cards on the page
            return driver.find_elements(By.CSS_SELECTOR, NaukriSelectors.RESULT_CARD)

    def _check_for_challenges(self) -> None:
        """
        Detects if Naukri presented a CAPTCHA or blocked page.
        """
        driver = self.client.driver

        # Check for CAPTCHA container
        try:
            captcha_el = driver.find_elements(
                By.CSS_SELECTOR, NaukriSelectors.CAPTCHA_CONTAINER
            )
            if captcha_el:
                raise NaukriSecurityChallenge()
        except NaukriSecurityChallenge:
            raise
        except Exception:
            pass

        # Check for Access Denied
        try:
            page_src = driver.page_source.lower()
            if "access denied" in page_src or "cloudflare" in page_src and "verify you are human" in page_src:
                raise NaukriSecurityChallenge()
        except NaukriSecurityChallenge:
            raise
        except Exception:
            pass
