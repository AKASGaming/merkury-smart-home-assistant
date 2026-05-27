"""Pepper OS cloud API client used by Merkury Smart and Geeni apps."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from yarl import URL

from ..const import CMD_POWER_OFF, CMD_POWER_ON, DEFAULT_BRAND
from .auth import apply_login_response, extract_lr_token
from .devices import build_discovered_entry, command_device_id, normalize_device_state
from .exceptions import PepperApiError, PepperAuthError, PepperCloudError, PepperSessionError
from .signer import ensure_trailing_slash, sign_request
from .transport import create_http_client
from .urls import DEFAULT_HOSTS

_LOGGER = logging.getLogger(__name__)

ENVIRONMENT_HOSTS = DEFAULT_HOSTS
DEFAULT_USER_AGENT = "okhttp/4.4.1"


@dataclass(slots=True)
class AwsSession:
    access_key_id: str
    secret_access_key: str
    session_token: str
    region: str


class PepperCloudClient:
    """Async client for api.pepperos.io."""

    def __init__(
        self,
        *,
        brand: str = DEFAULT_BRAND,
        environment: str = "production",
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if environment not in ENVIRONMENT_HOSTS and not base_url:
            raise ValueError(f"Unsupported environment: {environment}")

        self.brand = brand
        self.environment = environment
        self._custom_base_url = base_url is not None
        self.base_url = (base_url or ENVIRONMENT_HOSTS[environment]).rstrip("/")
        self._client = client
        self._owns_client = client is None
        self._pepper_token: str | None = None
        self._lr_token: str | None = None
        self._aws: AwsSession | None = None

    async def close(self) -> None:
        if self._owns_client and self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = create_http_client()
            self._owns_client = True
        return self._client

    @staticmethod
    def _basic_auth(brand: str, username: str, password: str) -> str:
        token = base64.b64encode(f"{brand}:{username}:{password}".encode()).decode(
            "ascii"
        )
        return f"Basic {token}"

    async def login(self, email: str, password: str, *, use_by_token: bool = False) -> None:
        """Authenticate with Merkury Smart / Geeni account credentials."""

        email_data = await self._fetch_login_by_email(self.base_url, email, password)
        self._apply_login_response(email_data)

        if not use_by_token:
            return

        lr_token = extract_lr_token(email_data)
        await self._refresh_session_by_token(self.base_url, lr_token, required=True)

    async def _auth_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": "4",
            "User-Agent": DEFAULT_USER_AGENT,
        }

    async def _fetch_login_by_email(
        self, base_url: str, email: str, password: str
    ) -> dict[str, Any]:
        client = await self._get_client()
        url = f"{base_url.rstrip('/')}/authentication/byEmail"
        headers = await self._auth_headers()
        headers["Authorization"] = self._basic_auth(self.brand, email, password)

        response = await client.post(url, headers=headers, content=b"null")
        body = response.text
        if response.status_code == 401:
            raise PepperAuthError("Invalid email or password")
        if response.status_code >= 400:
            raise PepperApiError(response.status_code, body or "Authentication failed")

        data = response.json()
        if not isinstance(data, dict):
            raise PepperCloudError("Unexpected authentication response")
        return data

    async def _refresh_session_by_token(
        self,
        base_url: str,
        lr_token: str | None = None,
        *,
        required: bool = False,
    ) -> None:
        """Refresh session via LoginRadius lrToken (not the long JWT)."""

        if not lr_token:
            if required:
                raise PepperCloudError("authenticateByToken requires lrToken")
            return

        client = await self._get_client()
        url = f"{base_url.rstrip('/')}/authentication/byToken"
        token = base64.b64encode(f"{self.brand}:{lr_token}".encode()).decode("ascii")
        headers = await self._auth_headers()
        headers["Authorization"] = f"Basic {token}"

        response = await client.post(url, headers=headers, content=b"null")
        body = response.text
        if response.status_code >= 400:
            if required:
                raise PepperApiError(
                    response.status_code,
                    body or "authenticateByToken failed",
                )
            _LOGGER.debug(
                "authenticateByToken returned HTTP %s (continuing with byEmail session)",
                response.status_code,
            )
            return

        data = response.json()
        if isinstance(data, dict):
            self._apply_login_response(data)
        elif required:
            raise PepperCloudError("authenticateByToken returned an unexpected payload")

    def _apply_login_response(self, data: dict[str, Any]) -> None:
        session = apply_login_response(data)
        self._pepper_token = session.pepper_token
        self._lr_token = data.get("lrToken")
        self._aws = AwsSession(
            access_key_id=session.access_key_id,
            secret_access_key=session.secret_access_key,
            session_token=session.session_token,
            region=session.region,
        )

    async def _signed_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
    ) -> Any:
        if not self._pepper_token or not self._aws:
            raise PepperSessionError("Not logged in")

        client = await self._get_client()
        url_obj = URL(self.base_url).joinpath(path.lstrip("/"))
        url_obj = url_obj.with_path(ensure_trailing_slash(url_obj.path))
        signed_url = str(url_obj)

        body = b""
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
            "peppertoken": self._pepper_token,
        }
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Length"] = str(len(body))

        signed_headers = sign_request(
            method,
            signed_url,
            headers,
            body,
            access_key=self._aws.access_key_id,
            secret_key=self._aws.secret_access_key,
            session_token=self._aws.session_token,
            region=self._aws.region,
        )

        response = await client.request(
            method,
            signed_url,
            headers=signed_headers,
            content=body or None,
        )
        text = response.text
        if response.status_code == 401:
            raise PepperSessionError("Session expired or unauthorized")
        if response.status_code >= 400:
            raise PepperApiError(
                response.status_code, text or response.reason_phrase
            )

        if not text:
            return None
        return response.json()

    async def list_devices(self) -> list[dict[str, Any]]:
        result = await self._signed_request("GET", "/account/devices")
        if not isinstance(result, list):
            return []
        return [item for item in result if isinstance(item, dict)]

    async def discover_devices(self) -> list[dict[str, Any]]:
        discovered: list[dict[str, Any]] = []
        for device in await self.list_devices():
            dev_id = command_device_id(device)
            if not dev_id:
                continue
            discovered.append(build_discovered_entry(device))
        return discovered

    async def get_device_state(self, device_id: str) -> dict[str, Any]:
        for device in await self.list_devices():
            if command_device_id(device) == device_id:
                return normalize_device_state(device)
        return {"power_on": None, "online": False, "raw": {}}

    async def send_command(
        self,
        device_id: str,
        command: str,
        *,
        value_json: str | None = None,
    ) -> None:
        path = f"/account/devices/{device_id}/settings/{command}"
        if value_json is None and command in {CMD_POWER_ON, CMD_POWER_OFF}:
            path = f"/account/devices/{device_id}/settings/{CMD_POWER_ON}"
            value_json = "1" if command == CMD_POWER_ON else "0"
        body = {"valueJson": value_json} if value_json is not None else {}
        await self._signed_request("PUT", path, json_body=body)

    async def set_power(self, device_id: str, on: bool) -> None:
        path = f"/account/devices/{device_id}/settings/{CMD_POWER_ON}"
        await self._signed_request(
            "PUT",
            path,
            json_body={"valueJson": "1" if on else "0"},
        )
