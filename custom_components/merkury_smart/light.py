"""Merkury Smart light platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import color as color_util

from .config_flow import async_get_device_entries
from .const import (
    BRIGHTNESS_MAX,
    BRIGHTNESS_MIN,
    CONF_DEVICE_CLASS,
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_NAME,
    DEVICE_CLASS_LIGHT,
    DOMAIN,
)
from .coordinator import MerkuryCoordinator
from .entity import MerkuryEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MerkuryCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[MerkuryLight] = []

    for device in await async_get_device_entries(hass, entry):
        if device.get(CONF_DEVICE_CLASS) != DEVICE_CLASS_LIGHT:
            continue
        entities.append(
            MerkuryLight(
                coordinator=coordinator,
                device_id=device[CONF_DEVICE_ID],
                name=device[CONF_NAME],
                model=device.get(CONF_MODEL),
            )
        )

    async_add_entities(entities)


class MerkuryLight(MerkuryEntity, LightEntity):
    """Representation of a Merkury smart bulb or strip."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS, ColorMode.COLOR_TEMP}
    _attr_min_mireds = 153
    _attr_max_mireds = 500

    def __init__(
        self,
        coordinator: MerkuryCoordinator,
        device_id: str,
        name: str,
        *,
        model: str | None = None,
    ) -> None:
        super().__init__(coordinator, device_id, name, model=model)
        self._attr_unique_id = f"{device_id}_light"
        self._attr_name = None

    @property
    def is_on(self) -> bool:
        power = self.power_on
        return bool(power) if power is not None else False

    @property
    def brightness(self) -> int | None:
        raw = self.device_state.get("brightness")
        if raw is None:
            return None
        return color_util.value_to_brightness((BRIGHTNESS_MIN, BRIGHTNESS_MAX), int(raw))

    @property
    def color_mode(self) -> ColorMode | None:
        if not self.is_on:
            return None
        if self.device_state.get("color_temp") is not None:
            return ColorMode.COLOR_TEMP
        if self.brightness is not None:
            return ColorMode.BRIGHTNESS
        return ColorMode.BRIGHTNESS

    @property
    def color_temp(self) -> int | None:
        raw = self.device_state.get("color_temp")
        if raw is None:
            return None
        return int(raw)

    @property
    def available(self) -> bool:
        state = self.device_state
        if state.get("online") is False:
            return False
        return super().available

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Brightness/color control via settings API is not implemented yet.
        await self.coordinator.set_power(self._device_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.set_power(self._device_id, False)
        await self.coordinator.async_request_refresh()
