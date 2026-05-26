"""HTTP transport for Pepper OS (requires HTTP/2 for signed account API calls)."""

from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(30.0)


def create_http_client() -> httpx.AsyncClient:
    """Return an async client configured like the Merkury Smart Android app."""

    return httpx.AsyncClient(http2=True, timeout=DEFAULT_TIMEOUT)
