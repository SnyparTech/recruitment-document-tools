import logging
import time
from typing import List
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
        Executes candidate profile search on live Naukri using Playwright.
        """
        try:
            candidate_search_url = settings.NAUKRI_RESDEX_URL
            logger.info(f"Navigating to live Naukri Resdex portal: {candidate_search_url}")
            self.client.navigate_to(candidate_search_url)

            self._wait_for_login_if_needed()
            self._check_for_challenges()

            page = self.client.page

            card_locators = self._fill_and_submit_search(query)

            self._check_for_challenges()

            candidates: List[CandidateProfile] = []
            for idx in range(card_locators.count()):
                card = card_locators.nth(idx)
                extracted = self.extractor.extract_from_card(card, index=idx + 1)
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
        """Detects if Naukri redirected to a login page and gives user time to log in."""
        page = self.client.page
        current_url = page.url.lower()

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
                    curr = page.url.lower()
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

    def _fill_and_submit_search(self, query: GeneratedQuery):
        """Enters candidate search parameters and submits."""
        page = self.client.page

        try:
            search_input = page.locator(NaukriSelectors.SEARCH_INPUT).first
            search_input.wait_for(state="visible")
            search_input.fill("")
            search_input.fill(query.primary_query)

            if query.location:
                try:
                    loc_input = page.locator(NaukriSelectors.LOCATION_INPUT).first
                    loc_input.fill("")
                    loc_input.fill(query.location)
                except Exception:
                    pass

            if query.min_experience is not None:
                try:
                    min_exp_el = page.locator(NaukriSelectors.EXPERIENCE_MIN_INPUT).first
                    min_exp_el.fill(str(int(query.min_experience)))
                except Exception:
                    pass

            try:
                btn = page.locator(NaukriSelectors.SEARCH_BUTTON).first
                btn.click()
            except Exception:
                search_input.press("Enter")

            result_cards = page.locator(NaukriSelectors.RESULT_CARD)
            result_cards.first.wait_for(state="visible", timeout=15000)
            return result_cards

        except Exception as exc:
            logger.warning(f"Candidate search interaction encountered: {exc}")
            return page.locator(NaukriSelectors.RESULT_CARD)

    def _check_for_challenges(self) -> None:
        """Detects if Naukri presented a CAPTCHA or blocked page."""
        page = self.client.page

        try:
            captcha = page.locator(NaukriSelectors.CAPTCHA_CONTAINER)
            if captcha.count() > 0 and captcha.first.is_visible():
                raise NaukriSecurityChallenge()
        except NaukriSecurityChallenge:
            raise
        except Exception:
            pass

        try:
            page_text = (page.content() or "").lower()
            if "access denied" in page_text or ("cloudflare" in page_text and "verify you are human" in page_text):
                raise NaukriSecurityChallenge()
        except NaukriSecurityChallenge:
            raise
        except Exception:
            pass
