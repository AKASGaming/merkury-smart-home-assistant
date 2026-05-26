"""Exceptions for the Pepper OS cloud API."""


class PepperCloudError(Exception):
    """Base Pepper cloud API error."""


class PepperAuthError(PepperCloudError):
    """Authentication failed."""


class PepperMfaRequiredError(PepperAuthError):
    """Multi-factor authentication is required."""


class PepperSessionError(PepperCloudError):
    """Session or credentials are invalid or expired."""


class PepperApiError(PepperCloudError):
    """API request failed."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message
