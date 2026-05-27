"""Normalize Pepper account devices for Home Assistant."""

from __future__ import annotations

from typing import Any

from ..const import DEVICE_CLASS_LIGHT, DEVICE_CLASS_SWITCH

_SWITCH_TYPES = frozenset(
    {
        "outlet",
        "plug",
        "switch",
        "socket",
        "relay",
        "powerstrip",
        "power_strip",
    }
)
_LIGHT_TYPES = frozenset(
    {
        "light",
        "bulb",
        "lamp",
        "strip",
        "rgb",
        "dimmer",
    }
)


def command_device_id(device: dict[str, Any]) -> str:
    """Return the id used by sendDeviceCommand."""

    return (
        device.get("pepperDeviceId")
        or device.get("pepper_device_id")
        or device.get("deviceId")
        or device.get("device_id")
        or ""
    )


def _device_type(device: dict[str, Any]) -> str:
    return str(device.get("deviceType") or device.get("device_type") or "")


def guess_device_class(device: dict[str, Any]) -> str:
    device_type = _device_type(device).lower()
    model = str(device.get("model") or "").lower()

    if device.get("light"):
        return DEVICE_CLASS_LIGHT

    if any(token in device_type for token in _LIGHT_TYPES):
        return DEVICE_CLASS_LIGHT
    if any(token in model for token in ("bulb", "light", "strip", "prisma")):
        return DEVICE_CLASS_LIGHT

    if any(token in device_type for token in _SWITCH_TYPES):
        return DEVICE_CLASS_SWITCH
    if any(token in model for token in ("ww", "plug", "outlet", "switch")):
        return DEVICE_CLASS_SWITCH

    if device.get("switches") or device.get("powerStateOn") is not None:
        return DEVICE_CLASS_SWITCH

    return DEVICE_CLASS_SWITCH


def parse_power_state(device: dict[str, Any]) -> bool | None:
    if device.get("powerStateOn") is not None:
        return bool(device["powerStateOn"])

    switches = device.get("switches")
    if isinstance(switches, list) and switches:
        state = switches[0].get("state")
        if state is not None:
            return bool(state)

    light = device.get("light")
    if isinstance(light, dict) and light.get("stateOn") is not None:
        return bool(light["stateOn"])

    return None


def parse_brightness(device: dict[str, Any]) -> int | None:
    light = device.get("light")
    if isinstance(light, dict) and light.get("brightness") is not None:
        return int(light["brightness"])
    return None


def parse_color_temp(device: dict[str, Any]) -> int | None:
    light = device.get("light")
    if isinstance(light, dict) and light.get("colorTemp") is not None:
        return int(light["colorTemp"])
    return None


def normalize_device_state(device: dict[str, Any]) -> dict[str, Any]:
    """Convert a PepperAccountDevice payload into coordinator-friendly state."""

    power = parse_power_state(device)
    return {
        "name": device.get("name"),
        "model": device.get("model"),
        "device_type": _device_type(device) or None,
        "provider": device.get("provider"),
        "online": str(device.get("status", "")).lower() not in {"offline", "disconnected"},
        "power_on": power,
        "brightness": parse_brightness(device),
        "color_temp": parse_color_temp(device),
        "raw": device,
    }


def build_discovered_entry(device: dict[str, Any]) -> dict[str, Any]:
    dev_id = command_device_id(device)
    return {
        "device_id": dev_id,
        "name": device.get("name") or dev_id,
        "device_class": guess_device_class(device),
        "model": device.get("model"),
        "device_type": _device_type(device) or None,
        "provider": device.get("provider"),
        "external_device_id": device.get("deviceId"),
    }
