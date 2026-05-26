"""Pepper OS cloud API for Merkury Smart / Geeni."""

from .auth import LoginSession, parse_login_response
from .devices import build_discovered_entry, guess_device_class
from .exceptions import (
    PepperApiError,
    PepperAuthError,
    PepperCloudError,
    PepperMfaRequiredError,
    PepperSessionError,
)

__all__ = [
    "ENVIRONMENT_HOSTS",
    "LoginSession",
    "PepperApiError",
    "PepperAuthError",
    "PepperCloudClient",
    "PepperCloudError",
    "PepperMfaRequiredError",
    "PepperSessionError",
    "build_discovered_entry",
    "guess_device_class",
    "parse_login_response",
]


def __getattr__(name: str):
    if name in {"PepperCloudClient", "ENVIRONMENT_HOSTS"}:
        from .client import ENVIRONMENT_HOSTS, PepperCloudClient

        return ENVIRONMENT_HOSTS if name == "ENVIRONMENT_HOSTS" else PepperCloudClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
