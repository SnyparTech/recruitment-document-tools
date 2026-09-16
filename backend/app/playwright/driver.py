import logging
import os
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
from app.core.config import settings
from app.core.exceptions import BrowserDriverError

logger = logging.getLogger(__name__)


class ResdexDriver:
    """
    Manages Playwright browser lifecycle with persistent session storage.
    Attaches to Chrome via CDP or launches a fresh Chromium context.
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def start_driver(self) -> Page:
        """
        Initializes Playwright browser with persistent user data profile.
        Returns a Page object for form interactions.
        """
        if self._page is not None:
            return self._page

        try:
            self._playwright = sync_playwright().start()

            chrome_bin = getattr(settings, "CHROME_BINARY_PATH", None)
            user_data_dir = getattr(
                settings,
                "CHROME_AUTOMATION_USER_DATA_DIR",
                os.path.expanduser("~/.playwright-naukri-profile"),
            )
            os.makedirs(user_data_dir, exist_ok=True)

            launch_args = [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ]

            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                executable_path=chrome_bin,
                headless=False,
                args=launch_args,
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
            )

            # Mask navigator.webdriver
            self._context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = self._context.new_page()

            logger.info("Playwright browser started successfully with persistent session.")
            return self._page

        except Exception as exc:
            logger.error(f"Failed to start Playwright browser: {exc}")
            raise BrowserDriverError(f"Could not start browser: {exc}")

    @property
    def page(self) -> Page:
        """Returns active page or starts a new instance."""
        if self._page is None:
            return self.start_driver()
        return self._page

    def navigate_to(self, url: str) -> None:
        """Navigates to the specified URL safely."""
        try:
            self.page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:
            raise BrowserDriverError(f"Navigation to '{url}' failed: {exc}")

    def close(self) -> None:
        """Detaches from the browser session without closing the recruiter's active window."""
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._page = None
        self._context = None
        self._playwright = None

    def __enter__(self):
        self.start_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
