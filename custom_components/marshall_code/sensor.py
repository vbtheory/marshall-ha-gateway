"""Sensors for the Marshall CODE integration: current preset name and
firmware/version info (as separate attributes on one sensor)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MarshallCodeConfigEntry, MarshallCodeCoordinator
from .entity import MarshallCodeEntity

PRESET_NAME_DESCRIPTION = SensorEntityDescription(
    key="preset_name",
    translation_key="preset_name",
)

VERSION_DESCRIPTION = SensorEntityDescription(
    key="version",
    translation_key="version",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarshallCodeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the preset-name and version sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            MarshallCodePresetNameSensor(coordinator),
            MarshallCodeVersionSensor(coordinator),
        ]
    )


class MarshallCodePresetNameSensor(MarshallCodeEntity, SensorEntity):
    """Name of the currently active preset."""

    def __init__(self, coordinator: MarshallCodeCoordinator) -> None:
        super().__init__(coordinator, PRESET_NAME_DESCRIPTION)

    @property
    def native_value(self) -> str | None:
        return self.coordinator.state.preset_name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"preset_index": self.coordinator.state.active_preset_index}


class MarshallCodeVersionSensor(MarshallCodeEntity, SensorEntity):
    """DSP firmware version, with the other component versions as attributes."""

    def __init__(self, coordinator: MarshallCodeCoordinator) -> None:
        super().__init__(coordinator, VERSION_DESCRIPTION)

    @property
    def native_value(self) -> str | None:
        version = self.coordinator.state.device_info.dsp_version
        return str(version) if version is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.coordinator.state.device_info
        return {
            "serial_number": info.serial_number,
            "hardware_version": str(info.hardware_version)
            if info.hardware_version
            else None,
            "bootloader_version": str(info.bootloader_version)
            if info.bootloader_version
            else None,
            "mcu_version": str(info.mcu_version) if info.mcu_version else None,
            "bluetooth_version": str(info.bluetooth_version)
            if info.bluetooth_version
            else None,
        }


__all__ = ["async_setup_entry"]
