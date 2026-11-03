"""The Marshall CODE amplifier integration."""
from __future__ import annotations

from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import MarshallCodeConfigEntry, MarshallCodeCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Marshall CODE integration (register services once)."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MarshallCodeConfigEntry
) -> bool:
    """Set up a Marshall CODE amplifier from a config entry."""
    coordinator = MarshallCodeCoordinator(hass, entry.data[CONF_ADDRESS])
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start listening/auto-connecting only after platforms have had a
    # chance to subscribe to the update signal.
    await coordinator.async_setup()
    entry.async_on_unload(coordinator.async_unload)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MarshallCodeConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


__all__ = ["PLATFORMS", "async_setup", "async_setup_entry", "async_unload_entry"]
