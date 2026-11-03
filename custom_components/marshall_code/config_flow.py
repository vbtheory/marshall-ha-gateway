"""Config flow for the Marshall CODE integration.

Two ways in:

- Automatic: HA's `bluetooth` integration discovers an advertisement that
  matches the `bluetooth` matchers in `manifest.json` and calls
  `async_step_bluetooth`, which just asks the user to confirm.
- Manual: the user picks "Add integration" themselves and is shown a list of
  currently-visible devices matching the amp's local-name prefixes (useful
  if the amp wasn't awake/paired yet when HA first scanned).
"""
from __future__ import annotations

import re
from typing import Any

import probatio as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, LOCAL_NAME_PREFIXES
from .verify import async_verify_amp

MANUAL_ENTRY = "__manual__"
MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def _looks_like_marshall_code(service_info: BluetoothServiceInfoBleak) -> bool:
    """Return True if a discovered BLE advertisement looks like a CODE amp."""
    name = service_info.name or ""
    return name.startswith(LOCAL_NAME_PREFIXES)


class MarshallCodeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Marshall CODE integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if not _looks_like_marshall_code(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a bluetooth discovery."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await async_verify_amp(self.hass, discovery_info.address)
            if error is None:
                return self.async_create_entry(
                    title=discovery_info.name,
                    data={CONF_ADDRESS: discovery_info.address},
                )
            errors["base"] = error
        else:
            self._set_confirm_only()

        placeholders = {"name": discovery_info.name}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a discovered amp, or choose to enter a MAC address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address == MANUAL_ENTRY:
                return await self.async_step_manual()
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            error = await async_verify_amp(self.hass, address)
            if error is None:
                discovery_info = self._discovered_devices[address]
                return self.async_create_entry(
                    title=discovery_info.name, data={CONF_ADDRESS: address}
                )
            errors["base"] = error

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, False):
            if discovery_info.address in current_addresses:
                continue
            if not _looks_like_marshall_code(discovery_info):
                continue
            self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return await self.async_step_manual()

        options = {
            address: f"{info.name} ({address})"
            for address, info in self._discovered_devices.items()
        }
        options[MANUAL_ENTRY] = "Enter MAC address manually"
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(options)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the amp's Bluetooth MAC address by hand."""
        errors: dict[str, str] = {}
        default = ""
        if user_input is not None:
            default = user_input[CONF_ADDRESS]
            address = default.strip().upper().replace("-", ":")
            if not MAC_RE.match(address):
                errors["base"] = "invalid_address"
            else:
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                error = await async_verify_amp(self.hass, address)
                if error is None:
                    info = self._discovered_devices.get(address)
                    return self.async_create_entry(
                        title=info.name if info else f"Marshall CODE {address}",
                        data={CONF_ADDRESS: address},
                    )
                errors["base"] = error

        return self.async_show_form(
            step_id="manual",
            errors=errors,
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS, default=default): str}
            ),
        )


__all__ = ["MarshallCodeConfigFlow"]
