import base64
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.playwright.driver import ResdexDriver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/login", tags=["Naukri Login"])

_driver: ResdexDriver | None = None


async def _get_driver() -> ResdexDriver:
    global _driver
    if _driver is None:
        _driver = ResdexDriver()
    return _driver


class ScreenshotResponse(BaseModel):
    screenshot: str
    url: str


class SubmitRequest(BaseModel):
    email: str
    password: str


@router.get("/screenshot", response_model=ScreenshotResponse)
async def login_screenshot():
    """Open Naukri login page and return screenshot."""
    driver = await _get_driver()
    try:
        await driver.start_driver()
        await driver.page.goto(
            "https://www.naukri.com/recruit/login/", wait_until="domcontentloaded"
        )
        await driver.page.wait_for_timeout(2000)
        screenshot_bytes = await driver.page.screenshot()
        return ScreenshotResponse(
            screenshot=base64.b64encode(screenshot_bytes).decode(),
            url=driver.page.url,
        )
    except Exception as exc:
        logger.error(f"Login screenshot failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/submit")
async def login_submit(req: SubmitRequest):
    """Submit login credentials and return result screenshot."""
    driver = await _get_driver()
    try:
        page = driver.page
        if not page:
            raise HTTPException(status_code=400, detail="No active browser. Call /login/screenshot first.")

        email_input = page.locator("input[placeholder*='Email'] or input[name='username'] or input[type='email']")
        pass_input = page.locator("input[placeholder*='Password'] or input[name='password'] or input[type='password']")

        await email_input.fill(req.email)
        await pass_input.fill(req.password)

        submit_btn = page.locator("button[type='submit'] or input[type='submit']")
        await submit_btn.click()

        await page.wait_for_timeout(5000)
        screenshot_bytes = await page.screenshot()
        return {
            "status": "submitted",
            "url": page.url,
            "screenshot": base64.b64encode(screenshot_bytes).decode(),
            "message": "Check screenshot for login result. If OTP/2FA needed, call /login/otp with the code.",
        }
    except Exception as exc:
        logger.error(f"Login submit failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


class OtpRequest(BaseModel):
    otp: str


@router.post("/otp")
async def login_otp(req: OtpRequest):
    """Submit OTP for 2FA login."""
    driver = await _get_driver()
    try:
        page = driver.page
        if not page:
            raise HTTPException(status_code=400, detail="No active browser.")

        otp_input = page.locator("input[placeholder*='OTP'] or input[name='otp'] or input[type='tel']")
        await otp_input.fill(req.otp)

        verify_btn = page.locator("button:has-text('Verify') or button:has-text('Submit') or button[type='submit']")
        await verify_btn.click()

        await page.wait_for_timeout(5000)
        screenshot_bytes = await page.screenshot()
        return {
            "status": "otp_submitted",
            "url": page.url,
            "screenshot": base64.b64encode(screenshot_bytes).decode(),
        }
    except Exception as exc:
        logger.error(f"OTP submit failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def login_status():
    """Check if browser has an active Naukri session."""
    driver = await _get_driver()
    try:
        if not driver._page:
            return {"logged_in": False, "message": "No browser session"}
        url = driver.page.url
        cookies = await driver._context.cookies()
        naukri_cookies = [c for c in cookies if "naukri" in c.get("domain", "")]
        return {
            "logged_in": len(naukri_cookies) > 0,
            "url": url,
            "cookie_count": len(naukri_cookies),
        }
    except Exception:
        return {"logged_in": False, "message": "Browser not running"}
