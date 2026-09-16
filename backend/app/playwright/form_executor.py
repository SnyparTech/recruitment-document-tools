import asyncio
import logging
from typing import Any, List, Optional, Union
from playwright.async_api import Page, Locator
from app.core.config import settings
from app.playwright.selectors import ResdexSelectors

logger = logging.getLogger(__name__)


class ResdexFormExecutor:
    """
    Deterministic Form Executor for Naukri Resdex using Playwright (async).
    Never calls the LLM during form interactions.
    """

    def __init__(self, page: Page):
        self.page = page
        self.timeout = (getattr(settings, "SELENIUM_TIMEOUT", 25) or 25) * 1000

    # ── Helpers ──────────────────────────────────────────────────────────

    def _locator(self, selector: str) -> Locator:
        if selector.startswith("//") or selector.startswith("("):
            return self.page.locator(f"xpath={selector}")
        return self.page.locator(selector).first

    def _locators(self, selector: str) -> Locator:
        if selector.startswith("//") or selector.startswith("("):
            return self.page.locator(f"xpath={selector}")
        return self.page.locator(selector)

    async def _js(self, script: str, *args) -> Any:
        return await self.page.evaluate(script, *args)

    # ── Core form actions ────────────────────────────────────────────────

    async def fill_text(
        self, selector: str, value: str, clear_first: bool = True
    ) -> bool:
        if not value:
            return False
        try:
            loc = self._locator(selector)
            await loc.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)

            await loc.click()
            await asyncio.sleep(0.1)

            if clear_first:
                await loc.fill("")
                await asyncio.sleep(0.1)

            # Native value setter for React state sync
            await self._js("""
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
            """, await loc.element_handle(), value)
            await asyncio.sleep(0.4)

            if clear_first:
                await loc.fill("")
            await loc.type(value, delay=30)
            await asyncio.sleep(0.3)

            await self._js("""
                (el) => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """, await loc.element_handle())
            await asyncio.sleep(0.2)

            logger.info(f"Filled text '{value}' into '{selector}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to fill text '{value}' on '{selector}': {exc}")
            return False

    async def fill_number(self, selector: str, value: Union[int, float]) -> bool:
        if value is None:
            return False
        num_str = str(int(value)) if isinstance(value, (int, float)) and value.is_integer() else str(value)
        return await self.fill_text(selector=selector, value=num_str)

    async def fill_checkbox(self, selector: str, checked: bool) -> bool:
        if checked is None:
            return False
        try:
            loc = self._locator(selector)
            await loc.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)
            is_checked = await loc.is_checked()
            if checked != is_checked:
                await loc.click()
                logger.info(f"Set checkbox '{selector}' to {checked}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to set checkbox '{selector}' to {checked}: {exc}")
            return False

    async def select_option(self, selector: str, value: str) -> bool:
        if not value:
            return False
        try:
            loc = self._locator(selector)
            await loc.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)

            tag = await self._js("(el) => el.tagName.toLowerCase()", await loc.element_handle())
            if tag == "select":
                await loc.select_option(label=value)
                await self._js("""
                    (el) => {
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                """, await loc.element_handle())
                logger.info(f"Selected option '{value}' in '{selector}'")
            else:
                await loc.click()
                logger.info(f"Clicked option '{selector}' for '{value}'")
            return True
        except Exception as exc:
            logger.warning(f"Failed to select option '{value}' on '{selector}': {exc}")
            return False

    async def select_multiple(self, selector: str, values: List[str]) -> bool:
        if not values:
            return False
        success = True
        for val in values:
            typed = await self.fill_text(selector=selector, value=val, clear_first=False)
            if typed:
                await asyncio.sleep(0.5)
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
                        count = await suggs.count()
                        for i in range(count):
                            s = suggs.nth(i)
                            if await s.is_visible():
                                await s.click()
                                clicked = True
                                await asyncio.sleep(0.3)
                                break
                        if clicked:
                            break

                    if not clicked:
                        try:
                            tokens = [t.lower() for t in val.replace('/', ' ').replace('-', ' ').split() if len(t) >= 2]
                            combo = "div.sug-item, li.sug-item, div[class*='sug'], li[class*='sug'], div[class*='tuple'], div[class*='option'], li[class*='option']"
                            sug_loc = self.page.locator(combo)
                            sug_count = await sug_loc.count()
                            for i in range(sug_count):
                                s = sug_loc.nth(i)
                                if await s.is_visible():
                                    stext = ((await s.text_content()) or "").strip().lower()
                                    if stext == val.strip().lower() or any(tok in stext for tok in tokens):
                                        await s.click()
                                        clicked = True
                                        await asyncio.sleep(0.3)
                                        break
                        except Exception:
                            pass

                    if not clicked:
                        loc = self._locator(selector)
                        await loc.press("Enter")
                        await asyncio.sleep(0.3)

                    try:
                        loc = self._locator(selector)
                        await loc.press("Escape")
                        await asyncio.sleep(0.2)
                    except Exception:
                        pass

                    await self._js("document.body.click()")
                    await asyncio.sleep(0.2)

                except Exception as e:
                    logger.warning(f"Error selecting option '{val}': {e}")
            else:
                success = False
        return success

    async def fill_range(
        self,
        min_selector: str,
        max_selector: str,
        min_val: Optional[Union[int, float]],
        max_val: Optional[Union[int, float]],
    ) -> bool:
        res_min = True
        res_max = True
        if min_val is not None:
            res_min = await self.fill_number(min_selector, min_val)
        if max_val is not None:
            res_max = await self.fill_number(max_selector, max_val)
            if not res_max:
                try:
                    num_str = str(int(max_val)) if isinstance(max_val, (int, float)) and max_val.is_integer() else str(max_val)
                    await self._js(f"""
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
                    await asyncio.sleep(0.3)
                    res_max = True
                    logger.info(f"Filled max value '{max_val}' via JS fallback")
                except Exception as e:
                    logger.warning(f"JS fallback for max value failed: {e}")
        return res_min and res_max

    async def submit_form(self, button_selector: str) -> bool:
        try:
            await self.dismiss_all_dropdowns()
            await asyncio.sleep(0.3)
            loc = self._locator(button_selector)
            await loc.click()
            logger.info(f"Clicked search submit '{button_selector}'")
            return True
        except Exception as exc:
            logger.error(f"Failed to click search submit '{button_selector}': {exc}")
            return False

    async def dismiss_all_dropdowns(self):
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.1)
        except Exception:
            pass
        try:
            await self._js("document.body.click()")
            await asyncio.sleep(0.1)
        except Exception:
            pass
        try:
            neutral = self.page.locator("h1, h2, header, main, .content")
            count = await neutral.count()
            for i in range(count):
                n = neutral.nth(i)
                if await n.is_visible():
                    await n.click()
                    break
        except Exception:
            pass

    async def fill_location(self, location: str) -> bool:
        if not location:
            return False
        try:
            loc = self._locator(ResdexSelectors.LOCATION_INPUT)
            await loc.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)

            await loc.click()
            await asyncio.sleep(0.1)
            await self._js("""
                (el) => {
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(el, '');
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """, await loc.element_handle())
            await asyncio.sleep(0.1)

            await loc.type(location, delay=30)
            await asyncio.sleep(0.8)

            clicked = False
            suggestion_xpaths = [
                f"//div[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
                f"//li[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
                f"//span[contains(@class, 'sug') or contains(@class, 'option')][contains(text(), '{location}')]",
            ]
            for xp in suggestion_xpaths:
                try:
                    suggs = self.page.locator(f"xpath={xp}")
                    sugg_count = await suggs.count()
                    for i in range(sugg_count):
                        s = suggs.nth(i)
                        if await s.is_visible():
                            await s.click()
                            clicked = True
                            await asyncio.sleep(0.3)
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
                        sugg_count = await suggs.count()
                        for i in range(sugg_count):
                            s = suggs.nth(i)
                            if await s.is_visible():
                                await s.click()
                                clicked = True
                                await asyncio.sleep(0.3)
                                break
                    except Exception:
                        pass
                    if clicked:
                        break

            if not clicked:
                await loc.press("Enter")
                await asyncio.sleep(0.3)

            await loc.press("Escape")
            await asyncio.sleep(0.1)
            await self._js("document.body.click()")
            await asyncio.sleep(0.2)

            chips = self.page.locator(
                f"//*[contains(@class, 'chip') or contains(@class, 'tag')][contains(text(), '{location}')]"
            )
            return (await chips.count()) > 0

        except Exception as e:
            logger.warning(f"Failed to fill location '{location}': {e}")
            return False

    async def fill_keywords_with_stars(
        self,
        required_keywords: List[str],
        preferred_keywords: Optional[List[str]] = None,
        input_selector: str = ResdexSelectors.KEYWORD_INPUT,
    ) -> bool:
        if not required_keywords and not preferred_keywords:
            return False

        try:
            loc = self._locator(input_selector)
            await loc.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
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

            chip_count_before = await self.page.locator(
                "//div[contains(@class,'chip') or contains(@class,'tag') or contains(@class,'pill')]"
            ).count()

            try:
                await self._js("""
                    (input) => {
                        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(input, '');
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                """, await loc.element_handle())
                await asyncio.sleep(0.1)

                await loc.type(kw_clean, delay=30)
                await asyncio.sleep(0.5)

                await loc.press("Enter")
                await asyncio.sleep(0.6)

                accepted = False
                for _ in range(6):
                    chip_count_after = await self.page.locator(
                        "//div[contains(@class,'chip') or contains(@class,'tag') or contains(@class,'pill')]"
                    ).count()
                    if chip_count_after > chip_count_before:
                        accepted = True
                        break
                    await asyncio.sleep(0.3)

                if not accepted:
                    sugg_selectors = [
                        "div.sug-item", "li.suggestion-item", "div.keyword-sug",
                        "li.sug-item", "div[class*='sug']", "li[class*='sug']",
                    ]
                    for sugg_sel in sugg_selectors:
                        suggs = self.page.locator(sugg_sel)
                        sugg_count = await suggs.count()
                        for i in range(sugg_count):
                            s = suggs.nth(i)
                            if await s.is_visible():
                                await s.click()
                                await asyncio.sleep(0.4)
                                chip_count_after = await self.page.locator(
                                    "//div[contains(@class,'chip') or contains(@class,'tag') or contains(@class,'pill')]"
                                ).count()
                                if chip_count_after > chip_count_before:
                                    accepted = True
                                break
                        if accepted:
                            break

                if accepted:
                    logger.info(f"Keyword chip confirmed for '{kw_clean}'")
                    await self._js("document.body.click()")
                    await asyncio.sleep(0.2)

                    if kw_clean.lower() in mandatory_set:
                        await self._click_keyword_star(kw_clean)
                        await asyncio.sleep(0.2)

                    success_count += 1
                else:
                    logger.warning(f"Keyword '{kw_clean}' not confirmed as chip — skipping star")

            except Exception as e:
                logger.warning(f"Error entering keyword '{kw_clean}': {e}")

        try:
            await self.fill_checkbox(ResdexSelectors.MANDATORY_KEYWORDS_CHECKBOX, True)
        except Exception:
            pass

        return success_count > 0

    async def _click_keyword_star(self, skill_name: str) -> bool:
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
                star_count = await stars.count()
                for i in range(star_count):
                    star = stars.nth(i)
                    if await star.is_visible():
                        star_class = await star.get_attribute("class") or ""
                        aria_pressed = await star.get_attribute("aria-pressed") or ""
                        if "active" not in star_class and "selected" not in star_class and "starred" not in star_class and aria_pressed != "true":
                            await star.click(force=True)
                            logger.info(f"Clicked mandatory star for '{skill_name}'")
                            await asyncio.sleep(0.2)
                            return True
                        else:
                            logger.info(f"Star for '{skill_name}' already active")
                            return True
        except Exception as exc:
            logger.warning(f"Could not click star for '{skill_name}': {exc}")
        return False

    async def _ensure_additional_section_expanded(self):
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
                header_count = await headers.count()
                for i in range(header_count):
                    h = headers.nth(i)
                    if await h.is_visible():
                        aria_exp = await h.get_attribute("aria-expanded")
                        cls = await h.get_attribute("class") or ""
                        if aria_exp == "false" or "collapsed" in cls:
                            await h.click(force=True)
                            await asyncio.sleep(0.4)
                            return
                        elif aria_exp != "true":
                            show_only = self.page.locator(
                                "xpath=//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show only candidates with')]"
                            )
                            so_count = await show_only.count()
                            if so_count == 0 or not any(await show_only.nth(j).is_visible() for j in range(so_count)):
                                await h.click(force=True)
                                await asyncio.sleep(0.4)
                                return
            except Exception:
                pass

    async def tick_show_only_candidates_options(
        self,
        verified_mobile: bool = False,
        verified_email: bool = False,
        attached_resume: bool = False,
    ) -> List[str]:
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
        await self._ensure_additional_section_expanded()
        await asyncio.sleep(0.3)

        for key, search_text in requested:
            success = False
            try:
                xpath = ResdexSelectors.SHOW_ONLY_PILL_TEMPLATE.format(text=search_text)
                els = self.page.locator(f"xpath={xpath}")
                el_count = await els.count()
                for i in range(el_count):
                    el = els.nth(i)
                    if await el.is_visible():
                        el_class = await el.get_attribute("class") or ""
                        aria_pressed = await el.get_attribute("aria-pressed") or ""
                        if "active" not in el_class and "selected" not in el_class and aria_pressed != "true":
                            await el.click(force=True)
                        logger.info(f"Clicked show-only pill '{search_text}'")
                        success = True
                        await asyncio.sleep(0.3)
                        break
            except Exception as e:
                logger.warning(f"Pill template failed for '{search_text}': {e}")

            if not success:
                try:
                    result = await self._js(f"""
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
                        await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning(f"JS fallback failed for '{search_text}': {e}")

            if success:
                ticked.append(key)
                logger.info(f"Successfully ticked show-only '{search_text}'")
            else:
                logger.warning(f"Could not locate show-only pill for '{search_text}'")

        return ticked

    async def select_active_in(self, period: str) -> bool:
        if not period:
            return False

        # Strategy 1: native <select>
        try:
            sel_loc = self._locators(ResdexSelectors.ACTIVE_IN_SELECT)
            sel_count = await sel_loc.count()
            for i in range(sel_count):
                s = sel_loc.nth(i)
                if await s.is_visible():
                    tag = await self._js("(el) => el.tagName.toLowerCase()", await s.element_handle())
                    if tag == "select":
                        await s.select_option(label=period)
                        await self._js("""
                            (el) => {
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        """, await s.element_handle())
                        logger.info(f"Selected '{period}' in active_in <select>")
                        return True
        except Exception:
            pass

        # Strategy 2: React custom dropdown — click trigger
        trigger_opened = False
        try:
            trigger_xpaths = ResdexSelectors.ACTIVE_IN_DROPDOWN_TRIGGER.split(" | ")
            for xp in trigger_xpaths:
                xp = xp.strip()
                try:
                    els = self.page.locator(f"xpath={xp}")
                    el_count = await els.count()
                    for i in range(el_count):
                        el = els.nth(i)
                        if await el.is_visible():
                            await el.click()
                            await asyncio.sleep(0.4)
                            trigger_opened = True
                            break
                except Exception:
                    pass
                if trigger_opened:
                    break
        except Exception:
            pass

        # Strategy 3: Click option text
        option_xpath = ResdexSelectors.ACTIVE_IN_OPTION_TEMPLATE.format(option=period)
        try:
            option_parts = option_xpath.split(" | ")
            for part in option_parts:
                part = part.strip()
                try:
                    els = self.page.locator(f"xpath={part}")
                    el_count = await els.count()
                    for i in range(el_count):
                        el = els.nth(i)
                        if await el.is_visible():
                            await el.click(force=True)
                            await self._js("""
                                (el) => {
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                    el.dispatchEvent(new Event('click', { bubbles: true }));
                                }
                            """, await el.element_handle())
                            await asyncio.sleep(0.3)
                            logger.info(f"Clicked Active In option '{period}'")
                            return True
                except Exception:
                    pass
        except Exception:
            pass

        # Strategy 4: JS text search
        try:
            result = await self._js(f"""
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
                await asyncio.sleep(0.3)
                logger.info(f"Active In '{period}' clicked via JS fallback")
                return True
        except Exception as e:
            logger.warning(f"JS fallback for Active In failed: {e}")

        logger.warning(f"Could not set Active In to '{period}'")
        return False

    async def fill_keyword_scope(self, scope: str) -> bool:
        if not scope or scope == "Entire resume":
            return True

        # Try native <select>
        try:
            sel_loc = self._locators(ResdexSelectors.KEYWORD_SEARCH_SCOPE_SELECT)
            sel_count = await sel_loc.count()
            for i in range(sel_count):
                s = sel_loc.nth(i)
                if await s.is_visible():
                    tag = await self._js("(el) => el.tagName.toLowerCase()", await s.element_handle())
                    if tag == "select":
                        await s.select_option(label=scope)
                        logger.info(f"Set keyword scope via <select>: '{scope}'")
                        return True
        except Exception:
            pass

        # Click trigger
        trigger_opened = False
        try:
            trigger_parts = ResdexSelectors.KEYWORD_SCOPE_TRIGGER.split(" | ")
            for xp in trigger_parts:
                xp = xp.strip()
                try:
                    els = self.page.locator(f"xpath={xp}")
                    el_count = await els.count()
                    for i in range(el_count):
                        el = els.nth(i)
                        if await el.is_visible():
                            await el.click()
                            await asyncio.sleep(0.4)
                            trigger_opened = True
                            break
                except Exception:
                    pass
                if trigger_opened:
                    break
        except Exception:
            pass

        # Click option
        option_xpath = ResdexSelectors.KEYWORD_SCOPE_OPTION_TEMPLATE.format(option=scope)
        try:
            option_parts = option_xpath.split(" | ")
            for part in option_parts:
                part = part.strip()
                try:
                    els = self.page.locator(f"xpath={part}")
                    el_count = await els.count()
                    for i in range(el_count):
                        el = els.nth(i)
                        if await el.is_visible():
                            await el.click(force=True)
                            await asyncio.sleep(0.3)
                            logger.info(f"Set keyword scope via dropdown: '{scope}'")
                            return True
                except Exception:
                    pass
        except Exception:
            pass

        logger.warning(f"Could not set keyword scope to '{scope}'")
        return False

    async def fill_education_qualifications(
        self,
        ug_qualification: Optional[str] = None,
        pg_qualification: Optional[str] = None,
    ) -> List[str]:
        filled = []
        if not ug_qualification and not pg_qualification:
            return filled

        await self.expand_section(ResdexSelectors.EDUCATION_SECTION_TOGGLE)
        await asyncio.sleep(0.4)

        if ug_qualification:
            ug_display = ug_qualification.strip()
            ok = await self.click_pill(ResdexSelectors.UG_QUALIFICATION_PILL_TEMPLATE, ug_display)
            if ok:
                filled.append("ug_qualification")
                logger.info(f"Set UG qualification: '{ug_display}'")

        if pg_qualification:
            pg_display = pg_qualification.strip()
            ok = await self.click_pill(ResdexSelectors.PG_QUALIFICATION_PILL_TEMPLATE, pg_display)
            if ok:
                filled.append("pg_qualification")
                logger.info(f"Set PG qualification: '{pg_display}'")

        return filled

    async def click_pill(self, xpath_template: str, value: str) -> bool:
        if not value:
            return False

        xpath = xpath_template.format(option=value)
        try:
            els = self.page.locator(f"xpath={xpath}")
            el_count = await els.count()
            for i in range(el_count):
                el = els.nth(i)
                if await el.is_visible():
                    await el.scroll_into_view_if_needed()
                    await asyncio.sleep(0.1)

                    el_class = await el.get_attribute("class") or ""
                    aria_pressed = await el.get_attribute("aria-pressed") or ""
                    is_already_active = (
                        "active" in el_class
                        or "selected" in el_class
                        or "checked" in el_class
                        or aria_pressed == "true"
                    )

                    if not is_already_active:
                        await el.click(force=True)
                        await asyncio.sleep(0.2)
                        logger.info(f"Clicked pill '{value}'")
                    else:
                        logger.info(f"Pill '{value}' already active")
                    return True
        except Exception as exc:
            logger.warning(f"Failed to click pill '{value}': {exc}")
        return False

    async def expand_section(self, xpath: str) -> bool:
        try:
            headers = self.page.locator(f"xpath={xpath}")
            header_count = await headers.count()
            for i in range(header_count):
                h = headers.nth(i)
                if await h.is_visible():
                    aria_exp = await h.get_attribute("aria-expanded")
                    cls = await h.get_attribute("class") or ""
                    if aria_exp == "false" or "collapsed" in cls:
                        await h.click(force=True)
                        await asyncio.sleep(0.4)
                        logger.info(f"Expanded section: {xpath}")
                    return True
        except Exception:
            pass
        return False

    async def _check_pill_active(self, search_text: str) -> bool:
        try:
            return await self._js("""
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

    async def verify_form_filled(self, fields_interacted: List[str], plan: dict) -> dict:
        filled = []
        missing = []

        if plan.get("keywords") and plan["keywords"].get("required"):
            kw_chips = self.page.locator(
                "//div[contains(@class, 'chip') or contains(@class, 'tag') or contains(@class, 'pill')]"
            )
            if (await kw_chips.count()) > 0:
                filled.append("keywords")
            else:
                missing.append("keywords")

        if plan.get("min_experience") is not None or plan.get("max_experience") is not None:
            min_el = self.page.locator("xpath=//input[contains(@placeholder, 'Min experience')]")
            max_el = self.page.locator("xpath=//input[contains(@placeholder, 'Max experience')]")
            min_val = await min_el.first.get_attribute("value") if (await min_el.count()) > 0 else ""
            max_val = await max_el.first.get_attribute("value") if (await max_el.count()) > 0 else ""
            if min_val or max_val:
                filled.append("experience")
            else:
                missing.append("experience")

        if plan.get("current_location"):
            loc_chips = self.page.locator(
                "xpath=//div[contains(@class, 'chip') or contains(@class, 'tag')][contains(@class, 'location')]"
            )
            if (await loc_chips.count()) > 0:
                filled.append("location")
            else:
                missing.append("location")

        if plan.get("notice_period"):
            np_filled = []
            for np in plan["notice_period"]:
                pill = self.page.locator(
                    f"xpath=//span[contains(@class, 'pill') or contains(@class, 'chip')][normalize-space()='{np}']"
                )
                if (await pill.count()) > 0:
                    cls = await pill.first.get_attribute("class") or ""
                    if "active" in cls or "selected" in cls:
                        np_filled.append(np)
            if np_filled:
                filled.append("notice_period")
            else:
                missing.append("notice_period")

        pill_checks = [("verified_mobile", "verified mobile"), ("verified_email", "verified email"), ("attached_resume", "attached resume")]
        for field, search_text in pill_checks:
            if plan.get(field):
                if await self._check_pill_active(search_text):
                    filled.append(field)
                else:
                    missing.append(field)

        if plan.get("active_in"):
            active_in_text = self.page.locator(
                f"xpath=//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'active in')]/following::span[contains(text(), '{plan['active_in']}')]"
            )
            if (await active_in_text.count()) > 0:
                filled.append("active_in")
            else:
                missing.append("active_in")

        return {"filled": filled, "missing": missing}
