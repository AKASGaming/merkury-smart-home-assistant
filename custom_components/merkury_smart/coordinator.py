"""Data update coordinator for Merkury Smart devices."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import MerkuryCloudClient
from .const import CONF_DEVICE_ID, CONF_DEVICES, DOMAIN, UPDATE_INTERVAL_SECONDS

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
        try:
            return await self.client.poll_device_states(self.device_ids)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Update failed: %s", err)
            raise UpdateFailed(str(err)) from err

    async def set_power(self, device_id: str, on: bool) -> None:
        await self.client.set_power(device_id, on)

    async def async_shutdown(self) -> None:
        await self.client.close()
