"""Base entity for Merkury Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MerkuryCoordinator


class MerkuryEntity(CoordinatorEntity[MerkuryCoordinator]):
    """Shared Merkury device entity behaviour."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MerkuryCoordinator,
        device_id: str,
        name: str,
        *,
        model: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = name
        self._default_model = model

    @property
    def device_state(self) -> dict:
        return self.coordinator.data.get(self._device_id, {})

    @property
    def device_info(self) -> DeviceInfo:
        state = self.device_state
        serial = state.get("external_device_id")
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=state.get("name") or self._device_name,
            manufacturer="Merkury Innovations",
            model=state.get("model") or self._default_model,
            sw_version=state.get("firmware_version"),
            serial_number=str(serial) if serial else None,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.device_state
        attrs: dict[str, Any] = {}
        if state.get("wifi_network"):
            attrs["wifi_network"] = state["wifi_network"]
        if state.get("timezone"):
            attrs["timezone"] = state["timezone"]
        if state.get("last_paired_at"):
            attrs["last_paired_at"] = state["last_paired_at"]
        if state.get("cloud_status"):
            attrs["cloud_status"] = state["cloud_status"]
        if state.get("external_device_id"):
            attrs["external_device_id"] = state["external_device_id"]
        if state.get("provider"):
            attrs["provider"] = state["provider"]
        if state.get("device_type"):
            attrs["device_type"] = state["device_type"]
        return attrs

    @property
    def power_on(self) -> bool | None:
        return self.device_state.get("power_on")

    async def async_set_power(self, on: bool) -> None:
        """Turn device on/off with optimistic coordinator update."""

        await self.coordinator.set_power(self._device_id, on)

    async def async_restart(self) -> None:
        """Send Pepper cloud restart command for this device."""

        await self.coordinator.restart_device(self._device_id)
