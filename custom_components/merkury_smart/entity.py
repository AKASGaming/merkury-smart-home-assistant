"""Base entity for Merkury Smart."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=name,
            manufacturer="Merkury Innovations",
            model=model,
            via_device=(DOMAIN, coordinator.entry.entry_id),
        )

    @property
    def device_state(self) -> dict:
        return self.coordinator.data.get(self._device_id, {})

    @property
    def power_on(self) -> bool | None:
        return self.device_state.get("power_on")
