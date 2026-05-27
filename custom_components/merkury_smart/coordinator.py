"""Data update coordinator for Merkury Smart devices."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import MerkuryCloudClient
from .const import (
    CONF_DEVICE_ID,
    CONF_EXTERNAL_DEVICE_ID,
    CONF_PROVIDER,
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
)
from .helpers import get_entry_devices

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

    def _configured_device_ids(self) -> list[str]:
        return [device[CONF_DEVICE_ID] for device in get_entry_devices(self.entry)]

    async def _async_update_data(self) -> dict[str, dict]:
        device_ids = self._configured_device_ids()
        try:
            return await self.client.poll_device_states(device_ids)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Update failed: %s", err)
            raise UpdateFailed(str(err)) from err

    def _device_meta(self, device_id: str) -> dict:
        for device in get_entry_devices(self.entry):
            if device.get(CONF_DEVICE_ID) == device_id:
                return device
        return {}

    async def set_power(self, device_id: str, on: bool) -> None:
        state = self.data.get(device_id, {}) if self.data else {}
        raw = state.get("raw") if isinstance(state.get("raw"), dict) else {}
        meta = self._device_meta(device_id)
        await self.client.set_power(
            device_id,
            on,
            provider=raw.get("provider") or meta.get(CONF_PROVIDER),
            external_device_id=raw.get("deviceId") or meta.get(CONF_EXTERNAL_DEVICE_ID),
        )

    async def async_shutdown(self) -> None:
        await self.client.close()
