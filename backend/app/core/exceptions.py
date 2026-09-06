class ProfileBotException(Exception):
    """Base domain exception for Candidate Search & Profile Bot."""

    def __init__(self, error_code: str, message: str, status_code: int = 500):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


# Backwards compatibility alias
CandidateBotException = ProfileBotException


class RequirementParsingError(ProfileBotException):
    """Raised when a requirement prompt cannot be parsed into a search plan."""

    def __init__(
        self,
        message: str = "Unable to extract recruitment criteria from the provided prompt.",
    ):
        super().__init__(
            error_code="REQUIREMENT_PARSING_ERROR",
            message=message,
            status_code=422,
        )


class NaukriAuthenticationRequired(ProfileBotException):
    """Raised when Naukri requires authenticated recruiter session."""

    def __init__(
        self,
        message: str = "Authenticated Naukri recruiter access is required. Please log in manually in non-headless mode.",
    ):
        super().__init__(
            error_code="NAUKRI_AUTH_REQUIRED",
            message=message,
            status_code=401,
        )


class NaukriSecurityChallenge(ProfileBotException):
    """Raised when Naukri presents CAPTCHA, verification, or anti-bot challenge."""

    def __init__(
        self,
        message: str = "Naukri presented a security verification challenge / CAPTCHA. Automation paused. Manual intervention required.",
    ):
        super().__init__(
            error_code="NAUKRI_SECURITY_CHALLENGE",
            message=message,
            status_code=409,
        )


class NaukriPageChanged(ProfileBotException):
    """Raised when expected page elements/selectors are missing or DOM changed."""

    def __init__(
        self,
        message: str = "Expected Naukri search page elements could not be found. Selectors may require configuration.",
    ):
        super().__init__(
            error_code="NAUKRI_PAGE_CHANGED",
            message=message,
            status_code=502,
        )


class NaukriSearchFailed(ProfileBotException):
    """Raised when a search execution fails on Naukri."""

    def __init__(
        self,
        message: str = "Failed to execute candidate search on Naukri portal.",
    ):
        super().__init__(
            error_code="NAUKRI_SEARCH_FAILED",
            message=message,
            status_code=500,
        )


class SeleniumDriverError(ProfileBotException):
    """Raised when Selenium WebDriver encounters initialization or runtime errors."""

    def __init__(
        self,
        message: str = "Failed to initialize or operate Selenium WebDriver. Ensure Chrome/Chromedriver is installed.",
    ):
        super().__init__(
            error_code="SELENIUM_DRIVER_ERROR",
            message=message,
            status_code=500,
        )


class PortalNotSupportedException(ProfileBotException):
    """Raised when an unsupported portal is requested."""

    def __init__(self, portal: str):
        super().__init__(
            error_code="PORTAL_NOT_SUPPORTED",
            message=f"Portal '{portal}' is not supported. Supported portals: ['naukri'].",
            status_code=400,
        )
