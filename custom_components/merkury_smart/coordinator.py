"""Data update coordinator for Merkury Smart devices."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import MerkuryCloudClient
from .const import CONF_DEVICE_ID, CONF_DEVICES, DOMAIN, UPDATE_INTERVAL_SECONDS
from .pepper_cloud import PepperSessionError

_LOGGER = logging.getLogger(__name__)


class MerkuryCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Poll Merkury Smart devices via the Pepper OS cloud API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MerkuryCloudClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.entry = entry
        self.client = client
        self.device_ids = [
            device[CONF_DEVICE_ID] for device in entry.data.get(CONF_DEVICES, [])
        ]

    async def _async_update_data(self) -> dict[str, dict]:
        data: dict[str, dict] = {}
        errors: list[str] = []

        for device_id in self.device_ids:
            try:
                data[device_id] = await self.client.get_device_state(device_id)
            except PepperSessionError:
                _LOGGER.debug("Session expired, re-authenticating")
                await self.client.login()
                data[device_id] = await self.client.get_device_state(device_id)
            except Exception as err:  # noqa: BLE001
                errors.append(device_id)
                _LOGGER.debug("Update failed for %s: %s", device_id, err)

        if errors and not data:
            raise UpdateFailed(f"All devices failed: {', '.join(errors)}")

        return data

    async def set_power(self, device_id: str, on: bool) -> None:
        try:
            await self.client.set_power(device_id, on)
        except PepperSessionError:
            await self.client.login()
            await self.client.set_power(device_id, on)

    async def async_shutdown(self) -> None:
        await self.client.close()
