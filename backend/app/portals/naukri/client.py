import logging
import os
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from app.core.config import settings
from app.core.exceptions import BrowserDriverError

logger = logging.getLogger(__name__)


class NaukriClient:
    """
    Manages Playwright browser lifecycle with persistent session storage.
    Async — safe to call from FastAPI endpoints.
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def start_driver(self) -> Page:
        if self._page is not None:
            return self._page

        try:
            self._playwright = await async_playwright().start()

            chrome_bin = getattr(settings, "CHROME_BINARY_PATH", None)
            raw_path = getattr(settings, "BROWSER_USER_DATA_DIR", None) or "./playwright_profile"
            if raw_path.lower().endswith(".lnk") or (os.path.exists(raw_path) and not os.path.isdir(raw_path)):
                raw_path = "./playwright_profile"

            profile_dir = os.path.abspath(raw_path)
            os.makedirs(profile_dir, exist_ok=True)

            launch_args = [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ]

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                executable_path=chrome_bin,
                headless=getattr(settings, "BROWSER_HEADLESS", False),
                args=launch_args,
                ignore_default_args=["--enable-automation"],
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
            )

            await self._context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = await self._context.new_page()

            logger.info("Playwright browser started successfully.")
            return self._page

        except Exception as exc:
            logger.error(f"Failed to start Playwright browser: {exc}")
            raise BrowserDriverError(f"Could not start browser: {str(exc)}")

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BrowserDriverError("Browser not started. Call start_driver() first.")
        return self._page

    async def navigate_to(self, url: str) -> None:
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:
            raise BrowserDriverError(f"Navigation to '{url}' failed: {str(exc)}")

    async def close(self) -> None:
        if self._context is not None:
            try:
                await self._context.close()
                logger.info("Playwright browser context closed (session saved).")
            except Exception as exc:
                logger.warning(f"Error while closing browser context: {exc}")
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._page = None
        self._context = None
        self._playwright = None

    async def __aenter__(self):
        await self.start_driver()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
