"""Merkury Smart integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .cloud import MerkuryCloudClient
from .const import CONF_DEVICE_ID, CONF_USERNAME, DOMAIN, PLATFORMS
from .coordinator import MerkuryCoordinator
from .helpers import get_entry_devices

_LOGGER = logging.getLogger(__name__)


def _register_hub_and_fix_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create account hub device and fix stale self-referential device links."""

    device_registry = dr.async_get(hass)
    hub = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Merkury Smart ({entry.data.get(CONF_USERNAME, 'account')})",
        manufacturer="Merkury Innovations",
        model="Cloud account",
    )

    for dev in get_entry_devices(entry):
        dev_id = dev[CONF_DEVICE_ID]
        device = device_registry.async_get_device(identifiers={(DOMAIN, dev_id)})
        if device is None:
            continue
        if device.via_device_id != hub.id:
            device_registry.async_update_device(device.id, via_device_id=hub.id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Merkury Smart from a config entry."""

    client = MerkuryCloudClient.from_entry(entry)
    await client.login()

    coordinator = MerkuryCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    _register_hub_and_fix_devices(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Merkury Smart config entry."""

    coordinator: MerkuryCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator:
        await coordinator.async_shutdown()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
