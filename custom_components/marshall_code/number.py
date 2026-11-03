"""Number entities for the Marshall CODE integration: the 6 "Home screen"
knobs (gate/gain/bass/middle/treble/volume) of the active preamp."""
from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import KNOB_MAX_VALUE, KNOB_MIN_VALUE, PREAMP_PARAMETER_MIDI_CODES
from .coordinator import MarshallCodeConfigEntry, MarshallCodeCoordinator
from .entity import MarshallCodeEntity
from .protocol import set_knob_value

KNOB_TRANSLATION_KEYS = {
    "gate": "gate",
    "gain": "gain",
    "bass": "bass",
    "middle": "middle",
    "treble": "treble",
    "volume": "volume",
}

KNOB_DESCRIPTIONS = {
    knob: NumberEntityDescription(
        key=knob,
        translation_key=KNOB_TRANSLATION_KEYS[knob],
        native_min_value=KNOB_MIN_VALUE,
        native_max_value=KNOB_MAX_VALUE,
        native_step=1,
        mode=NumberMode.SLIDER,
    )
    for knob in PREAMP_PARAMETER_MIDI_CODES
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarshallCodeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the 6 preamp knob number entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        MarshallCodeKnobNumber(coordinator, knob)
        for knob in PREAMP_PARAMETER_MIDI_CODES
    )


class MarshallCodeKnobNumber(MarshallCodeEntity, NumberEntity):
    """One of the 6 preamp knobs, bound to the currently selected preamp."""

    def __init__(self, coordinator: MarshallCodeCoordinator, knob: str) -> None:
        super().__init__(coordinator, KNOB_DESCRIPTIONS[knob])
        self._knob = knob

    @property
    def native_value(self) -> float | None:
        return self.coordinator.state.knobs.get(self._knob)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_send(set_knob_value(self._knob, int(value)))


__all__ = ["async_setup_entry"]
