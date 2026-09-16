import logging
import time
from typing import Any, List, Optional, Union
from playwright.sync_api import Page, Locator
from app.core.config import settings
from app.playwright.selectors import ResdexSelectors

logger = logging.getLogger(__name__)


class ResdexFormExecutor:
    """
    Deterministic Form Executor for Naukri Resdex using Playwright.
    Executes typed form actions with built-in waiting and decoupled selectors.
    Never calls the LLM during form interactions.
    """

    def __init__(self, page: Page):
        self.page = page
        self.timeout = (getattr(settings, "SELENIUM_TIMEOUT", 25) or 25) * 1000

    # ── Helpers ──────────────────────────────────────────────────────────

    def _locator(self, selector: str) -> Locator:
        """Returns a Locator for the first matching CSS or XPath selector."""
        if selector.startswith("//") or selector.startswith("("):
            return self.page.locator(f"xpath={selector}")
        return self.page.locator(selector).first

    def _locators(self, selector: str) -> Locator:
        """Returns a Locator for all matching CSS or XPath selectors."""
        if selector.startswith("//") or selector.startswith("("):
            return self.page.locator(f"xpath={selector}")
        return self.page.locator(selector)

    def _js(self, script: str, *args) -> Any:
        """Execute JavaScript on the page."""
        return self.page.evaluate(script, *args)

    # ── Core form actions ────────────────────────────────────────────────

    def fill_text(
        self, selector: str, value: str, clear_first: bool = True
    ) -> bool:
        """Finds a text input element, clears it, and types the value with React state sync."""
        if not value:
            return False
        try:
            loc = self._locator(selector)
            loc.scroll_into_view_if_needed()
            time.sleep(0.2)

            loc.click()
            time.sleep(0.1)

            if clear_first:
                loc.fill("")
                time.sleep(0.1)

            # Native value setter syncs React state; dispatched events trigger validation.
            # loc.type() is intentionally omitted: it would double-write into the input
            # after React has already processed the value, potentially causing duplicate text.
            self._js("""
                (el, val) => {
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    nativeInputValueSetter.call(el, val);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                    el.dispatchEvent(new Event('focusout', { bubbles: true }));
                }
            """, loc.element_handle(), value)
            time.sleep(0.4)

            # Dispatch events one more time to ensure any deferred React handlers fire
            self._js("""
                (el) => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """, loc.element_handle())
            time.sleep(0.2)

            logger.info(f"Filled text '{value}' into selector '{selector}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to fill text '{value}' on '{selector}': {exc}")
            return False

    def fill_number(
        self, selector: str, value: Union[int, float]
    ) -> bool:
        """Finds a numeric input and sets the number."""
        if value is None:
            return False
        num_str = str(int(value)) if isinstance(value, (int, float)) and value.is_integer() else str(value)
        return self.fill_text(selector=selector, value=num_str)

    def fill_checkbox(self, selector: str, checked: bool) -> bool:
        """Sets a checkbox to checked or unchecked state."""
        if checked is None:
            return False
        try:
            loc = self._locator(selector)
            loc.scroll_into_view_if_needed()
            time.sleep(0.2)
            is_checked = loc.is_checked()
            if checked != is_checked:
                loc.click()
                logger.info(f"Set checkbox '{selector}' to {checked}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to set checkbox '{selector}' to {checked}: {exc}")
            return False

    def select_option(self, selector: str, value: str) -> bool:
        """Selects an option in a <select> element or clicks matching element."""
        if not value:
            return False
        try:
            loc = self._locator(selector)
            loc.scroll_into_view_if_needed()
            time.sleep(0.2)

            tag = self._js("(el) => el.tagName.toLowerCase()", loc.element_handle())
            if tag == "select":
                loc.select_option(label=value)
                # Dispatch change event for React
                self._js("""
                    (el) => {
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                """, loc.element_handle())
                logger.info(f"Selected option '{value}' in dropdown '{selector}'")
            else:
                loc.click()
                logger.info(f"Clicked option '{selector}' for value '{value}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to select option '{value}' on '{selector}': {exc}")
            return False

    def select_multiple(self, selector: str, values: List[str]) -> bool:
        """Selects or types multiple options in a multiselect control."""
        if not values:
            return False
        success = True
        for val in values:
            typed = self.fill_text(selector=selector, value=val, clear_first=False)
            if typed:
                time.sleep(0.5)
                try:
                    clicked = False
                    sugg_selectors = [
                        "div.sug-item", "li.sug-item", "div.location-item",
                        "li.suggestion-item", "div[class*='sugItem']",
                        "div[class*='option']", "li[class*='option']",
                        "div[class*='dropdown'] div", "ul[class*='sug'] li",
                    ]
                    for sugg_sel in sugg_selectors:
                        suggs = self.page.locator(sugg_sel)
                        for i in range(suggs.count()):
                            s = suggs.nth(i)
                            if s.is_visible():
                                s.click()
                                clicked = True
                                time.sleep(0.3)
                                break
                        if clicked:
                            break

                    if not clicked:
                        try:
                            tokens = [t.lower() for t in val.replace('/', ' ').replace('-', ' ').split() if len(t) >= 2]
                            combo = "div.sug-item, li.sug-item, div[class*='sug'], li[class*='sug'], div[class*='tuple'], div[class*='option'], li[class*='option']"
                            sug_loc = self.page.locator(combo)
                            for i in range(sug_loc.count()):
                                s = sug_loc.nth(i)
                                if s.is_visible():
                                    stext = (s.text_content() or "").strip().lower()
                                    if stext == val.strip().lower() or any(tok in stext for tok in tokens):
                                        s.click()
                                        clicked = True
                                        time.sleep(0.3)
                                        break
                        except Exception:
                            pass

                    if not clicked:
                        loc = self._locator(selector)
                        loc.press("Enter")
                        time.sleep(0.3)

                    try:
                        loc = self._locator(selector)
                        loc.press("Escape")
                        time.sleep(0.2)
                    except Exception:
                        pass

                    self._js("document.body.click()")
                    time.sleep(0.2)

                except Exception as e:
                    logger.warning(f"Error selecting option '{val}': {e}")
            else:
                success = False
        return success

    def fill_range(
        self,
        min_selector: str,
        max_selector: str,
        min_val: Optional[Union[int, float]],
        max_val: Optional[Union[int, float]],
    ) -> bool:
        """Fills a minimum and maximum numeric/text range."""
        res_min = True
        res_max = True
        if min_val is not None:
            res_min = self.fill_number(min_selector, min_val)
        if max_val is not None:
            res_max = self.fill_number(max_selector, max_val)
            if not res_max:
                try:
                    num_str = str(int(max_val)) if isinstance(max_val, (int, float)) and max_val.is_integer() else str(max_val)
                    self._js(f"""
                        () => {{
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
                        }}
                    """)
                    time.sleep(0.3)
                    res_max = True
                    logger.info(f"Filled max value '{max_val}' via JS fallback")
                except Exception as e:
                    logger.warning(f"JS fallback for max value failed: {e}")
        return res_min and res_max

    def submit_form(self, button_selector: str) -> bool:
        """Clicks the search submission button."""
        try:
            self.dismiss_all_dropdowns()
            time.sleep(0.3)
            loc = self._locator(button_selector)
            loc.click()
            logger.info(f"Clicked search submit button '{button_selector}'")
            return True
        except Exception as exc:
            logger.error(f"Failed to click search submit button '{button_selector}': {exc}")
            return False

    def dismiss_all_dropdowns(self):
        """Dismisses any open dropdowns/modals by pressing Escape and clicking body."""
        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.1)
        except Exception:
            pass
        try:
            self._js("document.body.click()")
            time.sleep(0.1)
        except Exception:
            pass
        try:
            neutral = self.page.locator("h1, h2, header, main, .content")
            for i in range(neutral.count()):
                n = neutral.nth(i)
                if n.is_visible():
                    n.click()
                    break
        except Exception:
            pass

    def fill_location(self, location: str) -> bool:
        """Fills location field with robust suggestion handling."""
        if not location:
            return False
        try:
            loc = self._locator(ResdexSelectors.LOCATION_INPUT)
            loc.scroll_into_view_if_needed()
            time.sleep(0.2)

            loc.click()
            time.sleep(0.1)
            self._js("""
                (el) => {
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(el, '');
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """, loc.element_handle())
            time.sleep(0.1)

            loc.type(location, delay=30)
            time.sleep(0.8)

            clicked = False
            suggestion_xpaths = [
                f"//div[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
                f"//li[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
                f"//span[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
            ]
            for xp in suggestion_xpaths:
                try:
                    suggs = self.page.locator(f"xpath={xp}")
                    for i in range(suggs.count()):
                        s = suggs.nth(i)
                        if s.is_visible():
                            s.click()
                            clicked = True
                            time.sleep(0.3)
                            break
                except Exception:
                    pass
                if clicked:
                    break

            if not clicked:
                css_suggs = [
                    "div.sug-item", "li.sug-item", "div.location-item",
                    "li.suggestion-item", "div[class*='sugItem']", "li[class*='sugItem']",
                ]
                for sel in css_suggs:
                    try:
                        suggs = self.page.locator(sel)
                        for i in range(suggs.count()):
                            s = suggs.nth(i)
                            if s.is_visible():
                                s.click()
                                clicked = True
                                time.sleep(0.3)
                                break
                    except Exception:
                        pass
                    if clicked:
                        break

            if not clicked:
                loc.press("Enter")
                time.sleep(0.3)

            loc.press("Escape")
            time.sleep(0.1)
            self._js("document.body.click()")
            time.sleep(0.2)

            chips = self.page.locator(
                f"//*[contains(@class, 'chip') or contains(@class, 'tag')][contains(text(), '{location}')]"
            )
            return chips.count() > 0

        except Exception as e:
            logger.warning(f"Failed to fill location '{location}': {e}")
            return False

    def fill_keywords_with_stars(
        self,
        required_keywords: List[str],
        preferred_keywords: Optional[List[str]] = None,
        input_selector: str = ResdexSelectors.KEYWORD_INPUT,
    ) -> bool:
        """Enters keywords individually, verifying each chip is created, and clicking star for mandatory skills."""
        if not required_keywords and not preferred_keywords:
            return False

        try:
            loc = self._locator(input_selector)
            loc.scroll_into_view_if_needed()
            time.sleep(0.3)
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

            # Count existing chips before entry
            chip_count_before = self.page.locator(
                "//div[contains(@class,'chip') or contains(@class,'tag') or contains(@class,'pill')]"
            ).count()

            try:
                self._js("""
                    (input) => {
                        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(input, '');
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                """, loc.element_handle())
                time.sleep(0.1)

                loc.type(kw_clean, delay=30)
                time.sleep(0.5)

                loc.press("Enter")
                time.sleep(0.6)

                # Wait for chip count to increase (confirms keyword was accepted)
                accepted = False
                for _ in range(6):
                    chip_count_after = self.page.locator(
                        "//div[contains(@class,'chip') or contains(@class,'tag') or contains(@class,'pill')]"
                    ).count()
                    if chip_count_after > chip_count_before:
                        accepted = True
                        break
                    time.sleep(0.3)

                if not accepted:
                    # Try clicking first visible suggestion
                    sugg_selectors = [
                        "div.sug-item", "li.suggestion-item", "div.keyword-sug",
                        "li.sug-item", "div[class*='sug']", "li[class*='sug']",
                    ]
                    for sugg_sel in sugg_selectors:
                        suggs = self.page.locator(sugg_sel)
                        for i in range(suggs.count()):
                            s = suggs.nth(i)
                            if s.is_visible():
                                s.click()
                                time.sleep(0.4)
                                chip_count_after = self.page.locator(
                                    "//div[contains(@class,'chip') or contains(@class,'tag') or contains(@class,'pill')]"
                                ).count()
                                if chip_count_after > chip_count_before:
                                    accepted = True
                                break
                        if accepted:
                            break

                if accepted:
                    logger.info(f"Keyword chip confirmed for '{kw_clean}'")
                    self._js("document.body.click()")
                    time.sleep(0.2)

                    if kw_clean.lower() in mandatory_set:
                        self._click_keyword_star(kw_clean)
                        time.sleep(0.2)

                    success_count += 1
                else:
                    logger.warning(f"Keyword '{kw_clean}' not confirmed as chip — skipping star")

            except Exception as e:
                logger.warning(f"Error entering keyword '{kw_clean}': {e}")

        try:
            self.fill_checkbox(ResdexSelectors.MANDATORY_KEYWORDS_CHECKBOX, True)
        except Exception:
            pass

        return success_count > 0

    def _click_keyword_star(self, skill_name: str) -> bool:
        """Locates the star icon for a specific keyword chip and clicks it."""
        try:
            xpath_queries = [
                f"//div[contains(@class, 'chip') or contains(@class, 'tag') or contains(@class, 'pill')][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{skill_name.lower()}')]//*[contains(@class, 'star') or contains(@class, 'Star') or @title='Mandatory' or contains(@title, 'star') or local-name()='svg']",
                f"//span[contains(@class, 'chip') or contains(@class, 'tag')][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{skill_name.lower()}')]//*[contains(@class, 'star') or @title='Mandatory' or local-name()='svg']",
                f"//span[contains(text(), '{skill_name}')]/..//*[contains(@class, 'star') or @title='Mandatory']",
                "(//div[contains(@class, 'chip')]//*[contains(@class, 'star')])[last()]",
                "(//span[contains(@class, 'chip')]//*[contains(@class, 'star')])[last()]",
            ]
            for xp in xpath_queries:
                stars = self.page.locator(f"xpath={xp}")
                for i in range(stars.count()):
                    star = stars.nth(i)
                    if star.is_visible():
                        star_class = star.get_attribute("class") or ""
                        aria_pressed = star.get_attribute("aria-pressed") or ""
                        if "active" not in star_class and "selected" not in star_class and "starred" not in star_class and aria_pressed != "true":
                            star.click(force=True)
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
        """Expands 'Additional Details' accordion section if collapsed."""
        toggle_xpaths = [
            "//h2[contains(., 'Additional Details')]",
            "//div[contains(@class, 'accordion')][contains(., 'Additional Details')]",
            "//button[contains(., 'Additional Details')]",
            "//span[contains(., 'Additional Details')]",
            "div#additionalDetailsToggle",
            "button#additionalToggle",
        ]
        for xpath in toggle_xpaths:
            try:
                headers = self.page.locator(f"xpath={xpath}")
                for i in range(headers.count()):
                    h = headers.nth(i)
                    if h.is_visible():
                        aria_exp = h.get_attribute("aria-expanded")
                        cls = h.get_attribute("class") or ""
                        if aria_exp == "false" or "collapsed" in cls:
                            h.click(force=True)
                            time.sleep(0.4)
                            return
                        elif aria_exp != "true":
                            show_only = self.page.locator(
                                "xpath=//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show only candidates with')]"
                            )
                            if show_only.count() == 0 or not any(show_only.nth(j).is_visible() for j in range(show_only.count())):
                                h.click(force=True)
                                time.sleep(0.4)
                                return
            except Exception:
                pass

    def tick_show_only_candidates_options(
        self,
        verified_mobile: bool = False,
        verified_email: bool = False,
        attached_resume: bool = False,
    ) -> List[str]:
        """
        Clicks the 'Show only candidates with' pill buttons.
        The UI shows pill-style '+' buttons (NOT checkboxes) for:
        - Verified Mobile Number
        - Verified Email ID
        - Attached Resume
        """
        requested = []
        if verified_mobile:
            requested.append(("verified_mobile", ResdexSelectors.VERIFIED_MOBILE_TEXT))
        if verified_email:
            requested.append(("verified_email", ResdexSelectors.VERIFIED_EMAIL_TEXT))
        if attached_resume:
            requested.append(("attached_resume", ResdexSelectors.ATTACHED_RESUME_TEXT))

        if not requested:
            return []

        ticked = []
        self._ensure_additional_section_expanded()
        time.sleep(0.3)

        for key, search_text in requested:
            success = False
            # Strategy 1: SHOW_ONLY_PILL_TEMPLATE — pill/chip element containing the text
            try:
                xpath = ResdexSelectors.SHOW_ONLY_PILL_TEMPLATE.format(text=search_text)
                els = self.page.locator(f"xpath={xpath}")
                for i in range(els.count()):
                    el = els.nth(i)
                    if el.is_visible():
                        el_class = el.get_attribute("class") or ""
                        aria_pressed = el.get_attribute("aria-pressed") or ""
                        if "active" not in el_class and "selected" not in el_class and aria_pressed != "true":
                            el.click(force=True)
                        logger.info(f"Clicked show-only pill '{search_text}'")
                        success = True
                        time.sleep(0.3)
                        break
            except Exception as e:
                logger.warning(f"Pill template failed for '{search_text}': {e}")

            # Strategy 2: JS text-search fallback (shortest visible element containing the text)
            if not success:
                try:
                    result = self._js(f"""
                        (searchText) => {{
                            searchText = searchText.toLowerCase();
                            var allElements = document.querySelectorAll('span, div, button, label, a, li');
                            var matches = [];
                            for (var i = 0; i < allElements.length; i++) {{
                                var el = allElements[i];
                                var text = (el.textContent || '').toLowerCase().trim();
                                if (text === searchText && el.offsetParent !== null) {{
                                    matches.push({{ element: el, textLength: text.length }});
                                }}
                            }}
                            // Try exact match first, then contains
                            if (matches.length === 0) {{
                                for (var i = 0; i < allElements.length; i++) {{
                                    var el = allElements[i];
                                    var text = (el.textContent || '').toLowerCase().trim();
                                    if (text.indexOf(searchText) !== -1 && el.offsetParent !== null) {{
                                        matches.push({{ element: el, textLength: text.length }});
                                    }}
                                }}
                            }}
                            matches.sort(function(a, b) {{ return a.textLength - b.textLength; }});
                            if (matches.length > 0) {{
                                var target = matches[0].element;
                                var cls = target.className || '';
                                if (cls.indexOf('active') !== -1 || cls.indexOf('selected') !== -1) {{
                                    return 'already_active';
                                }}
                                target.click();
                                return 'clicked';
                            }}
                            return 'not_found';
                        }}
                    """, search_text)
                    if result in ('clicked', 'already_active'):
                        success = True
                        time.sleep(0.3)
                except Exception as e:
                    logger.warning(f"JS fallback failed for '{search_text}': {e}")

            if success:
                ticked.append(key)
                logger.info(f"Successfully ticked show-only '{search_text}'")
            else:
                logger.warning(f"Could not locate show-only pill/checkbox for '{search_text}'")

        return ticked

    def select_active_in(self, period: str) -> bool:
        """Sets the 'Active in' duration filter.

        Resdex uses a custom React dropdown (not a native <select>) in v3.
        Strategy:
          1. Try native <select> (older UI or fallback)
          2. Click the trigger element to open the dropdown
          3. Click the matching option text inside the open dropdown
        """
        if not period:
            return False

        # Strategy 1: native <select>
        try:
            sel_loc = self._locators(ResdexSelectors.ACTIVE_IN_SELECT)
            for i in range(sel_loc.count()):
                s = sel_loc.nth(i)
                if s.is_visible():
                    tag = self._js("(el) => el.tagName.toLowerCase()", s.element_handle())
                    if tag == "select":
                        s.select_option(label=period)
                        self._js("""
                            (el) => {
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        """, s.element_handle())
                        logger.info(f"Selected '{period}' in active_in <select>")
                        return True
        except Exception:
            pass

        # Strategy 2: React custom dropdown — click trigger to open
        trigger_opened = False
        try:
            trigger_xpaths = ResdexSelectors.ACTIVE_IN_DROPDOWN_TRIGGER.split(" | ")
            for xp in trigger_xpaths:
                xp = xp.strip()
                try:
                    els = self.page.locator(f"xpath={xp}")
                    for i in range(els.count()):
                        el = els.nth(i)
                        if el.is_visible():
                            el.click()
                            time.sleep(0.4)
                            trigger_opened = True
                            break
                except Exception:
                    pass
                if trigger_opened:
                    break
        except Exception:
            pass

        # Strategy 3: Click the option text inside the now-open dropdown
        option_xpath = ResdexSelectors.ACTIVE_IN_OPTION_TEMPLATE.format(option=period)
        try:
            option_parts = option_xpath.split(" | ")
            for part in option_parts:
                part = part.strip()
                try:
                    els = self.page.locator(f"xpath={part}")
                    for i in range(els.count()):
                        el = els.nth(i)
                        if el.is_visible():
                            el.click(force=True)
                            self._js("""
                                (el) => {
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                    el.dispatchEvent(new Event('click', { bubbles: true }));
                                }
                            """, el.element_handle())
                            time.sleep(0.3)
                            logger.info(f"Clicked Active In option '{period}'")
                            return True
                except Exception:
                    pass
        except Exception:
            pass

        # Strategy 4: JS text search over all visible elements
        try:
            result = self._js(f"""
                (period) => {{
                    period = period.toLowerCase().trim();
                    var candidates = document.querySelectorAll(
                        'li, div[role="option"], span, div[class*="option"], div[class*="menu"] *'
                    );
                    for (var i = 0; i < candidates.length; i++) {{
                        var el = candidates[i];
                        var text = (el.textContent || '').toLowerCase().trim();
                        if (text === period && el.offsetParent !== null) {{
                            el.click();
                            return 'clicked';
                        }}
                    }}
                    return 'not_found';
                }}
            """, period)
            if result == 'clicked':
                time.sleep(0.3)
                logger.info(f"Active In '{period}' clicked via JS fallback")
                return True
        except Exception as e:
            logger.warning(f"JS fallback for Active In failed: {e}")

        logger.warning(f"Could not set Active In to '{period}'")
        return False

    def fill_keyword_scope(self, scope: str) -> bool:
        """
        Sets the keyword search scope using the React custom link/dropdown.
        The trigger is a span/link like 'Search keyword in Entire resume ▼'.
        Clicking it opens a dropdown, then we click the desired scope option.
        """
        if not scope or scope == "Entire resume":
            return True  # Default — no action needed

        # Try native <select> first (some UI versions)
        try:
            sel_loc = self._locators(ResdexSelectors.KEYWORD_SEARCH_SCOPE_SELECT)
            for i in range(sel_loc.count()):
                s = sel_loc.nth(i)
                if s.is_visible():
                    tag = self._js("(el) => el.tagName.toLowerCase()", s.element_handle())
                    if tag == "select":
                        s.select_option(label=scope)
                        logger.info(f"Set keyword scope via <select>: '{scope}'")
                        return True
        except Exception:
            pass

        # Click the trigger link to open the dropdown
        trigger_opened = False
        try:
            trigger_parts = ResdexSelectors.KEYWORD_SCOPE_TRIGGER.split(" | ")
            for xp in trigger_parts:
                xp = xp.strip()
                try:
                    els = self.page.locator(f"xpath={xp}")
                    for i in range(els.count()):
                        el = els.nth(i)
                        if el.is_visible():
                            el.click()
                            time.sleep(0.4)
                            trigger_opened = True
                            break
                except Exception:
                    pass
                if trigger_opened:
                    break
        except Exception:
            pass

        # Now click the option
        option_xpath = ResdexSelectors.KEYWORD_SCOPE_OPTION_TEMPLATE.format(option=scope)
        try:
            option_parts = option_xpath.split(" | ")
            for part in option_parts:
                part = part.strip()
                try:
                    els = self.page.locator(f"xpath={part}")
                    for i in range(els.count()):
                        el = els.nth(i)
                        if el.is_visible():
                            el.click(force=True)
                            time.sleep(0.3)
                            logger.info(f"Set keyword scope via dropdown: '{scope}'")
                            return True
                except Exception:
                    pass
        except Exception:
            pass

        logger.warning(f"Could not set keyword scope to '{scope}'")
        return False

    def fill_education_qualifications(
        self,
        ug_qualification: Optional[str] = None,
        pg_qualification: Optional[str] = None,
    ) -> List[str]:
        """
        Clicks UG and PG qualification pill buttons in the Education Details section.
        Normalises option text casing before matching.
        Returns list of fields successfully clicked.
        """
        filled = []
        if not ug_qualification and not pg_qualification:
            return filled

        # Expand section
        self.expand_section(ResdexSelectors.EDUCATION_SECTION_TOGGLE)
        time.sleep(0.4)

        if ug_qualification:
            # Normalise: title-case the option to match UI text
            ug_display = ug_qualification.strip()
            ok = self.click_pill(ResdexSelectors.UG_QUALIFICATION_PILL_TEMPLATE, ug_display)
            if ok:
                filled.append("ug_qualification")
                logger.info(f"Set UG qualification: '{ug_display}'")
            else:
                logger.warning(f"Could not set UG qualification: '{ug_display}'")

        if pg_qualification:
            pg_display = pg_qualification.strip()
            ok = self.click_pill(ResdexSelectors.PG_QUALIFICATION_PILL_TEMPLATE, pg_display)
            if ok:
                filled.append("pg_qualification")
                logger.info(f"Set PG qualification: '{pg_display}'")
            else:
                logger.warning(f"Could not set PG qualification: '{pg_display}'")

        return filled

    def click_pill(self, xpath_template: str, value: str) -> bool:
        """Clicks a pill/chip button by filling in the template with the value."""
        if not value:
            return False

        xpath = xpath_template.format(option=value)
        try:
            els = self.page.locator(f"xpath={xpath}")
            for i in range(els.count()):
                el = els.nth(i)
                if el.is_visible():
                    el.scroll_into_view_if_needed()
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
                        el.click(force=True)
                        time.sleep(0.2)
                        logger.info(f"Clicked pill '{value}'")
                    else:
                        logger.info(f"Pill '{value}' already active")
                    return True
        except Exception as exc:
            logger.warning(f"Failed to click pill '{value}': {exc}")
        return False

    def expand_section(self, xpath: str) -> bool:
        """Expands a collapsible section if collapsed."""
        try:
            headers = self.page.locator(f"xpath={xpath}")
            for i in range(headers.count()):
                h = headers.nth(i)
                if h.is_visible():
                    aria_exp = h.get_attribute("aria-expanded")
                    cls = h.get_attribute("class") or ""
                    if aria_exp == "false" or "collapsed" in cls:
                        h.click(force=True)
                        time.sleep(0.4)
                        logger.info(f"Expanded section: {xpath}")
                    return True
        except Exception:
            pass
        return False

    def _check_pill_active(self, search_text: str) -> bool:
        """Check if a pill/chip with given text has active/selected/checked class."""
        try:
            return self._js("""
                (searchText) => {
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
                }
            """, search_text)
        except Exception:
            return False

    def verify_form_filled(self, fields_interacted: List[str], plan: dict) -> dict:
        """Verifies that all fields from the plan were actually filled in the form."""
        filled = []
        missing = []

        # Check keywords
        if plan.get("keywords") and plan["keywords"].get("required"):
            kw_chips = self.page.locator(
                "//div[contains(@class, 'chip') or contains(@class, 'tag') or contains(@class, 'pill')]"
            )
            if kw_chips.count() > 0:
                filled.append("keywords")
            else:
                missing.append("keywords")

        # Check experience
        if plan.get("min_experience") is not None or plan.get("max_experience") is not None:
            min_el = self.page.locator("xpath=//input[contains(@placeholder, 'Min experience')]")
            max_el = self.page.locator("xpath=//input[contains(@placeholder, 'Max experience')]")
            min_val = min_el.first.get_attribute("value") if min_el.count() > 0 else ""
            max_val = max_el.first.get_attribute("value") if max_el.count() > 0 else ""
            if min_val or max_val:
                filled.append("experience")
            else:
                missing.append("experience")

        # Check location
        if plan.get("current_location"):
            loc_chips = self.page.locator(
                "xpath=//div[contains(@class, 'chip') or contains(@class, 'tag')][contains(@class, 'location')]"
            )
            if loc_chips.count() > 0:
                filled.append("location")
            else:
                missing.append("location")

        # Check notice period
        if plan.get("notice_period"):
            np_filled = []
            for np in plan["notice_period"]:
                pill = self.page.locator(
                    f"xpath=//span[contains(@class, 'pill') or contains(@class, 'chip')][normalize-space()='{np}']"
                )
                if pill.count() > 0:
                    cls = pill.first.get_attribute("class") or ""
                    if "active" in cls or "selected" in cls:
                        np_filled.append(np)
            if np_filled:
                filled.append("notice_period")
            else:
                missing.append("notice_period")

        # Check pill-based fields
        pill_checks = [("verified_mobile", "verified mobile"), ("verified_email", "verified email"), ("attached_resume", "attached resume")]
        for field, search_text in pill_checks:
            if plan.get(field):
                if self._check_pill_active(search_text):
                    filled.append(field)
                else:
                    missing.append(field)

        # Check education fields — verify the pill has an active/selected class
        for field, label_text, option_value in [
            ("ug_qualification", "ug qualification", plan.get("ug_qualification")),
            ("pg_qualification", "pg qualification", plan.get("pg_qualification")),
        ]:
            if option_value:
                pill = self.page.locator(
                    f"xpath=//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label_text}')]"
                    f"/following::*[normalize-space()='{option_value}' and "
                    "(contains(@class,'active') or contains(@class,'selected') or contains(@class,'checked'))][1]"
                )
                if pill.count() > 0:
                    filled.append(field)
                else:
                    missing.append(field)

        # Check active_in
        if plan.get("active_in"):
            active_in_text = self.page.locator(
                f"xpath=//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::span[contains(text(), '{plan['active_in']}')]"
            )
            if active_in_text.count() > 0:
                filled.append("active_in")
            else:
                missing.append("active_in")

        return {"filled": filled, "missing": missing}
