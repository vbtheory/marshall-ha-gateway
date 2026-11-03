"""Services for the Marshall CODE integration."""
from __future__ import annotations

import probatio as vol
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DOMAIN
from .coordinator import MarshallCodeConfigEntry, MarshallCodeCoordinator

SERVICE_CONNECT = "connect"

SCHEMA_CONNECT_SERVICE = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


@callback
def _async_target(hass: HomeAssistant, device_id: str) -> MarshallCodeCoordinator:
    """Return the coordinator for a device id, raising if not found/loaded."""
    _, config_entry = service.async_get_device_and_config_entry(
        hass, DOMAIN, device_id
    )
    config_entry: MarshallCodeConfigEntry
    return config_entry.runtime_data


async def async_connect(call: ServiceCall) -> None:
    """Handle the `marshall_code.connect` service call."""
    coordinator = _async_target(call.hass, call.data[ATTR_DEVICE_ID])
    await coordinator.async_connect()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services for the Marshall CODE integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_CONNECT, async_connect, schema=SCHEMA_CONNECT_SERVICE
    )


__all__ = ["async_setup_services"]
