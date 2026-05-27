"""Shared helpers for Merkury Smart config entries."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import CONF_DEVICES


def get_entry_devices(entry: ConfigEntry) -> list[dict[str, Any]]:
    """Return configured devices (options re-sync overrides entry.data)."""

    if entry.options.get(CONF_DEVICES):
        return list(entry.options[CONF_DEVICES])
    return list(entry.data.get(CONF_DEVICES, []))
