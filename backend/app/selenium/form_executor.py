import logging
import time
from typing import Any, List, Optional, Union
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from app.core.config import settings
from app.selenium.selectors import ResdexSelectors

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

            # Focus the element first
            el.click()
            time.sleep(0.1)

            if clear_first:
                el.clear()
                time.sleep(0.1)

            # Use native setter to ensure React/Angular state updates
            self.driver.execute_script("""
                var el = arguments[0];
                var value = arguments[1];
                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(el, value);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
                el.dispatchEvent(new Event('focusout', { bubbles: true }));
            """, el, value)
            time.sleep(0.4)

            # Also try send_keys as backup for React's synthetic event system
            if clear_first:
                el.clear()
            el.send_keys(value)
            time.sleep(0.3)

            # Dispatch events again after send_keys
            self.driver.execute_script("""
                var el = arguments[0];
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, el)
            time.sleep(0.2)

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
                time.sleep(0.5)
                try:
                    # Try to click first visible suggestion
                    clicked = False
                    sugg_selectors = [
                        "div.sug-item",
                        "li.sug-item",
                        "div.location-item",
                        "li.suggestion-item",
                        "div[class*='sugItem']",
                        "div[class*='option']",
                        "li[class*='option']",
                        "div[class*='dropdown'] div",
                        "ul[class*='sug'] li",
                    ]
                    for sugg_sel in sugg_selectors:
                        suggs = self.driver.find_elements(By.CSS_SELECTOR, sugg_sel)
                        for s in suggs:
                            if s.is_displayed():
                                s.click()
                                clicked = True
                                time.sleep(0.3)
                                break
                        if clicked:
                            break

                    # If no suggestion clicked, try XPath text match
                    if not clicked:
                        try:
                            xpath = f"//*[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{val}')]"
                            xuggs = self.driver.find_elements(By.XPATH, xpath)
                            for s in xuggs:
                                if s.is_displayed():
                                    s.click()
                                    clicked = True
                                    time.sleep(0.3)
                                    break
                        except Exception:
                            pass

                    # Final fallback: press ENTER
                    if not clicked:
                        el = self.driver.find_element(by, selector)
                        el.send_keys(Keys.RETURN)
                        time.sleep(0.3)

                    # Close dropdown if still open
                    try:
                        el = self.driver.find_element(by, selector)
                        el.send_keys(Keys.ESCAPE)
                        time.sleep(0.2)
                    except Exception:
                        pass

                    # Click elsewhere to dismiss any open dropdowns
                    self.driver.execute_script("document.body.click();")
                    time.sleep(0.2)

                except Exception as e:
                    logger.warning(f"Error selecting option '{val}': {e}")
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
            if not res_max:
                # Fallback: use JavaScript to set value directly with multiple selectors
                try:
                    num_str = str(int(max_val)) if isinstance(max_val, (int, float)) and max_val.is_integer() else str(max_val)
                    self.driver.execute_script(f"""
                        var selectors = [
                            'input[placeholder*="Max experience"]',
                            'input[placeholder*="max experience"]',
                            'input[placeholder*="Max"]',
                            'input[placeholder*="max"]',
                            'input[name*="maxExp"]',
                            'input[name*="max_exp"]',
                            'input[id*="max"]',
                            'input[data-id*="max"]',
                            'input[type="number"]',
                            'input[type="text"]'
                        ];
                        for (var i = 0; i < selectors.length; i++) {{
                            var inputs = document.querySelectorAll(selectors[i]);
                            for (var j = 0; j < inputs.length; j++) {{
                                var input = inputs[j];
                                var rect = input.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0 && !input.value) {{
                                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    nativeInputValueSetter.call(input, '{num_str}');
                                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                                    break;
                                }}
                            }}
                        }}
                    """)
                    time.sleep(0.3)
                    res_max = True
                    logger.info(f"Filled max value '{max_val}' via JS fallback")
                except Exception as e:
                    logger.warning(f"JS fallback for max value failed: {e}")
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
            # First dismiss any open dropdowns
            self.dismiss_all_dropdowns()
            time.sleep(0.3)

            btn = self.wait.until(EC.element_to_be_clickable((by, button_selector)))
            btn.click()
            logger.info(f"Clicked search submit button '{button_selector}'")
            return True
        except Exception as exc:
            logger.error(f"Failed to click search submit button '{button_selector}': {exc}")
            return False

    def dismiss_all_dropdowns(self):
        """Dismisses any open dropdowns/modals by pressing Escape and clicking body."""
        try:
            # Press Escape to close any open dropdowns
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.1)
        except Exception:
            pass
        try:
            # Click on body to dismiss
            self.driver.execute_script("document.body.click();")
            time.sleep(0.1)
        except Exception:
            pass
        try:
            # Click on a neutral area (page header or main content)
            neutral = self.driver.find_elements(By.CSS_SELECTOR, "h1, h2, header, main, .content")
            for n in neutral:
                if n.is_displayed():
                    n.click()
                    break
        except Exception:
            pass

    def dispatch_input_events(self, selector: str, by: By = By.CSS_SELECTOR):
        """Dispatches input and change events on an element to update React/Angular state."""
        try:
            el = self.driver.find_element(by, selector)
            self.driver.execute_script("""
                var el = arguments[0];
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            """, el)
        except Exception:
            pass

    def fill_location(self, location: str) -> bool:
        """
        Fills location field with robust suggestion handling.
        Returns True if location was successfully added.
        """
        if not location:
            return False

        try:
            # Find location input
            input_el = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ResdexSelectors.LOCATION_INPUT))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", input_el)
            time.sleep(0.2)

            # Clear and type location using native setter + send_keys
            input_el.click()
            time.sleep(0.1)
            self.driver.execute_script("""
                var el = arguments[0];
                var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(el, '');
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, input_el)
            time.sleep(0.1)

            input_el.send_keys(location)
            time.sleep(0.8)  # Wait for suggestions to load

            # Try to click the first matching suggestion
            suggestion_selectors = [
                f"//div[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
                f"//li[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
                f"//span[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
                "div.sug-item",
                "li.sug-item",
                "div.location-item",
                "li.suggestion-item",
                "div[class*='sugItem']",
                "li[class*='sugItem']",
            ]

            clicked = False
            for sel in suggestion_selectors:
                by = By.XPATH if sel.startswith("//") or sel.startswith("(") else By.CSS_SELECTOR
                try:
                    suggs = self.driver.find_elements(by, sel)
                    for s in suggs:
                        if s.is_displayed():
                            s.click()
                            clicked = True
                            time.sleep(0.3)
                            break
                except Exception:
                    pass
                if clicked:
                    break

            # If no suggestion clicked, try pressing ENTER
            if not clicked:
                input_el.send_keys(Keys.RETURN)
                time.sleep(0.3)

            # Dismiss dropdown
            input_el.send_keys(Keys.ESCAPE)
            time.sleep(0.1)
            self.driver.execute_script("document.body.click();")
            time.sleep(0.2)

            # Verify location chip was added
            chips = self.driver.find_elements(
                By.XPATH,
                f"//*[contains(@class, 'chip') or contains(@class, 'tag')][contains(text(), '{location}')]"
            )
            return len(chips) > 0

        except Exception as e:
            logger.warning(f"Failed to fill location '{location}': {e}")
            return False

    def fill_keywords_with_stars(
        self,
        required_keywords: List[str],
        preferred_keywords: Optional[List[str]] = None,
        input_selector: str = ResdexSelectors.KEYWORD_INPUT,
    ) -> bool:
        """
        Enters keywords individually into Naukri Resdex.
        For each mandatory/required skill, automatically clicks the star icon on the chip
        to mark it mandatory.
        """
        if not required_keywords and not preferred_keywords:
            return False

        try:
            input_el = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, input_selector)))
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", input_el)
                time.sleep(0.3)
            except Exception:
                pass
        except Exception as exc:
            logger.warning(f"Could not locate keyword input: {exc}")
            return False

        mandatory_set = {k.strip().lower() for k in (required_keywords or []) if k.strip()}
        all_keywords = list(dict.fromkeys((required_keywords or []) + (preferred_keywords or [])))
        success_count = 0

        for kw in all_keywords:
            kw_clean = kw.strip()
            if not kw_clean:
                continue
            try:
                # Clear input first using JS to ensure clean state
                self.driver.execute_script("""
                    var input = arguments[0];
                    input.value = '';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                """, input_el)
                time.sleep(0.1)

                # Type keyword
                input_el.send_keys(kw_clean)
                time.sleep(0.4)

                # Press ENTER to add keyword
                input_el.send_keys(Keys.RETURN)
                time.sleep(0.5)

                # Dismiss or select auto-suggestion if shown
                try:
                    sugg_selectors = [
                        "div.sug-item",
                        "li.suggestion-item",
                        "div.keyword-sug",
                        "li.sug-item",
                        "div[class*='sug']",
                        "li[class*='sug']",
                    ]
                    for sugg_sel in sugg_selectors:
                        suggs = self.driver.find_elements(By.CSS_SELECTOR, sugg_sel)
                        for s in suggs:
                            if s.is_displayed():
                                s.click()
                                time.sleep(0.3)
                                break
                except Exception:
                    pass

                # Click elsewhere to dismiss any dropdown
                self.driver.execute_script("document.body.click();")
                time.sleep(0.2)

                # If this keyword is mandatory, click its star icon
                if kw_clean.lower() in mandatory_set:
                    self._click_keyword_star(kw_clean)
                    time.sleep(0.2)

                success_count += 1
            except Exception as e:
                logger.warning(f"Error entering keyword '{kw_clean}': {e}")

        # Also tick the global mandatory checkbox if present
        try:
            self.fill_checkbox(ResdexSelectors.MANDATORY_KEYWORDS_CHECKBOX, True)
        except Exception:
            pass

        return success_count > 0

    def _click_keyword_star(self, skill_name: str) -> bool:
        """Locates the star icon for a specific keyword chip and clicks it to mark mandatory."""
        try:
            xpath_queries = [
                f"//div[contains(@class, 'chip') or contains(@class, 'tag') or contains(@class, 'pill')][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{skill_name.lower()}')]//*[contains(@class, 'star') or contains(@class, 'Star') or @title='Mandatory' or contains(@title, 'star') or local-name()='svg']",
                f"//span[contains(@class, 'chip') or contains(@class, 'tag')][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{skill_name.lower()}')]//*[contains(@class, 'star') or @title='Mandatory' or local-name()='svg']",
                f"//span[contains(text(), '{skill_name}')]/..//*[contains(@class, 'star') or @title='Mandatory']",
                "(//div[contains(@class, 'chip')]//*[contains(@class, 'star')])[last()]",
                "(//span[contains(@class, 'chip')]//*[contains(@class, 'star')])[last()]",
            ]
            for xp in xpath_queries:
                stars = self.driver.find_elements(By.XPATH, xp)
                for star in stars:
                    if star.is_displayed():
                        star_class = star.get_attribute("class") or ""
                        aria_pressed = star.get_attribute("aria-pressed") or ""
                        if "active" not in star_class and "selected" not in star_class and "starred" not in star_class and aria_pressed != "true":
                            self.driver.execute_script("arguments[0].click();", star)
                            logger.info(f"Clicked mandatory star icon for keyword '{skill_name}'")
                            time.sleep(0.2)
                            return True
                        else:
                            logger.info(f"Star for keyword '{skill_name}' is already active")
                            return True
        except Exception as exc:
            logger.warning(f"Could not click star for keyword '{skill_name}': {exc}")
        return False

    def _ensure_additional_section_expanded(self):
        """Expands 'Additional Details' accordion section if it is collapsed."""
        toggle_xpaths = [
            "//h2[contains(., 'Additional Details')]",
            "//div[contains(@class, 'accordion')][contains(., 'Additional Details')]",
            "//button[contains(., 'Additional Details')]",
            "//span[contains(., 'Additional Details')]",
            "div#additionalDetailsToggle",
            "button#additionalToggle",
        ]
        for xpath in toggle_xpaths:
            by = By.XPATH if (xpath.startswith("//") or xpath.startswith("(")) else By.CSS_SELECTOR
            try:
                headers = self.driver.find_elements(by, xpath)
                for h in headers:
                    if h.is_displayed():
                        aria_exp = h.get_attribute("aria-expanded")
                        cls = h.get_attribute("class") or ""
                        if aria_exp == "false" or "collapsed" in cls:
                            self.driver.execute_script("arguments[0].click();", h)
                            time.sleep(0.4)
                            return
                        elif aria_exp != "true":
                            # Check if "Show only candidates with" section is visible
                            show_only_els = self.driver.find_elements(
                                By.XPATH,
                                "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show only candidates with')]"
                            )
                            if not show_only_els or not any(m.is_displayed() for m in show_only_els):
                                self.driver.execute_script("arguments[0].click();", h)
                                time.sleep(0.4)
                                return
            except Exception:
                pass

    def tick_show_only_candidates_options(self) -> List[str]:
        """
        In the Additional Details section, ticks all three options under 'Show only candidates with':
        1. Verified Mobile Number
        2. Verified Email ID
        3. Attached Resume
        Returns list of successfully ticked option names.
        """
        ticked = []
        self._ensure_additional_section_expanded()
        time.sleep(0.3)

        # Use JavaScript to find and click the pill elements directly
        options = [
            ("verified_mobile", "Verified Mobile Number"),
            ("verified_email", "Verified Email ID"),
            ("attached_resume", "Attached Resume"),
        ]

        for key, name in options:
            success = False
            try:
                # Use JS to find elements containing the text and click the smallest one
                result = self.driver.execute_script(f"""
                    var searchText = '{name}'.toLowerCase();
                    var allElements = document.querySelectorAll('span, div, button, label, a');
                    var matches = [];
                    for (var i = 0; i < allElements.length; i++) {{
                        var el = allElements[i];
                        var text = (el.textContent || '').toLowerCase().trim();
                        if (text.indexOf(searchText) !== -1 && el.offsetParent !== null) {{
                            matches.push({{
                                element: el,
                                textLength: text.length,
                                tag: el.tagName
                            }});
                        }}
                    }}
                    // Sort by text length ascending - smallest text = most specific element
                    matches.sort(function(a, b) {{ return a.textLength - b.textLength; }});
                    if (matches.length > 0) {{
                        var target = matches[0].element;
                        // Check if already active
                        var cls = target.className || '';
                        if (cls.indexOf('active') !== -1 || cls.indexOf('selected') !== -1 || cls.indexOf('checked') !== -1) {{
                            return 'already_active';
                        }}
                        // Click the element
                        target.click();
                        return 'clicked';
                    }}
                    return 'not_found';
                """)

                if result == 'clicked' or result == 'already_active':
                    success = True
                    time.sleep(0.3)

            except Exception as e:
                logger.warning(f"Error clicking {name}: {e}")

            if success:
                ticked.append(name)
                logger.info(f"Successfully ticked '{name}'")
            else:
                logger.warning(f"Could not locate '{name}' pill")

        return ticked

    def select_active_in(self, period: str) -> bool:
        """
        Dynamically sets the 'Active in' duration filter.
        (e.g. '15 days', '30 days', '2 months', '3 months', '6 months').
        """
        if not period:
            return False

        # Try standard select dropdown first
        try:
            sel_els = self.driver.find_elements(By.XPATH, ResdexSelectors.ACTIVE_IN_SELECT)
            for s in sel_els:
                if s.is_displayed():
                    select_obj = Select(s)
                    select_obj.select_by_visible_text(period)
                    # Dispatch change event for React
                    self.driver.execute_script("""
                        var sel = arguments[0];
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                        sel.dispatchEvent(new Event('input', { bubbles: true }));
                    """, s)
                    logger.info(f"Selected '{period}' in active_in dropdown")
                    return True
        except Exception:
            pass

        # Try clicking the dropdown first, then selecting option
        try:
            # Find and click the Active in dropdown container
            dropdown_xpaths = [
                "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::*[contains(@class, 'dropdown') or contains(@class, 'select')][1]",
                "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::div[contains(@class, 'react-select') or contains(@class, 'css-')][1]",
                "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::div[@role='combobox'][1]",
                "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::div[@role='listbox'][1]",
            ]
            for xp in dropdown_xpaths:
                try:
                    els = self.driver.find_elements(By.XPATH, xp)
                    for el in els:
                        if el.is_displayed():
                            el.click()
                            time.sleep(0.3)
                            break
                except Exception:
                    pass
        except Exception:
            pass

        # Try clicking the option text directly
        xpaths = [
            f"//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::span[contains(text(), '{period}')]",
            f"//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::option[contains(text(), '{period}')]",
            f"//div[contains(., 'Active in')]//span[contains(text(), '{period}')]",
            f"//div[contains(., 'Active in')]//li[contains(text(), '{period}')]",
            f"//li[contains(@class, 'option')][contains(text(), '{period}')]",
            f"//div[contains(@class, 'dropdown')]//div[contains(text(), '{period}')]",
            f"//div[contains(@class, 'menu')]//div[contains(text(), '{period}')]",
            f"//div[contains(@class, 'menu')]//span[contains(text(), '{period}')]",
            f"//li[contains(@class, 'menu')]//div[contains(text(), '{period}')]",
        ]
        for xp in xpaths:
            try:
                els = self.driver.find_elements(By.XPATH, xp)
                for el in els:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
                        # Dispatch change event for React
                        self.driver.execute_script("""
                            var el = arguments[0];
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.dispatchEvent(new Event('click', { bubbles: true }));
                        """, el)
                        time.sleep(0.3)
                        logger.info(f"Clicked Active In option '{period}'")
                        return True
            except Exception:
                pass

        return False

    def click_pill(self, xpath_template: str, value: str) -> bool:
        """
        Clicks a pill/chip button by filling in the template with the value.
        Returns True if successfully clicked or already active.
        """
        if not value:
            return False

        xpath = xpath_template.format(option=value)
        try:
            els = self.driver.find_elements(By.XPATH, xpath)
            for el in els:
                if el.is_displayed():
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", el)
                    time.sleep(0.1)

                    el_class = el.get_attribute("class") or ""
                    aria_pressed = el.get_attribute("aria-pressed") or ""
                    is_already_active = (
                        "active" in el_class
                        or "selected" in el_class
                        or "checked" in el_class
                        or aria_pressed == "true"
                    )

                    if not is_already_active:
                        self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.2)
                        logger.info(f"Clicked pill '{value}'")
                    else:
                        logger.info(f"Pill '{value}' already active")
                    return True
        except Exception as exc:
            logger.warning(f"Failed to click pill '{value}': {exc}")
        return False

    def expand_section(self, xpath: str) -> bool:
        """
        Expands a collapsible section if it's collapsed.
        Returns True if expanded or already expanded.
        """
        try:
            headers = self.driver.find_elements(By.XPATH, xpath)
            for h in headers:
                if h.is_displayed():
                    aria_exp = h.get_attribute("aria-expanded")
                    cls = h.get_attribute("class") or ""
                    if aria_exp == "false" or "collapsed" in cls:
                        self.driver.execute_script("arguments[0].click();", h)
                        time.sleep(0.4)
                        logger.info(f"Expanded section: {xpath}")
                    return True
        except Exception:
            pass
        return False

    def verify_form_filled(self, fields_interacted: List[str], plan: dict) -> dict:
        """
        Verifies that all fields from the plan were actually filled in the form.
        Returns a dict with 'filled' and 'missing' lists.
        """
        filled = []
        missing = []

        # Check keywords
        if plan.get("keywords") and plan["keywords"].get("required"):
            kw_chips = self.driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'chip') or contains(@class, 'tag') or contains(@class, 'pill')]"
            )
            if kw_chips:
                filled.append("keywords")
            else:
                missing.append("keywords")

        # Check experience
        if plan.get("min_experience") is not None or plan.get("max_experience") is not None:
            min_exp = self.driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'Min experience')]")
            max_exp = self.driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'Max experience')]")
            min_val = min_exp[0].get_attribute("value") if min_exp else ""
            max_val = max_exp[0].get_attribute("value") if max_exp else ""
            if min_val or max_val:
                filled.append("experience")
            else:
                missing.append("experience")

        # Check location
        if plan.get("current_location"):
            loc_chips = self.driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'chip') or contains(@class, 'tag')][contains(@class, 'location')]"
            )
            if loc_chips:
                filled.append("location")
            else:
                missing.append("location")

        # Check notice period
        if plan.get("notice_period"):
            np_filled = []
            for np in plan["notice_period"]:
                pill_xp = f"//span[contains(@class, 'pill') or contains(@class, 'chip')][normalize-space()='{np}']"
                pills = self.driver.find_elements(By.XPATH, pill_xp)
                if pills and any(p.get_attribute("class") and ("active" in (p.get_attribute("class") or "") or "selected" in (p.get_attribute("class") or "")) for p in pills):
                    np_filled.append(np)
            if np_filled:
                filled.append("notice_period")
            else:
                missing.append("notice_period")

        # Check verified_mobile
        if plan.get("verified_mobile"):
            try:
                result = self.driver.execute_script("""
                    var searchText = 'verified mobile';
                    var allElements = document.querySelectorAll('span, div, button, label, a');
                    for (var i = 0; i < allElements.length; i++) {
                        var el = allElements[i];
                        var text = (el.textContent || '').toLowerCase().trim();
                        if (text.indexOf(searchText) !== -1 && el.offsetParent !== null) {
                            var cls = el.className || '';
                            if (cls.indexOf('active') !== -1 || cls.indexOf('selected') !== -1 || cls.indexOf('checked') !== -1) {
                                return true;
                            }
                        }
                    }
                    return false;
                """)
                if result:
                    filled.append("verified_mobile")
                else:
                    missing.append("verified_mobile")
            except Exception:
                missing.append("verified_mobile")

        # Check verified_email
        if plan.get("verified_email"):
            try:
                result = self.driver.execute_script("""
                    var searchText = 'verified email';
                    var allElements = document.querySelectorAll('span, div, button, label, a');
                    for (var i = 0; i < allElements.length; i++) {
                        var el = allElements[i];
                        var text = (el.textContent || '').toLowerCase().trim();
                        if (text.indexOf(searchText) !== -1 && el.offsetParent !== null) {
                            var cls = el.className || '';
                            if (cls.indexOf('active') !== -1 || cls.indexOf('selected') !== -1 || cls.indexOf('checked') !== -1) {
                                return true;
                            }
                        }
                    }
                    return false;
                """)
                if result:
                    filled.append("verified_email")
                else:
                    missing.append("verified_email")
            except Exception:
                missing.append("verified_email")

        # Check attached_resume
        if plan.get("attached_resume"):
            try:
                result = self.driver.execute_script("""
                    var searchText = 'attached resume';
                    var allElements = document.querySelectorAll('span, div, button, label, a');
                    for (var i = 0; i < allElements.length; i++) {
                        var el = allElements[i];
                        var text = (el.textContent || '').toLowerCase().trim();
                        if (text.indexOf(searchText) !== -1 && el.offsetParent !== null) {
                            var cls = el.className || '';
                            if (cls.indexOf('active') !== -1 || cls.indexOf('selected') !== -1 || cls.indexOf('checked') !== -1) {
                                return true;
                            }
                        }
                    }
                    return false;
                """)
                if result:
                    filled.append("attached_resume")
                else:
                    missing.append("attached_resume")
            except Exception:
                missing.append("attached_resume")

        # Check active_in
        if plan.get("active_in"):
            active_in_text = self.driver.find_elements(
                By.XPATH,
                f"//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::span[contains(text(), '{plan['active_in']}')]"
            )
            if active_in_text:
                filled.append("active_in")
            else:
                missing.append("active_in")

        return {"filled": filled, "missing": missing}
