"""Data update coordinator for Merkury Smart devices."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import MerkuryCloudClient
from .const import CONF_DEVICE_ID, DOMAIN, UPDATE_INTERVAL_SECONDS
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

    @callback
    def _apply_power_state(self, device_id: str, on: bool) -> None:
        """Push a power state change to coordinator data and refresh entities."""

        data = dict(self.data or {})
        state = dict(data.get(device_id, {}))
        state["power_on"] = on
        data[device_id] = state
        self.async_set_updated_data(data)

    async def set_power(self, device_id: str, on: bool) -> None:
        """Set device power with optimistic UI update, then reconcile via cloud."""

        _LOGGER.debug("set_power device_id=%s on=%s", device_id, on)
        previous_state = (
            dict(self.data[device_id]) if self.data and device_id in self.data else {}
        )

        self._apply_power_state(device_id, on)
        try:
            await self.client.set_power(device_id, on)
        except Exception:
            _LOGGER.exception("set_power failed for %s", device_id)
            data = dict(self.data or {})
            data[device_id] = previous_state
            self.async_set_updated_data(data)
            raise

        # Reconcile with cloud without blocking the UI toggle.
        self.hass.async_create_task(self.async_request_refresh())

    async def async_shutdown(self) -> None:
        await self.client.close()
