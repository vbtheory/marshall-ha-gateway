"""Switches for the Marshall CODE integration: the 4 effect blocks shown on
the app's Home screen (Pedal/Modulation/Delay/Reverb)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EFFECT_DEVICE_TYPES
from .coordinator import MarshallCodeConfigEntry, MarshallCodeCoordinator
from .entity import MarshallCodeEntity
from .protocol import set_device_on

_EFFECT_TRANSLATION_KEYS = {
    "PEDAL": "pedal",
    "MODULATION": "modulation",
    "DELAY": "delay",
    "REVERB": "reverb",
}

_EFFECT_ICONS = {
    "PEDAL": "mdi:guitar-pick",
    "MODULATION": "mdi:sine-wave",
    "DELAY": "mdi:timer-outline",
    "REVERB": "mdi:waveform",
}

EFFECT_DESCRIPTIONS = {
    device_type: SwitchEntityDescription(
        key=device_type.lower(),
        translation_key=_EFFECT_TRANSLATION_KEYS[device_type],
        icon=_EFFECT_ICONS[device_type],
    )
    for device_type in EFFECT_DEVICE_TYPES
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarshallCodeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the 4 effect on/off switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        MarshallCodeEffectSwitch(coordinator, device_type)
        for device_type in EFFECT_DEVICE_TYPES
    )


class MarshallCodeEffectSwitch(MarshallCodeEntity, SwitchEntity):
    """On/off toggle for one effect block (Pedal/Modulation/Delay/Reverb)."""

    def __init__(self, coordinator: MarshallCodeCoordinator, device_type: str) -> None:
        super().__init__(coordinator, EFFECT_DESCRIPTIONS[device_type])
        self._device_type = device_type

    @property
    def is_on(self) -> bool:
        return self.coordinator.state.effects[self._device_type].is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"model": self.coordinator.state.effects[self._device_type].model_name}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send(set_device_on(self._device_type, True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send(set_device_on(self._device_type, False))


__all__ = ["async_setup_entry"]
