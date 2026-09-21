class ProfileBotException(Exception):
    """Base domain exception for Candidate Search & Profile Bot."""

    def __init__(self, error_code: str, message: str, status_code: int = 500):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
