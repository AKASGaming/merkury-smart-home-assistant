"""Merkury Smart integration for Home Assistant."""



from __future__ import annotations



import logging



from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant, callback



from .cloud import MerkuryCloudClient

from .const import DOMAIN, PLATFORMS

from .coordinator import MerkuryCoordinator



_LOGGER = logging.getLogger(__name__)





async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:

    """Set up Merkury Smart from a config entry."""



    client = MerkuryCloudClient.from_entry(entry)

    await client.login()



    coordinator = MerkuryCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()



    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = coordinator



    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True





@callback

def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:

    """Reload integration when options change."""



    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))





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

