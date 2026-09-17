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


class PortalNotSupportedException(ProfileBotException):
    """Raised when an unsupported portal is requested."""

    def __init__(self, portal: str):
        super().__init__(
            error_code="PORTAL_NOT_SUPPORTED",
            message=f"Portal '{portal}' is not supported. Supported portals: ['naukri'].",
            status_code=400,
        )
