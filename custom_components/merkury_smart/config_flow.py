"""Config flow for Merkury Smart."""

from __future__ import annotations

from typing import Any
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .cloud import MerkuryCloudClient
from .helpers import get_entry_devices
from .const import (
    CONF_BRAND,
    CONF_CLOUD_STATUS,
    CONF_DEVICE_CLASS,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_DEVICE_TYPE,
    CONF_ENVIRONMENT,
    CONF_EXTERNAL_DEVICE_ID,
    CONF_FIRMWARE_VERSION,
    CONF_LAST_PAIRED_AT,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PROVIDER,
    CONF_TIMEZONE,
    CONF_USERNAME,
    CONF_WIFI_NETWORK,
    DEFAULT_BRAND,
    DOMAIN,
    ENVIRONMENTS,
)
from .pepper_cloud import (
    PepperApiError,
    PepperAuthError,
    PepperCloudError,
    PepperMfaRequiredError,
)

_LOGGER = logging.getLogger(__name__)


def _device_entry_from_discovered(item: dict[str, Any]) -> dict[str, Any]:
    """Map a Pepper discovery record into config-entry device storage."""

    return {
        CONF_DEVICE_ID: item["device_id"],
        CONF_NAME: item["name"],
        CONF_DEVICE_CLASS: item["device_class"],
        CONF_MODEL: item.get("model"),
        CONF_DEVICE_TYPE: item.get("device_type"),
        CONF_PROVIDER: item.get("provider"),
        CONF_EXTERNAL_DEVICE_ID: item.get("external_device_id"),
        CONF_FIRMWARE_VERSION: item.get("firmware_version"),
        CONF_WIFI_NETWORK: item.get("wifi_network"),
        CONF_TIMEZONE: item.get("timezone"),
        CONF_LAST_PAIRED_AT: item.get("last_paired_at"),
        CONF_CLOUD_STATUS: item.get("cloud_status"),
    }


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
            vol.Optional(CONF_BRAND, default=defaults.get(CONF_BRAND, DEFAULT_BRAND)): str,
            vol.Required(
                CONF_ENVIRONMENT, default=defaults.get(CONF_ENVIRONMENT, "production")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(ENVIRONMENTS),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


class MerkuryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Merkury Smart config flow."""

    VERSION = 2

    def __init__(self) -> None:
        self._account: dict[str, Any] = {}
        self._discovered: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip().lower()
            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            client = MerkuryCloudClient(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                brand=user_input.get(CONF_BRAND, DEFAULT_BRAND),
                environment=user_input[CONF_ENVIRONMENT],
            )
            try:
                self._discovered = await client.validate()
            except PepperMfaRequiredError:
                errors["base"] = "mfa_required"
            except PepperAuthError:
                errors["base"] = "invalid_auth"
            except PepperApiError as err:
                _LOGGER.error("Pepper API error during setup: %s", err)
                errors["base"] = "cannot_connect"
            except PepperCloudError as err:
                _LOGGER.error("Pepper cloud setup failed: %s", err)
                errors["base"] = "cannot_connect"
            except ImportError as err:
                _LOGGER.exception("Missing dependency for Merkury Smart")
                if "h2" in str(err).lower() or "http2" in str(err).lower():
                    errors["base"] = "missing_http2"
                else:
                    errors["base"] = "unknown"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected setup error")
                errors["base"] = "unknown"
            else:
                if not self._discovered:
                    errors["base"] = "no_devices"
                else:
                    self._account = user_input
                    return self._create_entry()
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self._account or None),
            errors=errors,
        )

    def _create_entry(self) -> FlowResult:
        devices = [_device_entry_from_discovered(item) for item in self._discovered]

        return self.async_create_entry(
            title=f"Merkury Smart ({self._account[CONF_USERNAME]})",
            data={
                **self._account,
                CONF_DEVICES: devices,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MerkuryOptionsFlowHandler:
        return MerkuryOptionsFlowHandler(config_entry)


class MerkuryOptionsFlowHandler(config_entries.OptionsFlow):
    """Re-sync devices from the Pepper cloud."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            client = MerkuryCloudClient.from_entry(self._config_entry)
            discovered: list[dict[str, Any]] = []
            try:
                discovered = await client.validate()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Device re-sync failed")
                return self.async_abort(reason="cannot_connect")
            finally:
                await client.close()

            devices = [_device_entry_from_discovered(item) for item in discovered]
            return self.async_create_entry(title="", data={CONF_DEVICES: devices})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )


async def async_get_device_entries(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> list[dict[str, Any]]:
    """Return device list from config entry data and options."""

    return get_entry_devices(entry)
