"""Preset select for the Marshall CODE integration.

The app lets you pick any of the 100 preset slots from the Home screen. We
expose the same here as a `select` entity listing "Preset 1".."Preset 100"
(slots are 0-indexed on the wire, 1-indexed for display, matching the app).
Showing each preset's actual stored name instead would require fetching all
100 names up front over BLE (slow, many round trips) - left as a possible
future enhancement; for now the current preset's name is already available
separately via the `sensor.<amp>_preset_name` entity.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AVAILABLE_PRESETS
from .coordinator import MarshallCodeConfigEntry, MarshallCodeCoordinator
from .entity import MarshallCodeEntity
from .protocol import set_active_preset

PRESET_DESCRIPTION = SelectEntityDescription(
    key="preset",
    translation_key="preset",
)

_OPTIONS = [f"Preset {i + 1}" for i in range(AVAILABLE_PRESETS)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarshallCodeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the preset select entity."""
    async_add_entities([MarshallCodePresetSelect(entry.runtime_data)])


class MarshallCodePresetSelect(MarshallCodeEntity, SelectEntity):
    """Choose the active preset slot (0-based on the wire, 1-based in the UI)."""

    _attr_options = _OPTIONS

    def __init__(self, coordinator: MarshallCodeCoordinator) -> None:
        super().__init__(coordinator, PRESET_DESCRIPTION)

    @property
    def current_option(self) -> str | None:
        index = self.coordinator.state.active_preset_index
        if index is None or not (0 <= index < AVAILABLE_PRESETS):
            return None
        return _OPTIONS[index]

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_send(
            set_active_preset(_OPTIONS.index(option)), with_response=False
        )


__all__ = ["async_setup_entry"]
