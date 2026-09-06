import logging
import time
from typing import Any, List, Optional, Union
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from app.core.config import settings

logger = logging.getLogger(__name__)


class ResdexFormExecutor:
    """
    Deterministic Form Executor for Naukri Resdex.
    Executes typed form actions using explicit waits and decoupled selectors.
    Never calls the LLM during form interactions.
    """

    def __init__(self, driver: WebDriver, wait: WebDriverWait = None):
        self.driver = driver
        self.wait = wait or WebDriverWait(driver, 4.0)

    def fill_text(
        self, selector: str, value: str, by: By = By.CSS_SELECTOR, clear_first: bool = True
    ) -> bool:
        """Finds a text input element, clears it, and types the value."""
        if not value:
            return False
        try:
            el = self.wait.until(EC.presence_of_element_located((by, selector)))
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", el)
                time.sleep(0.2)
            except Exception:
                pass
            if clear_first:
                el.clear()
            el.send_keys(value)
            time.sleep(0.3)
            logger.info(f"Filled text '{value}' into selector '{selector}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to fill text '{value}' on '{selector}': {exc}")
            return False

    def fill_number(
        self, selector: str, value: Union[int, float], by: By = By.CSS_SELECTOR
    ) -> bool:
        """Finds a numeric input or dropdown and sets the number."""
        if value is None:
            return False
        num_str = str(int(value)) if isinstance(value, (int, float)) and value.is_integer() else str(value)
        return self.fill_text(selector=selector, value=num_str, by=by)

    def fill_checkbox(
        self, selector: str, checked: bool, by: By = By.CSS_SELECTOR
    ) -> bool:
        """Sets a checkbox to checked or unchecked state."""
        if checked is None:
            return False
        try:
            el = self.wait.until(EC.presence_of_element_located((by, selector)))
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", el)
                time.sleep(0.2)
            except Exception:
                pass
            is_selected = el.is_selected()
            if (checked and not is_selected) or (not checked and is_selected):
                el.click()
                logger.info(f"Set checkbox '{selector}' to {checked}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to set checkbox '{selector}' to {checked}: {exc}")
            return False

    def select_option(
        self, selector: str, value: str, by: By = By.CSS_SELECTOR
    ) -> bool:
        """Selects an option in a <select> element or clicks matching radio/option element."""
        if not value:
            return False
        try:
            el = self.wait.until(EC.presence_of_element_located((by, selector)))
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", el)
                time.sleep(0.2)
            except Exception:
                pass
            if el.tag_name.lower() == "select":
                select_obj = Select(el)
                select_obj.select_by_visible_text(value)
                logger.info(f"Selected option '{value}' in dropdown '{selector}'")
            else:
                el.click()
                logger.info(f"Clicked option '{selector}' for value '{value}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to select option '{value}' on '{selector}': {exc}")
            return False

    def select_multiple(
        self, selector: str, values: List[str], by: By = By.CSS_SELECTOR
    ) -> bool:
        """Selects or types multiple options in a multiselect control."""
        if not values:
            return False
        success = True
        for val in values:
            typed = self.fill_text(selector=selector, value=val, by=by, clear_first=False)
            if typed:
                time.sleep(0.4)
                try:
                    # Check if auto-suggestion list is displayed
                    suggs = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "div.sug-item, li.sug-item, div.location-item, li.suggestion-item, div[class*='sugItem'], div[class*='option']"
                    )
                    clicked = False
                    for s in suggs:
                        if s.is_displayed():
                            s.click()
                            clicked = True
                            break
                    if not clicked:
                        el = self.driver.find_element(by, selector)
                        el.send_keys(Keys.RETURN)
                    time.sleep(0.2)
                    try:
                        el = self.driver.find_element(by, selector)
                        el.send_keys(Keys.ESCAPE)
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                success = False
        return success

    def select_search_option(
        self, input_selector: str, option_selector: str, value: str
    ) -> bool:
        """Types value into a search-select input and clicks the resulting suggestion."""
        if not value:
            return False
        try:
            self.fill_text(input_selector, value)
            time.sleep(0.5)
            opt_el = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, option_selector))
            )
            opt_el.click()
            logger.info(f"Selected search suggestion for '{value}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to select search option for '{value}': {exc}")
            return False

    def fill_range(
        self,
        min_selector: str,
        max_selector: str,
        min_val: Optional[Union[int, float]],
        max_val: Optional[Union[int, float]],
        by: By = By.CSS_SELECTOR,
    ) -> bool:
        """Fills a minimum and maximum numeric/text range."""
        res_min = True
        res_max = True
        if min_val is not None:
            res_min = self.fill_number(min_selector, min_val, by=by)
        if max_val is not None:
            res_max = self.fill_number(max_selector, max_val, by=by)
        return res_min and res_max

    def apply_boolean_filter(
        self, selector: str, value: bool, by: By = By.CSS_SELECTOR
    ) -> bool:
        """Applies a boolean filter/toggle."""
        if value is None:
            return False
        return self.fill_checkbox(selector, value, by=by)

    def submit_form(self, button_selector: str, by: By = By.CSS_SELECTOR) -> bool:
        """Clicks the search submission button."""
        try:
            btn = self.wait.until(EC.element_to_be_clickable((by, button_selector)))
            btn.click()
            logger.info(f"Clicked search submit button '{button_selector}'")
            return True
        except Exception as exc:
            logger.error(f"Failed to click search submit button '{button_selector}': {exc}")
            return False
