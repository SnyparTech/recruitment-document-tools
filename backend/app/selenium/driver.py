import logging
import os
import subprocess
import time
import urllib.request
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from app.core.config import settings
from app.core.exceptions import SeleniumDriverError

logger = logging.getLogger(__name__)


class ResdexDriver:
    """
    Manages Selenium WebDriver lifecycle with persistent session storage,
    anti-automation flags removal, and explicit waits.
    Attaches to Chrome via remote debugging on port 9222.
    """

    def __init__(self):
        self._driver: Optional[webdriver.Chrome] = None
        self._wait: Optional[WebDriverWait] = None

    @staticmethod
    def _is_remote_debugging_open(port: int = 9222) -> bool:
        """Checks if Chrome is already running with remote debugging port enabled."""
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def get_chromedriver_path() -> Optional[str]:
        """Locates cached local chromedriver binary to bypass network downloads."""
        cache_dir = os.path.expanduser(r"~/.cache/selenium/chromedriver/win64")
        if os.path.exists(cache_dir):
            try:
                versions = sorted(os.listdir(cache_dir), reverse=True)
                for v in versions:
                    exe = os.path.join(cache_dir, v, "chromedriver.exe")
                    if os.path.isfile(exe):
                        return exe
            except Exception:
                pass
        return None

    _last_launch_time: float = 0.0

    @classmethod
    def launch_chrome_browser(cls, url: str = "https://resdex.naukri.com/v3?activeTab=advSrch") -> None:
        """
        Launches Google Chrome with dedicated automation profile directory and remote debugging port 9222.
        Debounced to ensure only one browser window is opened.
        """
        debug_port = getattr(settings, "SELENIUM_REMOTE_DEBUGGING_PORT", 9222)
        if cls._is_remote_debugging_open(debug_port):
            logger.info(f"Chrome is already listening on remote debugging port {debug_port}.")
            return

        now = time.time()
        if now - cls._last_launch_time < 3.0:
            logger.info("Chrome launch skipped (already launched within last 3 seconds).")
            return
        cls._last_launch_time = now

        chrome_bin = getattr(settings, "CHROME_BINARY_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        profile_dir_name = getattr(settings, "CHROME_PROFILE_DIRECTORY", "Profile 18")
        user_data_dir = getattr(
            settings,
            "CHROME_AUTOMATION_USER_DATA_DIR",
            r"C:\Users\sriha\AppData\Local\Google\Chrome\NaukriAutomation"
        )

        os.makedirs(user_data_dir, exist_ok=True)

        cmd = [
            chrome_bin,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={profile_dir_name}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ]
        flags = 0
        if hasattr(subprocess, "DETACHED_PROCESS") and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        logger.info(f"Launching Chrome with remote debugging on port {debug_port}: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd, creationflags=flags)
            # Wait briefly for port to start listening
            for _ in range(12):
                time.sleep(0.5)
                if cls._is_remote_debugging_open(debug_port):
                    logger.info(f"Chrome remote debugging port {debug_port} is ready.")
                    break
        except Exception as exc:
            logger.error(f"Failed to launch Chrome with command: {exc}")

    def start_driver(self) -> Optional[webdriver.Chrome]:
        """
        Initializes Chrome WebDriver attached to Chrome on port 9222.
        Ensures a single browser window is opened and directly automated.
        """
        if self._driver is not None:
            return self._driver

        try:
            debug_port = getattr(settings, "SELENIUM_REMOTE_DEBUGGING_PORT", 9222)

            # Ensure Chrome is running with remote debugging enabled
            if not self._is_remote_debugging_open(debug_port):
                self.launch_chrome_browser("https://resdex.naukri.com/v3?activeTab=advSrch")

            # Wait up to 5 seconds if not yet open
            for _ in range(10):
                if self._is_remote_debugging_open(debug_port):
                    break
                time.sleep(0.5)

            if not self._is_remote_debugging_open(debug_port):
                raise SeleniumDriverError(f"Chrome remote debugging port {debug_port} is not accessible.")

            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")

            chromedriver_path = self.get_chromedriver_path()
            service = Service(executable_path=chromedriver_path) if chromedriver_path else None

            if service:
                self._driver = webdriver.Chrome(service=service, options=options)
            else:
                self._driver = webdriver.Chrome(options=options)

            self._wait = WebDriverWait(self._driver, settings.SELENIUM_TIMEOUT)
            logger.info(f"Successfully attached to Chrome window on port {debug_port}.")
            return self._driver

        except Exception as exc:
            logger.error(f"Failed to start Selenium WebDriver: {exc}")
            raise SeleniumDriverError(f"Could not connect to Chrome on port 9222: {exc}")

    @property
    def driver(self) -> Optional[webdriver.Chrome]:
        """Returns active driver or starts a new instance."""
        if self._driver is None:
            return self.start_driver()
        return self._driver

    @property
    def wait(self) -> Optional[WebDriverWait]:
        """Returns active WebDriverWait instance."""
        return self._wait

    def navigate_to(self, url: str) -> None:
        """Navigates to the specified URL safely."""
        try:
            if self.driver is not None:
                self.driver.get(url)
        except Exception as exc:
            raise SeleniumDriverError(f"Navigation to '{url}' failed: {str(exc)}")

    def close(self) -> None:
        """
        Detaches from the WebDriver session without closing the recruiter's active browser window.
        """
        if self._driver is not None:
            try:
                # Detach reference without killing the browser window so user can review details
                pass
            finally:
                self._driver = None
                self._wait = None

    def __enter__(self):
        self.start_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
