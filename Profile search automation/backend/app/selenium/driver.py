import logging
import os
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from app.core.config import settings
from app.core.exceptions import SeleniumDriverError

logger = logging.getLogger(__name__)


class ResdexDriver:
    """
    Manages Selenium WebDriver lifecycle with persistent session storage,
    anti-automation flags removal, and explicit waits.
    """

    def __init__(self):
        self._driver: Optional[webdriver.Chrome] = None
        self._wait: Optional[WebDriverWait] = None

    def start_driver(self) -> webdriver.Chrome:
        """
        Initializes Chrome WebDriver with persistent user data profile and
        disables automation flags.
        """
        if self._driver is not None:
            return self._driver

        try:
            options = ChromeOptions()
            if settings.SELENIUM_HEADLESS:
                options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins-discovery")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-default-apps")
            options.add_argument("--remote-allow-origins=http://127.0.0.1,http://localhost")
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )

            # Prevent automation detection
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            # Use persistent session directory so login is preserved across all runs
            raw_path = settings.SELENIUM_USER_DATA_DIR or "./selenium_profile"
            if raw_path.lower().endswith(".lnk") or (
                os.path.exists(raw_path) and not os.path.isdir(raw_path)
            ):
                raw_path = "./selenium_profile"

            profile_dir = os.path.abspath(raw_path)
            os.makedirs(profile_dir, exist_ok=True)

            # Clean stale Chromium locks if any
            for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket", "DevToolsActivePort"]:
                lock_path = os.path.join(profile_dir, lock_file)
                if os.path.exists(lock_path):
                    try:
                        os.remove(lock_path)
                    except Exception:
                        pass

            options.add_argument(f"--user-data-dir={profile_dir}")
            logger.info(f"Using persistent Chrome profile directory: {profile_dir}")

            self._driver = webdriver.Chrome(options=options)

            # Mask navigator.webdriver in JavaScript
            try:
                self._driver.execute_cdp_cmd(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    },
                )
            except Exception:
                pass

            self._driver.set_page_load_timeout(settings.SELENIUM_TIMEOUT)
            self._wait = WebDriverWait(self._driver, settings.SELENIUM_TIMEOUT)
            logger.info("Selenium Chrome WebDriver started successfully.")
            return self._driver
        except Exception as exc:
            logger.error(f"Failed to start Selenium WebDriver: {exc}")
            raise SeleniumDriverError(f"Could not start Chrome WebDriver: {str(exc)}")

    @property
    def driver(self) -> webdriver.Chrome:
        """Returns active driver or starts a new instance."""
        if self._driver is None:
            return self.start_driver()
        return self._driver

    @property
    def wait(self) -> WebDriverWait:
        """Returns active WebDriverWait instance."""
        if self._wait is None:
            self.start_driver()
        return self._wait

    def navigate_to(self, url: str) -> None:
        """Navigates to the specified URL safely."""
        try:
            self.driver.get(url)
        except Exception as exc:
            raise SeleniumDriverError(f"Navigation to '{url}' failed: {str(exc)}")

    def close(self) -> None:
        """Closes and quits the WebDriver safely without deleting the persistent session."""
        if self._driver is not None:
            try:
                self._driver.quit()
                logger.info("Selenium WebDriver quit cleanly (session saved).")
            except Exception as exc:
                logger.warning(f"Error while quitting WebDriver: {exc}")
            finally:
                self._driver = None
                self._wait = None

    def __enter__(self):
        self.start_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
