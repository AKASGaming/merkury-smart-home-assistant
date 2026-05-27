"""Pepper OS cloud client wrapper for Merkury Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import CONF_BRAND, CONF_ENVIRONMENT, CONF_PASSWORD, CONF_USERNAME, DEFAULT_BRAND
from .pepper_cloud import PepperAuthError, PepperCloudClient, PepperCloudError, PepperMfaRequiredError


class MerkuryCloudClient:
    """High-level async client for Merkury Smart via Pepper OS."""

    def __init__(
        self,
        username: str,
        password: str,
        *,
        brand: str = DEFAULT_BRAND,
        environment: str = "production",
        client: PepperCloudClient | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.brand = brand
        self.environment = environment
        self._client = client or PepperCloudClient(
            brand=brand, environment=environment
        )

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> MerkuryCloudClient:
        return cls(
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            brand=config.get(CONF_BRAND, DEFAULT_BRAND),
            environment=config.get(CONF_ENVIRONMENT, "production"),
        )

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> MerkuryCloudClient:
        return cls.from_config(entry.data)

    async def close(self) -> None:
        await self._client.close()

    async def login(self) -> None:
        await self._client.login(self.username, self.password)

    async def ensure_session(self) -> None:
        """Refresh credentials before AWS temporary keys expire (~15 minutes)."""
        await self._client.ensure_session(self.username, self.password)

    async def validate(self) -> list[dict[str, Any]]:
        await self.login()
        return await self.discover_devices()

    async def discover_devices(self) -> list[dict[str, Any]]:
        return await self._client.discover_devices(
            email=self.username,
            password=self.password,
        )

    async def poll_device_states(self, device_ids: list[str]) -> dict[str, dict[str, Any]]:
        return await self._client.poll_device_states(
            device_ids,
            email=self.username,
            password=self.password,
        )

    async def get_device_state(self, device_id: str) -> dict[str, Any]:
        return await self._client.get_device_state(
            device_id,
            email=self.username,
            password=self.password,
        )

    async def set_power(
        self,
        device_id: str,
        on: bool,
        *,
        provider: str | None = None,
        external_device_id: str | None = None,
    ) -> None:
        await self._client.set_power(
            device_id,
            on,
            provider=provider,
            external_device_id=external_device_id,
            email=self.username,
            password=self.password,
        )

    @property
    def inner(self) -> PepperCloudClient:
        return self._client


__all__ = ["MerkuryCloudClient", "PepperAuthError", "PepperCloudError", "PepperMfaRequiredError"]
